from __future__ import annotations

import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import quote

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import (
    ABNORMAL_STATUS_CANCELLED,
    ABNORMAL_STATUS_OPEN,
    AbnormalReport,
    ChecklistItem,
    DailyConfirmation,
    DailyCheckResult,
    DailyCheckSheet,
    Line,
    NOTIFICATION_READ,
    NOTIFICATION_UNREAD,
    Notification,
    RESULT_ABNORMAL,
    RESULT_EMPTY,
    RESULT_NG,
    RESULT_OK,
    SHEET_STATUS_CONFIRMED,
    SHEET_STATUS_SUBMITTED,
    VALID_ABNORMAL_STATUSES,
    User,
    UserLine,
    db,
)
from routes.auth_routes import login_required


checklist_bp = Blueprint("checklist", __name__)
SMTP_SERVER = "172.24.46.52"
SMTP_PORT = 25
SMTP_FROM = "daily-check@app.local"


def parse_date(raw_value: str | None, fallback: date | None = None) -> date:
    fallback = fallback or date.today()
    if not raw_value:
        return fallback
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def managed_line_names(user: User) -> set[str]:
    if user.role in {"admin", "manager", "leader"}:
        return {line.line_name for line in Line.query.filter_by(is_active=True).all()}
    return {mapping.line.line_name for mapping in user.user_lines}


def period_bounds(anchor_date: date, period_type: str) -> tuple[date, date]:
    if period_type == "week":
        start = anchor_date - timedelta(days=anchor_date.weekday())
        return start, start + timedelta(days=6)
    if period_type == "month":
        start = anchor_date.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        return start, next_month - timedelta(days=1)
    return anchor_date, anchor_date


def period_label(period_type: str) -> str:
    return {"day": "ngay", "week": "tuan", "month": "thang"}.get(period_type, period_type)


def submitted_statuses() -> set[str]:
    return {"submitted", "confirmed"}


def send_outlook_email(to_address: str, subject: str, body: str, cc_addresses: list[str] | None = None) -> tuple[bool, str]:
    if not to_address:
        return False, "Missing Outlook address."

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_address
    if cc_addresses:
        message["Cc"] = ", ".join([item for item in cc_addresses if item])
    message["Subject"] = subject
    message.set_content(body)

    recipients = [to_address] + (cc_addresses or [])
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(message, from_addr=SMTP_FROM, to_addrs=recipients)
        return True, "Email sent."
    except OSError as exc:
        return False, str(exc)


def build_outlook_body(sheet: DailyCheckSheet, results: list[DailyCheckResult]) -> str:
    done_count = sum(1 for result in results if result.result == RESULT_OK)
    ng_count = sum(1 for result in results if result.result == RESULT_NG)
    abnormal_count = sum(1 for result in results if result.result == RESULT_ABNORMAL)
    empty_count = sum(1 for result in results if not result.result)
    lines = [
        "[DAILY CHECKLIST SUBMISSION]",
        "",
        f"Staff: {sheet.user.full_name}",
        f"Code: {sheet.user.employee_code}",
        f"Line: {sheet.line_name}",
        f"Department: {sheet.department}",
        f"Date: {sheet.check_date.strftime('%d/%m/%Y')}",
        f"Status: {sheet.status}",
        "",
        "Summary:",
        f"- OK: {done_count}",
        f"- NG: {ng_count}",
        f"- Abnormal: {abnormal_count}",
        f"- Empty: {empty_count}",
        "",
        "Checklist details:",
    ]
    for index, result in enumerate(results, start=1):
        value = result.result or "empty"
        note = f" | Note: {result.abnormal_note}" if result.abnormal_note else ""
        actual_date = result_work_date(sheet.line_name, sheet.check_date, result.check_time)
        lines.append(
            f"{index}. {actual_date.strftime('%d/%m/%Y')} {result.check_time.strftime('%H:%M')} | "
            f"{result.symbol} | {value} | {result.content}{note}"
        )
    return "\n".join(lines)


def sheet_is_submitted(sheet: DailyCheckSheet) -> bool:
    return sheet.status in submitted_statuses()


def sheet_has_confirmation(sheet: DailyCheckSheet, roles: set[str]) -> bool:
    return any(item.confirmed_role in roles for item in sheet.confirmations)


def leader_users_for_line(line_name: str) -> list[User]:
    return (
        User.query.join(UserLine)
        .join(Line)
        .filter(
            User.role == "leader",
            User.is_active.is_(True),
            Line.line_name == line_name,
        )
        .order_by(User.full_name.asc())
        .all()
    )


def higher_level_users() -> list[User]:
    return (
        User.query.filter(User.role.in_(["manager", "admin"]), User.is_active.is_(True))
        .order_by(User.role.desc(), User.full_name.asc())
        .all()
    )


def upsert_notification(
    user: User,
    title: str,
    message: str,
    period_type: str,
    target_date: date,
    dedupe_key: str,
    related_sheet_id: int | None = None,
) -> None:
    notification = Notification.query.filter_by(user_id=user.id, dedupe_key=dedupe_key).first()
    if notification is None:
        db.session.add(
            Notification(
                user=user,
                title=title,
                message=message,
                period_type=period_type,
                target_date=target_date,
                related_sheet_id=related_sheet_id,
                dedupe_key=dedupe_key,
                status=NOTIFICATION_UNREAD,
            )
        )
        return

    notification.title = title
    notification.message = message
    notification.period_type = period_type
    notification.target_date = target_date
    notification.related_sheet_id = related_sheet_id


def upsert_email_reminder(
    user: User,
    title: str,
    message: str,
    period_type: str,
    target_date: date,
    dedupe_key: str,
    related_sheet_id: int | None = None,
) -> None:
    if Notification.query.filter_by(user_id=user.id, dedupe_key=dedupe_key).first():
        return

    db.session.add(
        Notification(
            user=user,
            title=title,
            message=message,
            category="email_reminder",
            period_type=period_type,
            target_date=target_date,
            related_sheet_id=related_sheet_id,
            dedupe_key=dedupe_key,
            status=NOTIFICATION_UNREAD,
        )
    )
    if user.outlook_email:
        send_outlook_email(user.outlook_email, title, message)


def resolve_notification(user: User, dedupe_key: str) -> None:
    notification = Notification.query.filter_by(
        user_id=user.id,
        dedupe_key=dedupe_key,
        status=NOTIFICATION_UNREAD,
    ).first()
    if notification:
        notification.status = NOTIFICATION_READ
        notification.read_at = datetime.now()


def period_label_vi(period_type: str) -> str:
    return {"day": "trong ngày", "week": "trong tuần", "month": "trong tháng"}.get(period_type, period_type)


