from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import (
    ABNORMAL_STATUS_CANCELLED,
    ABNORMAL_STATUS_OPEN,
    ChecklistItem,
    DailyCheckResult,
    DailyCheckSheet,
    Line,
    RESULT_ABNORMAL,
    RESULT_EMPTY,
    RESULT_NG,
    RESULT_OK,
    VALID_ABNORMAL_STATUSES,
    User,
    db,
)
from routes.auth_routes import login_required


checklist_bp = Blueprint("checklist", __name__)


def parse_date(raw_value: str | None, fallback: date | None = None) -> date:
    fallback = fallback or date.today()
    if not raw_value:
        return fallback
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def managed_line_names(user: User) -> set[str]:
    if user.role in {"admin", "manager"}:
        return {line.line_name for line in Line.query.filter_by(is_active=True).all()}
    return {mapping.line.line_name for mapping in user.user_lines}


def can_view_sheet(user: User, sheet: DailyCheckSheet) -> bool:
    if user.role in {"admin", "manager"}:
        return True
    if user.role == "leader":
        return sheet.line_name in managed_line_names(user)
    return sheet.user_id == user.id


def can_edit_result(user: User, result: DailyCheckResult) -> bool:
    return user.role == "admin" or result.user_id == user.id


def get_template_id() -> int:
    sheet = DailyCheckSheet.query.first()
    return sheet.template_id if sheet else 1


def ensure_daily_sheet_and_results(user_id: int, template_id: int, selected_date: date):
    user = User.query.get_or_404(user_id)
    sheet = DailyCheckSheet.query.filter_by(
        user_id=user_id,
        template_id=template_id,
        check_date=selected_date,
    ).first()

    if sheet is None:
        sheet = DailyCheckSheet(
            user_id=user_id,
            template_id=template_id,
            check_date=selected_date,
            month=selected_date.month,
            year=selected_date.year,
            line_name=user.line_name,
            department=user.department,
            shift="day",
            status="draft",
        )
        db.session.add(sheet)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            sheet = DailyCheckSheet.query.filter_by(
                user_id=user_id,
                template_id=template_id,
                check_date=selected_date,
            ).first()

    active_items = sheet.template.checklist_items
    existing_item_ids = {
        item_id
        for (item_id,) in db.session.query(DailyCheckResult.checklist_item_id)
        .filter_by(daily_sheet_id=sheet.id)
        .all()
    }

    for item in active_items:
        if not item.is_active or item.id in existing_item_ids:
            continue
        db.session.add(
            DailyCheckResult(
                daily_sheet_id=sheet.id,
                checklist_item_id=item.id,
                user_id=user_id,
                check_date=selected_date,
                symbol=item.symbol,
                check_time=item.check_time,
                content=item.content_vi,
                result=RESULT_EMPTY,
                abnormal_note=None,
                checked_at=None,
            )
        )
    db.session.commit()
    return sheet


def get_target_users(current_user: User, selected_user_id: int | None, selected_line: str) -> list[User]:
    query = User.query.filter(User.role != "admin", User.is_active.is_(True))
    if current_user.role == "staff":
        query = query.filter(User.id == current_user.id)
    elif current_user.role == "leader":
        query = query.filter(User.line_name.in_(managed_line_names(current_user)))

    if selected_user_id:
        query = query.filter(User.id == selected_user_id)
    if selected_line:
        query = query.filter(User.line_name == selected_line)
    return query.order_by(User.full_name.asc()).all()


