from __future__ import annotations

import math

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import Line, ROLE_ADMIN, ROLE_LEADER, ROLE_MANAGER, ROLE_STAFF, User, db
from routes.auth_routes import admin_required, manager_or_admin_required


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
TEMP_SHARED_OUTLOOK = "hung.nguyen.duy.a0u@ap.denso.com"


def role_options_for(user: User) -> list[str]:
    if user.role == ROLE_MANAGER:
        return [ROLE_LEADER]
    if user.role == ROLE_LEADER:
        return [ROLE_STAFF]
    return [ROLE_ADMIN, ROLE_MANAGER, ROLE_LEADER, ROLE_STAFF]


def normalize_user_authority(role: str, actor: User, leader_id: int | None) -> tuple[int | None, int | None, str]:
    if actor.role == ROLE_LEADER:
        return None, actor.id, actor.outlook_email or TEMP_SHARED_OUTLOOK

    if role == ROLE_STAFF and leader_id:
        leader = User.query.filter_by(id=leader_id, role=ROLE_LEADER, is_active=True).first()
        if leader:
            return None, leader.id, leader.outlook_email or TEMP_SHARED_OUTLOOK

    return None, leader_id if role == ROLE_STAFF else None, TEMP_SHARED_OUTLOOK


def default_line_values() -> tuple[str, str]:
    line = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).first()
    if line:
        return line.line_name, line.department
    return "Line A", "Unknown"


def redirect_back(default_endpoint: str = "admin.users"):
    next_url = request.form.get("next") or request.args.get("next")
    return redirect(next_url or request.referrer or url_for(default_endpoint))


@admin_bp.route("/users", methods=["GET", "POST"])
@manager_or_admin_required
def users():
    edit_user_id = request.args.get("edit", type=int)
    edit_user = User.query.get(edit_user_id) if edit_user_id else None

    if request.method == "POST":
        action = request.form.get("action", "create")
        actor = g.current_user
        employee_code = request.form.get("employee_code", "").strip()
        username = request.form.get("username", "").strip() or employee_code
        leader_id = request.form.get("leader_id", type=int)
        requested_role = request.form.get("role", ROLE_STAFF).strip()
        allowed_roles = role_options_for(actor)
        role = requested_role if requested_role in allowed_roles else allowed_roles[-1]
        manager_id, leader_id, outlook_email = normalize_user_authority(role, actor, leader_id)
        if actor.role == ROLE_LEADER and role == ROLE_STAFF:
            outlook_email = request.form.get("outlook_email", "").strip() or outlook_email
        fallback_line_name, fallback_department = default_line_values()

        if action == "create":
            user = User(
                username=username,
                full_name=request.form.get("full_name", "").strip(),
                employee_code=employee_code,
                outlook_email=outlook_email,
                gender=request.form.get("gender", "").strip() or None,
                department=request.form.get("department", "").strip() or fallback_department,
                line_name=request.form.get("line_name", "").strip() or fallback_line_name,
                role=role,
                manager_id=manager_id,
                leader_id=leader_id,
                is_active=request.form.get("is_active") == "1",
            )
            password = request.form.get("password", "").strip() or "123456"
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            flash("Đã tạo tài khoản mới.", "success")
        elif action == "update":
            user = User.query.get_or_404(request.form.get("user_id", type=int))
            if actor.role == ROLE_LEADER and (user.role != ROLE_STAFF or user.leader_id != actor.id):
                flash("Bạn không có quyền sửa tài khoản này.", "danger")
                return redirect_back()

            if actor.role == ROLE_MANAGER and user.role not in {ROLE_LEADER, ROLE_STAFF}:
                flash("Manager chỉ được tạo tổ trưởng và đổi tổ trưởng quản lý của tổ phố.", "warning")
                return redirect_back()

            if actor.role == ROLE_MANAGER and user.role == ROLE_LEADER:
                flash("Manager chỉ được tạo tổ trưởng mới, không sửa tài khoản tổ trưởng hiện có.", "warning")
                return redirect_back()

            if actor.role == ROLE_MANAGER and user.role == ROLE_STAFF:
                manager_id, leader_id, outlook_email = normalize_user_authority(ROLE_STAFF, actor, leader_id)
                user.manager_id = manager_id
                user.leader_id = leader_id
                user.outlook_email = outlook_email
                db.session.commit()
                flash("Đã đổi tổ trưởng quản lý cho tổ phố.", "success")
                return redirect_back()

            if actor.role == ROLE_LEADER and user.role != ROLE_STAFF:
                role = user.role
                manager_id = user.manager_id
                leader_id = user.leader_id

            user.username = username
            user.full_name = request.form.get("full_name", "").strip()
            user.employee_code = employee_code
            user.outlook_email = outlook_email
            user.gender = request.form.get("gender", "").strip() or None
            user.department = request.form.get("department", "").strip() or user.department
            user.line_name = request.form.get("line_name", "").strip() or user.line_name
            user.role = role
            user.manager_id = manager_id
            user.leader_id = leader_id
            user.is_active = request.form.get("is_active") == "1"
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
    create_modal = request.args.get("create") == "1"
    return render_template(
        "admin_users.html",
        users=users_data,
        lines=lines,
        departments=departments,
        managers=managers,
        leaders=leaders,
        edit_user=edit_user,
        roles=role_options_for(g.current_user),
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
        create_modal=create_modal,
    )


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if g.current_user.role == ROLE_LEADER and (user.role != ROLE_STAFF or user.leader_id != g.current_user.id):
        flash("Bạn không có quyền khóa tài khoản này.", "danger")
        return redirect_back()
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
    if g.current_user.role == ROLE_LEADER and (user.role != ROLE_STAFF or user.leader_id != g.current_user.id):
        flash("Bạn không có quyền xóa tài khoản này.", "danger")
        return redirect_back()
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
        flash("Tài khoản đã có dữ liệu checklist nên đã chuyển sang trạng thái Khóa.", "warning")
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
    user.manager_id = None
    user.outlook_email = leader.outlook_email or TEMP_SHARED_OUTLOOK
    db.session.commit()
    flash("Đã gán nhân viên vào tổ trưởng.", "success")
    return redirect(request.referrer or url_for("checklist.dashboard"))