def line_time_sort_key(line_name: str | None, check_time, fallback_id: int = 0) -> tuple[int, int, int]:
    hour = check_time.hour if check_time else 0
    minute = check_time.minute if check_time else 0
    if line_name == "Line D" and hour < 6:
        hour += 24
    return hour, minute, fallback_id


def result_work_date(line_name: str | None, sheet_date: date, check_time) -> date:
    if line_name == "Line D" and check_time and check_time.hour >= 22:
        return sheet_date - timedelta(days=1)
    return sheet_date


def result_work_datetime(line_name: str | None, sheet_date: date, check_time) -> datetime:
    return datetime.combine(result_work_date(line_name, sheet_date, check_time), check_time)


def build_reminders_for_user(current_user: User, anchor_date: date) -> None:
    template_id = get_template_id()

    if current_user.role == "staff":
        now = datetime.now()
        one_hour_later = now + timedelta(hours=1)
        today_sheet = DailyCheckSheet.query.filter_by(
            user_id=current_user.id,
            template_id=template_id,
            check_date=anchor_date,
        ).first()
        if today_sheet and anchor_date == date.today():
            due_results = [
                result
                for result in today_sheet.results
                if (not result.result)
                and now <= result_work_datetime(today_sheet.line_name, today_sheet.check_date, result.check_time) <= one_hour_later
            ]
            if due_results:
                first_due = sorted(
                    due_results,
                    key=lambda item: result_work_datetime(today_sheet.line_name, today_sheet.check_date, item.check_time),
                )[0]
                dedupe_key = f"email-staff-due:{current_user.id}:{anchor_date.isoformat()}:{first_due.check_time.strftime('%H%M')}"
                upsert_email_reminder(
                    current_user,
                    "Nhắc gửi checklist trong 1 tiếng tới",
                    f"Bạn còn {len(due_results)} hạng mục checklist cần hoàn thành trước {one_hour_later.strftime('%H:%M')} ngày {anchor_date.strftime('%d/%m/%Y')}.",
                    "day",
                    anchor_date,
                    dedupe_key,
                    today_sheet.id,
                )

        # Nhắc nhở nộp checklist theo ngày / tuần / tháng
        for period_type in ["day", "week", "month"]:
            start_date, end_date = period_bounds(anchor_date, period_type)
            sheets = (
                DailyCheckSheet.query.filter(
                    DailyCheckSheet.user_id == current_user.id,
                    DailyCheckSheet.template_id == template_id,
                    DailyCheckSheet.check_date >= start_date,
                    DailyCheckSheet.check_date <= end_date,
                )
                .order_by(DailyCheckSheet.check_date.asc())
                .all()
            )
            pending_sheets = [sheet for sheet in sheets if not sheet_is_submitted(sheet)]
            if period_type == "day" and not sheets:
                pending_sheets = []
            dedupe_key = f"staff-submit:{current_user.id}:{period_type}:{start_date.isoformat()}"
            if not pending_sheets:
                resolve_notification(current_user, dedupe_key)
            else:
                period_name = {"day": "ngày", "week": "tuần", "month": "tháng"}.get(period_type, period_type)
                title = f"Nhắc nhở: Nộp checklist {period_name}"
                message = (
                    f"Bạn còn {len(pending_sheets)} checklist chưa nộp "
                    f"từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}. "
                    f"Vui lòng hoàn thành và nộp cho tổ trưởng xác nhận."
                )
                upsert_notification(
                    current_user,
                    title,
                    message,
                    period_type,
                    anchor_date,
                    dedupe_key,
                    pending_sheets[0].id if pending_sheets else None,
                )

        # Thông báo checklist đã được leader xác nhận (trong ngày)
        confirmed_sheets = (
            DailyCheckSheet.query.filter(
                DailyCheckSheet.user_id == current_user.id,
                DailyCheckSheet.template_id == template_id,
                DailyCheckSheet.check_date == anchor_date,
                DailyCheckSheet.status == SHEET_STATUS_CONFIRMED,
            ).all()
        )
        for sheet in confirmed_sheets:
            leader_confirmations = [c for c in sheet.confirmations if c.confirmed_role == "leader"]
            if leader_confirmations:
                conf = leader_confirmations[-1]
                dedupe_key = f"staff-confirmed-by-leader:{current_user.id}:{sheet.id}"
                title = "✅ Checklist của bạn đã được tổ trưởng xác nhận"
                message = (
                    f"Checklist ngày {sheet.check_date.strftime('%d/%m/%Y')} của bạn "
                    f"đã được tổ trưởng {conf.confirmed_by_name} xác nhận lúc "
                    f"{conf.confirmed_at.strftime('%H:%M %d/%m/%Y')}."
                )
                upsert_notification(
                    current_user,
                    title,
                    message,
                    "day",
                    anchor_date,
                    dedupe_key,
                    sheet.id,
                )

        # Thông báo checklist tuần/tháng đã được manager xác nhận
        for period_type in ["week", "month"]:
            start_date, end_date = period_bounds(anchor_date, period_type)
            period_sheets = (
                DailyCheckSheet.query.filter(
                    DailyCheckSheet.user_id == current_user.id,
                    DailyCheckSheet.template_id == template_id,
                    DailyCheckSheet.check_date >= start_date,
                    DailyCheckSheet.check_date <= end_date,
                    DailyCheckSheet.status == SHEET_STATUS_CONFIRMED,
                ).all()
            )
            for sheet in period_sheets:
                manager_confirmations = [c for c in sheet.confirmations if c.confirmed_role in {"manager", "admin"}]
                if manager_confirmations:
                    conf = manager_confirmations[-1]
                    period_name = "tuần" if period_type == "week" else "tháng"
                    dedupe_key = f"staff-confirmed-by-manager:{current_user.id}:{period_type}:{sheet.id}"
                    title = f"✅ Checklist {period_name} của bạn đã được quản lý xác nhận"
                    message = (
                        f"Checklist {period_name} (từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}) "
                        f"đã được {conf.confirmed_by_name} xác nhận lúc {conf.confirmed_at.strftime('%H:%M %d/%m/%Y')}."
                    )
                    upsert_notification(
                        current_user,
                        title,
                        message,
                        period_type,
                        anchor_date,
                        dedupe_key,
                        sheet.id,
                    )

    if current_user.role == "leader":
        # Nhắc xác nhận checklist staff trong ngày
        sheets = (
            DailyCheckSheet.query.join(User)
            .filter(
                User.role == "staff",
                User.leader_id == current_user.id,
                DailyCheckSheet.check_date == anchor_date,
            )
            .all()
        )
        if anchor_date == date.today():
            now = datetime.now()
            for sheet in sheets:
                if sheet_is_submitted(sheet) or not sheet.results:
                    continue
                incomplete_count = sum(1 for result in sheet.results if not result.result)
                if not incomplete_count:
                    continue
                last_result = max(
                    sheet.results,
                    key=lambda result: line_time_sort_key(sheet.line_name, result.check_time, result.id),
                )
                final_dt = datetime.combine(anchor_date, last_result.check_time)
                if sheet.line_name == "Line D" and last_result.check_time.hour < 6:
                    final_dt += timedelta(days=1)
                if final_dt - timedelta(hours=2) <= now <= final_dt:
                    upsert_email_reminder(
                        current_user,
                        "Nhac nho: staff chua nop checklist",
                        (
                            f"{sheet.user.full_name} con {incomplete_count} hang muc chua hoan thanh "
                            f"checklist {sheet.line_name} ngay {anchor_date.strftime('%d/%m/%Y')}."
                        ),
                        "day",
                        anchor_date,
                        f"leader-staff-due:{current_user.id}:{sheet.id}:{anchor_date.isoformat()}",
                        sheet.id,
                    )
        pending_sheets = [
            sheet
            for sheet in sheets
            if sheet_is_submitted(sheet) and not sheet_has_confirmation(sheet, {"leader"})
        ]
        dedupe_key = f"leader-confirm:{current_user.id}:day:{anchor_date.isoformat()}"
        if pending_sheets:
            upsert_notification(
                current_user,
                "🔔 Nhắc nhở: Xác nhận checklist nhân viên trong ngày",
                f"Còn {len(pending_sheets)} checklist của nhân viên chưa được tổ trưởng xác nhận ngày {anchor_date.strftime('%d/%m/%Y')}. Vui lòng xem xét và xác nhận.",
                "day",
                anchor_date,
                dedupe_key,
                pending_sheets[0].id,
            )
        else:
            resolve_notification(current_user, dedupe_key)

        # Nhắc nộp báo cáo tuần/tháng lên manager
        for period_type in ["week", "month"]:
            start_date, end_date = period_bounds(anchor_date, period_type)
            period_sheets = (
                DailyCheckSheet.query.filter(
                    DailyCheckSheet.user_id == current_user.id,
                    DailyCheckSheet.template_id == template_id,
                    DailyCheckSheet.check_date >= start_date,
                    DailyCheckSheet.check_date <= end_date,
                )
                .order_by(DailyCheckSheet.check_date.asc())
                .all()
            )
            pending_period = [s for s in period_sheets if not sheet_is_submitted(s)]
            period_name = "tuần" if period_type == "week" else "tháng"
            dedupe_key_period = f"leader-submit:{current_user.id}:{period_type}:{start_date.isoformat()}"
            if pending_period:
                upsert_notification(
                    current_user,
                    f"🔔 Nhắc nhở: Nộp báo cáo {period_name} lên quản lý",
                    f"Bạn còn {len(pending_period)} checklist {period_name} chưa nộp (từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}). Vui lòng hoàn thành và nộp lên quản lý xác nhận.",
                    period_type,
                    anchor_date,
                    dedupe_key_period,
                    pending_period[0].id,
                )
            else:
                resolve_notification(current_user, dedupe_key_period)

        now = datetime.now()
        if now.weekday() == 4 and now.hour >= 17:
            start_date, end_date = period_bounds(anchor_date, "week")
            for manager in higher_level_users():
                upsert_email_reminder(
                    manager,
                    "Nhac nho: can nhan bao cao tuan",
                    (
                        f"To truong {current_user.full_name} can nop bao cao tuan "
                        f"({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}) len quan ly."
                    ),
                    "week",
                    anchor_date,
                    f"manager-weekly-leader-submit:{manager.id}:{current_user.id}:{start_date.isoformat()}",
                )

    if current_user.role in {"manager", "admin"}:
        # Nhắc xác nhận checklist tổ trưởng theo tuần/tháng
        for period_type in ["week", "month"]:
            start_date, end_date = period_bounds(anchor_date, period_type)
            sheets = (
                DailyCheckSheet.query.join(User)
                .filter(
                    User.role == "leader",
                    DailyCheckSheet.check_date >= start_date,
                    DailyCheckSheet.check_date <= end_date,
                )
                .all()
            )
            pending_sheets = [
                sheet
                for sheet in sheets
                if sheet_is_submitted(sheet) and not sheet_has_confirmation(sheet, {"manager", "admin"})
            ]
            period_name = "tuần" if period_type == "week" else "tháng"
            dedupe_key = f"manager-confirm:{current_user.id}:{period_type}:{start_date.isoformat()}"
            if not pending_sheets:
                resolve_notification(current_user, dedupe_key)
            else:
                upsert_notification(
                    current_user,
                    f"🔔 Nhắc nhở: Xác nhận báo cáo {period_name} của tổ trưởng",
                    f"Còn {len(pending_sheets)} checklist của tổ trưởng chưa được quản lý xác nhận "
                    f"từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}. Vui lòng xem xét và xác nhận.",
                    period_type,
                    anchor_date,
                    dedupe_key,
                    pending_sheets[0].id,
                )

    db.session.commit()


