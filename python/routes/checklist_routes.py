from datetime import date, datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import asc, or_

from models import (
    STATUS_ABNORMAL,
    STATUS_DONE,
    STATUS_PENDING,
    VALID_STATUSES,
    AbnormalNote,
    Category,
    DailyCheck,
    DailyConfirmation,
    User,
    db,
)
from routes.auth_routes import login_required


checklist_bp = Blueprint("checklist", __name__)


def parse_date(date_str, fallback=None):
    if not date_str:
        return fallback
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def parse_time(time_str):
    return datetime.strptime(time_str, "%H:%M").time()


def time_to_minutes(t):
    return t.hour * 60 + t.minute


def find_nearest_check(checks):
    now = datetime.now().time()
    now_minutes = time_to_minutes(now)
    nearest = None
    nearest_diff = float("inf")

    for check in checks:
        diff = abs(time_to_minutes(check.limit_time) - now_minutes)
        if diff < nearest_diff:
            nearest = check
            nearest_diff = diff

    return nearest


def get_dashboard_context():
    current_user = g.current_user
    selected_date = parse_date(request.args.get("date"), fallback=date.today())
    selected_status = request.args.get("status", "").strip()
    selected_user_id = request.args.get("user_id", "").strip()
    keyword = request.args.get("keyword", "").strip()
    page = max(request.args.get("page", default=1, type=int), 1)
    per_page = current_user and current_user.role and 15 or 15

    users = []
    if current_user.role in {"admin", "manager"}:
        users = User.query.filter(User.role != "admin").order_by(User.name.asc()).all()

    query = DailyCheck.query.join(User).outerjoin(AbnormalNote).filter(DailyCheck.date == selected_date)

    if current_user.role == "user":
        query = query.filter(DailyCheck.user_id == current_user.id)
    elif selected_user_id:
        query = query.filter(DailyCheck.user_id == int(selected_user_id))

    if selected_status in VALID_STATUSES:
        query = query.filter(DailyCheck.status == selected_status)

    if keyword:
        like_keyword = f"%{keyword}%"
        query = query.filter(
            or_(
                DailyCheck.symbol.ilike(like_keyword),
                DailyCheck.category.ilike(like_keyword),
                User.name.ilike(like_keyword),
            )
        )

    query = query.order_by(asc(DailyCheck.date), asc(DailyCheck.limit_time), asc(DailyCheck.id))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    checks = pagination.items

    base_query = DailyCheck.query.filter(DailyCheck.date == selected_date)
    if current_user.role == "user":
        base_query = base_query.filter(DailyCheck.user_id == current_user.id)
    total_checks = base_query.count()
    total_done = base_query.filter(DailyCheck.status == STATUS_DONE).count()
    total_pending = base_query.filter(DailyCheck.status == STATUS_PENDING).count()
    total_abnormal = base_query.filter(DailyCheck.status == STATUS_ABNORMAL).count()

    nearest_check = None
    can_highlight = (
        current_user.role == "user" and not keyword and not selected_status
    ) or (
        current_user.role in {"admin", "manager"} and not keyword and not selected_status and selected_user_id
    )
    if can_highlight:
        nearest_source = base_query
        if current_user.role in {"admin", "manager"} and selected_user_id:
            nearest_source = nearest_source.filter(DailyCheck.user_id == int(selected_user_id))
        ordered_checks = nearest_source.order_by(asc(DailyCheck.date), asc(DailyCheck.limit_time), asc(DailyCheck.id)).all()
        nearest_check = find_nearest_check(ordered_checks)

    target_user = current_user if current_user.role == "user" else None
    if current_user.role in {"admin", "manager"} and selected_user_id:
        target_user = User.query.get(int(selected_user_id))

    notifications = {"incomplete": [], "abnormal": []}
    confirmation = None
    if target_user:
        daily_checks = (
            DailyCheck.query.filter_by(user_id=target_user.id, date=selected_date)
            .order_by(asc(DailyCheck.limit_time), asc(DailyCheck.id))
            .all()
        )
        notifications["incomplete"] = [check for check in daily_checks if check.status == STATUS_PENDING]
        notifications["abnormal"] = [check for check in daily_checks if check.status == STATUS_ABNORMAL]
        confirmation = DailyConfirmation.query.filter_by(user_id=target_user.id, date=selected_date).first()

    abnormal_note_map = {
        note.daily_check_id: note
        for note in AbnormalNote.query.join(DailyCheck).filter(DailyCheck.date == selected_date).all()
    }

    page_start = ((pagination.page - 1) * pagination.per_page) + 1 if pagination.total else 0
    page_end = min(pagination.page * pagination.per_page, pagination.total)

    return {
        "checks": checks,
        "users": users,
        "filters": {
            "date": selected_date.isoformat(),
            "status": selected_status,
            "user_id": selected_user_id,
            "keyword": keyword,
        },
        "pagination": pagination,
        "page_start": page_start,
        "page_end": page_end,
        "stats": {
            "total": total_checks,
            "done": total_done,
            "pending": total_pending,
            "abnormal": total_abnormal,
        },
        "nearest_check_id": nearest_check.id if nearest_check else None,
        "notifications": notifications,
        "abnormal_note_map": abnormal_note_map,
        "confirmation": confirmation,
        "target_user": target_user,
        "today": date.today().isoformat(),
        "can_manage_categories": current_user.role == "admin",
        "can_generate": current_user.role == "admin",
        "can_confirm": current_user.role in {"admin", "manager"},
        "show_user_column": current_user.role in {"admin", "manager"},
    }


