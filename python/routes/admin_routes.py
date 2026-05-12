from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from models import Line, ROLE_ADMIN, ROLE_LEADER, ROLE_MANAGER, ROLE_STAFF, User, UserLine, db
from routes.auth_routes import admin_required


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def upsert_user_lines(user: User, line_ids: list[int]) -> None:
    user.user_lines.clear()
    selected_lines = Line.query.filter(Line.id.in_(line_ids)).all() if line_ids else []
    for line in selected_lines:
        user.user_lines.append(UserLine(line=line))
    if selected_lines:
        user.line_name = selected_lines[0].line_name
        user.department = selected_lines[0].department


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    edit_user_id = request.args.get("edit", type=int)
    edit_user = User.query.get(edit_user_id) if edit_user_id else None

    if request.method == "POST":
        action = request.form.get("action", "create")
        line_ids = request.form.getlist("line_ids", type=int)

        if action == "create":
            user = User(
                username=request.form.get("username", "").strip(),
                full_name=request.form.get("full_name", "").strip(),
                employee_code=request.form.get("employee_code", "").strip(),
                department=request.form.get("department", "").strip() or "Unknown",
                line_name=request.form.get("line_name", "").strip() or "Line A",
                role=request.form.get("role", ROLE_STAFF).strip(),
                is_active=request.form.get("is_active") == "1",
            )
            password = request.form.get("password", "").strip() or "123456"
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            upsert_user_lines(user, line_ids)
            flash("Da tao tai khoan moi.", "success")
        elif action == "update":
            user = User.query.get_or_404(request.form.get("user_id", type=int))
            user.username = request.form.get("username", "").strip()
            user.full_name = request.form.get("full_name", "").strip()
            user.employee_code = request.form.get("employee_code", "").strip()
            user.department = request.form.get("department", "").strip() or user.department
            user.line_name = request.form.get("line_name", "").strip() or user.line_name
            user.role = request.form.get("role", user.role).strip()
            user.is_active = request.form.get("is_active") == "1"
            password = request.form.get("password", "").strip()
            if password:
                user.set_password(password)
            upsert_user_lines(user, line_ids)
            flash("Da cap nhat tai khoan.", "success")

        db.session.commit()
        return redirect(url_for("admin.users"))

    users_data = User.query.order_by(User.created_at.desc(), User.id.desc()).all()
    lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
    return render_template(
        "admin_users.html",
        users=users_data,
        lines=lines,
        edit_user=edit_user,
        roles=[ROLE_ADMIN, ROLE_MANAGER, ROLE_LEADER, ROLE_STAFF],
        current_endpoint="admin.users",
    )


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Không thể khóa tài khoản admin gốc.", "warning")
        return redirect(url_for("admin.users"))

    user.is_active = not user.is_active
    db.session.commit()
    flash("Da cap nhat trang thai tai khoan.", "success")
    return redirect(url_for("admin.users"))