def current_notifications(user: User) -> list[Notification]:
    return (
        Notification.query.filter_by(user_id=user.id, status=NOTIFICATION_UNREAD)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(10)
        .all()
    )


def build_print_text(sheet: DailyCheckSheet | None, results: list[DailyCheckResult]) -> str:
    if not sheet:
        return ""
    lines = [
        "Noi dung file in checklist",
        f"Nguoi thuc hien: {sheet.user.full_name}",
        f"Ma NV: {sheet.user.employee_code}",
        f"Line: {sheet.line_name}",
        f"Ngay: {sheet.check_date.strftime('%d/%m/%Y')}",
        "",
        "Ket qua checklist:",
    ]
    for index, result in enumerate(results, start=1):
        value = result.result or "Chua dien"
        note = f" - {result.abnormal_note}" if result.abnormal_note else ""
        lines.append(f"{index}. {result.check_time.strftime('%H:%M')} {result.symbol}: {value}{note}")
    return "\n".join(lines)


def build_outlook_url(sheet: DailyCheckSheet | None, results: list[DailyCheckResult]) -> str:
    if not sheet:
        return ""
    leaders = leader_users_for_line(sheet.line_name)
    higher_users = higher_level_users()
    to_addresses = ",".join([user.outlook_email for user in leaders if user.outlook_email])
    cc_addresses = ",".join([user.outlook_email for user in higher_users if user.outlook_email])
    subject = f"Checklist {sheet.user.full_name} - {sheet.line_name} - {sheet.check_date.strftime('%d/%m/%Y')}"
    print_url = url_for("checklist.print_checklist", sheet_id=sheet.id, _external=True)
    body = "\n".join(
        [
            "Em gửi bản in checklist:",
            "",
            f"Người thực hiện: {sheet.user.full_name}",
            f"Line: {sheet.line_name}",
            f"Ngày: {sheet.check_date.strftime('%d/%m/%Y')}",
            "",
            f"Mở bản in checklist: {print_url}",
        ]
    )
    return (
        "mailto:"
        f"{quote(to_addresses, safe='@,.')}"
        f"?cc={quote(cc_addresses, safe='@,.')}"
        f"&subject={quote(subject)}"
        f"&body={quote(body)}"
    )