def build_dashboard_context(
    selected_date: date,
    selected_line: str,
    selected_user_id: int | None,
    selected_sheet_id: int | None,
    keyword: str,
    result_filter: str,
    active_section: str = "checklist",
):
    current_user = g.current_user
    template_id = get_template_id()

    target_users = get_target_users(current_user, selected_user_id, selected_line)
    for user in target_users:
        ensure_daily_sheet_and_results(user.id, template_id, selected_date)

    query = DailyCheckSheet.query.join(User).filter(DailyCheckSheet.check_date == selected_date)
    if current_user.role == "staff":
        query = query.filter(DailyCheckSheet.user_id == current_user.id)
    elif current_user.role == "leader":
        query = query.filter(DailyCheckSheet.line_name.in_(managed_line_names(current_user)))
    if selected_line:
        query = query.filter(DailyCheckSheet.line_name == selected_line)
    if selected_user_id:
        query = query.filter(DailyCheckSheet.user_id == selected_user_id)

    sheets = query.order_by(DailyCheckSheet.line_name.asc(), DailyCheckSheet.user_id.asc()).all()

    selected_sheet = None
    if selected_sheet_id:
        candidate = DailyCheckSheet.query.get_or_404(selected_sheet_id)
        if can_view_sheet(current_user, candidate):
            selected_sheet = candidate
    if selected_sheet is None and sheets:
        selected_sheet = sheets[0]

    results_query = DailyCheckResult.query
    abnormal_reports = []
    confirmations = []
    result_summary = {"o": 0, "x": 0, "△": 0, "empty": 0}
    results = []

    if selected_sheet:
        results_query = results_query.filter_by(daily_sheet_id=selected_sheet.id)
        if keyword:
            like_value = f"%{keyword}%"
            results_query = results_query.join(ChecklistItem).filter(
                or_(
                    DailyCheckResult.symbol.ilike(like_value),
                    DailyCheckResult.content.ilike(like_value),
                    DailyCheckResult.abnormal_note.ilike(like_value),
                    DailyCheckResult.result.ilike(like_value),
                    ChecklistItem.content_vi.ilike(like_value),
                    ChecklistItem.content_en.ilike(like_value),
                    ChecklistItem.content_ja.ilike(like_value),
                )
            )
        if result_filter == "none":
            results_query = results_query.filter(
                or_(DailyCheckResult.result.is_(None), DailyCheckResult.result == RESULT_EMPTY)
            )
        elif result_filter in {RESULT_OK, RESULT_NG, RESULT_ABNORMAL}:
            results_query = results_query.filter(DailyCheckResult.result == result_filter)

        all_results = (
            DailyCheckResult.query.filter_by(daily_sheet_id=selected_sheet.id)
            .order_by(DailyCheckResult.check_time.asc(), DailyCheckResult.id.asc())
            .all()
        )
        for result in all_results:
            if result.result == RESULT_OK:
                result_summary["o"] += 1
            elif result.result == RESULT_NG:
                result_summary["x"] += 1
            elif result.result == RESULT_ABNORMAL:
                result_summary["△"] += 1
            else:
                result_summary["empty"] += 1

        results = results_query.order_by(DailyCheckResult.check_time.asc(), DailyCheckResult.id.asc()).all()
        abnormal_reports = [
            report
            for report in selected_sheet.abnormal_reports
            if report.status != ABNORMAL_STATUS_CANCELLED
            and report.daily_check_result.result in {RESULT_NG, RESULT_ABNORMAL}
        ]
        if current_user.role == "staff":
            abnormal_reports = [report for report in abnormal_reports if report.user_id == current_user.id]
        confirmations = sorted(selected_sheet.confirmations, key=lambda item: item.confirmed_at)

    if current_user.role in {"admin", "manager"}:
        visible_lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
        visible_users = User.query.filter(User.role != "admin").order_by(User.full_name.asc()).all()
    elif current_user.role == "leader":
        line_names = managed_line_names(current_user)
        visible_lines = Line.query.filter(Line.line_name.in_(line_names)).order_by(Line.line_name.asc()).all()
        visible_users = User.query.filter(User.line_name.in_(line_names)).order_by(User.full_name.asc()).all()
    else:
        visible_lines = []
        visible_users = []

    return {
        "sheets": sheets,
        "selected_sheet": selected_sheet,
        "results": results,
        "abnormal_reports": abnormal_reports,
        "confirmations": confirmations,
        "result_summary": result_summary,
        "visible_lines": visible_lines,
        "visible_users": visible_users,
        "selected_date": selected_date.isoformat(),
        "selected_line": selected_line,
        "selected_user_id": selected_user_id,
        "keyword": keyword,
        "result_filter": result_filter,
        "active_section": active_section,
        "can_edit_selected": bool(
            selected_sheet and (current_user.role == "admin" or current_user.id == selected_sheet.user_id)
        ),
    }


def redirect_to_sheet(sheet: DailyCheckSheet, active_section: str = "checklist"):
    return redirect(
        url_for(
            "checklist.dashboard",
            date=sheet.check_date.isoformat(),
            sheet_id=sheet.id,
            section=active_section,
        )
    )


@checklist_bp.route("/")
def index():
    if g.current_user:
        return redirect(url_for("checklist.dashboard"))
    return redirect(url_for("auth.login"))


@checklist_bp.route("/dashboard")
@login_required
def dashboard():
    selected_date = parse_date(request.args.get("date"), fallback=date.today())
    selected_line = request.args.get("line", "").strip()
    selected_user_id = request.args.get("user_id", type=int)
    selected_sheet_id = request.args.get("sheet_id", type=int)
    keyword = request.args.get("keyword", "").strip()
    result_filter = request.args.get("result_filter", "all").strip() or "all"
    active_section = request.args.get("section", "checklist")
    context = build_dashboard_context(
        selected_date,
        selected_line,
        selected_user_id,
        selected_sheet_id,
        keyword,
        result_filter,
        active_section=active_section,
    )
    return render_template("dashboard.html", **context)


@checklist_bp.route("/check-result/<int:result_id>/update", methods=["POST"])
@login_required
def update_result(result_id: int):
    result = DailyCheckResult.query.get_or_404(result_id)
    if not can_view_sheet(g.current_user, result.daily_sheet):
        flash("Ban khong co quyen truy cap checklist nay.", "danger")
        return redirect(url_for("checklist.dashboard"))
    if not can_edit_result(g.current_user, result):
        flash("Ban khong duoc sua checklist cua user khac.", "danger")
        return redirect_to_sheet(result.daily_sheet)

    selected_result = request.form.get("result", "").strip()
    if selected_result == "empty":
        selected_result = RESULT_EMPTY
    if selected_result not in {RESULT_OK, RESULT_EMPTY}:
        flash("Gia tri cap nhat khong hop le.", "danger")
        return redirect_to_sheet(result.daily_sheet)

    result.result = selected_result
    result.checked_at = datetime.now() if selected_result else None
    result.abnormal_note = None if selected_result in {RESULT_OK, RESULT_EMPTY} else result.abnormal_note
    if selected_result == RESULT_EMPTY and result.abnormal_reports:
        result.abnormal_reports[0].status = ABNORMAL_STATUS_CANCELLED

    db.session.commit()
    flash("Da cap nhat ket qua checklist.", "success")
    return redirect_to_sheet(result.daily_sheet)


