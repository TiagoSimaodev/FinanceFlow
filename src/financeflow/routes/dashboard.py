import calendar
from datetime import date
from io import BytesIO

from flask import Blueprint, current_app, g, jsonify, request, send_file

from financeflow.repositories.transactions import list_transactions
from financeflow.services.dashboard import DashboardValidationError, get_dashboard
from financeflow.services.report_export import export_transactions


dashboard_blueprint = Blueprint("dashboard", __name__)


@dashboard_blueprint.errorhandler(DashboardValidationError)
def handle_dashboard_validation_error(error):
    return jsonify({"error": str(error)}), 400


@dashboard_blueprint.get("/api/dashboard")
def dashboard_data():
    data = get_dashboard(
        current_app.config["DATABASE_PATH"],
        user_id=g.current_user["id"],
        month=request.args.get("month"),
        transaction_type=request.args.get("type"),
        category_id=request.args.get("category_id"),
    )
    return jsonify(data)


@dashboard_blueprint.get("/api/dashboard/export")
def export_dashboard_transactions():
    file_format = request.args.get("format", "")
    if file_format not in {"csv", "xlsx"}:
        return jsonify({"error": "Formato deve ser csv ou xlsx."}), 400

    data = get_dashboard(
        current_app.config["DATABASE_PATH"],
        user_id=g.current_user["id"],
        month=request.args.get("month"),
        transaction_type=request.args.get("type"),
        category_id=request.args.get("category_id"),
    )
    month_start = date.fromisoformat(f"{data['period']['month']}-01")
    month_end = date(
        month_start.year,
        month_start.month,
        calendar.monthrange(month_start.year, month_start.month)[1],
    )
    rows = list_transactions(
        current_app.config["DATABASE_PATH"],
        user_id=g.current_user["id"],
        transaction_type=data["period"]["type"],
        start_date=month_start.isoformat(),
        end_date=month_end.isoformat(),
        category_id=data["period"]["category_id"],
    )
    content, mimetype, filename = export_transactions(
        rows, file_format, data["period"]["month"]
    )
    return send_file(
        BytesIO(content),
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )
