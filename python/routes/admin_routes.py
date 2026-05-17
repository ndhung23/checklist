from __future__ import annotations

import math

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import Line, ROLE_ADMIN, ROLE_LEADER, ROLE_MANAGER, ROLE_STAFF, User, UserLine, db
from routes.auth_routes import admin_required, manager_or_admin_required


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
        employee_code = request.form.get("employee_code", "").strip()
        manager_id = request.form.get("manager_id", type=int)
        leader_id = request.form.get("leader_id", type=int)

        if action == "create":
            user = User(
                username=employee_code,
                full_name=request.form.get("full_name", "").strip(),
                employee_code=employee_code,
                outlook_email=request.form.get("outlook_email", "").strip() or None,
                gender=request.form.get("gender", "").strip() or None,
                department=request.form.get("department", "").strip() or "Unknown",
                line_name=request.form.get("line_name", "").strip() or "Line A",
                role=request.form.get("role", ROLE_STAFF).strip(),
                manager_id=manager_id,
                leader_id=leader_id,
                is_active=request.form.get("is_active") == "1",
            )
            password = request.form.get("password", "").strip() or "123456"
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            upsert_user_lines(user, line_ids)
            flash("Đã tạo tài khoản mới.", "success")
        elif action == "update":
            user = User.query.get_or_404(request.form.get("user_id", type=int))
            user.username = employee_code
            user.full_name = request.form.get("full_name", "").strip()
            user.employee_code = employee_code
            user.outlook_email = request.form.get("outlook_email", "").strip() or None
            user.gender = request.form.get("gender", "").strip() or None
            user.department = request.form.get("department", "").strip() or user.department
            user.line_name = request.form.get("line_name", "").strip() or user.line_name
            user.role = request.form.get("role", user.role).strip()
            user.manager_id = manager_id
            user.leader_id = leader_id
            user.is_active = request.form.get("is_active") == "1"
            password = request.form.get("password", "").strip()
            if password:
                user.set_password(password)
            upsert_user_lines(user, line_ids)
            flash("Đã cập nhật tài khoản.", "success")

        db.session.commit()
        return redirect(url_for("admin.users"))

    keyword = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    gender_filter = request.args.get("gender", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = User.query
    if keyword:
        like_value = f"%{keyword}%"
        query = query.filter(
            or_(
                User.username.ilike(like_value),
                User.employee_code.ilike(like_value),
                User.full_name.ilike(like_value),
                User.outlook_email.ilike(like_value),
                User.department.ilike(like_value),
            )
        )
    if role_filter:
        query = query.filter(User.role == role_filter)
    if gender_filter:
        query = query.filter(User.gender == gender_filter)
    if status_filter == "active":
        query = query.filter(User.is_active.is_(True))
    elif status_filter == "locked":
        query = query.filter(User.is_active.is_(False))

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 10
    total_users = query.count()
    users_data = (
        query.order_by(User.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
    departments = sorted({line.department for line in lines})
    managers = User.query.filter(User.role.in_([ROLE_ADMIN, ROLE_MANAGER]), User.is_active.is_(True)).order_by(User.full_name.asc()).all()
    leaders = User.query.filter(User.role == ROLE_LEADER, User.is_active.is_(True)).order_by(User.full_name.asc()).all()
    return render_template(
        "admin_users.html",
        users=users_data,
        lines=lines,
        departments=departments,
        managers=managers,
        leaders=leaders,
        edit_user=edit_user,
        roles=[ROLE_ADMIN, ROLE_MANAGER, ROLE_LEADER, ROLE_STAFF],
        genders=["male", "female", "other"],
        filters={
            "q": keyword,
            "role": role_filter,
            "gender": gender_filter,
            "status": status_filter,
        },
        pagination={
            "page": page,
            "pages": max(math.ceil(total_users / per_page), 1),
            "total": total_users,
        },
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
    flash("Đã cập nhật trạng thái tài khoản.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Không thể xóa tài khoản admin gốc.", "warning")
        return redirect(url_for("admin.users"))

    try:
        db.session.delete(user)
        db.session.commit()
        flash("Đã xóa tài khoản.", "success")
    except IntegrityError:
        db.session.rollback()
        user.is_active = False
        db.session.commit()
        flash("Tài khoản đã có dữ liệu checklist nên đã chuyển sang trạng thái Khóa.", "warning")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/assign-leader", methods=["POST"])
@manager_or_admin_required
def assign_leader(user_id: int):
    user = User.query.get_or_404(user_id)
    leader_id = request.form.get("leader_id", type=int)
    leader = User.query.filter_by(id=leader_id, role=ROLE_LEADER, is_active=True).first()
    if user.role != ROLE_STAFF or leader is None:
        flash("Không thể gán leader cho tài khoản này.", "danger")
        return redirect(request.referrer or url_for("checklist.dashboard"))

    user.leader_id = leader.id
    user.manager_id = leader.manager_id or user.manager_id
    db.session.commit()
    flash("Đã gán nhân viên vào tổ trưởng.", "success")
    return redirect(request.referrer or url_for("checklist.dashboard"))


@admin_bp.route("/leader-assignments")
@manager_or_admin_required
def leader_assignments():
    leaders_query = User.query.filter(User.role == ROLE_LEADER, User.is_active.is_(True))
    staff_query = User.query.filter(User.role == ROLE_STAFF, User.is_active.is_(True))

    if g.current_user.role == ROLE_MANAGER:
        leaders_query = leaders_query.filter(User.manager_id == g.current_user.id)
        staff_query = staff_query.filter(User.manager_id == g.current_user.id)

    leaders = leaders_query.order_by(User.full_name.asc()).all()
    staff_assignments = staff_query.order_by(User.line_name.asc(), User.full_name.asc()).all()

    return render_template(
        "leader_assignments.html",
        leaders=leaders,
        staff_assignments=staff_assignments,
        current_endpoint="admin.leader_assignments",
    )
