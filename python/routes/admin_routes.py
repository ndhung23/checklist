from __future__ import annotations

import math

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import (
    Line,
    ROLE_ADMIN,
    ROLE_LEADER,
    ROLE_MANAGER,
    ROLE_STAFF,
    ROLE_SUPERVISOR,
    User,
    db,
)
from routes.auth_routes import admin_required, manager_or_admin_required


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
TEMP_SHARED_OUTLOOK = "hung.nguyen.duy.a0u@ap.denso.com"


def role_options_for(user: User) -> list[str]:
    if user.role == ROLE_MANAGER:
        return [ROLE_SUPERVISOR]
    if user.role == ROLE_SUPERVISOR:
        return [ROLE_LEADER]
    if user.role == ROLE_LEADER:
        return [ROLE_STAFF]
    return [ROLE_ADMIN, ROLE_MANAGER, ROLE_SUPERVISOR, ROLE_LEADER, ROLE_STAFF]


def default_line_values(role: str = ROLE_STAFF) -> tuple[str, str]:
    line_name = "Ca hanh chinh" if role in {ROLE_MANAGER, ROLE_SUPERVISOR, ROLE_LEADER} else "Ca 1"
    line = Line.query.filter_by(line_name=line_name, is_active=True).first()
    if line:
        return line.line_name, line.department
    line = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).first()
    if line:
        return line.line_name, line.department
    return line_name, "Production"


def next_staff_code(leader: User) -> str:
    prefix = f"{leader.employee_code}-SL"
    existing = [
        user.employee_code
        for user in User.query.filter(User.employee_code.like(f"{prefix}%")).all()
    ]
    next_index = 1
    while f"{prefix}{next_index}" in existing:
        next_index += 1
    return f"{prefix}{next_index}"


def authority_for(role: str, actor: User) -> tuple[int | None, int | None, int | None, str | None]:
    manager_id = request.form.get("manager_id", type=int)
    supervisor_id = request.form.get("supervisor_id", type=int)
    leader_id = request.form.get("leader_id", type=int)
    outlook_email = request.form.get("outlook_email", "").strip() or None

    if actor.role == ROLE_MANAGER:
        return actor.id, None, None, outlook_email
    if actor.role == ROLE_SUPERVISOR:
        return None, actor.id, None, outlook_email
    if actor.role == ROLE_LEADER:
        return None, None, actor.id, actor.outlook_email or TEMP_SHARED_OUTLOOK

    if role == ROLE_SUPERVISOR:
        return manager_id, None, None, outlook_email
    if role == ROLE_LEADER:
        return None, supervisor_id, None, outlook_email
    if role == ROLE_STAFF:
        leader = User.query.filter_by(id=leader_id, role=ROLE_LEADER, is_active=True).first()
        if leader:
            return None, None, leader.id, leader.outlook_email or TEMP_SHARED_OUTLOOK
        return None, None, None, outlook_email
    return None, None, None, outlook_email


def redirect_back(default_endpoint: str = "admin.users"):
    next_url = request.form.get("next") or request.args.get("next")
    return redirect(next_url or request.referrer or url_for(default_endpoint))


def visible_user_query(actor: User):
    query = User.query
    if actor.role == ROLE_MANAGER:
        return query.filter(User.role == ROLE_SUPERVISOR, User.manager_id == actor.id)
    if actor.role == ROLE_SUPERVISOR:
        return query.filter(User.role == ROLE_LEADER, User.supervisor_id == actor.id)
    if actor.role == ROLE_LEADER:
        return query.filter(User.role == ROLE_STAFF, User.leader_id == actor.id)
    return query


