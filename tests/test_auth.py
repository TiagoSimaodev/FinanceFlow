import hashlib
import io
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from financeflow import create_app
from financeflow.db.connection import database_connection


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "financeflow.db"
        self.app = create_app(
            {"TESTING": True, "DATABASE_PATH": self.database_path}
        )
        self.client = self.app.test_client()
        self.user_a = self.create_user(
            "a@example.com", "User A", "password-a-123", "user-a-recovery-code"
        )
        self.user_b = self.create_user(
            "b@example.com", "User B", "password-b-123", "user-b-recovery-code"
        )
        self.login_as(self.user_a)
        self.category_ids = {
            (item["name"], item["type"]): item["id"]
            for item in self.client.get("/api/categories").get_json()
        }
        with self.client.session_transaction() as session:
            session.clear()

    def tearDown(self):
        self.temp_directory.cleanup()

    def create_user(self, email, name, password, recovery_code=None):
        with database_connection(self.database_path) as connection:
            user = connection.execute(
                """
                INSERT INTO users (google_sub, email, name, email_verified)
                VALUES (?, ?, ?, TRUE)
                RETURNING id, email, name, session_version
                """,
                (f"email-password:{email}", email, name),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO password_credentials (user_id, password_hash)
                VALUES (?, ?)
                """,
                (user["id"], generate_password_hash(password)),
            )
            if recovery_code:
                connection.execute(
                    """
                    INSERT INTO password_recovery_codes (user_id, code_hash)
                    VALUES (?, ?)
                    """,
                    (user["id"], self.code_hash(recovery_code)),
                )
        return user

    @staticmethod
    def code_hash(code):
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    @staticmethod
    def code_from_response(response):
        match = re.search(
            rb'<div class="recovery-code"[^>]*>\s*<code>([^<]+)</code>',
            response.data,
        )
        if match is None:
            raise AssertionError("Recovery code was not shown in the response.")
        return match.group(1).decode()

    def login_as(self, user, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["session_version"] = user["session_version"]

    def test_private_pages_and_apis_require_login(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.get("/").location, "/login")
        response = self.client.get("/api/transactions")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Autenticação necessária.")
        export = self.client.get("/api/dashboard/export?format=csv")
        self.assertEqual(export.status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/login").status_code, 200)

    def test_password_login_creates_authenticated_session(self):
        response = self.client.post(
            "/login",
            data={"email": "A@EXAMPLE.COM", "password": "password-a-123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")
        self.assertEqual(
            self.client.get("/api/me").get_json()["email"], "a@example.com"
        )

    def test_password_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/login",
            data={"email": "a@example.com", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("E-mail ou senha inválidos", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_registration_validates_fields(self):
        invalid_email = self.client.post(
            "/register",
            data={"name": "Test", "email": "invalid", "password": "password-123"},
        )
        weak_password = self.client.post(
            "/register",
            data={"name": "Test", "email": "test@example.com", "password": "short"},
        )

        self.assertEqual(invalid_email.status_code, 400)
        self.assertEqual(weak_password.status_code, 400)

    def test_registration_creates_account_and_shows_recovery_code_once(self):
        response = self.client.post(
            "/register",
            data={
                "name": "New User",
                "email": "New.User@Example.com",
                "password": "safe-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        code = self.code_from_response(response)
        self.assertIn("exibido uma única vez", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/api/me").get_json()["email"], "new.user@example.com")

        with database_connection(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT users.email, password_credentials.password_hash,
                       password_recovery_codes.code_hash
                FROM users
                JOIN password_credentials ON password_credentials.user_id = users.id
                JOIN password_recovery_codes
                    ON password_recovery_codes.user_id = users.id
                WHERE users.email = 'new.user@example.com'
                """
            ).fetchone()
        self.assertTrue(check_password_hash(row["password_hash"], "safe-password-123"))
        self.assertEqual(row["code_hash"], self.code_hash(code))
        self.assertNotEqual(row["code_hash"], code)
        self.assertNotIn(code, response.headers.get("Set-Cookie", ""))

        repeated_get = self.client.get("/register")
        self.assertNotIn(code, repeated_get.get_data(as_text=True))

    def test_registration_rejects_duplicate_email_without_changing_account(self):
        response = self.client.post(
            "/register",
            data={
                "name": "Attacker",
                "email": "A@EXAMPLE.COM",
                "password": "different-password",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Não foi possível criar", response.get_data(as_text=True))
        login = self.client.post(
            "/login",
            data={"email": "a@example.com", "password": "password-a-123"},
        )
        self.assertEqual(login.status_code, 302)

    def test_login_shows_a_recovery_code_for_an_existing_account_without_one(self):
        user = self.create_user(
            "legacy@example.com", "Legacy user", "legacy-password-123"
        )
        response = self.client.post(
            "/login",
            data={
                "email": "legacy@example.com",
                "password": "legacy-password-123",
            },
        )

        code = self.code_from_response(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/me").get_json()["id"], user["id"])
        with database_connection(self.database_path) as connection:
            stored_hash = connection.execute(
                """
                SELECT code_hash FROM password_recovery_codes WHERE user_id = ?
                """,
                (user["id"],),
            ).fetchone()["code_hash"]
        self.assertEqual(stored_hash, self.code_hash(code))

    def test_recovery_requires_matching_email_and_code(self):
        self.create_user(
            "recover@example.com",
            "Recover",
            "old-password-123",
            "correct-recovery-code",
        )
        response = self.client.post(
            "/forgot-password",
            data={
                "email": "a@example.com",
                "recovery_code": "wrong-code",
                "password": "new-password-123",
                "password_confirmation": "new-password-123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("inválido", response.get_data(as_text=True))
        old_password = self.client.post(
            "/login",
            data={"email": "a@example.com", "password": "password-a-123"},
        )
        self.assertEqual(old_password.status_code, 302)

    def test_recovery_rotates_code_and_invalidates_existing_sessions(self):
        recovery_code = "secret-recovery-code"
        user = self.create_user(
            "recover@example.com",
            "Recover",
            "old-password-123",
            recovery_code,
        )
        old_session = self.app.test_client()
        self.login_as(user, old_session)

        response = self.client.post(
            "/forgot-password",
            data={
                "email": "RECOVER@example.com",
                "recovery_code": recovery_code,
                "password": "new-password-123",
                "password_confirmation": "new-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Senha alterada", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        new_code = self.code_from_response(response)
        self.assertNotEqual(new_code, recovery_code)
        self.assertEqual(old_session.get("/api/me").status_code, 401)

        with database_connection(self.database_path) as connection:
            stored_hash = connection.execute(
                """
                SELECT password_recovery_codes.code_hash,
                       password_credentials.password_hash
                FROM password_recovery_codes
                JOIN password_credentials
                    ON password_credentials.user_id = password_recovery_codes.user_id
                WHERE password_recovery_codes.user_id = ?
                """,
                (user["id"],),
            ).fetchone()
        self.assertEqual(stored_hash["code_hash"], self.code_hash(new_code))
        self.assertTrue(
            check_password_hash(stored_hash["password_hash"], "new-password-123")
        )

        old_code_again = self.client.post(
            "/forgot-password",
            data={
                "email": "recover@example.com",
                "recovery_code": recovery_code,
                "password": "third-password-123",
                "password_confirmation": "third-password-123",
            },
        )
        self.assertEqual(old_code_again.status_code, 400)

        new_password_login = self.client.post(
            "/login",
            data={"email": "recover@example.com", "password": "new-password-123"},
        )
        self.assertEqual(new_password_login.status_code, 302)

    def test_recovery_rotated_code_can_be_used_once_for_next_recovery(self):
        initial_code = "first-recovery-code"
        self.create_user(
            "rotate@example.com", "Rotate", "old-password-123", initial_code
        )
        first_reset = self.client.post(
            "/forgot-password",
            data={
                "email": "rotate@example.com",
                "recovery_code": initial_code,
                "password": "second-password-123",
                "password_confirmation": "second-password-123",
            },
        )
        second_code = self.code_from_response(first_reset)
        second_reset = self.client.post(
            "/forgot-password",
            data={
                "email": "rotate@example.com",
                "recovery_code": second_code,
                "password": "third-password-123",
                "password_confirmation": "third-password-123",
            },
        )

        self.assertEqual(second_reset.status_code, 200)
        self.assertNotEqual(self.code_from_response(second_reset), second_code)

    def test_recovery_rejects_password_mismatch_and_invalid_password_length(self):
        code = "secret-recovery-code"
        self.create_user(
            "recover@example.com", "Recover", "old-password-123", code
        )
        mismatch = self.client.post(
            "/forgot-password",
            data={
                "email": "recover@example.com",
                "recovery_code": code,
                "password": "new-password-123",
                "password_confirmation": "different-password",
            },
        )
        too_long = self.client.post(
            "/forgot-password",
            data={
                "email": "recover@example.com",
                "recovery_code": code,
                "password": "x" * 129,
                "password_confirmation": "x" * 129,
            },
        )

        self.assertEqual(mismatch.status_code, 400)
        self.assertIn("não conferem", mismatch.get_data(as_text=True))
        self.assertEqual(too_long.status_code, 400)

    def test_csrf_protects_password_recovery(self):
        csrf_app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": self.database_path,
                "WTF_CSRF_ENABLED": True,
            }
        )
        client = csrf_app.test_client()
        code = "csrf-recovery-code"
        self.create_user(
            "csrf@example.com", "CSRF", "old-password-123", code
        )
        page = client.get("/forgot-password")
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', page.data
        ).group(1).decode()
        form = {
            "email": "csrf@example.com",
            "recovery_code": code,
            "password": "new-password-123",
            "password_confirmation": "new-password-123",
        }

        rejected = client.post("/forgot-password", data=form)
        accepted = client.post(
            "/forgot-password",
            data={**form, "csrf_token": csrf_token},
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 200)

    def test_transactions_are_only_visible_to_their_owner(self):
        self.login_as(self.user_a)
        created = self.client.post(
            "/api/transactions",
            json={
                "type": "despesa",
                "amount": "19.90",
                "date": "2026-10-10",
                "category_id": self.category_ids[("Alimentação", "despesa")],
                "description": "Mercado privado",
            },
        )
        self.assertEqual(created.status_code, 201)

        self.login_as(self.user_b)
        self.assertEqual(self.client.get("/api/transactions").get_json(), [])
        dashboard = self.client.get("/api/dashboard").get_json()
        self.assertEqual(dashboard["totals"]["expenses_cents"], 0)

    def test_exports_are_scoped_to_the_authenticated_user(self):
        self.login_as(self.user_a)
        transaction_date = date.today()
        created = self.client.post(
            "/api/transactions",
            json={
                "type": "despesa",
                "amount": "19.90",
                "date": transaction_date.isoformat(),
                "category_id": self.category_ids[("Alimentação", "despesa")],
                "description": "Privado da conta A",
            },
        )
        self.assertEqual(created.status_code, 201)

        self.login_as(self.user_b)
        response = self.client.get(
            "/api/dashboard/export",
            query_string={
                "format": "csv",
                "month": transaction_date.strftime("%Y-%m"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Privado da conta A", response.data)
        self.assertEqual(response.data.count(b"\r\n"), 1)

    def test_import_history_and_rejections_are_scoped_to_the_user(self):
        content = (
            b"data;tipo;valor;categoria;descricao\n"
            b"2026-10-10;despesa;1.00;categoria inexistente;Falha\n"
        )
        self.login_as(self.user_a)
        uploaded = self.client.post(
            "/api/imports",
            data={"file": (io.BytesIO(content), "private.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(uploaded.status_code, 201)
        import_id = uploaded.get_json()["import_id"]
        self.assertEqual(len(self.client.get("/api/imports").get_json()), 1)

        self.login_as(self.user_b)
        second_user_upload = self.client.post(
            "/api/imports",
            data={"file": (io.BytesIO(content), "private.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(second_user_upload.status_code, 201)
        self.assertEqual(len(self.client.get("/api/imports").get_json()), 1)
        self.assertEqual(
            self.client.get(f"/api/imports/{import_id}/rejections").status_code,
            404,
        )

    def test_logout_clears_authenticated_session(self):
        self.login_as(self.user_a)

        response = self.client.post("/auth/logout")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/login")
        self.assertEqual(self.client.get("/api/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
