from flask import Blueprint, Response, current_app, g, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from financeflow.repositories import imports as import_repository
from financeflow.repositories.imports import DuplicateImportError
from financeflow.services.csv_import import (
    CsvImportValidationError,
    import_csv,
    make_csv_template,
)


imports_blueprint = Blueprint("imports", __name__)


@imports_blueprint.errorhandler(CsvImportValidationError)
def handle_import_validation_error(error):
    return jsonify({"error": str(error)}), 400


@imports_blueprint.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    limit_mb = current_app.config["CSV_MAX_FILE_SIZE_BYTES"] // (1024 * 1024)
    return jsonify(
        {"error": f"O arquivo excede o limite de {limit_mb} MB: {error}"}
    ), 413


@imports_blueprint.get("/api/imports")
def import_history():
    batches = import_repository.list_import_batches(
        current_app.config["DATABASE_PATH"],
        g.current_user["id"],
    )
    return jsonify([dict(batch) for batch in batches])


@imports_blueprint.get("/api/imports/template")
def download_template():
    period_type = request.args.get("period_type", "")
    period = request.args.get("period", "")
    file_name, content = make_csv_template(period_type, period)
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@imports_blueprint.get("/api/imports/<int:import_id>/rejections")
def import_rejections(import_id: int):
    database_path = current_app.config["DATABASE_PATH"]
    user_id = g.current_user["id"]
    if not import_repository.import_exists(database_path, user_id, import_id):
        return jsonify({"error": "Importação não encontrada."}), 404
    rejections = import_repository.list_import_rejections(
        database_path,
        user_id,
        import_id,
    )
    return jsonify([dict(rejection) for rejection in rejections])


@imports_blueprint.post("/api/imports")
def create_import():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        raise CsvImportValidationError("Selecione um arquivo CSV para importar.")

    file_name = secure_filename(uploaded_file.filename)
    if not file_name:
        raise CsvImportValidationError("O nome do arquivo não é válido.")

    try:
        result = import_csv(
            current_app.config["DATABASE_PATH"],
            g.current_user["id"],
            file_name,
            uploaded_file.read(),
            period_type=request.form.get("period_type"),
            period=request.form.get("period"),
            max_file_size_bytes=current_app.config["CSV_MAX_FILE_SIZE_BYTES"],
        )
    except DuplicateImportError as error:
        return jsonify({"error": str(error), "import_id": error.import_id}), 409

    current_app.logger.info(
        "CSV import id=%s status=%s processed=%s accepted=%s rejected=%s duration_ms=%s",
        result["import_id"],
        result["status"],
        result["rows_processed"],
        result["rows_accepted"],
        result["rows_rejected"],
        result["duration_ms"],
    )
    return jsonify(result), 201
