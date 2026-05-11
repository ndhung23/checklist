from datetime import date, datetime

from flask import Blueprint, flash, g, redirect, request, url_for

from models import DailyConfirmation, User, db
from routes.auth_routes import manager_or_admin_required


confirmation_bp = Blueprint("confirmation", __name__)


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


@confirmation_bp.route("/confirm", methods=["POST"])
@manager_or_admin_required
def confirm_daily_check():
    user_id = request.form.get("user_id", type=int)
    selected_date = parse_date(request.form.get("date"))
    signature_note = request.form.get("signature_note", "").strip()

    target_user = User.query.get(user_id)
    if not target_user:
        flash("Người dùng xác nhận không hợp lệ.", "danger")
        return redirect(url_for("checklist.dashboard", date=selected_date.isoformat()))

    existing = DailyConfirmation.query.filter_by(user_id=user_id, date=selected_date).first()
    if existing:
        flash("Ngày này đã được ký xác nhận.", "warning")
        return redirect(url_for("checklist.dashboard", user_id=user_id, date=selected_date.isoformat()))

    db.session.add(
        DailyConfirmation(
            user_id=user_id,
            date=selected_date,
            confirmed_by=g.current_user.id,
            confirmed_by_name=g.current_user.name,
            confirmed_at=datetime.now(),
            signature_note=signature_note,
        )
    )
    db.session.commit()
    flash("Đã ký xác nhận checklist trong ngày.", "success")
    return redirect(url_for("checklist.dashboard", user_id=user_id, date=selected_date.isoformat()))
