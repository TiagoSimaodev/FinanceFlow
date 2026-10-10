import calendar
from datetime import date, timedelta
from pathlib import Path

from financeflow.db.connection import database_connection


def previous_month(month_start: date) -> date:
    return month_start - timedelta(days=1)


def last_six_months(month_start: date) -> list[str]:
    months = []
    current = month_start
    for _ in range(6):
        months.append(current.strftime("%Y-%m"))
        current = previous_month(current.replace(day=1))
    return list(reversed(months))


def get_dashboard_data(
    database_path: str | Path,
    user_id: int,
    month: str,
    transaction_type: str | None = None,
    category_id: int | None = None,
):
    month_start = date.fromisoformat(f"{month}-01")
    month_end = date(
        month_start.year,
        month_start.month,
        calendar.monthrange(month_start.year, month_start.month)[1],
    )
    prior_month_end = month_start - timedelta(days=1)
    prior_month_start = prior_month_end.replace(day=1)
    trend_months = last_six_months(month_start)

    with database_connection(database_path) as connection:
        totals = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 'receita' THEN amount_cents ELSE 0 END), 0)
                    AS income_cents,
                COALESCE(SUM(CASE WHEN type = 'despesa' THEN amount_cents ELSE 0 END), 0)
                    AS expenses_cents
            FROM transactions
            WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
            """,
            (user_id, month_start.isoformat(), month_end.isoformat()),
        ).fetchone()
        prior_expenses = connection.execute(
            """
            SELECT COALESCE(SUM(amount_cents), 0) AS previous_expenses_cents
            FROM transactions
            WHERE user_id = ? AND type = 'despesa'
                AND transaction_date BETWEEN ? AND ?
            """,
            (
                user_id,
                prior_month_start.isoformat(),
                prior_month_end.isoformat(),
            ),
        ).fetchone()["previous_expenses_cents"]
        category_rows = connection.execute(
            """
            SELECT c.id AS category_id, c.name AS category_name,
                   SUM(t.amount_cents) AS amount_cents
            FROM transactions AS t
            JOIN categories AS c ON c.id = t.category_id
            WHERE t.user_id = ? AND t.transaction_date BETWEEN ? AND ?
                AND t.type = ?
            GROUP BY c.id, c.name
            ORDER BY amount_cents DESC, lower(c.name)
            """,
            (
                user_id,
                month_start.isoformat(),
                month_end.isoformat(),
                transaction_type or "despesa",
            ),
        ).fetchall()
        monthly_conditions = [
            "user_id = ?",
            "transaction_date >= ?",
            "transaction_date <= ?",
        ]
        monthly_parameters = [
            user_id,
            f"{trend_months[0]}-01",
            month_end.isoformat(),
        ]
        if transaction_type is not None:
            monthly_conditions.append("type = ?")
            monthly_parameters.append(transaction_type)
        if category_id is not None:
            monthly_conditions.append("category_id = ?")
            monthly_parameters.append(category_id)

        monthly_rows = connection.execute(
            f"""
            SELECT substr(CAST(transaction_date AS TEXT), 1, 7) AS month,
                   COALESCE(SUM(CASE WHEN type = 'receita' THEN amount_cents ELSE 0 END), 0)
                       AS income_cents,
                   COALESCE(SUM(CASE WHEN type = 'despesa' THEN amount_cents ELSE 0 END), 0)
                       AS expenses_cents
            FROM transactions
            WHERE {" AND ".join(monthly_conditions)}
            GROUP BY substr(CAST(transaction_date AS TEXT), 1, 7)
            """,
            monthly_parameters,
        ).fetchall()

    monthly_by_period = {row["month"]: row for row in monthly_rows}
    monthly_data = []
    for period in trend_months:
        row = monthly_by_period.get(period)
        monthly_data.append(
            {
                "month": period,
                "income_cents": row["income_cents"] if row else 0,
                "expenses_cents": row["expenses_cents"] if row else 0,
            }
        )

    return {
        "month": month,
        "previous_month": prior_month_start.strftime("%Y-%m"),
        "transaction_type": transaction_type,
        "category_id": category_id,
        "income_cents": totals["income_cents"],
        "expenses_cents": totals["expenses_cents"],
        "previous_expenses_cents": prior_expenses,
        "categories": [
            {
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "amount_cents": row["amount_cents"],
            }
            for row in category_rows
        ],
        "monthly": monthly_data,
    }