@checklist_bp.route("/")
@checklist_bp.route("/dashboard")
@login_required
def dashboard():
    context = get_dashboard_context()
    return render_template("dashboard.html", **context)


@checklist_bp.route("/checklist/update-status", methods=["POST"])
@login_required
def update_status():
    check_id = request.form.get("check_id", type=int)
    status = request.form.get("status", "").strip()
    redirect_url = request.form.get("redirect_url") or url_for("checklist.dashboard")
    note_text = request.form.get("note", "").strip()

    if status not in VALID_STATUSES:
        flash("Trạng thái không hợp lệ.", "danger")
        return redirect(redirect_url)

    check = DailyCheck.query.get_or_404(check_id)
    if g.current_user.role == "user" and check.user_id != g.current_user.id:
        flash("Bạn chỉ được cập nhật checklist của mình.", "danger")
        return redirect(url_for("checklist.dashboard"))

    check.status = status

    existing_note = AbnormalNote.query.filter_by(daily_check_id=check.id).first()
    if status == STATUS_ABNORMAL and note_text:
        if existing_note:
            existing_note.note = note_text
            existing_note.symbol = check.symbol
            existing_note.category = check.category
        else:
            db.session.add(
                AbnormalNote(
                    user_id=check.user_id,
                    daily_check_id=check.id,
                    symbol=check.symbol,
                    category=check.category,
                    note=note_text,
                )
            )
    elif status != STATUS_ABNORMAL and existing_note:
        db.session.delete(existing_note)

    db.session.commit()
    flash("Đã cập nhật trạng thái checklist.", "success")
    return redirect(redirect_url)


@checklist_bp.route("/checklist/generate", methods=["POST"])
@login_required
def generate_daily_checks():
    if g.current_user.role != "admin":
        flash("Chỉ admin mới được generate checklist.", "danger")
        return redirect(url_for("checklist.dashboard"))

    user_id = request.form.get("user_id", type=int)
    selected_date = parse_date(request.form.get("date"), fallback=date.today())

    user = User.query.get(user_id)
    if not user or user.role == "admin":
        flash("Người dùng không hợp lệ.", "danger")
        return redirect(url_for("checklist.dashboard"))

    categories = Category.query.order_by(Category.limit_time.asc(), Category.id.asc()).all()
    created_count = 0

    for category in categories:
        exists = DailyCheck.query.filter_by(
            user_id=user.id,
            category_id=category.id,
            date=selected_date,
        ).first()
        if exists:
            continue

        db.session.add(
            DailyCheck(
                user_id=user.id,
                category_id=category.id,
                symbol=category.symbol,
                category=category.category,
                date=selected_date,
                status=STATUS_PENDING,
                limit_time=category.limit_time,
            )
        )
        created_count += 1

    db.session.commit()
    if created_count == 0:
        flash("Không có checklist mới được tạo vì dữ liệu ngày này đã tồn tại.", "warning")
    else:
        flash(f"Đã tạo {created_count} checklist cho {user.name}.", "success")

    return redirect(url_for("checklist.dashboard", user_id=user.id, date=selected_date.isoformat()))


@checklist_bp.route("/checklist/print")
@login_required
def print_checklist():
    current_user = g.current_user
    selected_date = parse_date(request.args.get("date"), fallback=date.today())
    user_id = request.args.get("user_id", type=int)

    if current_user.role == "user":
        user_id = current_user.id
    elif not user_id:
        flash("Vui lòng chọn người dùng để in checklist.", "warning")
        return redirect(url_for("checklist.dashboard", date=selected_date.isoformat()))

    target_user = User.query.get_or_404(user_id)
    checks = (
        DailyCheck.query.filter_by(user_id=target_user.id, date=selected_date)
        .order_by(asc(DailyCheck.limit_time), asc(DailyCheck.id))
        .all()
    )
    note_map = {note.daily_check_id: note for note in AbnormalNote.query.join(DailyCheck).filter(DailyCheck.user_id == user_id, DailyCheck.date == selected_date).all()}
    confirmation = DailyConfirmation.query.filter_by(user_id=user_id, date=selected_date).first()

    return render_template(
        "print_checklist.html",
        checks=checks,
        target_user=target_user,
        selected_date=selected_date,
        note_map=note_map,
        confirmation=confirmation,
    )
