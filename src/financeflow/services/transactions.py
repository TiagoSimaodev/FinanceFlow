from datetime import datetime
from decimal import Decimal, InvalidOperation

from financeflow.repositories import transactions as transaction_repository


TRANSACTION_TYPES = {"receita", "despesa"}
MAX_AMOUNT_CENTS = 2**63 - 1
MAX_DESCRIPTION_LENGTH = 200


class TransactionValidationError(ValueError):
    pass


def _validate_type(value):
    if not isinstance(value, str) or value not in TRANSACTION_TYPES:
        raise TransactionValidationError("Tipo deve ser 'receita' ou 'despesa'.")
    return value


def _validate_date(value, field_name):
    if not isinstance(value, str):
        raise TransactionValidationError(f"{field_name} deve estar no formato AAAA-MM-DD.")
    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise TransactionValidationError(
            f"{field_name} deve ser uma data válida no formato AAAA-MM-DD."
        ) from error
    if parsed_date.isoformat() != value:
        raise TransactionValidationError(f"{field_name} deve estar no formato AAAA-MM-DD.")
    return value


def _validate_category_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TransactionValidationError("Categoria inválida.")
    return value


def _validate_amount(value):
    if isinstance(value, bool) or value is None:
        raise TransactionValidationError("Informe um valor monetário válido.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise TransactionValidationError("Informe um valor monetário válido.") from None
    if not amount.is_finite() or amount <= 0:
        raise TransactionValidationError("O valor deve ser maior que zero.")

    if amount > Decimal(MAX_AMOUNT_CENTS) / 100:
        raise TransactionValidationError("O valor informado excede o limite permitido.")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise TransactionValidationError("O valor deve ter no máximo duas casas decimais.")
    amount_cents = int(cents)
    return amount_cents


def _validate_description(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TransactionValidationError("Descrição deve ser um texto.")
    description = value.strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise TransactionValidationError(
            f"Descrição deve ter no máximo {MAX_DESCRIPTION_LENGTH} caracteres."
        )
    return description


def get_categories(database_path, transaction_type=None):
    if transaction_type is not None:
        transaction_type = _validate_type(transaction_type)
    return transaction_repository.list_categories(database_path, transaction_type)


def add_transaction(database_path, user_id, payload):
    if not isinstance(payload, dict):
        raise TransactionValidationError("Envie os dados da movimentação em formato JSON.")
    transaction_type = _validate_type(payload.get("type"))
    amount_cents = _validate_amount(payload.get("amount"))
    transaction_date = _validate_date(payload.get("date"), "Data")
    category_id = _validate_category_id(payload.get("category_id"))
    description = _validate_description(payload.get("description", ""))

    if not transaction_repository.category_matches_type(
        database_path, category_id, transaction_type
    ):
        raise TransactionValidationError(
            "A categoria selecionada não existe ou não corresponde ao tipo da movimentação."
        )

    return transaction_repository.create_transaction(
        database_path,
        user_id,
        transaction_type,
        amount_cents,
        transaction_date,
        description,
        category_id,
    )


def get_transactions(
    database_path,
    user_id,
    transaction_type=None,
    start_date=None,
    end_date=None,
    category_id=None,
):
    if transaction_type is not None:
        transaction_type = _validate_type(transaction_type)
    if start_date is not None:
        start_date = _validate_date(start_date, "Data inicial")
    if end_date is not None:
        end_date = _validate_date(end_date, "Data final")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise TransactionValidationError(
            "Data inicial não pode ser posterior à data final."
        )
    if category_id is not None:
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            raise TransactionValidationError("Categoria inválida.") from None
        category_id = _validate_category_id(category_id)

    return transaction_repository.list_transactions(
        database_path,
        user_id,
        transaction_type,
        start_date,
        end_date,
        category_id,
    )
