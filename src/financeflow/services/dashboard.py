from datetime import date, datetime
from decimal import Decimal

from financeflow.repositories.dashboard import get_dashboard_data
from financeflow.repositories.transactions import category_matches_type, list_categories


class DashboardValidationError(ValueError):
    pass


def _validate_month(month):
    if not isinstance(month, str):
        raise DashboardValidationError("Informe o período no formato AAAA-MM.")
    try:
        parsed_month = datetime.strptime(month, "%Y-%m").date()
    except ValueError as error:
        raise DashboardValidationError(
            "Informe um período válido no formato AAAA-MM."
        ) from error
    if parsed_month.strftime("%Y-%m") != month:
        raise DashboardValidationError("Informe um período válido no formato AAAA-MM.")
    if parsed_month > date.today().replace(day=1):
        raise DashboardValidationError("O período não pode estar no futuro.")
    return month


def get_dashboard(
    database_path,
    user_id,
    month: str | None = None,
    transaction_type: str | None = None,
    category_id: int | str | None = None,
):
    month = _validate_month(month or date.today().strftime("%Y-%m"))
    if transaction_type not in {None, "receita", "despesa"}:
        raise DashboardValidationError("Tipo deve ser receita ou despesa.")
    if category_id is not None:
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            raise DashboardValidationError("Categoria inválida.") from None
        if category_id <= 0:
            raise DashboardValidationError("Categoria inválida.")
        if transaction_type is not None and not category_matches_type(
            database_path, category_id, transaction_type
        ):
            raise DashboardValidationError(
                "A categoria selecionada não corresponde ao tipo informado."
            )
        if transaction_type is None:
            categories = list_categories(database_path)
            selected_category = next(
                (category for category in categories if category["id"] == category_id),
                None,
            )
            if selected_category is None:
                raise DashboardValidationError("Categoria não encontrada.")
            transaction_type = selected_category["type"]

    data = get_dashboard_data(
        database_path,
        user_id,
        month,
        transaction_type,
        category_id,
    )

    income_cents = data["income_cents"]
    expenses_cents = data["expenses_cents"]
    previous_expenses_cents = data["previous_expenses_cents"]
    savings_rate_pct = (
        round(float(Decimal(income_cents - expenses_cents) / income_cents * 100), 2)
        if income_cents
        else None
    )
    expense_variation_pct = (
        round(
            float(
                Decimal(expenses_cents - previous_expenses_cents)
                / previous_expenses_cents
                * 100
            ),
            2,
        )
        if previous_expenses_cents
        else None
    )

    return {
        "period": {
            "month": data["month"],
            "previous_month": data["previous_month"],
            "type": transaction_type,
            "category_id": category_id,
        },
        "totals": {
            "income_cents": income_cents,
            "expenses_cents": expenses_cents,
            "balance_cents": income_cents - expenses_cents,
            "savings_rate_pct": savings_rate_pct,
            "previous_expenses_cents": previous_expenses_cents,
            "expense_variation_pct": expense_variation_pct,
        },
        "categories": data["categories"],
        "monthly": data["monthly"],
    }
