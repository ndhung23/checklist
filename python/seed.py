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


def normalize_symbol(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    return str(raw_value).strip().replace("Ｃ", "C")


def make_user(
    username: str,
    password: str,
    full_name: str,
    employee_code: str,
    department: str,
    line_name: str,
    role: str,
    outlook_email: str,
) -> User:
    user = User(
        username=username,
        full_name=full_name,
        employee_code=employee_code,
        outlook_email=outlook_email,
        department=department,
        line_name=line_name,
        role=role,
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


def seed_database(excel_path: Path = DEFAULT_EXCEL_PATH) -> None:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    db.drop_all()
    db.create_all()

    lines = [
        Line(line_name="Line A", department="TL/SL", description="Line A - TL/SL", is_active=True),
        Line(line_name="Line B", department="TL/SL", description="Line B - TL/SL", is_active=True),
        Line(line_name="Line C", department="Assembly", description="Line C - Assembly", is_active=True),
        Line(line_name="Line D", department="Inspection", description="Line D - Inspection", is_active=True),
    ]
    db.session.add_all(lines)

    users = {
        "admin": make_user("admin", "123456", "System Admin", "EMP001", "Administration", "Line A", ROLE_ADMIN, "admin@example.com"),
        "manager01": make_user("manager01", "123456", "Nguyen Van Manager", "EMP002", "Management", "Line A", ROLE_MANAGER, "manager01@example.com"),
        "leader01": make_user("leader01", "123456", "Tran Thi Leader 01", "EMP003", "TL/SL", "Line A", ROLE_LEADER, "leader01@example.com"),
        "leader02": make_user("leader02", "123456", "Tran Thi Leader 02", "EMP004", "Assembly", "Line C", ROLE_LEADER, "leader02@example.com"),
        "staff01": make_user("staff01", "123456", "Pham Van Staff 01", "EMP005", "TL/SL", "Line A", ROLE_STAFF, "staff01@example.com"),
        "staff02": make_user("staff02", "123456", "Le Thi Staff 02", "EMP006", "TL/SL", "Line B", ROLE_STAFF, "staff02@example.com"),
        "staff03": make_user("staff03", "123456", "Do Van Staff 03", "EMP007", "Assembly", "Line C", ROLE_STAFF, "staff03@example.com"),
        "staff04": make_user("staff04", "123456", "Vu Thi Staff 04", "EMP008", "Inspection", "Line D", ROLE_STAFF, "staff04@example.com"),
    }
    db.session.add_all(users.values())
    db.session.flush()

    line_map = {line.line_name: line for line in lines}
    assignments = [
        ("leader01", "Line A"),
        ("leader01", "Line B"),
        ("leader02", "Line C"),
        ("leader02", "Line D"),
        ("staff01", "Line A"),
        ("staff02", "Line B"),
        ("staff03", "Line C"),
        ("staff04", "Line D"),
    ]
    db.session.add_all(
        [
            UserLine(user_id=users[user_key].id, line_id=line_map[line_name].id)
            for user_key, line_name in assignments
        ]
    )

    templates = load_templates_from_excel(excel_path)
    db.session.add_all(templates)
    db.session.flush()
    template_vn = next(template for template in templates if template.template_code == "TL_SL_VN")

    today = date.today()
    sheet_map = {
        "leader01": create_daily_sheet(users["leader01"], template_vn, today, SHEET_STATUS_SUBMITTED),
        "leader02": create_daily_sheet(users["leader02"], template_vn, today, SHEET_STATUS_SUBMITTED),
        "staff01": create_daily_sheet(users["staff01"], template_vn, today, SHEET_STATUS_CHECKING),
        "staff02": create_daily_sheet(users["staff02"], template_vn, today, SHEET_STATUS_CONFIRMED),
        "staff03": create_daily_sheet(users["staff03"], template_vn, today, SHEET_STATUS_CHECKING),
        "staff04": create_daily_sheet(users["staff04"], template_vn, today, SHEET_STATUS_CHECKING),
    }
    db.session.add_all(sheet_map.values())
    db.session.flush()

    abnormal_targets: list[DailyCheckResult] = []
    patterns = {
        "leader01": {"abnormal": set(), "ng": set(), "empty": set()},
        "leader02": {"abnormal": {11}, "ng": set(), "empty": set()},
        "staff01": {"abnormal": {9, 16}, "ng": {2, 10, 18, 27}, "empty": {31, 32, 33, 34, 35, 36}},
        "staff02": {"abnormal": {5, 22}, "ng": {7, 14}, "empty": set()},
        "staff03": {"abnormal": {12}, "ng": {4, 15}, "empty": {34, 35}},
        "staff04": {"abnormal": {6, 24}, "ng": {8}, "empty": {30, 31, 32}},
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
    print("  admin / 123456 / admin")
    print("  manager01 / 123456 / manager")
    print("  leader01 / 123456 / leader")
    print("  leader02 / 123456 / leader")
    print("  staff01 / 123456 / staff")
    print("  staff02 / 123456 / staff")
    print("  staff03 / 123456 / staff")
    print("  staff04 / 123456 / staff")