@checklist_bp.route("/check-result/<int:result_id>/abnormal", methods=["POST"])
@login_required
def update_abnormal_result(result_id: int):
    result = DailyCheckResult.query.get_or_404(result_id)
    if not can_view_sheet(g.current_user, result.daily_sheet):
        flash("Ban khong co quyen truy cap checklist nay.", "danger")
        return redirect(url_for("checklist.dashboard"))
    if not can_edit_result(g.current_user, result):
        flash("Ban khong duoc sua checklist cua user khac.", "danger")
        return redirect_to_sheet(result.daily_sheet, "abnormal")

    selected_result = request.form.get("result", "").strip()
    if selected_result not in {RESULT_NG, RESULT_ABNORMAL}:
        flash("Kết quả phải là x hoặc △.", "danger")
        return redirect_to_sheet(result.daily_sheet, "abnormal")

    abnormal_content = request.form.get("abnormal_content", "").strip()
    if not abnormal_content:
        flash("Nội dung bất thường là bắt buộc.", "danger")
        return redirect_to_sheet(result.daily_sheet, "abnormal")

    countermeasure = request.form.get("countermeasure", "").strip()
    confirm_date_before_fix = parse_date(
        request.form.get("confirm_date_before_fix"),
        fallback=result.check_date,
    )
    result_after_fix = request.form.get("result_after_fix", "").strip()
    status = request.form.get("status", ABNORMAL_STATUS_OPEN).strip() or ABNORMAL_STATUS_OPEN
    if status not in VALID_ABNORMAL_STATUSES:
        status = ABNORMAL_STATUS_OPEN

    result.result = selected_result
    result.checked_at = datetime.now()
    result.abnormal_note = abnormal_content

    report = result.abnormal_reports[0] if result.abnormal_reports else None
    if report is None:
        from models import AbnormalReport

        report = AbnormalReport(
            daily_sheet=result.daily_sheet,
            daily_check_result=result,
            user=result.user,
            symbol=result.symbol,
            occurred_date=result.check_date,
            abnormal_content=abnormal_content,
            countermeasure=countermeasure,
            confirm_date_before_fix=confirm_date_before_fix,
            result_after_fix=result_after_fix,
            status=status,
        )
        db.session.add(report)
    else:
        report.symbol = result.symbol
        report.occurred_date = result.check_date
        report.abnormal_content = abnormal_content
        report.countermeasure = countermeasure
        report.confirm_date_before_fix = confirm_date_before_fix
        report.result_after_fix = result_after_fix
        report.status = status

    db.session.commit()
    flash("Da cap nhat noi dung bat thuong.", "success")
    return redirect_to_sheet(result.daily_sheet, "abnormal")


@checklist_bp.route("/abnormal-reports")
@login_required
def abnormal_reports():
    selected_date = parse_date(request.args.get("date"), fallback=date.today())
    selected_line = request.args.get("line", "").strip()
    selected_user_id = request.args.get("user_id", type=int)
    selected_sheet_id = request.args.get("sheet_id", type=int)
    keyword = request.args.get("keyword", "").strip()
    result_filter = request.args.get("result_filter", "all").strip() or "all"
    context = build_dashboard_context(
        selected_date,
        selected_line,
        selected_user_id,
        selected_sheet_id,
        keyword,
        result_filter,
        active_section="abnormal",
    )
    return render_template("dashboard.html", **context)


@checklist_bp.route("/checklist/print/<int:sheet_id>")
@login_required
def print_checklist(sheet_id: int):
    sheet = DailyCheckSheet.query.get_or_404(sheet_id)
    if not can_view_sheet(g.current_user, sheet):
        flash("Ban khong co quyen in checklist nay.", "danger")
        return redirect(url_for("checklist.dashboard"))

    current_lang = session.get("lang", "vi")
    results = (
        DailyCheckResult.query.filter_by(daily_sheet_id=sheet.id)
        .order_by(DailyCheckResult.check_time.asc(), DailyCheckResult.id.asc())
        .all()
    )
    abnormal_reports = [
        report
        for report in sheet.abnormal_reports
        if report.status != ABNORMAL_STATUS_CANCELLED
        and report.daily_check_result.result in {RESULT_NG, RESULT_ABNORMAL}
    ]
    confirmations = sorted(sheet.confirmations, key=lambda item: item.confirmed_at)
    return render_template(
        "print_checklist.html",
        sheet=sheet,
        results=results,
        abnormal_reports=abnormal_reports,
        confirmations=confirmations,
        current_lang=current_lang,
    )
