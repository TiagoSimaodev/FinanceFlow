from pathlib import Path

from financeflow.db.connection import database_connection, integrity_error_types


class UserIdentityConflict(ValueError):
    pass


def get_user(database: str | Path, user_id: int):
    with database_connection(database) as connection:
        return connection.execute(
            """
            SELECT id, email, name, session_version
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()


def get_password_user(database: str | Path, email: str):
    with database_connection(database) as connection:
        return connection.execute(
            """
            SELECT users.id, users.email, users.name, users.session_version,
                   password_credentials.password_hash,
                   password_recovery_codes.code_hash AS recovery_code_hash
            FROM users
            JOIN password_credentials ON password_credentials.user_id = users.id
            LEFT JOIN password_recovery_codes
                ON password_recovery_codes.user_id = users.id
            WHERE lower(users.email) = ?
            """,
            (email,),
        ).fetchone()


def register_password_user(
    database: str | Path,
    email: str,
    name: str,
    password_hash: str,
    recovery_code_hash: str,
):
    try:
        with database_connection(database) as connection:
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
                (user["id"], password_hash),
            )
            connection.execute(
                """
                INSERT INTO password_recovery_codes (user_id, code_hash)
                VALUES (?, ?)
                """,
                (user["id"], recovery_code_hash),
            )
            return user
    except integrity_error_types() as error:
        raise UserIdentityConflict(
            "Não foi possível cadastrar uma conta com este e-mail."
        ) from error


def ensure_password_recovery_code(
    database: str | Path,
    user_id: int,
    recovery_code_hash: str,
) -> bool:
    with database_connection(database) as connection:
        result = connection.execute(
            """
            INSERT INTO password_recovery_codes (user_id, code_hash)
            VALUES (?, ?)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, recovery_code_hash),
        )
        return result.rowcount == 1


def reset_password_with_recovery_code(
    database: str | Path,
    email: str,
    recovery_code_hash: str,
    password_hash: str,
    replacement_code_hash: str,
):
    with database_connection(database) as connection:
        user = connection.execute(
            """
            SELECT users.id
            FROM users
            JOIN password_recovery_codes
                ON password_recovery_codes.user_id = users.id
            WHERE lower(users.email) = ?
                AND password_recovery_codes.code_hash = ?
            """,
            (email, recovery_code_hash),
        ).fetchone()
        if user is None:
            return None

        deleted = connection.execute(
            """
            DELETE FROM password_recovery_codes
            WHERE user_id = ? AND code_hash = ?
            """,
            (user["id"], recovery_code_hash),
        )
        if deleted.rowcount != 1:
            return None

        connection.execute(
            """
            UPDATE users
            SET session_version = session_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user["id"],),
        )
        connection.execute(
            """
            INSERT INTO password_credentials (user_id, password_hash)
            VALUES (?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                password_hash = excluded.password_hash,
                created_at = CURRENT_TIMESTAMP
            """,
            (user["id"], password_hash),
        )
        connection.execute(
            """
            INSERT INTO password_recovery_codes (user_id, code_hash)
            VALUES (?, ?)
            """,
            (user["id"], replacement_code_hash),
        )
        return connection.execute(
            """
            SELECT id, email, name, session_version
            FROM users
            WHERE id = ?
            """,
            (user["id"],),
        ).fetchone()
