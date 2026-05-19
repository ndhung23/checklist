from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from models import ChecklistItem, ChecklistTemplate, DailyCheckResult, Line, db
from routes.auth_routes import admin_required


category_bp = Blueprint("category", __name__)

ALL_24H_OPTIONS = [f"{h:02d}:00" for h in range(24)]

LINE_TIME_OPTIONS = {}


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
    line_time_options_map = {str(line.id): LINE_TIME_OPTIONS.get(line.line_name, ALL_24H_OPTIONS) for line in lines}
    if template is None or selected_line is None:
        flash("ChÆ°a cĂ³ checklist template Ä‘á»ƒ quáº£n lĂ½ háº¡ng má»¥c.", "warning")
        return render_template(
            "admin_categories.html",
            templates=[],
            lines=lines,
            line_time_options_map=line_time_options_map,
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
            flash("Vui lĂ²ng nháº­p Ä‘áº§y Ä‘á»§ kĂ½ hiá»‡u, háº¡ng má»¥c vĂ  giá».", "danger")
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
        flash("ÄĂ£ thĂªm háº¡ng má»¥c má»›i.", "success")
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
        line_time_options=LINE_TIME_OPTIONS.get(selected_line.line_name, ALL_24H_OPTIONS),
        line_time_options_map=line_time_options_map,
        categories=categories,
        filters={"q": keyword, "status": status_filter},
        current_endpoint="category.categories",
    )


@category_bp.route("/categories/<int:category_id>/update", methods=["POST"])
@admin_required
def update_category(category_id: int):
    category = ChecklistItem.query.get_or_404(category_id)
    line_id = request.form.get("line_id", type=int)
    selected_line = Line.query.filter_by(id=line_id, is_active=True).first() if line_id else category.line
    symbol = request.form.get("symbol", "").strip()
    content = request.form.get("content", "").strip()
    check_time = request.form.get("check_time", "").strip()
    time_group = request.form.get("time_group", "").strip() or check_time

    if not symbol or not content or not check_time:
        flash("Vui lĂ²ng nháº­p Ä‘áº§y Ä‘á»§ dá»¯ liá»‡u khi cáº­p nháº­t.", "danger")
        return redirect(url_for("category.categories", template_id=category.template_id, line_id=category.line_id))

    if selected_line is None:
        flash("Vui lĂ²ng chá»n line há»£p lá»‡.", "danger")
        return redirect(url_for("category.categories", template_id=category.template_id, line_id=category.line_id))

    parsed_time = parse_check_time(check_time)
    if category.line_id != selected_line.id:
        next_order = (
            db.session.query(func.max(ChecklistItem.item_order))
            .filter(ChecklistItem.template_id == category.template_id, ChecklistItem.line_id == selected_line.id)
            .scalar()
            or 0
        ) + 1
        category.item_order = next_order
    category.line = selected_line
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
    flash("ÄĂ£ cáº­p nháº­t háº¡ng má»¥c.", "success")
    return redirect(url_for("category.categories", template_id=category.template_id, line_id=selected_line.id))


@category_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id: int):
    category = ChecklistItem.query.get_or_404(category_id)
    in_use = DailyCheckResult.query.filter_by(checklist_item_id=category.id).count()
    if in_use:
        category.is_active = False
        db.session.commit()
        flash("Háº¡ng má»¥c Ä‘Ă£ cĂ³ dá»¯ liá»‡u checklist nĂªn há»‡ thá»‘ng Ä‘Ă£ chuyá»ƒn sang inactive.", "warning")
        return redirect(url_for("category.categories", template_id=category.template_id, line_id=category.line_id))

    template_id = category.template_id
    line_id = category.line_id
    db.session.delete(category)
    db.session.commit()
    flash("ÄĂ£ xĂ³a háº¡ng má»¥c.", "success")
    return redirect(url_for("category.categories", template_id=template_id, line_id=line_id))

