from datetime import date, datetime, timedelta

from app import create_app
from models import (
    STATUS_ABNORMAL,
    STATUS_DONE,
    STATUS_PENDING,
    AbnormalNote,
    Category,
    DailyCheck,
    DailyConfirmation,
    User,
    db,
)


def make_user(username, password, role, name):
    user = User(username=username, role=role, name=name)
    user.set_password(password)
    return user


def parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


def create_categories():
    categories = [
        ("A01", "Thức dậy", "06:00"),
        ("A02", "Tập thể dục", "06:15"),
        ("A03", "Vệ sinh cá nhân", "06:30"),
        ("A04", "Ăn sáng", "07:00"),
        ("A05", "Đi đến công ty", "07:30"),
        ("A06", "Kiểm tra email", "08:00"),
        ("A07", "Họp sáng (Stand-up)", "08:15"),
        ("A08", "Công việc sáng 1", "08:30"),
        ("A09", "Giải lao sáng", "09:30"),
        ("A10", "Công việc sáng 2", "09:45"),
        ("A11", "Review code", "10:30"),
        ("A12", "Công việc sáng 3", "11:00"),
        ("A13", "Ăn trưa", "12:00"),
        ("A14", "Nghỉ trưa", "12:30"),
        ("A15", "Công việc chiều 1", "13:30"),
        ("A16", "Học Python", "14:00"),
        ("A17", "Giải lao chiều", "14:30"),
        ("A18", "Công việc chiều 2", "14:45"),
        ("A19", "Họp nhóm", "15:30"),
        ("A20", "Công việc chiều 3", "16:00"),
        ("A21", "Review công việc ngày", "16:30"),
        ("A22", "Dọn dẹp bàn làm việc", "17:00"),
        ("A23", "Di chuyển về nhà", "17:15"),
        ("A24", "Thể thao/giải trí", "17:45"),
        ("A25", "Ăn tối", "18:30"),
        ("A26", "Đọc sách/học thêm", "19:30"),
        ("A27", "Kiểm tra email tối", "20:30"),
        ("A28", "Chuẩn bị ngày mai", "21:00"),
        ("A29", "Vệ sinh cá nhân tối", "21:30"),
        ("A30", "Đi ngủ", "22:00"),
    ]
    return [Category(symbol=symbol, category=category, limit_time=parse_time(limit_time)) for symbol, category, limit_time in categories]


def create_daily_checks(user, categories, selected_date, status_map=None):
    status_map = status_map or {}
    checks = []
    for category in categories:
        check = DailyCheck(
            user_id=user.id,
            category_id=category.id,
            symbol=category.symbol,
            category=category.category,
            date=selected_date,
            status=status_map.get(category.symbol, STATUS_PENDING),
            limit_time=category.limit_time,
        )
        checks.append(check)
    return checks


app = create_app()


