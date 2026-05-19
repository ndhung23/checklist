from __future__ import annotations

from datetime import datetime
from flask import Flask, g, redirect, request, session
from sqlalchemy import inspect, text

from config import Config
from models import db
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.category_routes import category_bp
from routes.checklist_routes import checklist_bp


TRANSLATIONS = {
    "vi": {
        "dashboard": "Dashboard",
        "checklist": "Checklist",
        "date": "Ngày",
        "search": "Tìm kiếm",
        "result": "Kết quả",
        "abnormal_history": "Nội dung lỗi và lịch sử xử lý",
        "print_checklist": "In checklist",
        "logout": "Đăng xuất",
        "manage_accounts": "Quản lý tài khoản",
        "manage_items": "Quản lý hạng mục",
        "manage_lines": "Quản lý line",
        "abnormal_reports": "Báo cáo bất thường",
        "confirm_checklist": "Xác nhận checklist",
        "filters": "Bộ lọc",
        "empty": "Chưa điền",
        "done": "Đạt",
        "ng": "Lỗi",
        "abnormal": "Bất thường",
    },
    "en": {
        "dashboard": "Dashboard",
        "checklist": "Checklist",
        "date": "Date",
        "search": "Search",
        "result": "Result",
        "abnormal_history": "Abnormal Content and Handling History",
        "print_checklist": "Print Checklist",
        "logout": "Logout",
        "manage_accounts": "Account Management",
        "manage_items": "Checklist Item Management",
        "manage_lines": "Line Management",
        "abnormal_reports": "Abnormal Reports",
        "confirm_checklist": "Checklist Confirmation",
        "filters": "Filters",
        "empty": "Not Filled",
        "done": "Done",
        "ng": "Issue",
        "abnormal": "Abnormal",
    },
    "ja": {
        "dashboard": "ăƒ€ăƒƒă‚·ăƒ¥ăƒœăƒ¼ăƒ‰",
        "checklist": "ăƒă‚§ăƒƒă‚¯ăƒªă‚¹ăƒˆ",
        "date": "æ—¥ä»˜",
        "search": "æ¤œç´¢",
        "result": "çµæœ",
        "abnormal_history": "ç•°å¸¸å†…å®¹ă¨å‡¦ç½®å±¥æ­´",
        "print_checklist": "ăƒă‚§ăƒƒă‚¯ăƒªă‚¹ăƒˆå°åˆ·",
        "logout": "ăƒ­ă‚°ă‚¢ă‚¦ăƒˆ",
        "manage_accounts": "ă‚¢ă‚«ă‚¦ăƒ³ăƒˆç®¡ç†",
        "manage_items": "é …ç›®ç®¡ç†",
        "manage_lines": "ăƒ©ă‚¤ăƒ³ç®¡ç†",
        "abnormal_reports": "ç•°å¸¸ăƒ¬ăƒăƒ¼ăƒˆ",
        "confirm_checklist": "ăƒă‚§ăƒƒă‚¯ç¢ºèª",
        "filters": "ăƒ•ă‚£ăƒ«ă‚¿ăƒ¼",
        "empty": "æœªå…¥å›",
        "done": "å®Œäº†",
        "ng": "ä¸è‰¯",
        "abnormal": "ç•°å¸¸",
    },
}

ROLE_LABELS = {
    "staff": "Tổ phó",
    "leader": "Tổ trưởng",
}

TEMP_SHARED_OUTLOOK = "hung.nguyen.duy.a0u@ap.denso.com"


def get_item_content(item, lang: str) -> str:
    if lang == "ja" and item.content_ja:
        return item.content_ja
    if lang == "en" and item.content_en:
        return item.content_en
    return item.content_vi or item.content


def ensure_database_schema(app: Flask) -> None:
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)

        if "users" in inspector.get_table_names():
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "outlook_email" not in user_columns:
                db.session.execute(text("ALTER TABLE users ADD COLUMN outlook_email VARCHAR(255)"))
                db.session.commit()
            if "gender" not in user_columns:
                db.session.execute(text("ALTER TABLE users ADD COLUMN gender VARCHAR(20)"))
                db.session.commit()
            if "manager_id" not in user_columns:
                db.session.execute(text("ALTER TABLE users ADD COLUMN manager_id INTEGER"))
                db.session.commit()
            if "leader_id" not in user_columns:
                db.session.execute(text("ALTER TABLE users ADD COLUMN leader_id INTEGER"))
                db.session.commit()
            db.session.execute(
                text("UPDATE users SET outlook_email = :outlook WHERE outlook_email IS NULL OR outlook_email = ''"),
                {"outlook": TEMP_SHARED_OUTLOOK},
            )
            db.session.execute(text("UPDATE users SET manager_id = NULL WHERE role IN ('leader', 'staff')"))
            db.session.commit()

        if "notifications" not in inspector.get_table_names():
            db.create_all()

        if "checklist_items" in inspector.get_table_names():
            item_columns = {column["name"] for column in inspector.get_columns("checklist_items")}
            if "line_id" not in item_columns:
                db.session.execute(text("ALTER TABLE checklist_items ADD COLUMN line_id INTEGER"))
                db.session.commit()

        if "daily_check_results" in inspector.get_table_names():
            result_columns = {column["name"] for column in inspector.get_columns("daily_check_results")}
            if "leader_note" not in result_columns:
                db.session.execute(text("ALTER TABLE daily_check_results ADD COLUMN leader_note TEXT"))
                db.session.commit()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(category_bp)
    ensure_database_schema(app)

    @app.before_request
    def ensure_language():
        if session.get("lang") not in TRANSLATIONS:
            session["lang"] = "vi"

    @app.context_processor
    def inject_globals():
        from flask import g
        from models import Notification, NOTIFICATION_UNREAD
        current_lang = session.get("lang", "vi")

        def t(key: str) -> str:
            return TRANSLATIONS.get(current_lang, TRANSLATIONS["vi"]).get(key, key)

        def role_label(role: str | None) -> str:
            return ROLE_LABELS.get(role or "", role or "")

        current_user = getattr(g, "current_user", None)
        notifications = []
        if current_user:
            notifications = (
                Notification.query.filter_by(user_id=current_user.id, status=NOTIFICATION_UNREAD)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .limit(20)
                .all()
            )

        return {
            "current_user": current_user,
            "current_lang": current_lang,
            "t": t,
            "role_label": role_label,
            "get_item_content": get_item_content,
            "current_endpoint": request.endpoint or "",
            "notifications": notifications,
            "now": datetime.utcnow,
        }

    @app.template_filter("date_local")
    def date_local(value):
        return value.strftime("%d/%m/%Y") if value else ""

    @app.template_filter("time_local")
    def time_local(value):
        return value.strftime("%H:%M") if value else ""

    @app.template_filter("datetime_local")
    def datetime_local(value):
        return value.strftime("%d/%m/%Y %H:%M") if value else ""

    @app.cli.command("init-db")
    def init_db_command() -> None:
        with app.app_context():
            db.drop_all()
            db.create_all()
        print("Database initialized.")

    @app.route("/set-language/<lang>")
    def set_language(lang: str):
        if lang in TRANSLATIONS:
            session["lang"] = lang
        return redirect(request.referrer or "/")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5999)
