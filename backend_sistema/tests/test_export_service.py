import unittest

from app.services.export_service import ExportService


class ExportServiceTest(unittest.TestCase):
    def test_excel_value_flattens_matrix_dict(self):
        valor = {
            "Fila 1": "Nunca",
            "Fila 2": "Siempre",
        }

        result = ExportService._excel_value(valor)

        self.assertEqual(result, "Fila 1: Nunca | Fila 2: Siempre")


if __name__ == "__main__":
    unittest.main()
