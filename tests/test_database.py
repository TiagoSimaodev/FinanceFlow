import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from financeflow import create_app
from financeflow.db.connection import (
    _ConnectionAdapter,
    database_connection,
    initialize_database,
)


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "financeflow.db"

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_initialization_is_idempotent_and_seeds_categories(self):
        initialize_database(self.database_path)
        initialize_database(self.database_path)

        with database_connection(self.database_path) as connection:
            categories = connection.execute(
                "SELECT name, type FROM categories ORDER BY name"
            ).fetchall()
            user = connection.execute(
                """
                SELECT id FROM users
                WHERE google_sub = 'financeflow-test-user'
                """
            ).fetchone()

        self.assertEqual(len(categories), 14)
        self.assertIn(("Salário", "receita"), [tuple(row) for row in categories])
        self.assertTrue(
            {
                ("Água", "despesa"),
                ("Luz", "despesa"),
                ("Internet", "despesa"),
                ("Cartão de crédito", "despesa"),
                ("Moradia", "despesa"),
                ("Carro", "despesa"),
                ("Moto", "despesa"),
                ("Compras do mês", "despesa"),
                ("Telefone", "despesa"),
                ("Streaming", "despesa"),
            }.issubset({tuple(row) for row in categories})
        )
        self.assertIsNone(user)

    def test_initialization_adds_new_categories_to_an_existing_database(self):
        initialize_database(self.database_path)
        with database_connection(self.database_path) as connection:
            connection.execute(
                "DELETE FROM categories WHERE name IN (?, ?, ?)",
                ("Água", "Cartão de crédito", "Streaming"),
            )

        initialize_database(self.database_path)

        with database_connection(self.database_path) as connection:
            categories = connection.execute(
                "SELECT name FROM categories"
            ).fetchall()
        self.assertIn("Água", [category["name"] for category in categories])
        self.assertIn(
            "Cartão de crédito", [category["name"] for category in categories]
        )
        self.assertIn("Streaming", [category["name"] for category in categories])

    def test_postgresql_executemany_uses_cursor_and_converts_placeholders(self):
        raw_connection = MagicMock()
        cursor = raw_connection.cursor.return_value
        adapter = _ConnectionAdapter(raw_connection, is_postgres=True)
        parameters = (("Água", "despesa"), ("Salário", "receita"))

        adapter.executemany(
            "INSERT INTO categories (name, type) VALUES (?, ?)",
            parameters,
        )

        raw_connection.cursor.assert_called_once_with()
        cursor.executemany.assert_called_once_with(
            "INSERT INTO categories (name, type) VALUES (%s, %s)",
            parameters,
        )

    def test_database_enforces_amount_category_and_date_constraints(self):
        initialize_database(self.database_path)

        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users (google_sub, email, name)
                VALUES ('test-sub', 'test@example.invalid', 'Test')
                """
            )
            user_id = connection.execute(
                "SELECT id FROM users WHERE google_sub = 'test-sub'"
            ).fetchone()["id"]
            category_id = connection.execute(
                "SELECT id FROM categories WHERE name = 'Salário'"
            ).fetchone()["id"]
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO transactions
                        (user_id, type, amount_cents, transaction_date, category_id)
                    VALUES (?, 'receita', 0, '2026-01-15', ?)
                    """,
                    (user_id, category_id),
                )

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO transactions
                        (user_id, type, amount_cents, transaction_date, category_id)
                    VALUES (?, 'despesa', 1000, '2026-01-15', ?)
                    """,
                    (user_id, category_id),
                )

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO transactions
                        (user_id, type, amount_cents, transaction_date, category_id)
                    VALUES (?, 'despesa', 1000, '2026-01-15', -1)
                    """,
                    (user_id,),
                )

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO transactions
                        (user_id, type, amount_cents, transaction_date, category_id)
                    VALUES (?, 'receita', 1000, '2026-02-30', ?)
                    """,
                    (user_id, category_id),
                )

    def test_database_rejects_duplicate_import_file_hashes(self):
        initialize_database(self.database_path)

        with database_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users (google_sub, email, name)
                VALUES ('test-sub', 'test@example.invalid', 'Test')
                """
            )
            user_id = connection.execute(
                "SELECT id FROM users WHERE google_sub = 'test-sub'"
            ).fetchone()["id"]
            import_batch = (user_id, "movimentacoes.csv", "a" * 64)
            connection.execute(
                """
                INSERT INTO import_batches (user_id, file_name, file_sha256)
                VALUES (?, ?, ?)
                """,
                import_batch,
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO import_batches (user_id, file_name, file_sha256)
                    VALUES (?, ?, ?)
                    """,
                    import_batch,
                )

    def test_initialization_adds_owner_columns_without_claiming_old_records(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                CREATE TABLE import_batches (
                    id INTEGER PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX idx_import_batches_file_sha256
                ON import_batches (file_sha256)
                """
            )
            connection.execute(
                """
                INSERT INTO import_batches (file_name, file_sha256)
                VALUES ('legacy.csv', ?)
                """,
                ("b" * 64,),
            )
            connection.commit()
        finally:
            connection.close()

        initialize_database(self.database_path)

        with database_connection(self.database_path) as connection:
            columns = connection.execute(
                "PRAGMA table_info(import_batches)"
            ).fetchall()
            legacy_batch = connection.execute(
                "SELECT user_id, file_name FROM import_batches WHERE file_name = ?",
                ("legacy.csv",),
            ).fetchone()
            old_index = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name = ?",
                ("idx_import_batches_file_sha256",),
            ).fetchone()

        self.assertIn("user_id", [column["name"] for column in columns])
        self.assertIsNone(legacy_batch["user_id"])
        self.assertIsNone(old_index)

    def test_initialization_adds_session_version_to_existing_users(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            connection.execute(
                """
                INSERT INTO users (google_sub, email, name)
                VALUES ('legacy-sub', 'legacy@example.com', 'Legacy')
                """
            )
            connection.commit()
        finally:
            connection.close()

        initialize_database(self.database_path)

        with database_connection(self.database_path) as connection:
            legacy_user = connection.execute(
                """
                SELECT session_version FROM users
                WHERE google_sub = 'legacy-sub'
                """
            ).fetchone()
        self.assertEqual(legacy_user["session_version"], 0)

    def test_app_initializes_database_and_health_endpoint(self):
        app = create_app(
            {
                "TESTING": True,
                "AUTH_DISABLED": True,
                "DATABASE_PATH": self.database_path,
            }
        )
        response = app.test_client().get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertTrue(self.database_path.exists())

    def test_vercel_requires_a_persistent_database_url(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
            create_app({"TESTING": True, "VERCEL": True})

    def test_vercel_starts_with_database_and_secret_without_email_service(self):
        with patch("financeflow.initialize_database"):
            app = create_app(
                {
                    "TESTING": True,
                    "VERCEL": True,
                    "DATABASE_URL": "postgresql://example.invalid/financeflow",
                    "SECRET_KEY": "test-secret",
                }
            )

        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app.config["SECRET_KEY"], "test-secret")

    def test_static_assets_are_served_from_public_directory(self):
        app = create_app(
            {
                "TESTING": True,
                "AUTH_DISABLED": True,
                "DATABASE_PATH": self.database_path,
            }
        )

        response = app.test_client().get("/static/css/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b":root", response.data)
        response.close()

    def test_vercel_limits_csv_upload_size_below_function_payload_limit(self):
        with patch("financeflow.initialize_database"):
            app = create_app(
                {
                    "TESTING": True,
                    "VERCEL": True,
                    "DATABASE_URL": (
                        "postgresql://user:password@example.invalid/financeflow"
                    ),
                    "SECRET_KEY": "test-secret",
                }
            )

        self.assertEqual(app.config["CSV_MAX_FILE_SIZE_BYTES"], 4 * 1024 * 1024)
        self.assertLess(app.config["MAX_CONTENT_LENGTH"], 4.5 * 1024 * 1024)

    def test_postgresql_url_is_selected_for_app_database(self):
        database_url = "postgresql://user:password@example.invalid/financeflow"

        with patch("financeflow.initialize_database") as initialize:
            create_app({"TESTING": True, "DATABASE_URL": database_url})

        initialize.assert_called_once_with(database_url)


if __name__ == "__main__":
    unittest.main()
