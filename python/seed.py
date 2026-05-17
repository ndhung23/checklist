from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import load_workbook

from app import create_app
from models import (
    ABNORMAL_STATUS_CONFIRMED,
    ABNORMAL_STATUS_OPEN,
    RESULT_ABNORMAL,
    RESULT_EMPTY,
    RESULT_NG,
    RESULT_OK,
    ROLE_ADMIN,
    ROLE_LEADER,
    ROLE_MANAGER,
    ROLE_STAFF,
    SHEET_STATUS_CHECKING,
    SHEET_STATUS_CONFIRMED,
    SHEET_STATUS_SUBMITTED,
    AbnormalReport,
    ChecklistItem,
    ChecklistTemplate,
    DailyCheckResult,
    DailyCheckSheet,
    DailyConfirmation,
    Line,
    User,
    UserLine,
    db,
)


DEFAULT_EXCEL_PATH = Path(r"c:\Users\zoxy4\Downloads\TL.SL.xlsx")
SPECIAL_TIME_GROUPS = {
    "Sau ăn giữa ca": time(11, 30),
    "Cuối ca": time(17, 30),
}
LINE_TIME_BY_NAME = {
    "Line A": [time(6, 0), time(7, 0), time(8, 0), time(9, 0), time(11, 0), time(12, 0), time(13, 0)],
    "Line B": [time(8, 20), time(9, 20), time(10, 0), time(11, 0), time(13, 0), time(15, 0), time(16, 0)],
    "Line C": [time(14, 0), time(15, 0), time(16, 0), time(17, 0), time(19, 0), time(20, 0), time(21, 0)],
    "Line D": [time(22, 0), time(23, 0), time(0, 0), time(1, 0), time(3, 0), time(4, 0), time(5, 0)],
}


