import csv
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from openpyxl import load_workbook

from financeflow import create_app


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "financeflow.db"
        self.app = create_app(
            {"TESTING": True, "AUTH_DISABLED": True, "DATABASE_PATH": database_path}
        )
        self.client = self.app.test_client()
        categories = self.client.get("/api/categories").get_json()
        self.category_ids = {
            (category["name"], category["type"]): category["id"]
            for category in categories
        }
        self.month_start = date.today().replace(day=1)
        self.month = self.month_start.strftime("%Y-%m")
        self.previous_month_date = self.month_start - timedelta(days=1)
        self.previous_month = self.previous_month_date.strftime("%Y-%m")

    def tearDown(self):
        self.temp_directory.cleanup()

    def add_transaction(self, transaction_type, amount, date_value, category):
        return self.client.post(
            "/api/transactions",
            json={
                "type": transaction_type,
                "amount": amount,
                "date": date_value.isoformat(),
                "category_id": self.category_ids[(category, transaction_type)],
            },
        )

    def test_dashboard_calculates_period_totals_and_month_over_month_variation(self):
        self.add_transaction(
            "receita", "100.00", self.month_start, "Salário"
        )
        self.add_transaction(
            "despesa", "15.00", self.month_start + timedelta(days=2), "Alimentação"
        )
        self.add_transaction(
            "despesa", "5.00", self.month_start + timedelta(days=3), "Transporte"
        )
        self.add_transaction(
            "despesa", "10.00", self.previous_month_date.replace(day=10), "Moradia"
        )

        response = self.client.get(f"/api/dashboard?month={self.month}")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["period"]["month"], self.month)
        self.assertEqual(result["period"]["previous_month"], self.previous_month)
        self.assertEqual(
            result["totals"],
            {
                "income_cents": 10000,
                "expenses_cents": 2000,
                "balance_cents": 8000,
                "savings_rate_pct": 80.0,
                "previous_expenses_cents": 1000,
                "expense_variation_pct": 100.0,
            },
        )
        self.assertEqual(
            [category["category_name"] for category in result["categories"]],
            ["Alimentação", "Transporte"],
        )
        self.assertEqual(
            [category["amount_cents"] for category in result["categories"]],
            [1500, 500],
        )
        self.assertEqual(len(result["monthly"]), 6)
        previous_period = next(
            item for item in result["monthly"] if item["month"] == self.previous_month
        )
        self.assertEqual(previous_period["expenses_cents"], 1000)
        self.assertEqual(result["monthly"][-1]["month"], self.month)

    def test_empty_period_returns_zero_totals_and_undefined_percentages(self):
        response = self.client.get(f"/api/dashboard?month={self.month}")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["totals"]["income_cents"], 0)
        self.assertEqual(result["totals"]["expenses_cents"], 0)
        self.assertEqual(result["totals"]["balance_cents"], 0)
        self.assertIsNone(result["totals"]["savings_rate_pct"])
        self.assertIsNone(result["totals"]["expense_variation_pct"])
        self.assertEqual(result["categories"], [])
        self.assertEqual(len(result["monthly"]), 6)
        self.assertTrue(
            all(
                item["income_cents"] == item["expenses_cents"] == 0
                for item in result["monthly"]
            )
        )

    def test_invalid_or_future_month_is_rejected(self):
        invalid = self.client.get("/api/dashboard?month=2026-13")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("formato AAAA-MM", invalid.get_json()["error"])

        next_month = self.month_start.replace(day=28) + timedelta(days=4)
        next_month = next_month.replace(day=1)
        future = self.client.get(f"/api/dashboard?month={next_month:%Y-%m}")
        self.assertEqual(future.status_code, 400)
        self.assertIn("futuro", future.get_json()["error"])

    def test_dashboard_page_includes_theme_switch(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Modo escuro".encode(), response.data)
        self.assertIn(b"Baixar CSV", response.data)
        self.assertIn(b"Baixar Excel", response.data)
        self.assertEqual(response.data.count(b"data-export-chart="), 2)

    def test_csv_export_respects_month_and_category_and_prevents_formula_injection(self):
        self.add_transaction(
            "despesa",
            "12.34",
            self.month_start + timedelta(days=1),
            "Alimentação",
        )
        created = self.client.post(
            "/api/transactions",
            json={
                "type": "despesa",
                "amount": "89.90",
                "date": (self.month_start + timedelta(days=2)).isoformat(),
                "category_id": self.category_ids[("Água", "despesa")],
                "description": "=HYPERLINK(\"https://example.com\")",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.add_transaction(
            "despesa",
            "25.00",
            self.previous_month_date.replace(day=10),
            "Água",
        )

        response = self.client.get(
            "/api/dashboard/export",
            query_string={
                "format": "csv",
                "month": self.month,
                "type": "despesa",
                "category_id": self.category_ids[("Água", "despesa")],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn(
            f'filename=financeflow-movimentacoes-{self.month}.csv',
            response.headers["Content-Disposition"],
        )
        rows = list(
            csv.reader(
                io.StringIO(response.data.decode("utf-8-sig")),
                delimiter=";",
            )
        )
        self.assertEqual(
            rows[0], ["Data", "Tipo", "Categoria", "Descrição", "Valor (R$)"]
        )
        self.assertEqual(
            rows[1],
            [
                (self.month_start + timedelta(days=2)).strftime("%d/%m/%Y"),
                "Despesa",
                "Água",
                "'=HYPERLINK(\"https://example.com\")",
                "89,90",
            ],
        )
        self.assertEqual(len(rows), 2)

    def test_excel_export_has_formatted_date_and_numeric_currency(self):
        transaction_date = self.month_start + timedelta(days=4)
        self.client.post(
            "/api/transactions",
            json={
                "type": "receita",
                "amount": "2500.75",
                "date": transaction_date.isoformat(),
                "category_id": self.category_ids[("Salário", "receita")],
                "description": "=1+1",
            },
        )

        response = self.client.get(
            "/api/dashboard/export",
            query_string={"format": "xlsx", "month": self.month},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response.content_type,
        )
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        worksheet = workbook["Movimentações"]
        self.assertEqual(
            [cell.value for cell in worksheet[1]],
            ["Data", "Tipo", "Categoria", "Descrição", "Valor (R$)"],
        )
        self.assertEqual(worksheet["A2"].value.date(), transaction_date)
        self.assertEqual(worksheet["A2"].number_format, "dd/mm/yyyy")
        self.assertEqual(worksheet["B2"].value, "Receita")
        self.assertEqual(worksheet["C2"].value, "Salário")
        self.assertEqual(worksheet["D2"].value, "'=1+1")
        self.assertEqual(worksheet["D2"].data_type, "s")
        self.assertEqual(worksheet["E2"].value, 2500.75)
        self.assertEqual(worksheet["E2"].number_format, '"R$" #,##0.00')
        self.assertEqual(worksheet.freeze_panes, "A2")

    def test_export_rejects_unknown_format(self):
        response = self.client.get(
            "/api/dashboard/export",
            query_string={"format": "pdf", "month": self.month},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("csv ou xlsx", response.get_json()["error"])

    def test_category_filter_shows_salary_or_one_expense_in_chart_data(self):
        self.add_transaction("receita", "2500.00", self.month_start, "Salário")
        self.add_transaction("despesa", "60.00", self.month_start, "Alimentação")
        self.add_transaction("despesa", "40.00", self.month_start, "Transporte")

        salary_id = self.category_ids[("Salário", "receita")]
        salary_result = self.client.get(
            f"/api/dashboard?month={self.month}&category_id={salary_id}"
        ).get_json()

        self.assertEqual(salary_result["period"]["type"], "receita")
        self.assertEqual(salary_result["totals"]["income_cents"], 250000)
        self.assertEqual(salary_result["totals"]["expenses_cents"], 10000)
        self.assertEqual(salary_result["monthly"][-1]["income_cents"], 250000)
        self.assertEqual(salary_result["monthly"][-1]["expenses_cents"], 0)
        self.assertEqual(
            [category["category_name"] for category in salary_result["categories"]],
            ["Salário"],
        )

        food_id = self.category_ids[("Alimentação", "despesa")]
        food_result = self.client.get(
            f"/api/dashboard?month={self.month}&type=despesa&category_id={food_id}"
        ).get_json()
        self.assertEqual(food_result["period"]["type"], "despesa")
        self.assertEqual(food_result["monthly"][-1]["expenses_cents"], 6000)
        self.assertEqual(food_result["monthly"][-1]["income_cents"], 0)
        self.assertEqual(
            [category["category_name"] for category in food_result["categories"]],
            ["Alimentação", "Transporte"],
        )

    def test_dashboard_rejects_nonexistent_or_mismatched_category(self):
        nonexistent = self.client.get(
            f"/api/dashboard?month={self.month}&category_id=99999"
        )
        mismatched = self.client.get(
            f"/api/dashboard?month={self.month}&type=despesa"
            f"&category_id={self.category_ids[('Salário', 'receita')]}"
        )

        self.assertEqual(nonexistent.status_code, 400)
        self.assertIn("não encontrada", nonexistent.get_json()["error"])
        self.assertEqual(mismatched.status_code, 400)
        self.assertIn("não corresponde", mismatched.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
