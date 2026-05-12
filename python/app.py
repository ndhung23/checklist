from __future__ import annotations

from flask import Flask, g, redirect, request, session

from config import Config
from models import db
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
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
        "dashboard": "ダッシュボード",
        "checklist": "チェックリスト",
        "date": "日付",
        "search": "検索",
        "result": "結果",
        "abnormal_history": "異常内容と処置履歴",
        "print_checklist": "チェックリスト印刷",
        "logout": "ログアウト",
        "manage_accounts": "アカウント管理",
        "manage_items": "項目管理",
        "manage_lines": "ライン管理",
        "abnormal_reports": "異常レポート",
        "confirm_checklist": "チェック確認",
        "filters": "フィルター",
        "empty": "未入力",
        "done": "完了",
        "ng": "不良",
        "abnormal": "異常",
    },
}


def get_item_content(item, lang: str) -> str:
    if lang == "ja" and item.content_ja:
        return item.content_ja
    if lang == "en" and item.content_en:
        return item.content_en
    return item.content_vi or item.content


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(admin_bp)

    @app.before_request
    def ensure_language():
        if session.get("lang") not in TRANSLATIONS:
            session["lang"] = "vi"

    @app.context_processor
    def inject_globals():
        current_lang = session.get("lang", "vi")

        def t(key: str) -> str:
            return TRANSLATIONS.get(current_lang, TRANSLATIONS["vi"]).get(key, key)

        return {
            "current_user": getattr(g, "current_user", None),
            "current_lang": current_lang,
            "t": t,
            "get_item_content": get_item_content,
            "current_endpoint": request.endpoint or "",
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
    app.run(debug=True, host="0.0.0.0", port=5000)
