import tempfile
import unittest
from pathlib import Path

from financeflow import create_app


class TransactionApiTests(unittest.TestCase):
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

    def tearDown(self):
        self.temp_directory.cleanup()

    def create_transaction(
        self,
        transaction_type="despesa",
        amount="12.34",
        date="2026-10-10",
        category_name="Alimentação",
        description="  Almoço  ",
    ):
        return self.client.post(
            "/api/transactions",
            json={
                "type": transaction_type,
                "amount": amount,
                "date": date,
                "category_id": self.category_ids[(category_name, transaction_type)],
                "description": description,
            },
        )

    def test_categories_can_be_filtered_by_type(self):
        response = self.client.get("/api/categories?type=receita")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json())
        self.assertTrue(all(item["type"] == "receita" for item in response.get_json()))

    def test_expense_categories_are_available_for_entry_and_filters(self):
        response = self.client.get("/api/categories?type=despesa")

        self.assertEqual(response.status_code, 200)
        names = {category["name"] for category in response.get_json()}
        self.assertTrue(
            {
                "Água",
                "Luz",
                "Internet",
                "Cartão de crédito",
                "Moradia",
                "Carro",
                "Moto",
                "Compras do mês",
                "Telefone",
                "Streaming",
            }.issubset(names)
        )
        water_id = self.category_ids[("Água", "despesa")]
        created = self.client.post(
            "/api/transactions",
            json={
                "type": "despesa",
                "amount": "89.90",
                "date": "2026-10-10",
                "category_id": water_id,
                "description": "Conta de água",
            },
        )
        self.assertEqual(created.status_code, 201)
        filtered = self.client.get(
            "/api/transactions",
            query_string={"category_id": water_id},
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.get_json()), 1)
        self.assertEqual(filtered.get_json()[0]["category_name"], "Água")
        self.assertEqual(
            self.client.get("/api/categories?type=receita").get_json()[0]["name"],
            "Salário",
        )

    def test_create_and_list_transaction_with_amount_in_cents(self):
        response = self.create_transaction()

        self.assertEqual(response.status_code, 201)
        transaction = response.get_json()
        self.assertEqual(transaction["amount_cents"], 1234)
        self.assertEqual(transaction["description"], "Almoço")
        self.assertEqual(transaction["category_name"], "Alimentação")

        listed = self.client.get("/api/transactions")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json(), [transaction])

    def test_listing_filters_by_type_category_and_date_range(self):
        self.create_transaction()
        self.create_transaction(
            transaction_type="receita",
            amount="3500.00",
            date="2026-10-12",
            category_name="Salário",
            description="Pagamento",
        )
        self.create_transaction(
            amount="8.00",
            date="2026-09-30",
            description="Compra antiga",
        )

        response = self.client.get(
            "/api/transactions",
            query_string={
                "type": "despesa",
                "category_id": self.category_ids[("Alimentação", "despesa")],
                "start_date": "2026-10-01",
                "end_date": "2026-10-31",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 1)
        self.assertEqual(response.get_json()[0]["description"], "Almoço")

    def test_invalid_amount_type_date_and_category_are_rejected(self):
        invalid_payloads = (
            {"type": "outro", "amount": "10", "date": "2026-10-10",
             "category_id": self.category_ids[("Alimentação", "despesa")]},
            {"type": "despesa", "amount": "0", "date": "2026-10-10",
             "category_id": self.category_ids[("Alimentação", "despesa")]},
            {"type": "despesa", "amount": "1.001", "date": "2026-10-10",
             "category_id": self.category_ids[("Alimentação", "despesa")]},
            {"type": "despesa", "amount": "10", "date": "2026-02-30",
             "category_id": self.category_ids[("Alimentação", "despesa")]},
            {"type": "despesa", "amount": "10", "date": "2026-10-10",
             "category_id": 9999},
            {"type": ["despesa"], "amount": "10", "date": "2026-10-10",
             "category_id": self.category_ids[("Alimentação", "despesa")]},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/api/transactions", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

        self.assertEqual(self.client.get("/api/transactions").get_json(), [])

    def test_category_must_match_transaction_type(self):
        response = self.client.post(
            "/api/transactions",
            json={
                "type": "despesa",
                "amount": "10.00",
                "date": "2026-10-10",
                "category_id": self.category_ids[("Salário", "receita")],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("não corresponde", response.get_json()["error"])

    def test_invalid_filters_return_validation_error(self):
        response = self.client.get(
            "/api/transactions?start_date=2026-10-31&end_date=2026-10-01"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Data inicial", response.get_json()["error"])

    def test_home_page_is_served(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Dashboard".encode(), response.data)

    def test_transaction_page_is_served(self):
        response = self.client.get("/transactions")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Movimentações".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
