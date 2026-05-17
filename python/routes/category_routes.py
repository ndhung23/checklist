from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from models import ChecklistItem, ChecklistTemplate, DailyCheckResult, Line, db
from routes.auth_routes import admin_required


category_bp = Blueprint("category", __name__)

LINE_TIME_OPTIONS = {
    "Line A": ["06:00", "07:00", "08:00", "09:00", "11:00", "12:00", "13:00"],
    "Line B": ["08:20", "09:20", "10:00", "11:00", "13:00", "15:00", "16:00"],
    "Line C": ["14:00", "15:00", "16:00", "17:00", "19:00", "20:00", "21:00"],
    "Line D": ["22:00", "23:00", "00:00", "01:00", "03:00", "04:00", "05:00"],
}


def parse_check_time(value: str):
    return datetime.strptime(value, "%H:%M").time()


def get_template() -> ChecklistTemplate | None:
    template_id = request.values.get("template_id", type=int)
    query = ChecklistTemplate.query.filter_by(is_active=True)
    if template_id:
        return query.filter_by(id=template_id).first()
    return query.order_by(ChecklistTemplate.id.asc()).first()


def get_line() -> Line | None:
    line_id = request.values.get("line_id", type=int)
    query = Line.query.filter_by(is_active=True)
    if line_id:
        return query.filter_by(id=line_id).first()
    return query.order_by(Line.line_name.asc()).first()


@category_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    template = get_template()
    selected_line = get_line()
    lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
    if template is None or selected_line is None:
        flash("Chưa có checklist template để quản lý hạng mục.", "warning")
        return render_template(
            "admin_categories.html",
            templates=[],
            lines=lines,
            selected_template=None,
            selected_line=selected_line,
            line_time_options=[],
            categories=[],
            filters={"q": "", "status": ""},
            current_endpoint="category.categories",
        )

    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip()
        content = request.form.get("content", "").strip()
        check_time = request.form.get("check_time", "").strip()
        time_group = request.form.get("time_group", "").strip() or check_time

        if not symbol or not content or not check_time:
            flash("Vui lòng nhập đầy đủ ký hiệu, hạng mục và giờ.", "danger")
            return redirect(url_for("category.categories", template_id=template.id, line_id=selected_line.id))

        next_order = (
            db.session.query(func.max(ChecklistItem.item_order))
            .filter(ChecklistItem.template_id == template.id, ChecklistItem.line_id == selected_line.id)
            .scalar()
            or 0
        ) + 1
        db.session.add(
            ChecklistItem(
                template=template,
                line=selected_line,
                symbol=symbol,
                check_time=parse_check_time(check_time),
                time_group=time_group,
                item_order=next_order,
                category_type=symbol,
                content=content,
                content_vi=content,
                content_en=content,
                content_ja=content,
                is_active=True,
            )
        )
        db.session.commit()
        flash("Đã thêm hạng mục mới.", "success")
        return redirect(url_for("category.categories", template_id=template.id, line_id=selected_line.id))

    keyword = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    query = ChecklistItem.query.filter_by(template_id=template.id, line_id=selected_line.id)
    if keyword:
        like_value = f"%{keyword}%"
        query = query.filter(
            or_(
                ChecklistItem.symbol.ilike(like_value),
                ChecklistItem.time_group.ilike(like_value),
                ChecklistItem.content_vi.ilike(like_value),
            )
        )
    if status_filter == "active":
        query = query.filter(ChecklistItem.is_active.is_(True))
    elif status_filter == "locked":
        query = query.filter(ChecklistItem.is_active.is_(False))

    categories = query.order_by(ChecklistItem.check_time.asc(), ChecklistItem.item_order.asc()).all()
    templates = ChecklistTemplate.query.order_by(ChecklistTemplate.template_name.asc()).all()
    return render_template(
        "admin_categories.html",
        templates=templates,
        lines=lines,
        selected_template=template,
        selected_line=selected_line,
        line_time_options=LINE_TIME_OPTIONS.get(selected_line.line_name, []),
        categories=categories,
        filters={"q": keyword, "status": status_filter},
        current_endpoint="category.categories",
    )


@category_bp.route("/categories/<int:category_id>/update", methods=["POST"])
@admin_required
def update_category(category_id: int):
    category = ChecklistItem.query.get_or_404(category_id)
    symbol = request.form.get("symbol", "").strip()
    content = request.form.get("content", "").strip()
    check_time = request.form.get("check_time", "").strip()
    time_group = request.form.get("time_group", "").strip() or check_time

    if not symbol or not content or not check_time:
        flash("Vui lòng nhập đầy đủ dữ liệu khi cập nhật.", "danger")
        return redirect(url_for("category.categories", template_id=category.template_id, line_id=category.line_id))

    parsed_time = parse_check_time(check_time)
    category.symbol = symbol
    category.category_type = symbol
    category.content = content
    category.content_vi = content
    category.content_en = request.form.get("content_en", "").strip() or content
    category.content_ja = request.form.get("content_ja", "").strip() or content
    category.check_time = parsed_time
    category.time_group = time_group
    category.is_active = request.form.get("is_active") == "1"

    related_results = DailyCheckResult.query.filter_by(checklist_item_id=category.id).all()
    for result in related_results:
        result.symbol = symbol
        result.check_time = parsed_time
        result.content = content

    db.session.commit()
    flash("Đã cập nhật hạng mục.", "success")
    return redirect(url_for("category.categories", template_id=category.template_id, line_id=category.line_id))


@category_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id: int):
    category = ChecklistItem.query.get_or_404(category_id)
    in_use = DailyCheckResult.query.filter_by(checklist_item_id=category.id).count()
    if in_use:
        category.is_active = False
        db.session.commit()
        flash("Hạng mục đã có dữ liệu checklist nên hệ thống đã chuyển sang inactive.", "warning")
        return redirect(url_for("category.categories", template_id=category.template_id, line_id=category.line_id))

    template_id = category.template_id
    line_id = category.line_id
    db.session.delete(category)
    db.session.commit()
    flash("Đã xóa hạng mục.", "success")
    return redirect(url_for("category.categories", template_id=template_id, line_id=line_id))
