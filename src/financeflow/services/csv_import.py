import hashlib
import io
import json
import logging
import time
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from financeflow.repositories import imports as import_repository
from financeflow.repositories.transactions import list_categories
from financeflow.db.connection import database_error_types


logger = logging.getLogger(__name__)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_AMOUNT_CENTS = 2**63 - 1
MAX_DESCRIPTION_LENGTH = 200
REQUIRED_COLUMNS = {"data", "tipo", "valor", "categoria"}
OPTIONAL_COLUMNS = {"descricao"}
COLUMN_ALIASES = {
    "data": "data",
    "tipo": "tipo",
    "valor": "valor",
    "categoria": "categoria",
    "descricao": "descricao",
    "descrição": "descricao",
}


class CsvImportValidationError(ValueError):
    pass


def _normalize_header(header: str) -> str:
    return unicodedata.normalize("NFC", str(header)).strip().lstrip("\ufeff").casefold()


def _parse_date(value: str) -> str:
    raw_date = value.strip()
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw_date, date_format).date()
        except ValueError:
            continue
        if parsed.strftime(date_format) == raw_date:
            return parsed.isoformat()
    raise ValueError("Data inválida; use AAAA-MM-DD ou DD/MM/AAAA.")


def _parse_amount(value: str) -> int:
    raw_amount = value.strip().replace("R$", "").replace(" ", "")
    if not raw_amount:
        raise ValueError("Valor obrigatório.")

    if "," in raw_amount and "." in raw_amount:
        decimal_separator = "," if raw_amount.rfind(",") > raw_amount.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        raw_amount = raw_amount.replace(thousands_separator, "")
        raw_amount = raw_amount.replace(decimal_separator, ".")
    elif "," in raw_amount:
        raw_amount = raw_amount.replace(".", "").replace(",", ".")

    try:
        amount = Decimal(raw_amount)
    except InvalidOperation:
        raise ValueError("Valor monetário inválido.") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Valor deve ser maior que zero.")
    if amount > Decimal(MAX_AMOUNT_CENTS) / 100:
        raise ValueError("Valor excede o limite permitido.")
    amount_cents = amount * 100
    if amount_cents != amount_cents.to_integral_value():
        raise ValueError("Valor deve ter no máximo duas casas decimais.")
    return int(amount_cents)