def can_view_sheet(user: User, sheet: DailyCheckSheet) -> bool:
    if user.role in {"admin", "manager"}:
        return True
    if user.role == "leader":
        return sheet.user.role == "staff" and sheet.user.leader_id == user.id
    return sheet.user_id == user.id


def can_edit_result(user: User, result: DailyCheckResult) -> bool:
    if result.daily_sheet.status in {SHEET_STATUS_SUBMITTED, SHEET_STATUS_CONFIRMED} and user.role == "staff":
        return False
    if user.role in {"admin", "manager"}:
        return True
    if user.role == "leader":
        return result.daily_sheet.user.role == "staff" and result.daily_sheet.user.leader_id == user.id
    return result.user_id == user.id


def can_submit_sheet(user: User, sheet: DailyCheckSheet) -> bool:
    return user.role == "admin" or sheet.user_id == user.id


def can_confirm_sheet(user: User, sheet: DailyCheckSheet) -> bool:
    if user.role == "admin":
        return True
    if user.role == "leader":
        return sheet.user.role == "staff" and sheet.user.leader_id == user.id
    if user.role == "manager":
        return True
    return False


def can_write_leader_note(user: User, result: DailyCheckResult) -> bool:
    if user.role in {"admin", "manager"}:
        return True
    if user.role == "leader":
        return result.daily_sheet.user.role == "staff" and result.daily_sheet.user.leader_id == user.id
    return False


def get_template_id() -> int:
    sheet = DailyCheckSheet.query.first()
    return sheet.template_id if sheet else 1


def ensure_daily_sheet_and_results(user_id: int, template_id: int, selected_date: date, line_name: str | None = None):
    user = User.query.get_or_404(user_id)
    selected_line = Line.query.filter_by(line_name=line_name, is_active=True).first() if line_name else None
    sheet_line_name = selected_line.line_name if selected_line else user.line_name
    sheet_department = selected_line.department if selected_line else user.department
    sheet = DailyCheckSheet.query.filter_by(
        user_id=user_id,
        template_id=template_id,
        check_date=selected_date,
    ).first()

    if sheet is None:
        sheet = DailyCheckSheet(
            user_id=user_id,
            template_id=template_id,
            check_date=selected_date,
            month=selected_date.month,
            year=selected_date.year,
            line_name=sheet_line_name,
            department=sheet_department,
            shift="day",
            status="draft",
        )
        db.session.add(sheet)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            sheet = DailyCheckSheet.query.filter_by(
                user_id=user_id,
                template_id=template_id,
                check_date=selected_date,
            ).first()
    elif selected_line and sheet.line_name != selected_line.line_name:
        if sheet.status not in {SHEET_STATUS_SUBMITTED, SHEET_STATUS_CONFIRMED}:
            AbnormalReport.query.filter_by(daily_sheet_id=sheet.id).delete()
            DailyCheckResult.query.filter_by(daily_sheet_id=sheet.id).delete()
        sheet.line_name = selected_line.line_name
        sheet.department = selected_line.department

    sheet_line = Line.query.filter_by(line_name=sheet.line_name).first()
    active_items_query = ChecklistItem.query.filter(
        ChecklistItem.template_id == template_id,
        ChecklistItem.is_active.is_(True),
    )
    if sheet_line:
        active_items_query = active_items_query.filter(ChecklistItem.line_id == sheet_line.id)
    active_items = active_items_query.order_by(ChecklistItem.check_time.asc(), ChecklistItem.item_order.asc()).all()
    active_items = sorted(
        active_items,
        key=lambda item: (*line_time_sort_key(sheet.line_name, item.check_time), item.item_order or 0),
    )
    if not active_items:
        active_items = [
            item
            for item in sheet.template.checklist_items
            if item.is_active and item.line_id is None
        ]
    existing_item_ids = {
        item_id
        for (item_id,) in db.session.query(DailyCheckResult.checklist_item_id)
        .filter_by(daily_sheet_id=sheet.id)
        .all()
    }

    for item in active_items:
        if not item.is_active or item.id in existing_item_ids:
            continue
        db.session.add(
            DailyCheckResult(
                daily_sheet_id=sheet.id,
                checklist_item_id=item.id,
                user_id=user_id,
                check_date=result_work_date(sheet.line_name, selected_date, item.check_time),
                symbol=item.symbol,
                check_time=item.check_time,
                content=item.content_vi,
                result=RESULT_EMPTY,
                abnormal_note=None,
                checked_at=None,
            )
        )
    for result in sheet.results:
        expected_date = result_work_date(sheet.line_name, sheet.check_date, result.check_time)
        if result.check_date != expected_date:
            result.check_date = expected_date
    db.session.commit()
    return sheet


def get_target_users(current_user: User, selected_user_id: int | None, selected_line: str) -> list[User]:
    query = User.query.filter(User.role != "admin", User.is_active.is_(True))
    if current_user.role == "staff":
        query = query.filter(User.id == current_user.id)
        return query.order_by(User.full_name.asc()).all()
    if current_user.role == "leader":
        query = query.filter(User.role == "staff", User.leader_id == current_user.id)

    if selected_user_id:
        query = query.filter(User.id == selected_user_id)
    if selected_line:
        query = query.filter(User.line_name == selected_line)
    return query.order_by(User.full_name.asc()).all()


