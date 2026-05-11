from flask import Flask, g, redirect, request, session, url_for

from config import Config
from models import db
from routes.auth_routes import auth_bp
from routes.category_routes import category_bp
from routes.checklist_routes import checklist_bp
from routes.confirmation_routes import confirmation_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(confirmation_bp)

    @app.context_processor
    def inject_globals():
        return {
            "current_user": getattr(g, "current_user", None),
            "current_role": session.get("role"),
        }

    @app.template_filter("datetime_local")
    def datetime_local(value):
        if not value:
            return ""
        return value.strftime("%d/%m/%Y %H:%M")

    @app.template_filter("date_local")
    def date_local(value):
        if not value:
            return ""
        return value.strftime("%d/%m/%Y")

    @app.template_filter("time_local")
    def time_local(value):
        if not value:
            return ""
        return value.strftime("%H:%M")

    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