def _normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    original_columns = list(dataframe.columns)
    normalized_columns = []
    for column in original_columns:
        normalized = _normalize_header(column)
        canonical = COLUMN_ALIASES.get(normalized)
        if canonical is None:
            raise CsvImportValidationError(f"Coluna não reconhecida: '{column}'.")
        normalized_columns.append(canonical)

    if len(set(normalized_columns)) != len(normalized_columns):
        raise CsvImportValidationError("O arquivo contém colunas repetidas.")
    missing_columns = REQUIRED_COLUMNS - set(normalized_columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise CsvImportValidationError(f"Colunas obrigatórias ausentes: {missing}.")

    dataframe.columns = normalized_columns
    if "descricao" not in dataframe.columns:
        dataframe["descricao"] = ""
    return dataframe


def _read_csv(file_content: bytes) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(
            io.BytesIO(file_content),
            sep=None,
            engine="python",
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
            encoding="utf-8-sig",
        )
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise CsvImportValidationError(
            "Não foi possível ler o CSV UTF-8. Confira o separador e o cabeçalho."
        ) from error

    dataframe = _normalize_dataframe(dataframe)
    if dataframe.empty:
        raise CsvImportValidationError("O CSV não contém linhas de movimentação.")
    return dataframe


def _category_lookup(database_path: str | Path):
    categories = list_categories(database_path)
    return {
        (category["name"].strip().casefold(), category["type"]): category["id"]
        for category in categories
    }


def _validate_row(row: dict, category_ids: dict) -> dict:
    transaction_type = row["tipo"].strip().casefold()
    if transaction_type not in {"receita", "despesa"}:
        raise ValueError("Tipo inválido; use receita ou despesa.")

    category_name = row["categoria"].strip()
    category_id = category_ids.get((category_name.casefold(), transaction_type))
    if category_id is None:
        raise ValueError(
            f"Categoria '{category_name}' não existe ou não corresponde ao tipo."
        )

    description = row.get("descricao", "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"Descrição deve ter no máximo {MAX_DESCRIPTION_LENGTH} caracteres."
        )

    return {
        "type": transaction_type,
        "amount_cents": _parse_amount(row["valor"]),
        "transaction_date": _parse_date(row["data"]),
        "description": description,
        "category_id": category_id,
    }


def _validate_period(period_type: str, period: str) -> tuple[str, str]:
    if period_type == "month":
        try:
            parsed_period = datetime.strptime(period, "%Y-%m").date()
        except (TypeError, ValueError) as error:
            raise CsvImportValidationError("Selecione um mês válido no formato AAAA-MM.") from error
        if parsed_period.strftime("%Y-%m") != period:
            raise CsvImportValidationError("Selecione um mês válido no formato AAAA-MM.")
        return f"{period}-01", f"{period}-31"
    if period_type == "year":
        if not isinstance(period, str) or not period.isdigit() or len(period) != 4:
            raise CsvImportValidationError("Selecione um ano válido no formato AAAA.")
        if int(period) < 1900 or int(period) > datetime.now().year:
            raise CsvImportValidationError("Selecione um ano entre 1900 e o ano atual.")
        return f"{period}-01-01", f"{period}-12-31"
    raise CsvImportValidationError("Selecione o período mensal ou anual.")


def make_csv_template(period_type: str, period: str) -> tuple[str, bytes]:
    _validate_period(period_type, period)
    prefix = "mes" if period_type == "month" else "ano"
    content = "\ufeffdata;tipo;valor;categoria;descricao\r\n"
    return f"financeflow_modelo_{prefix}_{period}.csv", content.encode("utf-8")


def import_csv(
    database_path: str | Path,
    user_id: int,
    file_name: str,
    file_content: bytes,
    period_type: str | None = None,
    period: str | None = None,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> dict:
    if not file_name.lower().endswith(".csv"):
        raise CsvImportValidationError("Envie um arquivo com extensão .csv.")
    if not file_content:
        raise CsvImportValidationError("O arquivo CSV está vazio.")
    if len(file_content) > max_file_size_bytes:
        limit_mb = max_file_size_bytes // (1024 * 1024)
        raise CsvImportValidationError(f"O arquivo excede o limite de {limit_mb} MB.")
    if (period_type is None) != (period is None):
        raise CsvImportValidationError("Informe o tipo e o período para filtrar a importação.")
    date_range = _validate_period(period_type, period) if period_type else None

    file_sha256 = hashlib.sha256(file_content).hexdigest()
    existing = import_repository.find_import_by_hash(
        database_path, user_id, file_sha256
    )
    if existing is not None:
        raise import_repository.DuplicateImportError(existing["id"])

    import_id = import_repository.create_import_batch(
        database_path, user_id, Path(file_name).name, file_sha256
    )
    started_at = time.perf_counter()
    rows_processed = 0

    try:
        dataframe = _read_csv(file_content)
        rows_processed = len(dataframe.index)
        category_ids = _category_lookup(database_path)
        records = []
        rejections = []
        seen_records = set()

        for dataframe_index, series in dataframe.iterrows():
            raw_row = {
                str(column): str(value)
                for column, value in series.to_dict().items()
            }
            row_number = int(dataframe_index) + 2
            try:
                record = _validate_row(raw_row, category_ids)
                if date_range and not date_range[0] <= record["transaction_date"] <= date_range[1]:
                    raise ValueError(
                        f"A data está fora do período selecionado ({period})."
                    )
                duplicate_key = (
                    record["type"],
                    record["amount_cents"],
                    record["transaction_date"],
                    record["category_id"],
                    record["description"].casefold(),
                )
                if duplicate_key in seen_records:
                    raise ValueError("Registro duplicado no mesmo arquivo.")
                seen_records.add(duplicate_key)
                records.append(record)
            except ValueError as error:
                rejections.append(
                    {
                        "row_number": row_number,
                        "raw_data": json.dumps(raw_row, ensure_ascii=False),
                        "reason": str(error),
                    }
                )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        status = import_repository.persist_import_results(
            database_path,
            user_id,
            import_id,
            records,
            rejections,
            rows_processed,
            duration_ms,
        )
    except (CsvImportValidationError, OSError, ValueError, *database_error_types()) as error:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        import_repository.mark_import_failed(
            database_path,
            user_id,
            import_id,
            rows_processed,
            duration_ms,
            str(error),
        )
        if isinstance(error, CsvImportValidationError):
            logger.warning(
                "CSV import id=%s failed validation: %s rows_processed=%s duration_ms=%s",
                import_id,
                error,
                rows_processed,
                duration_ms,
            )
        else:
            logger.exception(
                "CSV import id=%s failed rows_processed=%s duration_ms=%s",
                import_id,
                rows_processed,
                duration_ms,
            )
        raise

    result = {
        "import_id": import_id,
        "status": status,
        "rows_processed": rows_processed,
        "rows_accepted": len(records),
        "rows_rejected": len(rejections),
        "duration_ms": duration_ms,
    }
    return result