def build_dashboard_context(
    selected_date: date,
    selected_line: str,
    selected_user_id: int | None,
    selected_sheet_id: int | None,
    keyword: str,
    result_filter: str,
    period_type: str = "day",
    active_section: str = "checklist",
):
    current_user = g.current_user
    template_id = get_template_id()
    build_reminders_for_user(current_user, selected_date)
    staff_missing_line = current_user.role == "staff" and not selected_line

    target_users = get_target_users(current_user, selected_user_id, selected_line)
    if not staff_missing_line:
        for user in target_users:
            ensure_daily_sheet_and_results(
                user.id,
                template_id,
                selected_date,
                selected_line if current_user.role == "staff" else None,
            )

    query = DailyCheckSheet.query.join(User).filter(DailyCheckSheet.check_date == selected_date)
    if current_user.role == "staff":
        query = query.filter(DailyCheckSheet.user_id == current_user.id)
    elif current_user.role == "leader":
        query = query.filter(User.role == "staff", User.leader_id == current_user.id)
    if selected_line:
        query = query.filter(DailyCheckSheet.line_name == selected_line)
    if selected_user_id:
        query = query.filter(DailyCheckSheet.user_id == selected_user_id)

    sheets = query.order_by(DailyCheckSheet.line_name.asc(), DailyCheckSheet.user_id.asc()).all()

    selected_sheet = None
    if selected_sheet_id:
        candidate = DailyCheckSheet.query.get_or_404(selected_sheet_id)
        if can_view_sheet(current_user, candidate):
            selected_sheet = candidate
    if selected_sheet is None and sheets:
        selected_sheet = sheets[0]

    results_query = DailyCheckResult.query
    abnormal_reports = []
    confirmations = []
    result_summary = {"o": 0, "x": 0, "△": 0, "empty": 0}
    period_summary = {"total": 0, "submitted": 0, "confirmed": 0, "pending": 0, "completion": 0}
    results = []

    if selected_sheet:
        results_query = results_query.filter_by(daily_sheet_id=selected_sheet.id)
        if keyword:
            like_value = f"%{keyword}%"
            results_query = results_query.join(ChecklistItem).filter(
                or_(
                    DailyCheckResult.symbol.ilike(like_value),
                    DailyCheckResult.content.ilike(like_value),
                    DailyCheckResult.abnormal_note.ilike(like_value),
                    DailyCheckResult.result.ilike(like_value),
                    ChecklistItem.content_vi.ilike(like_value),
                    ChecklistItem.content_en.ilike(like_value),
                    ChecklistItem.content_ja.ilike(like_value),
                )
            )
        if result_filter == "none":
            results_query = results_query.filter(
                or_(DailyCheckResult.result.is_(None), DailyCheckResult.result == RESULT_EMPTY)
            )
        elif result_filter in {RESULT_OK, RESULT_NG, RESULT_ABNORMAL}:
            results_query = results_query.filter(DailyCheckResult.result == result_filter)

        all_results = (
            DailyCheckResult.query.filter_by(daily_sheet_id=selected_sheet.id)
            .all()
        )
        all_results = sorted(
            all_results,
            key=lambda result: line_time_sort_key(selected_sheet.line_name, result.check_time, result.id),
        )
        for result in all_results:
            if result.result == RESULT_OK:
                result_summary["o"] += 1
            elif result.result == RESULT_NG:
                result_summary["x"] += 1
            elif result.result == RESULT_ABNORMAL:
                result_summary["△"] += 1
            else:
                result_summary["empty"] += 1

        results = sorted(
            results_query.all(),
            key=lambda result: line_time_sort_key(selected_sheet.line_name, result.check_time, result.id),
        )
        abnormal_reports = [
            report
            for report in selected_sheet.abnormal_reports
            if report.status != ABNORMAL_STATUS_CANCELLED
            and report.daily_check_result.result in {RESULT_NG, RESULT_ABNORMAL}
        ]
        if current_user.role == "staff":
            abnormal_reports = [report for report in abnormal_reports if report.user_id == current_user.id]
        confirmations = sorted(selected_sheet.confirmations, key=lambda item: item.confirmed_at)

    if current_user.role == "staff":
        start_date, end_date = period_bounds(selected_date, period_type)
        period_sheets = DailyCheckSheet.query.filter(
            DailyCheckSheet.user_id == current_user.id,
            DailyCheckSheet.check_date >= start_date,
            DailyCheckSheet.check_date <= end_date,
        ).all()
        period_summary["total"] = len(period_sheets)
        period_summary["submitted"] = sum(1 for sheet in period_sheets if sheet.status == SHEET_STATUS_SUBMITTED)
        period_summary["confirmed"] = sum(1 for sheet in period_sheets if sheet.status == SHEET_STATUS_CONFIRMED)
        period_summary["pending"] = sum(1 for sheet in period_sheets if sheet.status not in submitted_statuses())
        if period_summary["total"]:
            period_summary["completion"] = round(
                ((period_summary["submitted"] + period_summary["confirmed"]) / period_summary["total"]) * 100
            )

    outlook_url = ""
    if current_user.role == "staff" and selected_sheet and selected_sheet.user_id == current_user.id:
        outlook_url = build_outlook_url(selected_sheet, results)

    if current_user.role in {"admin", "manager"}:
        visible_lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
        visible_users = User.query.filter(User.role != "admin").order_by(User.full_name.asc()).all()
    elif current_user.role == "leader":
        visible_lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
        visible_users = User.query.filter(
            User.role == "staff",
            User.leader_id == current_user.id,
            User.is_active.is_(True),
        ).order_by(User.full_name.asc()).all()
    else:
        visible_lines = Line.query.filter_by(is_active=True).order_by(Line.line_name.asc()).all()
        visible_users = []

    staff_assignments = []
    leaders_for_assignment = []
    if current_user.role in {"manager", "admin", "leader"}:
        leaders_for_assignment = User.query.filter(
            User.role == "leader",
            User.is_active.is_(True),
        ).order_by(User.full_name.asc()).all()
        staff_assignments = User.query.filter(
            User.role == "staff",
            User.is_active.is_(True),
        ).order_by(User.full_name.asc()).all()

    can_change_line = True
    if current_user.role == "staff" and selected_sheet:
        has_data = any(r.result and r.result != RESULT_EMPTY for r in selected_sheet.results)
        if has_data:
            can_change_line = False

    return {
        "sheets": sheets,
        "selected_sheet": selected_sheet,
        "results": results,
        "abnormal_reports": abnormal_reports,
        "confirmations": confirmations,
        "notifications": current_notifications(current_user),
        "outlook_url": outlook_url,
        "result_summary": result_summary,
        "period_summary": period_summary,
        "period_type": period_type,
        "visible_lines": visible_lines,
        "visible_users": visible_users,
        "staff_assignments": staff_assignments,
        "can_change_line": can_change_line,
        "staff_must_choose_line": bool(staff_missing_line and selected_sheet is None),
        "leaders_for_assignment": leaders_for_assignment,
        "selected_date": selected_date.isoformat(),
        "selected_line": selected_line,
        "selected_user_id": selected_user_id,
        "keyword": keyword,
        "result_filter": result_filter,
        "active_section": active_section,
        "can_edit_selected": bool(
            selected_sheet
            and (
                current_user.role in {"admin", "manager"}
                or current_user.id == selected_sheet.user_id
                or (
                    current_user.role == "leader"
                    and selected_sheet.user.role == "staff"
                    and selected_sheet.user.leader_id == current_user.id
                )
            )
            and not (
                current_user.role == "staff"
                and selected_sheet.status in {SHEET_STATUS_SUBMITTED, SHEET_STATUS_CONFIRMED}
            )
        ),
        "can_submit_selected": bool(selected_sheet and can_submit_sheet(current_user, selected_sheet)),
        "can_confirm_selected": bool(selected_sheet and can_confirm_sheet(current_user, selected_sheet)),
        "result_work_date": result_work_date,
        "current_endpoint": "checklist.dashboard",
    }


