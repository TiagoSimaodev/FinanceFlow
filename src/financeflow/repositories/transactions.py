from pathlib import Path

from financeflow.db.connection import database_connection


def list_categories(database_path: str | Path, transaction_type: str | None = None):
    query = "SELECT id, name, type FROM categories"
    parameters = ()
    if transaction_type is not None:
        query += " WHERE type = ?"
        parameters = (transaction_type,)
    query += " ORDER BY lower(name)"

    with database_connection(database_path) as connection:
        return connection.execute(query, parameters).fetchall()


def category_matches_type(
    database_path: str | Path, category_id: int, transaction_type: str
) -> bool:
    with database_connection(database_path) as connection:
        return (
            connection.execute(
                "SELECT 1 FROM categories WHERE id = ? AND type = ?",
                (category_id, transaction_type),
            ).fetchone()
            is not None
        )


def create_transaction(
    database_path: str | Path,
    user_id: int,
    transaction_type: str,
    amount_cents: int,
    transaction_date: str,
    description: str,
    category_id: int,
):
    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO transactions
                (user_id, type, amount_cents, transaction_date, description, category_id)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                user_id,
                transaction_type,
                amount_cents,
                transaction_date,
                description,
                category_id,
            ),
        )
        return connection.execute(
            """
            SELECT t.id, t.type, t.amount_cents, t.transaction_date,
                   t.description, t.category_id, c.name AS category_name
            FROM transactions AS t
            JOIN categories AS c ON c.id = t.category_id
            WHERE t.id = ?
                AND t.user_id = ?
            """,
            (cursor.fetchone()["id"], user_id),
        ).fetchone()


def list_transactions(
    database_path: str | Path,
    user_id: int,
    transaction_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    category_id: int | None = None,
):
    conditions = ["t.user_id = ?"]
    parameters = [user_id]

    if transaction_type is not None:
        conditions.append("t.type = ?")
        parameters.append(transaction_type)
    if start_date is not None:
        conditions.append("t.transaction_date >= ?")
        parameters.append(start_date)
    if end_date is not None:
        conditions.append("t.transaction_date <= ?")
        parameters.append(end_date)
    if category_id is not None:
        conditions.append("t.category_id = ?")
        parameters.append(category_id)

    query = """
        SELECT t.id, t.type, t.amount_cents, t.transaction_date,
               t.description, t.category_id, c.name AS category_name
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
    """
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY t.transaction_date DESC, t.id DESC"

    with database_connection(database_path) as connection:
        return connection.execute(query, parameters).fetchall()
