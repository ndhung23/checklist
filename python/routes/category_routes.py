from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from models import Category, DailyCheck, db
from routes.auth_routes import admin_required


category_bp = Blueprint("category", __name__)


def parse_limit_time(value):
    return datetime.strptime(value, "%H:%M").time()


@category_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip()
        category_name = request.form.get("category", "").strip()
        limit_time = request.form.get("limit_time", "").strip()

        if not symbol or not category_name or not limit_time:
            flash("Vui lòng nhập đầy đủ symbol, hạng mục và giờ giới hạn.", "danger")
            return redirect(url_for("category.categories"))

        db.session.add(
            Category(
                symbol=symbol,
                category=category_name,
                limit_time=parse_limit_time(limit_time),
            )
        )
        db.session.commit()
        flash("Đã thêm hạng mục mới.", "success")
        return redirect(url_for("category.categories"))

    categories = Category.query.order_by(Category.limit_time.asc(), Category.id.asc()).all()
    return render_template("admin_categories.html", categories=categories)


@category_bp.route("/categories/<int:category_id>/update", methods=["POST"])
@admin_required
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    symbol = request.form.get("symbol", "").strip()
    category_name = request.form.get("category", "").strip()
    limit_time = request.form.get("limit_time", "").strip()

    if not symbol or not category_name or not limit_time:
        flash("Vui lòng nhập đầy đủ dữ liệu khi cập nhật.", "danger")
        return redirect(url_for("category.categories"))

    category.symbol = symbol
    category.category = category_name
    category.limit_time = parse_limit_time(limit_time)

    related_checks = DailyCheck.query.filter_by(category_id=category.id).all()
    for check in related_checks:
        check.symbol = symbol
        check.category = category_name
        check.limit_time = category.limit_time

    db.session.commit()
    flash("Đã cập nhật hạng mục.", "success")
    return redirect(url_for("category.categories"))


@category_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    in_use = DailyCheck.query.filter_by(category_id=category.id).count()
    if in_use:
        flash("Không thể xóa hạng mục đã được dùng trong checklist.", "danger")
        return redirect(url_for("category.categories"))

    db.session.delete(category)
    db.session.commit()
    flash("Đã xóa hạng mục.", "success")
    return redirect(url_for("category.categories"))