def redirect_to_sheet(sheet: DailyCheckSheet, active_section: str = "checklist"):
    return redirect(
        url_for(
            "checklist.dashboard",
            date=sheet.check_date.isoformat(),
            sheet_id=sheet.id,
            section=active_section,
        )
    )


@checklist_bp.route("/")
def index():
    if g.current_user:
        return redirect(url_for("checklist.dashboard"))
    return redirect(url_for("auth.login"))


@checklist_bp.route("/dashboard")
@login_required
def dashboard():
    selected_date = parse_date(request.args.get("date"), fallback=date.today())
    selected_line = request.args.get("line", "").strip()
    selected_user_id = request.args.get("user_id", type=int)
    selected_sheet_id = request.args.get("sheet_id", type=int)
    keyword = request.args.get("keyword", "").strip()
    result_filter = request.args.get("result_filter", "all").strip() or "all"
    period_type = request.args.get("period", "day").strip() or "day"
    if period_type not in {"day", "week", "month"}:
        period_type = "day"
    active_section = request.args.get("section", "checklist")
    context = build_dashboard_context(
        selected_date,
        selected_line,
        selected_user_id,
        selected_sheet_id,
        keyword,
        result_filter,
        period_type=period_type,
        active_section=active_section,
    )
    return render_template("dashboard.html", **context)


@checklist_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    from flask import jsonify
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != g.current_user.id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False}), 403
        flash("Bạn không có quyền cập nhật thông báo này.", "danger")
        return redirect(url_for("checklist.dashboard"))

    notification.status = NOTIFICATION_READ
    notification.read_at = datetime.now()
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(request.referrer or url_for("checklist.dashboard"))


