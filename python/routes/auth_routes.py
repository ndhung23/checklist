from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from models import User


auth_bp = Blueprint("auth", __name__)


def get_current_user():
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
        if user.role != "admin":
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
        if user.role not in {"admin", "manager"}:
            flash("Chỉ admin hoặc manager mới được thực hiện chức năng này.", "danger")
            return redirect(url_for("checklist.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


@auth_bp.before_app_request
def load_logged_in_user():
    g.current_user = get_current_user()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("checklist.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username và password là bắt buộc.", "danger")
            return render_template("login.html")

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash("Sai username hoặc password.", "danger")
            return render_template("login.html", username=username)

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role
        session["name"] = user.name
        flash("Đăng nhập thành công.", "success")
        return redirect(url_for("checklist.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))
