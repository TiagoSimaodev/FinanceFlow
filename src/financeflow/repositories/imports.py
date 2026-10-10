from pathlib import Path

from financeflow.db.connection import database_connection, integrity_error_types


class DuplicateImportError(ValueError):
    def __init__(self, import_id: int):
        super().__init__("Este arquivo já foi importado.")
        self.import_id = import_id


def find_import_by_hash(database_path: str | Path, user_id: int, file_sha256: str):
    with database_connection(database_path) as connection:
        return connection.execute(
            "SELECT id FROM import_batches WHERE user_id = ? AND file_sha256 = ?",
            (user_id, file_sha256),
        ).fetchone()


def create_import_batch(
    database_path: str | Path, user_id: int, file_name: str, file_sha256: str
) -> int:
    try:
        with database_connection(database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_batches (user_id, file_name, file_sha256)
                VALUES (?, ?, ?)
                RETURNING id
                """,
                (user_id, file_name, file_sha256),
            )
            return cursor.fetchone()["id"]
    except integrity_error_types():
        existing = find_import_by_hash(database_path, user_id, file_sha256)
        if existing is not None:
            raise DuplicateImportError(existing["id"]) from None
        raise


def persist_import_results(
    database_path: str | Path,
    user_id: int,
    import_id: int,
    records: list[dict],
    rejections: list[dict],
    rows_processed: int,
    duration_ms: int,
) -> str:
    with database_connection(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO transactions
                (user_id, type, amount_cents, transaction_date, description,
                 category_id, source, import_batch_id)
            VALUES (?, ?, ?, ?, ?, ?, 'import', ?)
            """,
            [
                (
                    user_id,
                    record["type"],
                    record["amount_cents"],
                    record["transaction_date"],
                    record["description"],
                    record["category_id"],
                    import_id,
                )
                for record in records
            ],
        )
        connection.executemany(
            """
            INSERT INTO import_rejections
                (import_batch_id, row_number, raw_data, reason)
            VALUES (?, ?, ?, ?)
            """,
            [
                (import_id, row["row_number"], row["raw_data"], row["reason"])
                for row in rejections
            ],
        )
        status = "partial" if rejections else "succeeded"
        connection.execute(
            """
            UPDATE import_batches
            SET status = ?, finished_at = CURRENT_TIMESTAMP,
                rows_processed = ?, rows_accepted = ?, rows_rejected = ?,
                duration_ms = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                status,
                rows_processed,
                len(records),
                len(rejections),
                duration_ms,
                import_id,
                user_id,
            ),
        )
    return status


def mark_import_failed(
    database_path: str | Path,
    user_id: int,
    import_id: int,
    rows_processed: int,
    duration_ms: int,
    error_message: str,
) -> None:
    with database_connection(database_path) as connection:
        connection.execute(
            """
            UPDATE import_batches
            SET status = 'failed', finished_at = CURRENT_TIMESTAMP,
                rows_processed = ?, duration_ms = ?, error_message = ?
            WHERE id = ? AND user_id = ?
            """,
            (rows_processed, duration_ms, error_message, import_id, user_id),
        )


def list_import_batches(database_path: str | Path, user_id: int):
    with database_connection(database_path) as connection:
        return connection.execute(
            """
            SELECT id, file_name, status, started_at, finished_at,
                   rows_processed, rows_accepted, rows_rejected, duration_ms,
                   error_message
            FROM import_batches
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()


def list_import_rejections(
    database_path: str | Path, user_id: int, import_id: int
):
    with database_connection(database_path) as connection:
        return connection.execute(
            """
            SELECT row_number, raw_data, reason
            FROM import_rejections AS rejection
            JOIN import_batches AS batch ON batch.id = rejection.import_batch_id
            WHERE batch.user_id = ? AND batch.id = ?
            ORDER BY row_number
            """,
            (user_id, import_id),
        ).fetchall()


def import_exists(database_path: str | Path, user_id: int, import_id: int) -> bool:
    with database_connection(database_path) as connection:
        return (
            connection.execute(
                "SELECT 1 FROM import_batches WHERE id = ? AND user_id = ?",
                (import_id, user_id),
            ).fetchone()
            is not None
        )