with app.app_context():
    db.drop_all()
    db.create_all()

    admin = make_user("admin", "123456", "admin", "Administrator")
    manager = make_user("manager01", "123456", "manager", "Trưởng ca Nguyễn")
    user01 = make_user("user01", "123456", "user", "Nguyễn Văn A")
    user02 = make_user("user02", "123456", "user", "Trần Thị B")

    db.session.add_all([admin, manager, user01, user02])
    db.session.commit()

    categories = create_categories()
    db.session.add_all(categories)
    db.session.commit()

    today = date.today()
    yesterday = today - timedelta(days=1)

    status_map_user01 = {
        "A01": STATUS_DONE,
        "A02": STATUS_DONE,
        "A03": STATUS_DONE,
        "A04": STATUS_DONE,
        "A05": STATUS_DONE,
        "A06": STATUS_DONE,
        "A07": STATUS_DONE,
        "A08": STATUS_DONE,
        "A09": STATUS_DONE,
        "A10": STATUS_DONE,
        "A11": STATUS_ABNORMAL,
        "A12": STATUS_DONE,
        "A13": STATUS_DONE,
        "A14": STATUS_DONE,
        "A15": STATUS_DONE,
        "A16": STATUS_ABNORMAL,
        "A17": STATUS_DONE,
        "A18": STATUS_DONE,
        "A19": STATUS_PENDING,
        "A20": STATUS_DONE,
        "A21": STATUS_DONE,
        "A22": STATUS_DONE,
        "A23": STATUS_DONE,
        "A24": STATUS_PENDING,
        "A25": STATUS_DONE,
        "A26": STATUS_PENDING,
        "A27": STATUS_PENDING,
        "A28": STATUS_PENDING,
        "A29": STATUS_PENDING,
        "A30": STATUS_PENDING,
    }
    status_map_user02 = {
        "A01": STATUS_DONE,
        "A02": STATUS_DONE,
        "A03": STATUS_DONE,
        "A04": STATUS_DONE,
        "A05": STATUS_DONE,
        "A06": STATUS_PENDING,
        "A07": STATUS_DONE,
        "A08": STATUS_DONE,
        "A09": STATUS_DONE,
        "A10": STATUS_DONE,
        "A11": STATUS_DONE,
        "A12": STATUS_PENDING,
        "A13": STATUS_DONE,
        "A14": STATUS_DONE,
        "A15": STATUS_DONE,
        "A16": STATUS_DONE,
        "A17": STATUS_DONE,
        "A18": STATUS_DONE,
        "A19": STATUS_DONE,
        "A20": STATUS_ABNORMAL,
        "A21": STATUS_DONE,
        "A22": STATUS_DONE,
        "A23": STATUS_DONE,
        "A24": STATUS_PENDING,
        "A25": STATUS_DONE,
        "A26": STATUS_PENDING,
        "A27": STATUS_PENDING,
        "A28": STATUS_PENDING,
        "A29": STATUS_PENDING,
        "A30": STATUS_PENDING,
    }

    today_checks_user01 = create_daily_checks(user01, categories, today, status_map_user01)
    today_checks_user02 = create_daily_checks(user02, categories, today, status_map_user02)
    yesterday_checks_user01 = [
        DailyCheck(
            user_id=user01.id,
            category_id=categories[index].id,
            symbol=categories[index].symbol,
            category=categories[index].category,
            date=yesterday,
            status=status,
            limit_time=categories[index].limit_time,
        )
        for index, status in [(0, STATUS_PENDING), (3, STATUS_DONE), (12, STATUS_DONE), (15, STATUS_ABNORMAL), (24, STATUS_DONE)]
    ]

    db.session.add_all(today_checks_user01 + today_checks_user02 + yesterday_checks_user01)
    db.session.commit()

    check_map = {(check.user_id, check.symbol, check.date): check for check in DailyCheck.query.all()}
    notes = [
        AbnormalNote(
            user_id=user01.id,
            daily_check_id=check_map[(user01.id, "A11", today)].id,
            symbol="A11",
            category="Review code",
            note="Không kịp review hết code trong giờ.",
        ),
        AbnormalNote(
            user_id=user01.id,
            daily_check_id=check_map[(user01.id, "A16", today)].id,
            symbol="A16",
            category="Học Python",
            note="Bị gián đoạn do họp đột xuất.",
        ),
        AbnormalNote(
            user_id=user02.id,
            daily_check_id=check_map[(user02.id, "A20", today)].id,
            symbol="A20",
            category="Công việc chiều 3",
            note="Hoàn thành muộn 30 phút.",
        ),
        AbnormalNote(
            user_id=user01.id,
            daily_check_id=check_map[(user01.id, "A16", yesterday)].id,
            symbol="A16",
            category="Học Python",
            note="Bị trễ 1 tiếng do phát sinh công việc.",
        ),
    ]
    db.session.add_all(notes)

    db.session.add(
        DailyConfirmation(
            user_id=user01.id,
            date=yesterday,
            confirmed_by=admin.id,
            confirmed_by_name=admin.name,
            confirmed_at=datetime.combine(yesterday, parse_time("18:30")),
            signature_note="Đã kiểm tra và xác nhận checklist.",
        )
    )
    db.session.commit()

    print("Seed completed.")
    print("Accounts:")
    print("  admin / 123456")
    print("  manager01 / 123456")
    print("  user01 / 123456")
    print("  user02 / 123456")
