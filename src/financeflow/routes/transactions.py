from flask import Blueprint, current_app, g, jsonify, request

from financeflow.services.transactions import (
    TransactionValidationError,
    add_transaction,
    get_categories,
    get_transactions,
)


transactions_blueprint = Blueprint("transactions", __name__)


def _serialize_transaction(transaction):
    return {
        "id": transaction["id"],
        "type": transaction["type"],
        "amount_cents": transaction["amount_cents"],
        "date": transaction["transaction_date"],
        "description": transaction["description"],
        "category_id": transaction["category_id"],
        "category_name": transaction["category_name"],
    }


@transactions_blueprint.errorhandler(TransactionValidationError)
def handle_validation_error(error):
    return jsonify({"error": str(error)}), 400


@transactions_blueprint.get("/api/categories")
def categories():
    transaction_type = request.args.get("type")
    category_rows = get_categories(current_app.config["DATABASE_PATH"], transaction_type)
    return jsonify(
        [
            {"id": category["id"], "name": category["name"], "type": category["type"]}
            for category in category_rows
        ]
    )


@transactions_blueprint.route("/api/transactions", methods=["GET", "POST"])
def transactions():
    database_path = current_app.config["DATABASE_PATH"]

    if request.method == "POST":
        if not request.is_json:
            raise TransactionValidationError("Envie a movimentação como JSON.")
        transaction = add_transaction(
            database_path,
            g.current_user["id"],
            request.get_json(silent=True),
        )
        return jsonify(_serialize_transaction(transaction)), 201

    transaction_rows = get_transactions(
        database_path,
        user_id=g.current_user["id"],
        transaction_type=request.args.get("type"),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
        category_id=request.args.get("category_id"),
    )
    return jsonify([_serialize_transaction(row) for row in transaction_rows])
