import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import psycopg
from psycopg.rows import dict_row


DEFAULT_CATEGORIES = (
    ("Moradia", "despesa"),
    ("Alimentação", "despesa"),
    ("Transporte", "despesa"),
    ("Lazer", "despesa"),
    ("Água", "despesa"),
    ("Luz", "despesa"),
    ("Internet", "despesa"),
    ("Cartão de crédito", "despesa"),
    ("Carro", "despesa"),
    ("Moto", "despesa"),
    ("Compras do mês", "despesa"),
    ("Telefone", "despesa"),
    ("Streaming", "despesa"),
    ("Salário", "receita"),
)


class _ConnectionAdapter:
    def __init__(self, connection, is_postgres: bool):
        self._connection = connection
        self._is_postgres = is_postgres

    def execute(self, query: str, parameters=()):
        if self._is_postgres:
            query = re.sub(r"\?", "%s", query)
        return self._connection.execute(query, parameters)

    def executemany(self, query: str, parameters):
        if self._is_postgres:
            query = re.sub(r"\?", "%s", query)
            return self._connection.cursor().executemany(query, parameters)
        return self._connection.executemany(query, parameters)

    def executescript(self, script: str):
        return self._connection.executescript(script)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


@contextmanager
def database_connection(database: str | Path) -> Generator[Any, None, None]:
    database_value = str(database)
    is_postgres = database_value.startswith(("postgres://", "postgresql://"))
    if is_postgres:
        if database_value.startswith("postgres://"):
            database_value = "postgresql://" + database_value.removeprefix("postgres://")
        connection = psycopg.connect(database_value, row_factory=dict_row)
    else:
        connection = sqlite3.connect(database_value)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
    connection = _ConnectionAdapter(connection, is_postgres)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database: str | Path) -> None:
    database_value = str(database)
    is_postgres = database_value.startswith(("postgres://", "postgresql://"))
    if not is_postgres and database_value != ":memory:":
        Path(database_value).parent.mkdir(parents=True, exist_ok=True)

    schema_name = "schema_postgresql.sql" if is_postgres else "schema.sql"
    schema_path = Path(__file__).with_name(schema_name)
    statements = [
        statement.strip()
        for statement in schema_path.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]

    with database_connection(database) as connection:
        if is_postgres:
            connection.execute(statements[0])
            _ensure_user_session_version(connection, is_postgres=True)
            _ensure_owner_columns(connection, is_postgres=True)
            for statement in statements[1:]:
                connection.execute(statement)
        else:
            connection.execute(statements[0])
            _ensure_user_session_version(connection, is_postgres=False)
            _ensure_owner_columns(connection, is_postgres=False)
            connection.executescript(";\n".join(statements) + ";")
        connection.executemany(
            "INSERT INTO categories (name, type) VALUES (?, ?) ON CONFLICT DO NOTHING",
            DEFAULT_CATEGORIES,
        )


def _ensure_user_session_version(
    connection: _ConnectionAdapter,
    is_postgres: bool,
) -> None:
    if is_postgres:
        connection.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS session_version BIGINT NOT NULL DEFAULT 0
            """
        )
        return

    columns = connection.execute("PRAGMA table_info(users)").fetchall()
    if not any(column["name"] == "session_version" for column in columns):
        connection.execute(
            """
            ALTER TABLE users
            ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0
            """
        )


def _ensure_owner_columns(connection: _ConnectionAdapter, is_postgres: bool) -> None:
    tables = ("transactions", "import_batches", "goals")
    for table in tables:
        if is_postgres:
            exists = connection.execute(
                "SELECT to_regclass(?) AS table_name",
                (table,),
            ).fetchone()["table_name"]
            if exists is None:
                continue
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
                "user_id BIGINT REFERENCES users(id) ON DELETE CASCADE"
            )
            connection.execute(
                f"ALTER TABLE {table} ALTER COLUMN user_id DROP NOT NULL"
            )
        else:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if exists is None:
                continue
            columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
            if not any(column["name"] == "user_id" for column in columns):
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN "
                    "user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
                )
            elif any(
                column["name"] == "user_id" and column["notnull"]
                for column in columns
            ):
                connection.execute(
                    f"ALTER TABLE {table} ALTER COLUMN user_id DROP NOT NULL"
                )

    if is_postgres:
        batches_exist = connection.execute(
            "SELECT to_regclass(?) AS table_name",
            ("import_batches",),
        ).fetchone()["table_name"] is not None
    else:
        batches_exist = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("import_batches",),
        ).fetchone() is not None
    if batches_exist:
        connection.execute("DROP INDEX IF EXISTS idx_import_batches_file_sha256")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_import_batches_user_file_sha256
            ON import_batches (user_id, file_sha256)
            """
        )


def database_error_types() -> tuple[type[Exception], ...]:
    return (sqlite3.Error, psycopg.Error)


def integrity_error_types() -> tuple[type[Exception], ...]:
    return (sqlite3.IntegrityError, psycopg.IntegrityError)
