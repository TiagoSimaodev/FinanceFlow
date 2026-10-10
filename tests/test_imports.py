import io
import json
import tempfile
import unittest
from pathlib import Path

from financeflow import create_app


class CsvImportApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "financeflow.db"
        self.app = create_app(
            {"TESTING": True, "AUTH_DISABLED": True, "DATABASE_PATH": database_path}
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_directory.cleanup()

    def upload(
        self,
        content,
        file_name="movimentacoes.csv",
        period_type=None,
        period=None,
    ):
        data = {"file": (io.BytesIO(content), file_name)}
        if period_type is not None:
            data["period_type"] = period_type
            data["period"] = period
        return self.client.post(
            "/api/imports",
            data=data,
            content_type="multipart/form-data",
        )

    def test_import_accepts_brazilian_csv_and_reports_rejected_rows(self):
        content = (
            "data;tipo;valor;categoria;descricao\n"
            "10/10/2026;despesa;1.234,56;Alimentação;Mercado\n"
            "2026-10-11;receita;3500.00;Salário;Pagamento\n"
            "31/02/2026;despesa;20,00;Moradia;Data inválida\n"
            "12/10/2026;receita;30,00;Alimentação;Tipo incompatível\n"
            "10/10/2026;despesa;1.234,56;Alimentação;Mercado\n"
        ).encode("utf-8")

        response = self.upload(content)

        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["rows_processed"], 5)
        self.assertEqual(result["rows_accepted"], 2)
        self.assertEqual(result["rows_rejected"], 3)
        self.assertGreaterEqual(result["duration_ms"], 0)

        transactions = self.client.get("/api/transactions").get_json()
        self.assertEqual(len(transactions), 2)
        self.assertEqual(
            sorted(item["amount_cents"] for item in transactions),
            [123456, 350000],
        )

        rejection_response = self.client.get(
            f"/api/imports/{result['import_id']}/rejections"
        )
        rejections = rejection_response.get_json()
        self.assertEqual(rejection_response.status_code, 200)
        self.assertEqual([item["row_number"] for item in rejections], [4, 5, 6])
        self.assertIn("Data inválida", rejections[0]["reason"])
        self.assertIn("não corresponde", rejections[1]["reason"])
        self.assertIn("duplicado", rejections[2]["reason"])
        self.assertEqual(json.loads(rejections[2]["raw_data"])["descricao"], "Mercado")

        history = self.client.get("/api/imports").get_json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["rows_accepted"], 2)
        self.assertEqual(history[0]["rows_rejected"], 3)
        self.assertEqual(history[0]["status"], "partial")

    def test_same_file_cannot_be_imported_twice(self):
        content = (
            "data,tipo,valor,categoria,descricao\n"
            "2026-10-10,despesa,10.50,Lazer,Cinema\n"
        ).encode("utf-8")

        first = self.upload(content)
        second = self.upload(content)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(
            second.get_json()["import_id"],
            first.get_json()["import_id"],
        )
        self.assertEqual(len(self.client.get("/api/transactions").get_json()), 1)
        self.assertEqual(len(self.client.get("/api/imports").get_json()), 1)

    def test_bad_headers_are_logged_as_failed_imports(self):
        response = self.upload(b"date,kind,amount\n2026-10-10,expense,1")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Coluna não reconhecida", response.get_json()["error"])
        history = self.client.get("/api/imports").get_json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "failed")
        self.assertIsNotNone(history[0]["finished_at"])
        self.assertIsNotNone(history[0]["duration_ms"])
        self.assertEqual(history[0]["error_message"], response.get_json()["error"])

    def test_missing_file_and_non_csv_are_rejected(self):
        missing = self.client.post("/api/imports", data={})
        wrong_extension = self.upload(b"data,tipo,valor,categoria\n", "dados.txt")

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(wrong_extension.status_code, 400)
        self.assertEqual(self.client.get("/api/imports").get_json(), [])

    def test_import_page_is_served(self):
        response = self.client.get("/imports")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Importar movimentações".encode(), response.data)
        self.assertIn("Modo escuro".encode(), response.data)

    def test_month_scope_imports_matching_rows_and_rejects_other_months(self):
        content = (
            "data;tipo;valor;categoria;descricao\n"
            "10/10/2026;despesa;12,50;Alimentação;Dentro do mês\n"
            "2026-11-01;receita;100,00;Salário;Fora do mês\n"
        ).encode("utf-8")

        response = self.upload(
            content,
            period_type="month",
            period="2026-10",
        )

        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result["rows_accepted"], 1)
        self.assertEqual(result["rows_rejected"], 1)
        rejections = self.client.get(
            f"/api/imports/{result['import_id']}/rejections"
        ).get_json()
        self.assertIn("fora do período selecionado", rejections[0]["reason"])

    def test_year_scope_imports_rows_from_all_months_of_the_year(self):
        content = (
            "data,tipo,valor,categoria,descricao\n"
            "2026-01-01,despesa,10.00,Lazer,Janeiro\n"
            "31/12/2026,receita,1000.00,Salário,Dezembro\n"
            "2025-12-31,despesa,5.00,Moradia,Fora do ano\n"
        ).encode("utf-8")

        response = self.upload(content, period_type="year", period="2026")

        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result["rows_accepted"], 2)
        self.assertEqual(result["rows_rejected"], 1)

    def test_blank_csv_lines_are_reported_as_rejections(self):
        content = (
            "data;tipo;valor;categoria;descricao\n"
            "2026-10-01;despesa;10,00;Lazer;Cinema\n"
            "\n"
            "2026-10-02;despesa;5,00;Transporte;Ônibus\n"
        ).encode("utf-8")

        response = self.upload(content)

        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result["rows_processed"], 3)
        self.assertEqual(result["rows_accepted"], 2)
        self.assertEqual(result["rows_rejected"], 1)
        rejections = self.client.get(
            f"/api/imports/{result['import_id']}/rejections"
        ).get_json()
        self.assertEqual(rejections[0]["row_number"], 3)

    def test_month_and_year_template_downloads_have_expected_columns(self):
        month_template = self.client.get(
            "/api/imports/template?period_type=month&period=2026-10"
        )
        year_template = self.client.get(
            "/api/imports/template?period_type=year&period=2026"
        )

        self.assertEqual(month_template.status_code, 200)
        self.assertEqual(year_template.status_code, 200)
        self.assertIn(
            "financeflow_modelo_mes_2026-10.csv",
            month_template.headers["Content-Disposition"],
        )
        self.assertIn(
            "financeflow_modelo_ano_2026.csv",
            year_template.headers["Content-Disposition"],
        )
        self.assertIn(
            "data;tipo;valor;categoria;descricao",
            month_template.data.decode("utf-8-sig"),
        )
        self.assertEqual(
            month_template.data.decode("utf-8-sig"),
            year_template.data.decode("utf-8-sig"),
        )
        invalid = self.client.get(
            "/api/imports/template?period_type=month&period=2026-13"
        )
        self.assertEqual(invalid.status_code, 400)


if __name__ == "__main__":
    unittest.main()
