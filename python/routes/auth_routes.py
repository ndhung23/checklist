from __future__ import annotations

from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from sqlalchemy import or_

from models import User


auth_bp = Blueprint("auth", __name__)


def get_current_user() -> User | None:
    if hasattr(g, "current_user"):
        return g.current_user

    user_id = session.get("user_id")
    g.current_user = User.query.get(user_id) if user_id else None
    return g.current_user


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not get_current_user():
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login"))
        if user.role not in {"admin", "leader"}:
            flash("Bạn không có quyền truy cập trang này.", "danger")
            return redirect(url_for("checklist.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


def manager_or_admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login"))
        if user.role not in {"manager", "admin", "leader"}:
            flash("Bạn không có quyền truy cập trang này.", "danger")
            return redirect(url_for("checklist.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


@auth_bp.before_app_request
def load_logged_in_user() -> None:
    g.current_user = get_current_user()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("checklist.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            or_(User.username == username, User.employee_code == username),
            User.is_active.is_(True),
        ).first()
        if not user or not user.check_password(password):
            flash("Sai tên đăng nhập hoặc mật khẩu.", "danger")
            return render_template("login.html", username=username)

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role
        session["lang"] = session.get("lang", "vi")

        flash("Đăng nhập thành công.", "success")
        return redirect(url_for("checklist.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    lang = session.get("lang", "vi")
    session.clear()
    session["lang"] = lang
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))


def _profile_month_options(today):
    from datetime import date

    options = []
    year, month = today.year, today.month
    for _ in range(24):
        options.append({"value": f"{year:04d}-{month:02d}", "label": f"{month:02d}/{year}"})
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    return options


def build_excel_month_context(user, year: int, month: int):
    from calendar import monthrange
    from datetime import date

    from models import (
        ABNORMAL_STATUS_CANCELLED,
        ChecklistItem,
        DailyCheckSheet,
        RESULT_ABNORMAL,
        RESULT_NG,
        RESULT_OK,
    )

    days_in_month = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    month_sheets = (
        DailyCheckSheet.query.filter(
            DailyCheckSheet.user_id == user.id,
            DailyCheckSheet.check_date >= month_start,
            DailyCheckSheet.check_date <= month_end,
        )
        .order_by(DailyCheckSheet.check_date.asc(), DailyCheckSheet.id.asc())
        .all()
    )
    latest_month_sheet = month_sheets[-1] if month_sheets else None
    latest_sheet = latest_month_sheet or (
        DailyCheckSheet.query.filter_by(user_id=user.id)
        .order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc())
        .first()
    )
    if not latest_sheet:
        return {
            "days_in_month": days_in_month,
            "excel_groups": [],
            "excel_abnormal_reports": [],
            "signature_rows": [],
            "excel_year": year,
            "excel_month": month,
            "latest_sheet_id": None,
            "sheet_id_by_day": {},
            "status_by_day": {},
            "line_name": getattr(user, "line_name", None),
        }

    active_line_name = latest_sheet.line_name or getattr(user, "line_name", None)
    month_sheets = [sheet for sheet in month_sheets if sheet.line_name == active_line_name]

    item_query = ChecklistItem.query.filter_by(
        template_id=latest_sheet.template_id,
        is_active=True,
    )
    if active_line_name:
        item_query = item_query.filter(ChecklistItem.line.has(line_name=active_line_name))

    items = item_query.order_by(ChecklistItem.check_time.asc(), ChecklistItem.item_order.asc()).all()
    items = sorted(
        items,
        key=lambda item: (
            (item.check_time.hour if item.check_time else 0)
            + (
                24
                if active_line_name == "Line D"
                and item.check_time
                and item.check_time.hour < 6
                else 0
            ),
            item.check_time.minute if item.check_time else 0,
            item.item_order or 0,
            item.id,
        ),
    )

    result_by_item_day: dict[tuple[int, int], str] = {}
    result_id_by_item_day: dict[tuple[int, int], int] = {}
    sheet_id_by_day: dict[int, int] = {}
    status_by_day: dict[int, str] = {}
    for sheet in month_sheets:
        day = sheet.check_date.day
        status_by_day[day] = sheet.status
        sheet_id_by_day[day] = sheet.id
        for result in sheet.results:
            val = (result.result or "").strip()
            result_by_item_day[(result.checklist_item_id, day)] = val
            result_id_by_item_day[(result.checklist_item_id, day)] = result.id

    excel_groups: list[dict] = []
    group_index: dict[str, int] = {}
    for item in items:
        group_key = item.time_group or "Khác"
        row = {
            "item_id": item.id,
            "symbol": item.symbol,
            "category_type": item.category_type or item.symbol,
            "content": item.content_vi or item.content,
            "days": {
                day: result_by_item_day.get((item.id, day), "")
                for day in range(1, days_in_month + 1)
            },
            "result_ids": {
                day: result_id_by_item_day.get((item.id, day))
                for day in range(1, days_in_month + 1)
            },
        }
        if group_key not in group_index:
            group_index[group_key] = len(excel_groups)
            excel_groups.append({"time_group": group_key, "rows": [row]})
        else:
            excel_groups[group_index[group_key]]["rows"].append(row)

    abnormal_reports = []
    for sheet in month_sheets:
        for report in sheet.abnormal_reports:
            if report.status == ABNORMAL_STATUS_CANCELLED:
                continue
            if report.daily_check_result.result not in {RESULT_NG, RESULT_ABNORMAL}:
                continue
            abnormal_reports.append(report)
    abnormal_reports.sort(key=lambda r: (r.occurred_date, r.id), reverse=True)

    weekly_days = [1, 8, 15, 22, 29][: ((days_in_month - 1) // 7) + 1]
    weekly_day_set = set(weekly_days)

    signature_rows = [
        {
            "label": "SL/TL (1/D)",
            "days": {day: ("o" if status_by_day.get(day) in {"submitted", "confirmed"} else "") for day in range(1, days_in_month + 1)},
        },
        {
            "label": "TL (1/D)",
            "days": {day: ("o" if status_by_day.get(day) == "confirmed" else "") for day in range(1, days_in_month + 1)},
        },
        {
            "label": "SV (1/W)",
            "days": {day: ("o" if status_by_day.get(day) == "confirmed" and day in weekly_day_set else "") for day in range(1, days_in_month + 1)},
        },
    ]

    return {
        "days_in_month": days_in_month,
        "excel_groups": excel_groups,
        "excel_abnormal_reports": abnormal_reports,
        "signature_rows": signature_rows,
        "excel_year": year,
        "excel_month": month,
        "latest_sheet_id": latest_sheet.id,
        "sheet_id_by_day": sheet_id_by_day,
        "status_by_day": status_by_day,
        "line_name": active_line_name,
    }


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    from datetime import date, timedelta
    from models import (
        DailyCheckSheet, DailyCheckResult, ChecklistItem,
        RESULT_OK, RESULT_NG, RESULT_ABNORMAL, RESULT_EMPTY, db,
        AbnormalReport, ABNORMAL_STATUS_CANCELLED,
    )

    user = get_current_user()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        outlook_email = request.form.get("outlook_email", "").strip()
        gender = request.form.get("gender", "").strip()
        department = request.form.get("department", "").strip()
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not department:
            flash("Vui lòng nhập đầy đủ họ tên và bộ phận.", "danger")
        elif gender and gender not in {"male", "female", "other"}:
            flash("Giới tính không hợp lệ.", "danger")
        elif new_password and not user.check_password(old_password):
            flash("Mật khẩu cũ không chính xác.", "danger")
        elif new_password and new_password != confirm_password:
            flash("Mật khẩu mới không khớp.", "danger")
        else:
            user.full_name = full_name
            user.outlook_email = outlook_email or None
            user.gender = gender or None
            user.department = department
            if new_password:
                user.set_password(new_password)
            db.session.commit()
            flash("Cập nhật thông tin thành công.", "success")
            return redirect(url_for("auth.profile"))
        return redirect(url_for("auth.profile", _anchor="pw-error", show_pw=1))

    # ── Bộ lọc ngày ──────────────────────────────────────────────────────────
    today = date.today()
    raw_start = request.args.get("date_from", "")
    raw_end = request.args.get("date_to", "")

    try:
        from datetime import datetime as _dt
        date_from = _dt.strptime(raw_start, "%Y-%m-%d").date() if raw_start else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)

    try:
        from datetime import datetime as _dt
        date_to = _dt.strptime(raw_end, "%Y-%m-%d").date() if raw_end else today
    except ValueError:
        date_to = today

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    view_mode = request.args.get("view", "excel")
    if view_mode not in {"report", "daily", "excel"}:
        view_mode = "excel"

    raw_excel_month = request.args.get("excel_month", "").strip()
    excel_year = today.year
    excel_month_num = today.month
    if raw_excel_month:
        try:
            from datetime import datetime as _dt
            parsed = _dt.strptime(raw_excel_month, "%Y-%m")
            excel_year, excel_month_num = parsed.year, parsed.month
        except ValueError:
            pass
    # Mặc định luôn có excel_month = tháng hiện tại
    if not raw_excel_month:
        raw_excel_month = f"{excel_year:04d}-{excel_month_num:02d}"
        view_mode = "excel"

    month_options = _profile_month_options(today)
    excel_context = build_excel_month_context(user, excel_year, excel_month_num)

    # ── Lấy tất cả hạng mục (category_type) của user ─────────────────────────
    # Lấy các category_type duy nhất từ checklist items
    all_category_types = (
        db.session.query(ChecklistItem.category_type)
        .filter(ChecklistItem.is_active.is_(True))
        .distinct()
        .order_by(ChecklistItem.category_type.asc())
        .all()
    )
    all_category_types = [row[0] for row in all_category_types if row[0]]

    # ── Xây dựng báo cáo theo ngày trong khoảng lọc ──────────────────────────
    sheets = (
        DailyCheckSheet.query.filter(
            DailyCheckSheet.user_id == user.id,
            DailyCheckSheet.check_date >= date_from,
            DailyCheckSheet.check_date <= date_to,
        )
        .order_by(DailyCheckSheet.check_date.desc())
        .all()
    )

    sheet_by_date = {s.check_date: s for s in sheets}

    report_rows = []
    curr = date_to
    while curr >= date_from:
        s = sheet_by_date.get(curr)
        row = {"date": curr, "sheet": s, "status": None, "by_category": {}, "total_ok": 0, "total_ng": 0, "total_abn": 0, "total_empty": 0, "ng_count": 0, "fixed_count": 0, "rate": None}

        if s:
            row["status"] = s.status
            total = len(s.results)
            ok = ng = abn = empty = 0
            cat_results = {}  # category_type -> list of results

            for r in s.results:
                cat = r.checklist_item.category_type if r.checklist_item else None
                if cat not in cat_results:
                    cat_results[cat] = []
                cat_results[cat].append(r.result)

                if r.result == RESULT_OK:
                    ok += 1
                elif r.result == RESULT_NG:
                    ng += 1
                elif r.result == RESULT_ABNORMAL:
                    abn += 1
                else:
                    empty += 1

            row["total_ok"] = ok
            row["total_ng"] = ng
            row["total_abn"] = abn
            row["total_empty"] = empty

            # Tính kết quả tổng hợp theo category_type
            # o = tất cả đạt, x = có lỗi, △ = có bất thường, - = chưa điền
            for cat, results_list in cat_results.items():
                if any(r == RESULT_NG for r in results_list):
                    cat_val = "x"
                elif any(r == RESULT_ABNORMAL for r in results_list):
                    cat_val = "△"
                elif all(r == RESULT_OK for r in results_list):
                    cat_val = "o"
                else:
                    cat_val = "-"
                row["by_category"][cat] = cat_val

            # NG phát sinh và đã xử lý
            ng_reports = [
                rpt for rpt in s.abnormal_reports
                if rpt.status != ABNORMAL_STATUS_CANCELLED
            ]
            row["ng_count"] = len(ng_reports)
            row["fixed_count"] = sum(1 for rpt in ng_reports if rpt.status in {"fixed", "confirmed"})

            # Tỷ lệ đạt
            if total > 0:
                row["rate"] = round((ok / total) * 100)
        else:
            row["status"] = None

        report_rows.append(row)
        curr -= timedelta(days=1)

    # ── Báo cáo tổng hợp theo tuần (cho bảng tháng/tuần kiểu ảnh) ────────────
    # Nhóm theo tuần trong khoảng lọc
    weekly_summary = {}
    for row in report_rows:
        if not row["sheet"]:
            continue
        s = row["sheet"]
        week_start = row["date"] - timedelta(days=row["date"].weekday())
        week_key = week_start.isoformat()
        if week_key not in weekly_summary:
            week_num = (week_start.day - 1) // 7 + 1
            weekly_summary[week_key] = {
                "week_start": week_start,
                "week_label": f"W{week_num}",
                "month": week_start.month,
                "by_category": {},
                "ng_count": 0,
                "fixed_count": 0,
                "total_ok": 0,
                "total_all": 0,
            }
        wk = weekly_summary[week_key]
        wk["ng_count"] += row["ng_count"]
        wk["fixed_count"] += row["fixed_count"]
        wk["total_ok"] += row["total_ok"]
        wk["total_all"] += row["total_ok"] + row["total_ng"] + row["total_abn"] + row["total_empty"]

        for cat, val in row["by_category"].items():
            prev = wk["by_category"].get(cat, "o")
            if val == "x" or prev == "x":
                wk["by_category"][cat] = "x"
            elif val == "△" or prev == "△":
                wk["by_category"][cat] = "△"
            elif val == "o":
                wk["by_category"][cat] = "o"
            else:
                wk["by_category"][cat] = prev

    weekly_rows = sorted(weekly_summary.values(), key=lambda x: x["week_start"], reverse=True)
    for wk in weekly_rows:
        if wk["total_all"] > 0:
            wk["rate"] = round((wk["total_ok"] / wk["total_all"]) * 100)
        else:
            wk["rate"] = None

    # Tên tháng viết tắt
    MONTH_ABBR = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    for wk in weekly_rows:
        wk["month_label"] = MONTH_ABBR.get(wk["month"], str(wk["month"]))

    show_pw_modal = request.args.get("show_pw") == "1"

    return render_template(
        "profile.html",
        user=user,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        report_rows=report_rows,
        weekly_rows=weekly_rows,
        all_category_types=all_category_types,
        show_pw_modal=show_pw_modal,
        view_mode=view_mode,
        excel_month=raw_excel_month or f"{excel_year:04d}-{excel_month_num:02d}",
        month_options=month_options,
        excel_context=excel_context,
    )


@auth_bp.route("/profile/print")
@login_required
def print_profile_report():
    from datetime import date, timedelta
    from models import (
        DailyCheckSheet, ChecklistItem,
        RESULT_OK, RESULT_NG, RESULT_ABNORMAL, db,
        AbnormalReport, ABNORMAL_STATUS_CANCELLED,
    )

    user = get_current_user()
    today = date.today()

    try:
        from datetime import datetime as _dt
        raw_start = request.args.get("date_from", "")
        date_from = _dt.strptime(raw_start, "%Y-%m-%d").date() if raw_start else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)

    try:
        from datetime import datetime as _dt
        raw_end = request.args.get("date_to", "")
        date_to = _dt.strptime(raw_end, "%Y-%m-%d").date() if raw_end else today
    except ValueError:
        date_to = today

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    view = request.args.get("view", "report")

    all_category_types = (
        db.session.query(ChecklistItem.category_type)
        .filter(ChecklistItem.is_active.is_(True))
        .distinct()
        .order_by(ChecklistItem.category_type.asc())
        .all()
    )
    all_category_types = [row[0] for row in all_category_types if row[0]]

    sheets = (
        DailyCheckSheet.query.filter(
            DailyCheckSheet.user_id == user.id,
            DailyCheckSheet.check_date >= date_from,
            DailyCheckSheet.check_date <= date_to,
        )
        .order_by(DailyCheckSheet.check_date.desc())
        .all()
    )

    sheet_by_date = {s.check_date: s for s in sheets}
    report_rows = []
    curr = date_to
    while curr >= date_from:
        s = sheet_by_date.get(curr)
        row = {"date": curr, "sheet": s, "by_category": {}, "total_ok": 0, "total_ng": 0, "total_abn": 0, "total_empty": 0, "ng_count": 0, "fixed_count": 0, "rate": None}
        if s:
            total = len(s.results)
            ok = ng = abn = empty = 0
            cat_results = {}
            for r in s.results:
                cat = r.checklist_item.category_type if r.checklist_item else None
                if cat not in cat_results:
                    cat_results[cat] = []
                cat_results[cat].append(r.result)
                if r.result == RESULT_OK: ok += 1
                elif r.result == RESULT_NG: ng += 1
                elif r.result == RESULT_ABNORMAL: abn += 1
                else: empty += 1
            row.update({"total_ok": ok, "total_ng": ng, "total_abn": abn, "total_empty": empty})
            for cat, rl in cat_results.items():
                if any(r == RESULT_NG for r in rl): row["by_category"][cat] = "x"
                elif any(r == RESULT_ABNORMAL for r in rl): row["by_category"][cat] = "△"
                elif all(r == RESULT_OK for r in rl): row["by_category"][cat] = "o"
                else: row["by_category"][cat] = "-"
            ng_reports = [rpt for rpt in s.abnormal_reports if rpt.status != ABNORMAL_STATUS_CANCELLED]
            row["ng_count"] = len(ng_reports)
            row["fixed_count"] = sum(1 for rpt in ng_reports if rpt.status in {"fixed", "confirmed"})
            if total > 0:
                row["rate"] = round((ok / total) * 100)
        report_rows.append(row)
        curr -= timedelta(days=1)

    # Tổng hợp tuần
    weekly_summary = {}
    MONTH_ABBR = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    for row in report_rows:
        if not row["sheet"]: continue
        week_start = row["date"] - timedelta(days=row["date"].weekday())
        week_key = week_start.isoformat()
        if week_key not in weekly_summary:
            week_num = (week_start.day - 1) // 7 + 1
            weekly_summary[week_key] = {
                "week_start": week_start,
                "week_label": f"W{week_num}",
                "month": week_start.month,
                "month_label": MONTH_ABBR.get(week_start.month, str(week_start.month)),
                "by_category": {},
                "ng_count": 0, "fixed_count": 0, "total_ok": 0, "total_all": 0,
            }
        wk = weekly_summary[week_key]
        wk["ng_count"] += row["ng_count"]
        wk["fixed_count"] += row["fixed_count"]
        wk["total_ok"] += row["total_ok"]
        wk["total_all"] += row["total_ok"] + row["total_ng"] + row["total_abn"] + row["total_empty"]
        for cat, val in row["by_category"].items():
            prev = wk["by_category"].get(cat, "o")
            if val == "x" or prev == "x": wk["by_category"][cat] = "x"
            elif val == "△" or prev == "△": wk["by_category"][cat] = "△"
            elif val == "o": wk["by_category"][cat] = "o"
            else: wk["by_category"][cat] = prev

    weekly_rows = sorted(weekly_summary.values(), key=lambda x: x["week_start"], reverse=True)
    for wk in weekly_rows:
        wk["rate"] = round((wk["total_ok"] / wk["total_all"]) * 100) if wk["total_all"] > 0 else None

    return render_template(
        "print_profile_report.html",
        user=user,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        view=view,
        report_rows=report_rows,
        weekly_rows=weekly_rows,
        all_category_types=all_category_types,
    )