@admin_bp.route("/users", methods=["GET", "POST"])
@manager_or_admin_required
def users():
    edit_user_id = request.args.get("edit", type=int)
    edit_user = User.query.get(edit_user_id) if edit_user_id else None

    if request.method == "POST":
        action = request.form.get("action", "create")
        actor = g.current_user
        requested_role = request.form.get("role", ROLE_STAFF).strip()
        allowed_roles = role_options_for(actor)
        role = requested_role if requested_role in allowed_roles else allowed_roles[0]
        manager_id, supervisor_id, leader_id, outlook_email = authority_for(role, actor)
        if actor.role == ROLE_ADMIN:
            missing_authority = (
                (role == ROLE_SUPERVISOR and not manager_id)
                or (role == ROLE_LEADER and not supervisor_id)
                or (role == ROLE_STAFF and not leader_id)
            )
            if missing_authority:
                flash("Vui lòng chọn thẩm quyền quản lý phù hợp với role.", "danger")
                return redirect_back()

        employee_code = request.form.get("employee_code", "").strip()
        if action == "create" and actor.role == ROLE_LEADER and role == ROLE_STAFF:
            employee_code = employee_code or next_staff_code(actor)
        username = request.form.get("username", "").strip() or employee_code
        fallback_line_name, fallback_department = default_line_values(role)

        if action == "create":
            if not username or not request.form.get("full_name", "").strip():
                flash("Username và full name là bắt buộc.", "danger")
                return redirect_back()
            user = User(
                username=username,
                full_name=request.form.get("full_name", "").strip(),
                employee_code=employee_code or username,
                outlook_email=outlook_email,
                gender=request.form.get("gender", "").strip() or None,
                department=fallback_department,
                line_name=request.form.get("line_name", "").strip() or fallback_line_name,
                role=role,
                manager_id=manager_id,
                supervisor_id=supervisor_id,
                leader_id=leader_id,
                is_active=True,
            )
            password = request.form.get("password", "").strip() or "1"
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            flash("Đã tạo tài khoản mới.", "success")
        elif action == "update":
            user = User.query.get_or_404(request.form.get("user_id", type=int))
            if actor.role == ROLE_MANAGER and not (user.role == ROLE_SUPERVISOR and user.manager_id == actor.id):
                flash("Manager chỉ được sửa supervisor thuộc quyền.", "danger")
                return redirect_back()
            if actor.role == ROLE_SUPERVISOR and not (user.role == ROLE_LEADER and user.supervisor_id == actor.id):
                flash("Supervisor chỉ được sửa leader thuộc quyền.", "danger")
                return redirect_back()
            if actor.role == ROLE_LEADER and not (user.role == ROLE_STAFF and user.leader_id == actor.id):
                flash("Leader chỉ được sửa staff thuộc quyền.", "danger")
                return redirect_back()

            user.username = username
            user.full_name = request.form.get("full_name", "").strip()
            user.employee_code = employee_code or user.employee_code
            user.outlook_email = outlook_email
            user.gender = request.form.get("gender", "").strip() or None
            user.role = role
            user.manager_id = manager_id
            user.supervisor_id = supervisor_id
            user.leader_id = leader_id
            if request.form.get("line_name"):
                user.line_name = request.form.get("line_name", "").strip()
            password = request.form.get("password", "").strip()
            if password:
                user.set_password(password)
            flash("Đã cập nhật tài khoản.", "success")

        db.session.commit()
        return redirect_back()

    keyword = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    gender_filter = request.args.get("gender", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = visible_user_query(g.current_user)
    if keyword:
        like_value = f"%{keyword}%"
        query = query.filter(
            or_(
                User.username.ilike(like_value),
                User.employee_code.ilike(like_value),
                User.full_name.ilike(like_value),
                User.outlook_email.ilike(like_value),
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
    users_data = query.order_by(User.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
    managers = User.query.filter_by(role=ROLE_MANAGER, is_active=True).order_by(User.full_name.asc()).all()
    supervisors = User.query.filter_by(role=ROLE_SUPERVISOR, is_active=True).order_by(User.full_name.asc()).all()
    leaders = User.query.filter_by(role=ROLE_LEADER, is_active=True).order_by(User.full_name.asc()).all()

    return render_template(
        "admin_users.html",
        users=users_data,
        lines=lines,
        managers=managers,
        supervisors=supervisors,
        leaders=leaders,
        edit_user=edit_user,
        roles=role_options_for(g.current_user),
        genders=["male", "female", "other"],
        filters={"q": keyword, "role": role_filter, "gender": gender_filter, "status": status_filter},
        pagination={"page": page, "pages": max(math.ceil(total_users / per_page), 1), "total": total_users},
        current_endpoint="admin.users",
        create_modal=request.args.get("create") == "1",
    )


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Không thể khóa tài khoản admin gốc.", "warning")
        return redirect_back()
    user.is_active = not user.is_active
    db.session.commit()
    flash("Đã cập nhật trạng thái tài khoản.", "success")
    return redirect_back()


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Không thể xóa tài khoản admin gốc.", "warning")
        return redirect_back()
    try:
        db.session.delete(user)
        db.session.commit()
        flash("Đã xóa tài khoản.", "success")
    except IntegrityError:
        db.session.rollback()
        user.is_active = False
        db.session.commit()
        flash("Tài khoản đã có dữ liệu checklist nên đã chuyển sang trạng thái khóa.", "warning")
    return redirect_back()


@admin_bp.route("/users/<int:user_id>/assign-leader", methods=["POST"])
@manager_or_admin_required
def assign_leader(user_id: int):
    user = User.query.get_or_404(user_id)
    leader_id = request.form.get("leader_id", type=int)
    leader = User.query.filter_by(id=leader_id, role=ROLE_LEADER, is_active=True).first()
    if user.role != ROLE_STAFF or leader is None:
        flash("Không thể gán tổ trưởng cho tài khoản này.", "danger")
        return redirect(request.referrer or url_for("checklist.dashboard"))
    user.leader_id = leader.id
    user.outlook_email = leader.outlook_email or TEMP_SHARED_OUTLOOK
    db.session.commit()
    flash("Đã gán nhân viên vào tổ trưởng.", "success")
    return redirect(request.referrer or url_for("checklist.dashboard"))


@admin_bp.route("/leader-assignments")
@manager_or_admin_required
def leader_assignments():
    return redirect(url_for("admin.users"))
