from __future__ import annotations

from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from sqlalchemy import or_

from models import Line, User


auth_bp = Blueprint("auth", __name__)


def get_current_user() -> User | None:
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
        if user.role not in {"admin", "leader", "supervisor"}:
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
        if user.role not in {"manager", "admin", "supervisor", "leader"}:
            flash("Bạn không có quyền truy cập trang này.", "danger")
            return redirect(url_for("checklist.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


@auth_bp.before_app_request
def load_logged_in_user() -> None:
    g.current_user = get_current_user()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("checklist.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            or_(User.username == username, User.employee_code == username),
            User.is_active.is_(True),
        ).first()
        if not user or not user.check_password(password):
            flash("Sai tên đăng nhập hoặc mật khẩu.", "danger")
            return render_template("login.html", username=username)

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role
        session["lang"] = session.get("lang", "vi")

        flash("Đăng nhập thành công.", "success")
        return redirect(url_for("checklist.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    lang = session.get("lang", "vi")
    session.clear()
    session["lang"] = lang
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))


def _profile_month_options(today):
    from datetime import date

    options = []
    year, month = today.year, today.month
    for _ in range(24):
        options.append({"value": f"{year:04d}-{month:02d}", "label": f"{month:02d}/{year}"})
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    return options


def build_excel_month_context(user, year: int, month: int, line_name: str | None = None, sheet_kind: str | None = None, target_sv_id: int | None = None):
    from calendar import monthrange
    from datetime import date

    from models import (
        ABNORMAL_STATUS_CANCELLED,
        ChecklistItem,
        ChecklistTemplate,
        DailyCheckSheet,
        RESULT_ABNORMAL,
        RESULT_NG,
        RESULT_OK,
    )

    days_in_month = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    # ── Xác định user thực sự cần xem file ──────────────────────────────────
    # Manager chọn SV cụ thể → xem file của SV đó (giống như SV tự xem)
    view_as_user = user
    if user.role == "manager" and target_sv_id:
        sv = User.query.get(target_sv_id)
        if sv and sv.role == "supervisor" and sv.manager_id == user.id:
            view_as_user = sv
    elif user.role == "admin" and target_sv_id:
        sv = User.query.get(target_sv_id)
        if sv and sv.role == "supervisor":
            view_as_user = sv

    selected_line_name = (line_name or "").strip() or None
    line_names_filter: set[str] | None = None

    # sheet_kind chỉ áp dụng cho supervisor (hoặc manager xem file SV)
    effective_role = view_as_user.role
    if effective_role == "supervisor":
        if sheet_kind == "tl_admin":
            line_names_filter = {"Ca hanh chinh"}
            selected_line_name = None
        elif sheet_kind == "tl_shift":
            line_names_filter = {"Ca 1", "Ca 2", "Ca 3"}
            selected_line_name = None
        elif sheet_kind == "sv":
            line_names_filter = None
            selected_line_name = None

    if selected_line_name:
        accessible_lines = {row.line_name for row in Line.query.filter_by(is_active=True).all()}
        if effective_role not in {"admin", "manager", "supervisor", "leader"} and selected_line_name != view_as_user.line_name:
            selected_line_name = view_as_user.line_name
        elif selected_line_name not in accessible_lines:
            selected_line_name = view_as_user.line_name

    month_sheets = (
        DailyCheckSheet.query.filter(
            DailyCheckSheet.check_date >= month_start,
            DailyCheckSheet.check_date <= month_end,
        )
        .order_by(DailyCheckSheet.check_date.asc(), DailyCheckSheet.id.asc())
        .all()
    )

    # Lọc sheets theo role của view_as_user
    if effective_role == "leader":
        month_sheets = [
            sheet for sheet in month_sheets
            if sheet.user and sheet.user.role == "staff" and sheet.user.leader_id == view_as_user.id
        ]
    elif effective_role == "supervisor":
        if sheet_kind == "sv":
            # File SV: chỉ lấy sheets của chính SV
            month_sheets = [sheet for sheet in month_sheets if sheet.user_id == view_as_user.id]
        else:
            # File TL: lấy sheets của các leader dưới SV
            month_sheets = [
                sheet for sheet in month_sheets
                if sheet.user and sheet.user.role == "leader" and sheet.user.supervisor_id == view_as_user.id
            ]
    elif effective_role == "manager":
        month_sheets = [
            sheet for sheet in month_sheets
            if sheet.user and sheet.user.role == "supervisor" and sheet.user.manager_id == view_as_user.id
        ]
    elif effective_role not in {"admin"}:
        month_sheets = [sheet for sheet in month_sheets if sheet.user_id == view_as_user.id]

    if selected_line_name:
        month_sheets = [sheet for sheet in month_sheets if sheet.line_name == selected_line_name]
    if line_names_filter:
        month_sheets = [sheet for sheet in month_sheets if sheet.line_name in line_names_filter]

    latest_month_sheet = month_sheets[-1] if month_sheets else None
    if latest_month_sheet:
        latest_sheet = latest_month_sheet
    elif selected_line_name and effective_role == "leader":
        latest_sheet = (
            DailyCheckSheet.query.join(User)
            .filter(
                DailyCheckSheet.line_name == selected_line_name,
                DailyCheckSheet.check_date >= month_start,
                DailyCheckSheet.check_date <= month_end,
                User.role == "staff",
                User.leader_id == view_as_user.id,
            )
            .order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc())
            .first()
        )
    elif selected_line_name and effective_role in {"admin", "manager", "supervisor"}:
        latest_sheet = (
            DailyCheckSheet.query.filter_by(line_name=selected_line_name)
            .order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc())
            .first()
        )
    elif effective_role == "supervisor" and sheet_kind == "sv":
        latest_sheet = (
            DailyCheckSheet.query.filter_by(user_id=view_as_user.id)
            .order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc())
            .first()
        )
    elif effective_role == "supervisor":
        latest_query = (
            DailyCheckSheet.query.join(User)
            .filter(
                DailyCheckSheet.check_date >= month_start,
                DailyCheckSheet.check_date <= month_end,
                User.role == "leader",
                User.supervisor_id == view_as_user.id,
            )
        )
        if line_names_filter:
            latest_query = latest_query.filter(DailyCheckSheet.line_name.in_(line_names_filter))
        latest_sheet = latest_query.order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc()).first()
    elif effective_role == "leader":
        latest_sheet = (
            DailyCheckSheet.query.join(User)
            .filter(
                DailyCheckSheet.check_date >= month_start,
                DailyCheckSheet.check_date <= month_end,
                User.role == "staff",
                User.leader_id == view_as_user.id,
            )
            .order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc())
            .first()
        )
    else:
        latest_sheet = (
            DailyCheckSheet.query.filter_by(user_id=view_as_user.id)
            .order_by(DailyCheckSheet.check_date.desc(), DailyCheckSheet.id.desc())
            .first()
        )
    month_user_names = []
    month_user_codes = []
    seen_user_ids = set()
    for sheet in month_sheets:
        if sheet.user_id in seen_user_ids or not sheet.user:
            continue
        seen_user_ids.add(sheet.user_id)
        month_user_names.append(sheet.user.full_name)
        month_user_codes.append(sheet.user.employee_code)
    if not latest_sheet:
        template_code = "SV_DSV_VN" if sheet_kind == "sv" else "TL_SL_VN"
        template = ChecklistTemplate.query.filter_by(template_code=template_code, is_active=True).first()
        empty_groups: list[dict] = []
        if template:
            item_query = ChecklistItem.query.filter_by(template_id=template.id, is_active=True)
            if selected_line_name:
                item_query = item_query.filter(ChecklistItem.line.has(line_name=selected_line_name))
            elif line_names_filter:
                item_query = item_query.filter(ChecklistItem.line.has(Line.line_name.in_(line_names_filter)))
            items = item_query.order_by(ChecklistItem.check_time.asc(), ChecklistItem.item_order.asc()).all()
            items = sorted(
                items,
                key=lambda item: (
                    (item.check_time.hour if item.check_time else 0)
                    + (
                        24
                        if item.line
                        and item.line.line_name in {"Line D", "Ca 3"}
                        and item.check_time
                        and item.check_time.hour < 6
                        else 0
                    ),
                    item.check_time.minute if item.check_time else 0,
                    item.item_order or 0,
                    item.id,
                ),
            )
            group_index: dict[str, int] = {}
            for item in items:
                group_key = item.time_group or (item.check_time.strftime("%H:%M") if item.check_time else "Khác")
                row = {
                    "item_id": item.id,
                    "symbol": item.symbol,
                    "category_type": item.category_type or item.symbol,
                    "content": item.content_vi or item.content,
                    "days": {day: "" for day in range(1, days_in_month + 1)},
                    "result_ids": {day: None for day in range(1, days_in_month + 1)},
                }
                if group_key not in group_index:
                    group_index[group_key] = len(empty_groups)
                    empty_groups.append({"time_group": group_key, "rows": [row]})
                else:
                    empty_groups[group_index[group_key]]["rows"].append(row)
        return {
            "days_in_month": days_in_month,
            "excel_groups": empty_groups,
            "excel_abnormal_reports": [],
            "signature_rows": [],
            "excel_year": year,
            "excel_month": month,
            "latest_sheet_id": None,
            "sheet_id_by_day": {},
            "status_by_day": {},
            "line_name": selected_line_name or getattr(user, "line_name", None),
            "month_user_names": month_user_names,
            "month_user_codes": month_user_codes,
            "sheet_kind": sheet_kind,
        }

    active_line_name = selected_line_name or latest_sheet.line_name or getattr(view_as_user, "line_name", None)
    if line_names_filter or sheet_kind == "sv":
        active_line_name = None
    if active_line_name:
        month_sheets = [sheet for sheet in month_sheets if sheet.line_name == active_line_name]

    item_query = ChecklistItem.query.filter_by(
        template_id=latest_sheet.template_id,
        is_active=True,
    )
    if active_line_name:
        item_query = item_query.filter(ChecklistItem.line.has(line_name=active_line_name))
    elif line_names_filter:
        item_query = item_query.filter(ChecklistItem.line.has(Line.line_name.in_(line_names_filter)))

    items = item_query.order_by(ChecklistItem.check_time.asc(), ChecklistItem.item_order.asc()).all()
    items = sorted(
        items,
        key=lambda item: (
            (item.check_time.hour if item.check_time else 0)
            + (
                24
                if active_line_name in {"Line D", "Ca 3"}
                and item.check_time
                and item.check_time.hour < 6
                else 0
            ),
            item.check_time.minute if item.check_time else 0,
            item.item_order or 0,
            item.id,
        ),
    )

    result_by_item_day: dict[tuple[int, int], str] = {}
    result_id_by_item_day: dict[tuple[int, int], int] = {}
    sheet_id_by_day: dict[int, int] = {}
    status_by_day: dict[int, str] = {}
    for sheet in month_sheets:
        day = sheet.check_date.day
        status_by_day[day] = sheet.status
        sheet_id_by_day[day] = sheet.id
        for result in sheet.results:
            val = (result.result or "").strip()
            result_by_item_day[(result.checklist_item_id, day)] = val
            result_id_by_item_day[(result.checklist_item_id, day)] = result.id

    excel_groups: list[dict] = []

    # Gộp các time_group có cùng tập hạng mục thành 1 nhóm hiển thị
    # (VD: 06:00, 08:20, 14:00, 22:00 đều có cùng M/Q/Q/Q → 1 nhóm)

    # Bước 1: nhóm items theo time_group, giữ thứ tự xuất hiện
    tg_to_items: dict[str, list] = {}
    tg_order: list[str] = []
    for item in items:
        tg = item.time_group or (item.check_time.strftime("%H:%M") if item.check_time else "Khác")
        if tg not in tg_to_items:
            tg_to_items[tg] = []
            tg_order.append(tg)
        tg_to_items[tg].append(item)

    # Bước 2: tạo content_key cho mỗi time_group (dùng full content)
    def make_ck(tg_items):
        return tuple((i.symbol or "", (i.content_vi or i.content or "").strip()) for i in tg_items)

    # Build toàn bộ ck_to_tgs trước
    ck_to_tgs: dict[tuple, list[str]] = {}
    ck_to_items: dict[tuple, list] = {}
    for tg in tg_order:
        tg_items = tg_to_items[tg]
        ck = make_ck(tg_items)
        if ck not in ck_to_tgs:
            ck_to_tgs[ck] = []
            ck_to_items[ck] = tg_items
        ck_to_tgs[ck].append(tg)

    # Bước 3: xây dựng excel_groups theo thứ tự xuất hiện đầu tiên của mỗi ck
    def fmt_time(t):
        try:
            h, m = t.split(":")
            return f"{int(h)}:{m}"
        except Exception:
            return t

    processed_cks: set[tuple] = set()
    for tg in tg_order:
        tg_items = tg_to_items[tg]
        ck = make_ck(tg_items)
        if ck in processed_cks:
            continue
        processed_cks.add(ck)

        times_list = ck_to_tgs[ck]

        # Sắp xếp giờ theo thứ tự hợp lý (xử lý ca đêm: 22, 23, 0, 1...)
        def sort_key_time(t):
            try:
                h, m = t.split(":")
                h = int(h)
                # Ca đêm: giờ < 6 → cộng 24 để sort sau giờ chiều
                return h + 24 if h < 6 else h
            except Exception:
                return 99
        times_sorted = sorted(times_list, key=sort_key_time)

        # Nhãn thời gian gộp: "6:00\n(8:20)\n(14:00)\n(22:00)"
        if len(times_sorted) > 1:
            time_label = fmt_time(times_sorted[0]) + "".join(f"\n({fmt_time(t)})" for t in times_sorted[1:])
        else:
            time_label = fmt_time(times_sorted[0])

        group_rows = []
        for idx, gi in enumerate(ck_to_items[ck]):
            merged_days = {}
            merged_result_ids = {}
            for day in range(1, days_in_month + 1):
                val = ""
                rid = None
                for tg2 in times_list:
                    tg2_items = tg_to_items.get(tg2, [])
                    if idx < len(tg2_items):
                        match_item = tg2_items[idx]
                        v = result_by_item_day.get((match_item.id, day), "")
                        r = result_id_by_item_day.get((match_item.id, day))
                        if v:
                            val = v
                            rid = r
                        elif r and not rid:
                            rid = r
                merged_days[day] = val
                merged_result_ids[day] = rid

            group_rows.append({
                "item_id": gi.id,
                "symbol": gi.symbol,
                "category_type": gi.category_type or gi.symbol,
                "content": gi.content_vi or gi.content,
                "days": merged_days,
                "result_ids": merged_result_ids,
            })

        excel_groups.append({"time_group": time_label, "rows": group_rows})

    abnormal_reports = []
    for sheet in month_sheets:
        for report in sheet.abnormal_reports:
            if report.status == ABNORMAL_STATUS_CANCELLED:
                continue
            if report.daily_check_result.result not in {RESULT_NG, RESULT_ABNORMAL}:
                continue
            abnormal_reports.append(report)
    abnormal_reports.sort(key=lambda r: (r.occurred_date, r.id), reverse=True)

    weekly_days = [1, 8, 15, 22, 29][: ((days_in_month - 1) // 7) + 1]
    weekly_day_set = set(weekly_days)

    signature_rows = [
        {
            "label": "SL/TL (1/D)",
            "days": {day: ("o" if status_by_day.get(day) in {"submitted", "confirmed"} else "") for day in range(1, days_in_month + 1)},
        },
        {
            "label": "TL (1/D)",
            "days": {day: ("o" if status_by_day.get(day) == "confirmed" else "") for day in range(1, days_in_month + 1)},
        },
        {
            "label": "SV (1/W)",
            "days": {day: ("o" if status_by_day.get(day) == "confirmed" and day in weekly_day_set else "") for day in range(1, days_in_month + 1)},
        },
    ]

    return {
        "days_in_month": days_in_month,
        "excel_groups": excel_groups,
        "excel_abnormal_reports": abnormal_reports,
        "signature_rows": signature_rows,
        "excel_year": year,
        "excel_month": month,
        "latest_sheet_id": latest_sheet.id,
        "sheet_id_by_day": sheet_id_by_day,
        "status_by_day": status_by_day,
        "line_name": active_line_name,
        "month_user_names": month_user_names,
        "month_user_codes": month_user_codes,
        "sheet_kind": sheet_kind,
        "view_as_user": view_as_user,
        "is_viewing_other": view_as_user.id != user.id,
    }


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    from datetime import date, timedelta
    from models import (
        DailyCheckSheet, DailyCheckResult, ChecklistItem,
        RESULT_OK, RESULT_NG, RESULT_ABNORMAL, RESULT_EMPTY, db,
        AbnormalReport, ABNORMAL_STATUS_CANCELLED,
    )

    user = get_current_user()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        outlook_email = request.form.get("outlook_email", "").strip()
        gender = request.form.get("gender", "").strip()
        department = request.form.get("department", "").strip()
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not department:
            flash("Vui lòng nhập đầy đủ họ tên và bộ phận.", "danger")
        elif gender and gender not in {"male", "female", "other"}:
            flash("Giới tính không hợp lệ.", "danger")
        elif new_password and not user.check_password(old_password):
            flash("Mật khẩu cũ không chính xác.", "danger")
        elif new_password and new_password != confirm_password:
            flash("Mật khẩu mới không khớp.", "danger")
        else:
            user.full_name = full_name
            user.outlook_email = outlook_email or None
            user.gender = gender or None
            user.department = department
            if new_password:
                user.set_password(new_password)
            db.session.commit()
            flash("Cập nhật thông tin thành công.", "success")
            return redirect(url_for("auth.profile"))
        return redirect(url_for("auth.profile", _anchor="pw-error", show_pw=1))

    # ── Bộ lọc ngày ──────────────────────────────────────────────────────────
    today = date.today()
    raw_start = request.args.get("date_from", "")
    raw_end = request.args.get("date_to", "")

    try:
        from datetime import datetime as _dt
        date_from = _dt.strptime(raw_start, "%Y-%m-%d").date() if raw_start else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)

    try:
        from datetime import datetime as _dt
        date_to = _dt.strptime(raw_end, "%Y-%m-%d").date() if raw_end else today
    except ValueError:
        date_to = today

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    view_mode = request.args.get("view", "excel")
    if view_mode not in {"report", "daily", "excel"}:
        view_mode = "excel"

    raw_excel_month = request.args.get("excel_month", "").strip()
    raw_excel_line = request.args.get("excel_line", "").strip()
    raw_excel_sheet = request.args.get("excel_sheet", "").strip()
    raw_excel_sv_id = request.args.get("excel_sv_id", type=int)

    if raw_excel_sheet not in {"tl_admin", "tl_shift", "sv"}:
        raw_excel_sheet = "sv" if user.role in {"supervisor", "manager"} else ""

    excel_year = today.year
    excel_month_num = today.month
    if raw_excel_month:
        try:
            from datetime import datetime as _dt
            parsed = _dt.strptime(raw_excel_month, "%Y-%m")
            excel_year, excel_month_num = parsed.year, parsed.month
        except ValueError:
            pass
    if not raw_excel_month:
        raw_excel_month = f"{excel_year:04d}-{excel_month_num:02d}"
        view_mode = "excel"

    month_options = _profile_month_options(today)
    excel_line_options = []
    sv_options = []  # Danh sách SV cho manager chọn

    if user.role == "manager":
        # Manager: lấy danh sách SV dưới quyền
        sv_options = (
            User.query.filter_by(role="supervisor", manager_id=user.id, is_active=True)
            .order_by(User.full_name.asc())
            .all()
        )
        # Mặc định chọn SV đầu tiên nếu chưa chọn
        if not raw_excel_sv_id and sv_options:
            raw_excel_sv_id = sv_options[0].id
        # Lấy line options của SV được chọn
        if raw_excel_sv_id:
            sv_user = User.query.get(raw_excel_sv_id)
            if sv_user and sv_user.role == "supervisor" and sv_user.manager_id == user.id:
                excel_line_options = (
                    Line.query.filter_by(is_active=True)
                    .order_by(Line.line_name.asc())
                    .all()
                )
    elif user.role in {"admin", "supervisor", "leader"}:
        excel_line_options = (
            Line.query.filter_by(is_active=True)
            .order_by(Line.line_name.asc())
            .all()
        )
        if user.role == "supervisor" and raw_excel_sheet in {"tl_shift", "sv"}:
            raw_excel_line = ""
        elif not raw_excel_line:
            raw_excel_line = user.line_name if user.line_name else (excel_line_options[0].line_name if excel_line_options else "")
    elif user.line_name:
        raw_excel_line = user.line_name

    excel_context = build_excel_month_context(
        user,
        excel_year,
        excel_month_num,
        raw_excel_line or None,
        raw_excel_sheet or None,
        target_sv_id=raw_excel_sv_id,
    )

    # ── Lấy tất cả hạng mục (category_type) của user ─────────────────────────
    # Lấy các category_type duy nhất từ checklist items
    all_category_types = (
        db.session.query(ChecklistItem.category_type)
        .filter(ChecklistItem.is_active.is_(True))
        .distinct()
        .order_by(ChecklistItem.category_type.asc())
        .all()
    )
    all_category_types = [row[0] for row in all_category_types if row[0]]

    # ── Xây dựng báo cáo theo ngày trong khoảng lọc ──────────────────────────
    sheets = (
        DailyCheckSheet.query.filter(
            DailyCheckSheet.user_id == user.id,
            DailyCheckSheet.check_date >= date_from,
            DailyCheckSheet.check_date <= date_to,
        )
        .order_by(DailyCheckSheet.check_date.desc())
        .all()
    )

    sheet_by_date = {s.check_date: s for s in sheets}

    report_rows = []
    curr = date_to
    while curr >= date_from:
        s = sheet_by_date.get(curr)
        row = {"date": curr, "sheet": s, "status": None, "by_category": {}, "total_ok": 0, "total_ng": 0, "total_abn": 0, "total_empty": 0, "ng_count": 0, "fixed_count": 0, "rate": None}

        if s:
            row["status"] = s.status
            total = len(s.results)
            ok = ng = abn = empty = 0
            cat_results = {}  # category_type -> list of results

            for r in s.results:
                cat = r.checklist_item.category_type if r.checklist_item else None
                if cat not in cat_results:
                    cat_results[cat] = []
                cat_results[cat].append(r.result)

                if r.result == RESULT_OK:
                    ok += 1
                elif r.result == RESULT_NG:
                    ng += 1
                elif r.result == RESULT_ABNORMAL:
                    abn += 1
                else:
                    empty += 1

            row["total_ok"] = ok
            row["total_ng"] = ng
            row["total_abn"] = abn
            row["total_empty"] = empty

            # Tính kết quả tổng hợp theo category_type
            # o = tất cả đạt, x = có lỗi, △ = có bất thường, - = chưa điền
            for cat, results_list in cat_results.items():
                if any(r == RESULT_NG for r in results_list):
                    cat_val = "x"
                elif any(r == RESULT_ABNORMAL for r in results_list):
                    cat_val = "△"
                elif all(r == RESULT_OK for r in results_list):
                    cat_val = "o"
                else:
                    cat_val = "-"
                row["by_category"][cat] = cat_val

            # NG phát sinh và đã xử lý
            ng_reports = [
                rpt for rpt in s.abnormal_reports
                if rpt.status != ABNORMAL_STATUS_CANCELLED
            ]
            row["ng_count"] = len(ng_reports)
            row["fixed_count"] = sum(1 for rpt in ng_reports if rpt.status in {"fixed", "confirmed"})

            # Tỷ lệ đạt
            if total > 0:
                row["rate"] = round((ok / total) * 100)
        else:
            row["status"] = None

        report_rows.append(row)
        curr -= timedelta(days=1)

    # ── Báo cáo tổng hợp theo tuần (cho bảng tháng/tuần kiểu ảnh) ────────────
    # Nhóm theo tuần trong khoảng lọc
    weekly_summary = {}
    for row in report_rows:
        if not row["sheet"]:
            continue
        s = row["sheet"]
        week_start = row["date"] - timedelta(days=row["date"].weekday())
        week_key = week_start.isoformat()
        if week_key not in weekly_summary:
            week_num = (week_start.day - 1) // 7 + 1
            weekly_summary[week_key] = {
                "week_start": week_start,
                "week_label": f"W{week_num}",
                "month": week_start.month,
                "by_category": {},
                "ng_count": 0,
                "fixed_count": 0,
                "total_ok": 0,
                "total_all": 0,
            }
        wk = weekly_summary[week_key]
        wk["ng_count"] += row["ng_count"]
        wk["fixed_count"] += row["fixed_count"]
        wk["total_ok"] += row["total_ok"]
        wk["total_all"] += row["total_ok"] + row["total_ng"] + row["total_abn"] + row["total_empty"]

        for cat, val in row["by_category"].items():
            prev = wk["by_category"].get(cat, "o")
            if val == "x" or prev == "x":
                wk["by_category"][cat] = "x"
            elif val == "△" or prev == "△":
                wk["by_category"][cat] = "△"
            elif val == "o":
                wk["by_category"][cat] = "o"
            else:
                wk["by_category"][cat] = prev

    weekly_rows = sorted(weekly_summary.values(), key=lambda x: x["week_start"], reverse=True)
    for wk in weekly_rows:
        if wk["total_all"] > 0:
            wk["rate"] = round((wk["total_ok"] / wk["total_all"]) * 100)
        else:
            wk["rate"] = None

    weekly_total = {
        "month_label": "Tổng",
        "week_label": "",
        "by_category": {},
        "category_counts": {},
        "ng_count": 0,
        "fixed_count": 0,
        "total_ok": 0,
        "total_all": 0,
        "rate": None,
    }
    if weekly_rows:
        category_values: dict[str, list[str]] = {cat: [] for cat in all_category_types}
        for wk in weekly_rows:
            weekly_total["ng_count"] += wk["ng_count"]
            weekly_total["fixed_count"] += wk["fixed_count"]
            weekly_total["total_ok"] += wk["total_ok"]
            weekly_total["total_all"] += wk["total_all"]
            for cat in all_category_types:
                val = wk["by_category"].get(cat, "-")
                if val != "-":
                    category_values[cat].append(val)
                    weekly_total["category_counts"][cat] = weekly_total["category_counts"].get(cat, 0) + 1

        for cat, vals in category_values.items():
            if any(v == "x" for v in vals):
                weekly_total["by_category"][cat] = "x"
            elif any(v == "△" for v in vals):
                weekly_total["by_category"][cat] = "△"
            elif any(v == "o" for v in vals):
                weekly_total["by_category"][cat] = "o"
            else:
                weekly_total["by_category"][cat] = "-"

        if weekly_total["total_all"] > 0:
            weekly_total["rate"] = round((weekly_total["total_ok"] / weekly_total["total_all"]) * 100)

    # Tên tháng viết tắt
    MONTH_ABBR = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    for wk in weekly_rows:
        wk["month_label"] = MONTH_ABBR.get(wk["month"], str(wk["month"]))

    show_pw_modal = request.args.get("show_pw") == "1"

    return render_template(
        "profile.html",
        user=user,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        report_rows=report_rows,
        weekly_rows=weekly_rows,
        weekly_total=weekly_total,
        all_category_types=all_category_types,
        show_pw_modal=show_pw_modal,
        view_mode=view_mode,
        excel_month=raw_excel_month or f"{excel_year:04d}-{excel_month_num:02d}",
        month_options=month_options,
        excel_context=excel_context,
        excel_line=raw_excel_line,
        excel_sheet=raw_excel_sheet,
        excel_line_options=excel_line_options,
        sv_options=sv_options,
        excel_sv_id=raw_excel_sv_id,
    )


@auth_bp.route("/profile/print")
@login_required
def print_profile_report():
    from datetime import date, timedelta
    from models import (
        DailyCheckSheet, ChecklistItem,
        RESULT_OK, RESULT_NG, RESULT_ABNORMAL, db,
        AbnormalReport, ABNORMAL_STATUS_CANCELLED,
    )

    user = get_current_user()
    today = date.today()

    try:
        from datetime import datetime as _dt
        raw_start = request.args.get("date_from", "")
        date_from = _dt.strptime(raw_start, "%Y-%m-%d").date() if raw_start else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)

    try:
        from datetime import datetime as _dt
        raw_end = request.args.get("date_to", "")
        date_to = _dt.strptime(raw_end, "%Y-%m-%d").date() if raw_end else today
    except ValueError:
        date_to = today

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    view = request.args.get("view", "report")

    all_category_types = (
        db.session.query(ChecklistItem.category_type)
        .filter(ChecklistItem.is_active.is_(True))
        .distinct()
        .order_by(ChecklistItem.category_type.asc())
        .all()
    )
    all_category_types = [row[0] for row in all_category_types if row[0]]

    sheets = (
        DailyCheckSheet.query.filter(
            DailyCheckSheet.user_id == user.id,
            DailyCheckSheet.check_date >= date_from,
            DailyCheckSheet.check_date <= date_to,
        )
        .order_by(DailyCheckSheet.check_date.desc())
        .all()
    )

    sheet_by_date = {s.check_date: s for s in sheets}
    report_rows = []
    curr = date_to
    while curr >= date_from:
        s = sheet_by_date.get(curr)
        row = {"date": curr, "sheet": s, "by_category": {}, "total_ok": 0, "total_ng": 0, "total_abn": 0, "total_empty": 0, "ng_count": 0, "fixed_count": 0, "rate": None}
        if s:
            total = len(s.results)
            ok = ng = abn = empty = 0
            cat_results = {}
            for r in s.results:
                cat = r.checklist_item.category_type if r.checklist_item else None
                if cat not in cat_results:
                    cat_results[cat] = []
                cat_results[cat].append(r.result)
                if r.result == RESULT_OK: ok += 1
                elif r.result == RESULT_NG: ng += 1
                elif r.result == RESULT_ABNORMAL: abn += 1
                else: empty += 1
            row.update({"total_ok": ok, "total_ng": ng, "total_abn": abn, "total_empty": empty})
            for cat, rl in cat_results.items():
                if any(r == RESULT_NG for r in rl): row["by_category"][cat] = "x"
                elif any(r == RESULT_ABNORMAL for r in rl): row["by_category"][cat] = "△"
                elif all(r == RESULT_OK for r in rl): row["by_category"][cat] = "o"
                else: row["by_category"][cat] = "-"
            ng_reports = [rpt for rpt in s.abnormal_reports if rpt.status != ABNORMAL_STATUS_CANCELLED]
            row["ng_count"] = len(ng_reports)
            row["fixed_count"] = sum(1 for rpt in ng_reports if rpt.status in {"fixed", "confirmed"})
            if total > 0:
                row["rate"] = round((ok / total) * 100)
        report_rows.append(row)
        curr -= timedelta(days=1)

    # Tổng hợp tuần
    weekly_summary = {}
    MONTH_ABBR = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    for row in report_rows:
        if not row["sheet"]: continue
        week_start = row["date"] - timedelta(days=row["date"].weekday())
        week_key = week_start.isoformat()
        if week_key not in weekly_summary:
            week_num = (week_start.day - 1) // 7 + 1
            weekly_summary[week_key] = {
                "week_start": week_start,
                "week_label": f"W{week_num}",
                "month": week_start.month,
                "month_label": MONTH_ABBR.get(week_start.month, str(week_start.month)),
                "by_category": {},
                "ng_count": 0, "fixed_count": 0, "total_ok": 0, "total_all": 0,
            }
        wk = weekly_summary[week_key]
        wk["ng_count"] += row["ng_count"]
        wk["fixed_count"] += row["fixed_count"]
        wk["total_ok"] += row["total_ok"]
        wk["total_all"] += row["total_ok"] + row["total_ng"] + row["total_abn"] + row["total_empty"]
        for cat, val in row["by_category"].items():
            prev = wk["by_category"].get(cat, "o")
            if val == "x" or prev == "x": wk["by_category"][cat] = "x"
            elif val == "△" or prev == "△": wk["by_category"][cat] = "△"
            elif val == "o": wk["by_category"][cat] = "o"
            else: wk["by_category"][cat] = prev

    weekly_rows = sorted(weekly_summary.values(), key=lambda x: x["week_start"], reverse=True)
    for wk in weekly_rows:
        wk["rate"] = round((wk["total_ok"] / wk["total_all"]) * 100) if wk["total_all"] > 0 else None

    return render_template(
        "print_profile_report.html",
        user=user,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        view=view,
        report_rows=report_rows,
        weekly_rows=weekly_rows,
        all_category_types=all_category_types,
    )


@auth_bp.route("/profile/print-month")
@login_required
def print_profile_month():
    from datetime import date
    from datetime import datetime as _dt

    user = get_current_user()
    today = date.today()
    raw_excel_month = request.args.get("excel_month", "").strip()
    raw_excel_line = request.args.get("excel_line", "").strip()
    raw_excel_sheet = request.args.get("excel_sheet", "").strip()
    raw_excel_sv_id = request.args.get("excel_sv_id", type=int)

    if raw_excel_sheet not in {"tl_admin", "tl_shift", "sv"}:
        raw_excel_sheet = "sv" if user.role in {"supervisor", "manager"} else ""

    excel_year = today.year
    excel_month_num = today.month
    if raw_excel_month:
        try:
            parsed = _dt.strptime(raw_excel_month, "%Y-%m")
            excel_year, excel_month_num = parsed.year, parsed.month
        except ValueError:
            pass

    excel_context = build_excel_month_context(
        user,
        excel_year,
        excel_month_num,
        raw_excel_line or None,
        raw_excel_sheet or None,
        target_sv_id=raw_excel_sv_id,
    )

    return render_template(
        "print_profile_month.html",
        user=user,
        excel_context=excel_context,
        auto_print=request.args.get("autoprint") == "1",
    )