def normalize_symbol(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    return str(raw_value).strip().replace("Ｃ", "C")


def make_user(
    password: str,
    full_name: str,
    employee_code: str,
    department: str,
    line_name: str,
    role: str,
    outlook_email: str,
    gender: str | None = None,
    manager: User | None = None,
    leader: User | None = None,
    user_id: int | None = None,
) -> User:
    user = User(
        id=user_id,
        username=employee_code,
        full_name=full_name,
        employee_code=employee_code,
        outlook_email=outlook_email,
        gender=gender,
        department=department,
        line_name=line_name,
        role=role,
        manager=manager,
        leader=leader,
        is_active=True,
    )
    user.set_password(password)
    return user


def normalize_template_code(sheet_name: str) -> str:
    if "VN" in sheet_name.upper():
        return "TL_SL_VN"
    if "JP" in sheet_name.upper():
        return "TL_SL_JP"
    return re.sub(r"[^A-Za-z0-9]+", "_", sheet_name).strip("_").upper() or "CHECKLIST_TEMPLATE"


def primary_time_from_group(group_label: str, previous_value: time | None) -> time:
    clean_label = (group_label or "").strip()
    if clean_label in SPECIAL_TIME_GROUPS:
        return SPECIAL_TIME_GROUPS[clean_label]

    match = re.search(r"(\d{1,2}):(\d{2})", clean_label)
    if not match:
        if previous_value:
            return (datetime.combine(date.today(), previous_value) + timedelta(minutes=1)).time()
        return time(0, 0)

    parsed = time(int(match.group(1)), int(match.group(2)))
    if previous_value and parsed <= previous_value and parsed.hour < 12:
        parsed = (datetime.combine(date.today(), parsed) + timedelta(hours=12)).time()
    return parsed


def parse_sheet_rows(ws) -> list[dict]:
    rows: list[dict] = []
    current_group = ""
    current_time: time | None = None
    item_order = 1

    for row_idx in range(10, ws.max_row + 1):
        group_value = ws.cell(row_idx, 2).value
        symbol_value = ws.cell(row_idx, 3).value
        content_value = ws.cell(row_idx, 4).value

        group_text = str(group_value).strip() if group_value else ""
        content_text = str(content_value).strip() if content_value else ""
        symbol_text = normalize_symbol(symbol_value)

        if group_text.startswith("Nội dung lỗi") or group_text.startswith("内容"):
            break
        if not content_text or not symbol_text:
            continue

        if group_text:
            current_group = group_text.splitlines()[0].strip()
            current_time = primary_time_from_group(current_group, current_time)

        rows.append(
            {
                "item_order": item_order,
                "symbol": symbol_text,
                "check_time": current_time or time(0, 0),
                "time_group": current_group or "Khac",
                "content": content_text.replace("\n", " ").strip(),
            }
        )
        item_order += 1
    return rows


def load_templates_from_excel(excel_path: Path) -> list[ChecklistTemplate]:
    workbook = load_workbook(excel_path, data_only=True)
    vn_sheet = next(ws for ws in workbook.worksheets if "VN" in ws.title.upper())
    jp_sheet = next(ws for ws in workbook.worksheets if "JP" in ws.title.upper())

    vn_rows = parse_sheet_rows(vn_sheet)
    jp_rows = parse_sheet_rows(jp_sheet)
    jp_map = {row["item_order"]: row for row in jp_rows}

    templates: list[ChecklistTemplate] = []
    for ws in workbook.worksheets:
        template = ChecklistTemplate(
            template_code=normalize_template_code(ws.title),
            template_name=str(ws["B2"].value or ws.title).strip(),
            description=f"Factory inspection template from sheet {ws.title}",
            version="Rev.25-02-06",
            is_active=True,
        )

        for vn_row in vn_rows:
            jp_row = jp_map.get(vn_row["item_order"], {})
            source_row = vn_row if "VN" in ws.title.upper() else jp_row or vn_row
            template.checklist_items.append(
                ChecklistItem(
                    symbol=source_row.get("symbol", vn_row["symbol"]),
                    check_time=vn_row["check_time"],
                    time_group=vn_row["time_group"],
                    item_order=vn_row["item_order"],
                    category_type=vn_row["symbol"],
                    content=vn_row["content"],
                    content_vi=vn_row["content"],
                    content_en=vn_row["content"],
                    content_ja=jp_row.get("content", vn_row["content"]),
                    note=None,
                    is_active=True,
                )
            )

        templates.append(template)
    return templates


def create_fallback_templates() -> list[ChecklistTemplate]:
    template = ChecklistTemplate(
        template_code="TL_SL_VN",
        template_name="TL/SL Daily Checklist",
        description="Fallback checklist template",
        version="1.0",
        is_active=True,
    )
    fallback_items = [
        ("C1", time(8, 0), "08:00", "Kiểm tra khu vực làm việc sạch sẽ trước ca."),
        ("C2", time(9, 0), "09:00", "Kiểm tra dụng cụ và thiết bị an toàn."),
        ("C3", time(10, 0), "10:00", "Kiểm tra tình trạng vận hành line."),
        ("C4", time(11, 30), "Sau ăn giữa ca", "Kiểm tra 5S sau giờ nghỉ giữa ca."),
        ("C5", time(14, 0), "14:00", "Kiểm tra chất lượng bán thành phẩm."),
        ("C6", time(17, 30), "Cuối ca", "Kiểm tra tổng vệ sinh và bàn giao cuối ca."),
    ]
    for index, (symbol, check_time, time_group, content) in enumerate(fallback_items, start=1):
        template.checklist_items.append(
            ChecklistItem(
                symbol=symbol,
                check_time=check_time,
                time_group=time_group,
                item_order=index,
                category_type=symbol,
                content=content,
                content_vi=content,
                content_en=content,
                content_ja=content,
                is_active=True,
            )
        )
    return [template]


def create_daily_sheet(user: User, template: ChecklistTemplate, target_date: date, status: str) -> DailyCheckSheet:
    return DailyCheckSheet(
        user=user,
        template=template,
        check_date=target_date,
        month=target_date.month,
        year=target_date.year,
        line_name=user.line_name,
        department=user.department,
        shift="day",
        status=status,
    )


def create_result(sheet: DailyCheckSheet, item: ChecklistItem, result: str, note: str | None = None) -> DailyCheckResult:
    checked_at = datetime.combine(sheet.check_date, item.check_time) if result else None
    return DailyCheckResult(
        daily_sheet=sheet,
        checklist_item=item,
        user=sheet.user,
        check_date=sheet.check_date,
        symbol=item.symbol,
        check_time=item.check_time,
        content=item.content_vi,
        result=result,
        abnormal_note=note,
        checked_at=checked_at,
    )


def create_abnormal_report(
    result: DailyCheckResult,
    abnormal_content: str,
    countermeasure: str,
    status: str,
    confirm_offset: int,
    result_after_fix: str,
) -> AbnormalReport:
    return AbnormalReport(
        daily_sheet=result.daily_sheet,
        daily_check_result=result,
        user=result.user,
        symbol=result.symbol,
        occurred_date=result.check_date,
        abnormal_content=abnormal_content,
        countermeasure=countermeasure,
        confirm_date_before_fix=result.check_date + timedelta(days=confirm_offset),
        result_after_fix=result_after_fix,
        status=status,
    )


def copy_template_items_to_lines(templates: list[ChecklistTemplate], lines: list[Line]) -> None:
    for template in templates:
        base_items = list(template.checklist_items)
        template.checklist_items.clear()
        for line in lines:
            for item in base_items:
                line_times = LINE_TIME_BY_NAME.get(line.line_name, [item.check_time])
                line_time = line_times[(item.item_order - 1) % len(line_times)]
                template.checklist_items.append(
                    ChecklistItem(
                        line=line,
                        symbol=item.symbol,
                        check_time=line_time,
                        time_group=line_time.strftime("%H:%M"),
                        item_order=item.item_order,
                        category_type=item.category_type,
                        content=item.content,
                        content_vi=item.content_vi,
                        content_en=item.content_en,
                        content_ja=item.content_ja,
                        note=item.note,
                        is_active=item.is_active,
                    )
                )


def seed_database(excel_path: Path = DEFAULT_EXCEL_PATH) -> None:
    db.drop_all()
    db.create_all()

    lines = [
        Line(line_name="Line A", department="TL/SL", description="Line A - TL/SL", is_active=True),
        Line(line_name="Line B", department="TL/SL", description="Line B - TL/SL", is_active=True),
        Line(line_name="Line C", department="Assembly", description="Line C - Assembly", is_active=True),
        Line(line_name="Line D", department="Inspection", description="Line D - Inspection", is_active=True),
    ]
    db.session.add_all(lines)

    admin = make_user("1", "System Admin", "admin", "Administration", "Line A", ROLE_ADMIN, "admin1@example.com", "other")
    manager = make_user("1", "Manager", "hv90124", "Management", "Line A", ROLE_MANAGER, "manager.nguyen.duy.au0@ap.denso1.com", "male")
    leader = make_user("1", "Vu Hoang Phuong", "hv10000", "TL/SL", "Line A", ROLE_LEADER, "phuong.vu.hoang.a7p@ap.denso1.com", "female", manager=manager)
    staff_1 = make_user("1", "Nguyen Duy Hung", "hv90122", "TL/SL", "Line A", ROLE_STAFF, "hung.nguyen.duy.a0u@ap.denso1.com", "male", manager=manager, leader=leader, user_id=4)
    staff_2 = make_user("1", "Vu Quang Anh", "hv90121", "TL/SL", "Line B", ROLE_STAFF, "anh.vu.quang.a6i@ap.denso1.com", "male", manager=manager, leader=leader)
    manager_test = make_user("1", "Test Manager", "manager_test", "Management", "Line A", ROLE_MANAGER, "manager_test@example.com", "male")
    leader_test = make_user("1", "Test Leader", "leader_test", "TL/SL", "Line A", ROLE_LEADER, "leader_test@example.com", "female", manager=manager_test)
    staff_test = make_user("1", "Test Staff", "staff_test", "TL/SL", "Line C", ROLE_STAFF, "staff_test@example.com", "male", manager=manager_test, leader=leader_test)

    users = {
        "admin": admin,
        "manager01": manager,
        "leader01": leader,
        "staff01": staff_1,
        "staff02": staff_2,
        "manager_test": manager_test,
        "leader_test": leader_test,
        "staff_test": staff_test,
    }
    db.session.add_all(users.values())
    db.session.flush()

    line_map = {line.line_name: line for line in lines}
    assignments = [
        ("manager01", "Line A"),
        ("manager01", "Line B"),
        ("leader01", "Line A"),
        ("leader01", "Line B"),
        ("staff01", "Line A"),
        ("staff02", "Line B"),
        ("manager_test", "Line A"),
        ("manager_test", "Line B"),
        ("manager_test", "Line C"),
        ("manager_test", "Line D"),
        ("leader_test", "Line A"),
        ("leader_test", "Line B"),
        ("leader_test", "Line C"),
        ("leader_test", "Line D"),
        ("staff_test", "Line C"),
    ]
    db.session.add_all(
        [
            UserLine(user_id=users[user_key].id, line_id=line_map[line_name].id)
            for user_key, line_name in assignments
        ]
    )

    templates = load_templates_from_excel(excel_path) if excel_path.exists() else create_fallback_templates()
    copy_template_items_to_lines(templates, lines)
    db.session.add_all(templates)
    db.session.flush()
    template_vn = next(template for template in templates if template.template_code == "TL_SL_VN")

    today = date.today()
    sheet_map = {
        "leader01": create_daily_sheet(users["leader01"], template_vn, today, SHEET_STATUS_SUBMITTED),
        "staff01": create_daily_sheet(users["staff01"], template_vn, today, SHEET_STATUS_CHECKING),
        "staff02": create_daily_sheet(users["staff02"], template_vn, today, SHEET_STATUS_CONFIRMED),
    }
    db.session.add_all(sheet_map.values())
    db.session.flush()

    abnormal_targets: list[DailyCheckResult] = []
    patterns = {
        "leader01": {"abnormal": set(), "ng": set(), "empty": set()},
        "staff01": {"abnormal": {9, 16}, "ng": {2, 10, 18, 27}, "empty": {31, 32, 33, 34, 35, 36}},
        "staff02": {"abnormal": {5, 22}, "ng": {7, 14}, "empty": set()},
    }

    for user_key, sheet in sheet_map.items():
        for item in template_vn.checklist_items:
            if item.item_order in patterns[user_key]["abnormal"]:
                result = create_result(sheet, item, RESULT_ABNORMAL, "Can xu ly va theo doi.")
                abnormal_targets.append(result)
            elif item.item_order in patterns[user_key]["ng"]:
                result = create_result(sheet, item, RESULT_NG, "Chua dat, can xu ly.")
                abnormal_targets.append(result)
            elif item.item_order in patterns[user_key]["empty"]:
                result = create_result(sheet, item, RESULT_EMPTY)
            else:
                result = create_result(sheet, item, RESULT_OK)
            db.session.add(result)

    db.session.flush()

    abnormal_reports = []
    for index, result in enumerate(abnormal_targets, start=1):
        abnormal_reports.append(
            create_abnormal_report(
                result=result,
                abnormal_content=result.content,
                countermeasure=f"Doi sach xu ly mau so {index}.",
                status=ABNORMAL_STATUS_OPEN if index % 2 else ABNORMAL_STATUS_CONFIRMED,
                confirm_offset=0 if index % 2 == 0 else 1,
                result_after_fix="Dang theo doi" if index % 2 else "Da xac nhan lai",
            )
        )
    db.session.add_all(abnormal_reports)

    confirmations = [
        DailyConfirmation(
            daily_sheet=sheet_map["leader01"],
            user=sheet_map["leader01"].user,
            signer=users["manager01"],
            confirmed_by_name=users["manager01"].full_name,
            confirmed_role=users["manager01"].role,
            confirmed_at=datetime.combine(today, time(17, 45)),
            signature_note="Manager da xem toan bo checklist line A va B.",
        ),
        DailyConfirmation(
            daily_sheet=sheet_map["staff02"],
            user=sheet_map["staff02"].user,
            signer=users["leader01"],
            confirmed_by_name=users["leader01"].full_name,
            confirmed_role=users["leader01"].role,
            confirmed_at=datetime.combine(today, time(17, 30)),
            signature_note="Leader da xac nhan trong ca.",
        ),
    ]
    db.session.add_all(confirmations)
    db.session.commit()


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        seed_database()
    print("Seed completed.")
    print("Accounts:")
    print("  admin / 1 / admin")
    print("  hv90124 / 1 / manager")
    print("  hv10000 / 1 / leader")
    print("  hv90122 / 1 / staff")
    print("  hv90121 / 1 / staff")
    print("  manager_test / 1 / manager")
    print("  leader_test / 1 / leader")
    print("  staff_test / 1 / staff")