@checklist_bp.route("/sheets/<int:sheet_id>/submit", methods=["POST"])
@login_required
def submit_sheet(sheet_id: int):
    sheet = DailyCheckSheet.query.get_or_404(sheet_id)
    if not can_view_sheet(g.current_user, sheet) or not can_submit_sheet(g.current_user, sheet):
        flash("Bạn không có quyền nộp checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))

    empty_count = DailyCheckResult.query.filter(
        DailyCheckResult.daily_sheet_id == sheet.id,
        or_(DailyCheckResult.result.is_(None), DailyCheckResult.result == RESULT_EMPTY),
    ).count()
    if empty_count:
        flash(f"Checklist còn {empty_count} hạng mục chưa điền, chưa thể nộp.", "warning")
        return redirect_to_sheet(sheet)

    sheet.status = SHEET_STATUS_SUBMITTED
    db.session.commit()
    leader = sheet.user.leader or (leader_users_for_line(sheet.line_name)[0] if leader_users_for_line(sheet.line_name) else None)
    if leader and leader.outlook_email:
        results = DailyCheckResult.query.filter_by(daily_sheet_id=sheet.id).all()
        results = sorted(results, key=lambda result: line_time_sort_key(sheet.line_name, result.check_time, result.id))
        print_url = url_for("checklist.print_checklist", sheet_id=sheet.id, _external=True)
        send_outlook_email(
            leader.outlook_email,
            f"Staff submitted checklist: {sheet.user.full_name} - {sheet.check_date.strftime('%d/%m/%Y')}",
            f"{build_outlook_body(sheet, results)}\n\nConfirm URL: {print_url}",
        )
    flash("Đã nộp checklist thành công. Vui lòng chờ tổ trưởng xác nhận.", "success")
    return redirect_to_sheet(sheet)


@checklist_bp.route("/sheets/<int:sheet_id>/quick-check", methods=["POST"])
@login_required
def quick_check_sheet(sheet_id: int):
    sheet = DailyCheckSheet.query.get_or_404(sheet_id)
    if not can_view_sheet(g.current_user, sheet) or not can_submit_sheet(g.current_user, sheet):
        flash("Bạn không có quyền tích nhanh checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))

    mode = request.form.get("mode", "empty_to_ok")
    updated_count = 0
    for result in sheet.results:
        if mode == "all_ok" or not result.result:
            result.result = RESULT_OK
            result.checked_at = datetime.now()
            result.abnormal_note = None
            updated_count += 1
    db.session.commit()
    flash(f"Đã tích nhanh {updated_count} hạng mục OK.", "success")
    return redirect_to_sheet(sheet)


@checklist_bp.route("/sheets/<int:sheet_id>/send-outlook", methods=["POST"])
@login_required
def send_sheet_outlook(sheet_id: int):
    sheet = DailyCheckSheet.query.get_or_404(sheet_id)
    if not can_view_sheet(g.current_user, sheet) or sheet.user_id != g.current_user.id:
        flash("Bạn không có quyền gửi Outlook checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))

    supervisor_outlook = request.form.get("supervisor_outlook", "").strip()
    supervisor = None
    if supervisor_outlook:
        supervisor = User.query.filter(
            User.outlook_email == supervisor_outlook,
            User.role.in_(["leader", "manager", "admin"]),
            User.is_active.is_(True),
        ).first()
    if supervisor is None:
        supervisor = sheet.user.leader or (leader_users_for_line(sheet.line_name)[0] if leader_users_for_line(sheet.line_name) else None)
    if supervisor is None:
        flash("Không tìm thấy tổ trưởng/cấp trên có Outlook để gửi.", "danger")
        return redirect_to_sheet(sheet)
    supervisor_outlook = supervisor.outlook_email
    if not supervisor_outlook:
        flash("Tài khoản cấp trên chưa có Outlook.", "danger")
        return redirect_to_sheet(sheet)

    results = DailyCheckResult.query.filter_by(daily_sheet_id=sheet.id).all()
    results = sorted(results, key=lambda result: line_time_sort_key(sheet.line_name, result.check_time, result.id))
    subject = f"Checklist {sheet.user.full_name} - {sheet.line_name} - {sheet.check_date.strftime('%d/%m/%Y')}"
    print_url = url_for("checklist.print_checklist", sheet_id=sheet.id, _external=True)
    body = f"{build_outlook_body(sheet, results)}\n\nPrint URL: {print_url}"
    cc_addresses = [user.outlook_email for user in higher_level_users() if user.outlook_email and user.id != supervisor.id]
    ok, message = send_outlook_email(supervisor_outlook, subject, body, cc_addresses)
    if ok:
        flash("Đã gửi Outlook đến cấp trên.", "success")
    else:
        flash(f"Không gửi được qua SMTP: {message}", "danger")
    return redirect_to_sheet(sheet)


@checklist_bp.route("/sheets/<int:sheet_id>/confirm", methods=["POST"])
@login_required
def confirm_sheet(sheet_id: int):
    sheet = DailyCheckSheet.query.get_or_404(sheet_id)
    if not can_view_sheet(g.current_user, sheet) or not can_confirm_sheet(g.current_user, sheet):
        flash("Bạn không có quyền xác nhận checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))
    if not sheet_is_submitted(sheet):
        flash("Checklist chưa được nộp nên chưa thể xác nhận.", "warning")
        return redirect_to_sheet(sheet)

    existing = DailyConfirmation.query.filter_by(
        daily_sheet_id=sheet.id,
        confirmed_role=g.current_user.role,
    ).first()
    if existing:
        flash("Vai trò này đã xác nhận checklist rồi.", "warning")
        return redirect_to_sheet(sheet)

    confirmed_at = datetime.now()
    db.session.add(
        DailyConfirmation(
            daily_sheet=sheet,
            user=sheet.user,
            signer=g.current_user,
            confirmed_by_name=g.current_user.full_name,
            confirmed_role=g.current_user.role,
            confirmed_at=confirmed_at,
            signature_note=request.form.get("signature_note", "").strip() or None,
        )
    )
    sheet.status = SHEET_STATUS_CONFIRMED

    # Gửi thông báo cho staff khi leader xác nhận checklist ngày
    if g.current_user.role == "leader" and sheet.user.role == "staff":
        dedupe_key = f"staff-confirmed-by-leader:{sheet.user_id}:{sheet.id}"
        upsert_notification(
            sheet.user,
            "✅ Checklist của bạn đã được tổ trưởng xác nhận",
            f"Checklist ngày {sheet.check_date.strftime('%d/%m/%Y')} của bạn đã được tổ trưởng "
            f"{g.current_user.full_name} xác nhận lúc {confirmed_at.strftime('%H:%M %d/%m/%Y')}.",
            "day",
            sheet.check_date,
            dedupe_key,
            sheet.id,
        )
        if sheet.user.outlook_email:
            send_outlook_email(
                sheet.user.outlook_email,
                f"Checklist confirmed: {sheet.check_date.strftime('%d/%m/%Y')}",
                f"Checklist ngày {sheet.check_date.strftime('%d/%m/%Y')} của bạn đã được {g.current_user.full_name} xác nhận.",
            )

    # Gửi thông báo cho leader khi manager xác nhận checklist tuần/tháng
    if g.current_user.role in {"manager", "admin"} and sheet.user.role == "leader":
        for period_type in ["week", "month"]:
            start_date, end_date = period_bounds(sheet.check_date, period_type)
            period_name = "tuần" if period_type == "week" else "tháng"
            dedupe_key = f"leader-confirmed-by-manager:{sheet.user_id}:{period_type}:{sheet.id}"
            upsert_notification(
                sheet.user,
                f"✅ Báo cáo {period_name} của bạn đã được quản lý xác nhận",
                f"Checklist {period_name} (từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}) "
                f"đã được {g.current_user.full_name} xác nhận lúc {confirmed_at.strftime('%H:%M %d/%m/%Y')}.",
                period_type,
                sheet.check_date,
                dedupe_key,
                sheet.id,
            )

    db.session.commit()
    flash("Đã xác nhận checklist thành công.", "success")
    return redirect_to_sheet(sheet)


@checklist_bp.route("/check-result/<int:result_id>/update", methods=["POST"])
@login_required
def update_result(result_id: int):
    result = DailyCheckResult.query.get_or_404(result_id)
    if not can_view_sheet(g.current_user, result.daily_sheet):
        flash("Bạn không có quyền truy cập checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))
    if not can_edit_result(g.current_user, result):
        flash("Bạn không được sửa checklist của người dùng khác.", "danger")
        return redirect_to_sheet(result.daily_sheet)

    selected_result = request.form.get("result", "").strip()
    if selected_result == "empty":
        selected_result = RESULT_EMPTY
    if selected_result not in {RESULT_OK, RESULT_EMPTY}:
        flash("Giá trị cập nhật không hợp lệ.", "danger")
        return redirect_to_sheet(result.daily_sheet)

    result.result = selected_result
    result.checked_at = datetime.now() if selected_result else None
    result.abnormal_note = None if selected_result in {RESULT_OK, RESULT_EMPTY} else result.abnormal_note
    if selected_result == RESULT_EMPTY and result.abnormal_reports:
        result.abnormal_reports[0].status = ABNORMAL_STATUS_CANCELLED

    db.session.commit()
    flash("Đã cập nhật kết quả checklist.", "success")
    return redirect_to_sheet(result.daily_sheet)


@checklist_bp.route("/check-result/<int:result_id>/ajax-update", methods=["POST"])
@login_required
def ajax_update_result(result_id: int):
    result = DailyCheckResult.query.get_or_404(result_id)
    if not can_view_sheet(g.current_user, result.daily_sheet) or not can_edit_result(g.current_user, result):
        return jsonify({"ok": False, "message": "Permission denied."}), 403

    selected_result = request.form.get("result", "").strip()
    if selected_result == "empty":
        selected_result = RESULT_EMPTY

    # Cho phép tất cả giá trị hợp lệ từ profile excel view
    if selected_result not in {RESULT_OK, RESULT_NG, RESULT_ABNORMAL, RESULT_EMPTY}:
        return jsonify({"ok": False, "message": "Invalid result."}), 400

    result.result = selected_result
    result.checked_at = datetime.now() if selected_result else None
    actual_date = result_work_date(result.daily_sheet.line_name, result.daily_sheet.check_date, result.check_time)
    result.check_date = actual_date

    # Nếu xóa kết quả → hủy abnormal report
    if selected_result == RESULT_EMPTY and result.abnormal_reports:
        result.abnormal_reports[0].status = ABNORMAL_STATUS_CANCELLED
    # Nếu đổi từ x/△ sang o → hủy abnormal report
    elif selected_result == RESULT_OK and result.abnormal_reports:
        result.abnormal_reports[0].status = ABNORMAL_STATUS_CANCELLED
        result.abnormal_note = None
    elif selected_result in {RESULT_NG, RESULT_ABNORMAL}:
        abnormal_content = result.abnormal_note or result.content or result.symbol
        result.abnormal_note = abnormal_content
        report = result.abnormal_reports[0] if result.abnormal_reports else None
        if report is None:
            report = AbnormalReport(
                daily_sheet=result.daily_sheet,
                daily_check_result=result,
                user=result.user,
                symbol=result.symbol,
                occurred_date=actual_date,
                abnormal_content=abnormal_content,
                status=ABNORMAL_STATUS_OPEN,
            )
            db.session.add(report)
        else:
            report.symbol = result.symbol
            report.occurred_date = actual_date
            report.abnormal_content = abnormal_content
            if report.status == ABNORMAL_STATUS_CANCELLED:
                report.status = ABNORMAL_STATUS_OPEN

    db.session.commit()

    return jsonify({
        "ok": True,
        "result": result.result or "empty",
        "note": result.abnormal_note or "",
        "abnormal": selected_result in {RESULT_NG, RESULT_ABNORMAL},
        "result_id": result.id,
        "symbol": result.symbol,
        "date": actual_date.isoformat(),
        "date_label": actual_date.strftime("%d/%m/%Y"),
        "content": result.content or "",
        "status": result.abnormal_reports[0].status if result.abnormal_reports else ABNORMAL_STATUS_OPEN,
        "abnormal_url": url_for("checklist.update_abnormal_result", result_id=result.id),
    })


@checklist_bp.route("/check-result/<int:result_id>/leader-note", methods=["POST"])
@login_required
def update_leader_note(result_id: int):
    result = DailyCheckResult.query.get_or_404(result_id)
    if not can_view_sheet(g.current_user, result.daily_sheet) or not can_write_leader_note(g.current_user, result):
        return jsonify({"ok": False, "message": "Permission denied."}), 403

    result.leader_note = request.form.get("leader_note", "").strip() or None
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "leader_note": result.leader_note or ""})
    flash("Đã cập nhật ghi chú của tổ trưởng.", "success")
    return redirect_to_sheet(result.daily_sheet)


@checklist_bp.route("/check-result/<int:result_id>/abnormal", methods=["POST"])
@login_required
def update_abnormal_result(result_id: int):
    result = DailyCheckResult.query.get_or_404(result_id)
    if not can_view_sheet(g.current_user, result.daily_sheet):
        flash("Bạn không có quyền truy cập checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))
    if not can_edit_result(g.current_user, result):
        flash("Bạn không được sửa checklist của người dùng khác.", "danger")
        return redirect_to_sheet(result.daily_sheet, "abnormal")

    selected_result = request.form.get("result", "").strip()
    if selected_result not in {RESULT_NG, RESULT_ABNORMAL}:
        flash("Kết quả phải là x hoặc △.", "danger")
        return redirect_to_sheet(result.daily_sheet, "abnormal")

    abnormal_content = request.form.get("abnormal_content", "").strip()
    if not abnormal_content:
        flash("Nội dung bất thường là bắt buộc.", "danger")
        return redirect_to_sheet(result.daily_sheet, "abnormal")

    countermeasure = request.form.get("countermeasure", "").strip()
    actual_date = result_work_date(result.daily_sheet.line_name, result.daily_sheet.check_date, result.check_time)
    result.check_date = actual_date
    confirm_date_before_fix = parse_date(
        request.form.get("confirm_date_before_fix"),
        fallback=actual_date,
    )
    result_after_fix = request.form.get("result_after_fix", "").strip()
    status = request.form.get("status", ABNORMAL_STATUS_OPEN).strip() or ABNORMAL_STATUS_OPEN
    if status not in VALID_ABNORMAL_STATUSES:
        status = ABNORMAL_STATUS_OPEN

    result.result = selected_result
    result.checked_at = datetime.now()
    result.abnormal_note = abnormal_content

    report = result.abnormal_reports[0] if result.abnormal_reports else None
    if report is None:
        from models import AbnormalReport

        report = AbnormalReport(
            daily_sheet=result.daily_sheet,
            daily_check_result=result,
            user=result.user,
            symbol=result.symbol,
            occurred_date=actual_date,
            abnormal_content=abnormal_content,
            countermeasure=countermeasure,
            confirm_date_before_fix=confirm_date_before_fix,
            result_after_fix=result_after_fix,
            status=status,
        )
        db.session.add(report)
    else:
        report.symbol = result.symbol
        report.occurred_date = actual_date
        report.abnormal_content = abnormal_content
        report.countermeasure = countermeasure
        report.confirm_date_before_fix = confirm_date_before_fix
        report.result_after_fix = result_after_fix
        report.status = status

    db.session.commit()
    flash("Đã cập nhật nội dung bất thường.", "success")
    return redirect_to_sheet(result.daily_sheet, "abnormal")


@checklist_bp.route("/abnormal-reports")
@login_required
def abnormal_reports():
    selected_date = parse_date(request.args.get("date"), fallback=date.today())
    selected_line = request.args.get("line", "").strip()
    selected_user_id = request.args.get("user_id", type=int)
    selected_sheet_id = request.args.get("sheet_id", type=int)
    keyword = request.args.get("keyword", "").strip()
    result_filter = request.args.get("result_filter", "all").strip() or "all"
    context = build_dashboard_context(
        selected_date,
        selected_line,
        selected_user_id,
        selected_sheet_id,
        keyword,
        result_filter,
        active_section="abnormal",
    )
    return render_template("dashboard.html", **context)


@checklist_bp.route("/checklist/print/<int:sheet_id>")
@login_required
def print_checklist(sheet_id: int):
    sheet = DailyCheckSheet.query.get_or_404(sheet_id)
    if not can_view_sheet(g.current_user, sheet):
        flash("Bạn không có quyền in checklist này.", "danger")
        return redirect(url_for("checklist.dashboard"))

    current_lang = session.get("lang", "vi")
    results = DailyCheckResult.query.filter_by(daily_sheet_id=sheet.id).all()
    results = sorted(results, key=lambda result: line_time_sort_key(sheet.line_name, result.check_time, result.id))
    abnormal_reports = [
        report
        for report in sheet.abnormal_reports
        if report.status != ABNORMAL_STATUS_CANCELLED
        and report.daily_check_result.result in {RESULT_NG, RESULT_ABNORMAL}
    ]
    confirmations = sorted(sheet.confirmations, key=lambda item: item.confirmed_at)
    return render_template(
        "print_checklist.html",
        sheet=sheet,
        results=results,
        abnormal_reports=abnormal_reports,
        confirmations=confirmations,
        result_work_date=result_work_date,
        current_lang=current_lang,
    )
