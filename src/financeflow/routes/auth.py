import hashlib
import re
import secrets

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from financeflow.repositories.users import (
    UserIdentityConflict,
    ensure_password_recovery_code,
    get_password_user,
    register_password_user,
    reset_password_with_recovery_code,
)


auth_blueprint = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


def _new_recovery_code() -> str:
    return secrets.token_urlsafe(32)


def _recovery_code_hash(recovery_code: str) -> str:
    return hashlib.sha256(recovery_code.encode("utf-8")).hexdigest()


def _start_session(user) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["session_version"] = user["session_version"]
    session.permanent = True


def _render_recovery_code(recovery_code: str, notice: str | None = None):
    response = current_app.make_response(
        render_template(
            "recovery_code.html",
            recovery_code=recovery_code,
            notice=notice,
        )
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        user = get_password_user(current_app.config["DATABASE_PATH"], email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("E-mail ou senha inválidos.", "error")
            return render_template("login.html"), 401

        _start_session(user)
        if user["recovery_code_hash"] is None:
            recovery_code = _new_recovery_code()
            created = ensure_password_recovery_code(
                current_app.config["DATABASE_PATH"],
                user["id"],
                _recovery_code_hash(recovery_code),
            )
            if created:
                return _render_recovery_code(
                    recovery_code,
                    "Guarde seu código de recuperação para não perder o acesso.",
                )
        return redirect(url_for("index"))
    return render_template("login.html"), 200


@auth_blueprint.route("/register", methods=["GET", "POST"])
def register():
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("register.html"), 200

    email = request.form.get("email", "").strip().casefold()
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        flash("Informe um endereço de e-mail válido.", "error")
        return render_template("register.html"), 400
    if not name or len(name) > 100:
        flash("Informe seu nome (até 100 caracteres).", "error")
        return render_template("register.html"), 400
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        flash(
            f"A senha deve ter entre {MIN_PASSWORD_LENGTH} e "
            f"{MAX_PASSWORD_LENGTH} caracteres.",
            "error",
        )
        return render_template("register.html"), 400

    recovery_code = _new_recovery_code()
    try:
        user = register_password_user(
            current_app.config["DATABASE_PATH"],
            email,
            name,
            generate_password_hash(password),
            _recovery_code_hash(recovery_code),
        )
    except UserIdentityConflict:
        flash(
            "Não foi possível criar a conta com esses dados. "
            "Se você já tem uma conta, tente entrar.",
            "error",
        )
        return render_template("register.html"), 409

    _start_session(user)
    return _render_recovery_code(recovery_code)


@auth_blueprint.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html"), 200

    email = request.form.get("email", "").strip().casefold()
    recovery_code = request.form.get("recovery_code", "").strip()
    password = request.form.get("password", "")
    confirmation = request.form.get("password_confirmation", "")

    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        flash(
            f"A senha deve ter entre {MIN_PASSWORD_LENGTH} e "
            f"{MAX_PASSWORD_LENGTH} caracteres.",
            "error",
        )
        return render_template("forgot_password.html"), 400
    if password != confirmation:
        flash("As senhas não conferem.", "error")
        return render_template("forgot_password.html"), 400
    if (
        len(email) > 254
        or not EMAIL_PATTERN.fullmatch(email)
        or len(recovery_code) > 128
    ):
        flash("E-mail ou código de recuperação inválido.", "error")
        return render_template("forgot_password.html"), 400

    replacement_code = _new_recovery_code()
    user = reset_password_with_recovery_code(
        current_app.config["DATABASE_PATH"],
        email,
        _recovery_code_hash(recovery_code),
        generate_password_hash(password),
        _recovery_code_hash(replacement_code),
    )
    if user is None:
        flash("E-mail ou código de recuperação inválido.", "error")
        return render_template("forgot_password.html"), 400

    _start_session(user)
    return _render_recovery_code(
        replacement_code,
        "Senha alterada. Este novo código substitui o anterior; guarde-o.",
    )


@auth_blueprint.post("/auth/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for("auth.login"))


@auth_blueprint.get("/api/me")
def current_user():
    return jsonify(
        {
            "id": g.current_user["id"],
            "email": g.current_user["email"],
            "name": g.current_user["name"],
        }
    )
