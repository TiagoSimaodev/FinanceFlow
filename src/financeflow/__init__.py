import secrets
from datetime import timedelta

from flask import (
    Flask,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFError, CSRFProtect

from financeflow.config import Config, PROJECT_ROOT
from financeflow.db.connection import database_connection, initialize_database
from financeflow.repositories.users import get_user
from financeflow.routes.auth import auth_blueprint
from financeflow.routes.dashboard import dashboard_blueprint
from financeflow.routes.imports import imports_blueprint
from financeflow.routes.transactions import transactions_blueprint


def create_app(test_config=None):
    app = Flask(
        __name__,
        static_folder=str(PROJECT_ROOT / "public" / "static"),
    )
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)
    if app.config.get("DATABASE_URL"):
        app.config["DATABASE_PATH"] = app.config["DATABASE_URL"]
    if app.config["VERCEL"]:
        required_settings = (
            "DATABASE_URL",
            "SECRET_KEY",
        )
        missing_settings = [
            setting for setting in required_settings if not app.config.get(setting)
        ]
        if missing_settings:
            raise RuntimeError(
                "Configure no Vercel as variáveis: " + ", ".join(missing_settings)
            )
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = bool(app.config["VERCEL"])
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    app.config.setdefault("WTF_CSRF_ENABLED", not app.config["TESTING"])
    app.config.setdefault(
        "CSV_MAX_FILE_SIZE_BYTES",
        (4 if app.config.get("VERCEL") else 5) * 1024 * 1024,
    )
    app.config["MAX_CONTENT_LENGTH"] = (
        app.config["CSV_MAX_FILE_SIZE_BYTES"] + 64 * 1024
    )
    if app.config.get("VERCEL") and not app.config.get("DATABASE_URL"):
        raise RuntimeError(
            "Configure DATABASE_URL ou POSTGRES_URL para usar o FinanceFlow no Vercel."
        )
    initialize_database(app.config["DATABASE_PATH"])
    csrf = CSRFProtect()
    csrf.init_app(app)

    test_user = None
    if app.config["AUTH_DISABLED"]:
        with database_connection(app.config["DATABASE_PATH"]) as connection:
            test_user = connection.execute(
                """
                INSERT INTO users (google_sub, email, name, email_verified)
                VALUES ('financeflow-test-user', 'financeflow-test@example.invalid',
                        'FinanceFlow Test', TRUE)
                ON CONFLICT (google_sub) DO UPDATE SET name = excluded.name
                RETURNING id, email, name
                """
            ).fetchone()

    @app.before_request
    def load_authenticated_user():
        if app.config["AUTH_DISABLED"]:
            g.current_user = test_user
            return None

        public_endpoints = {
            "auth.login",
            "auth.register",
            "auth.forgot_password",
            "health",
        }
        if (
            request.endpoint is None
            or request.endpoint == "static"
            or request.endpoint in public_endpoints
        ):
            return None

        user_id = session.get("user_id")
        user = get_user(app.config["DATABASE_PATH"], user_id) if user_id else None
        if (
            user is None
            or session.get("session_version") != user["session_version"]
        ):
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({"error": "Autenticação necessária."}), 401
            return redirect(url_for("auth.login"))
        g.current_user = user
        return None

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        current_app.logger.warning(
            "Rejected request with invalid CSRF token: %s",
            error.description,
        )
        if request.path.startswith("/api/"):
            return jsonify({"error": "A sessão expirou. Atualize a página e tente novamente."}), 400
        return render_template("login.html"), 400

    @app.after_request
    def prevent_token_page_caching(response):
        if request.endpoint in {"auth.register", "auth.forgot_password"}:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(transactions_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(imports_blueprint)

    @app.get("/")
    def index():
        return render_template("dashboard.html")

    @app.get("/transactions")
    def transaction_page():
        return render_template("index.html")

    @app.get("/imports")
    def import_page():
        return render_template("imports.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "application": "FinanceFlow"})

    return app