@admin_bp.route("/leader-assignments")
@manager_or_admin_required
def leader_assignments():
    keyword = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    gender_filter = request.args.get("gender", "").strip()

    leaders_query = User.query.filter(User.role == ROLE_LEADER, User.is_active.is_(True))
    staff_query = User.query.filter(User.role == ROLE_STAFF)
    if g.current_user.role == ROLE_LEADER:
        leaders_query = leaders_query.filter(User.id == g.current_user.id)
        staff_query = staff_query.filter(User.leader_id == g.current_user.id)

    if keyword:
        like_value = f"%{keyword}%"
        staff_query = staff_query.filter(
            or_(
                User.username.ilike(like_value),
                User.employee_code.ilike(like_value),
                User.full_name.ilike(like_value),
                User.outlook_email.ilike(like_value),
                User.department.ilike(like_value),
            )
        )
    if status_filter == "active":
        staff_query = staff_query.filter(User.is_active.is_(True))
    elif status_filter == "locked":
        staff_query = staff_query.filter(User.is_active.is_(False))
    if gender_filter:
        staff_query = staff_query.filter(User.gender == gender_filter)

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 10
    total_staff = staff_query.count()
    staff_assignments = (
        staff_query.order_by(User.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    leaders = leaders_query.order_by(User.full_name.asc()).all()
    lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
    departments = sorted({line.department for line in lines} | {g.current_user.department})

    return render_template(
        "leader_assignments.html",
        leaders=leaders,
        staff_assignments=staff_assignments,
        lines=lines,
        departments=departments,
        roles=[ROLE_STAFF],
        genders=["male", "female", "other"],
        filters={"q": keyword, "status": status_filter, "gender": gender_filter},
        pagination={"page": page, "pages": max(math.ceil(total_staff / per_page), 1), "total": total_staff},
        current_endpoint="admin.leader_assignments",
    )
