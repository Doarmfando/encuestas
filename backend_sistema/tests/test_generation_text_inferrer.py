"""Tests para text_inferrer.py"""
import unittest
import re
from app.services.generation.text_inferrer import infer_text_value


class TextInferrerTest(unittest.TestCase):
    def test_edad_es_numero(self):
        val = infer_text_value("¿Cuál es tu edad?")
        self.assertTrue(val.isdigit())
        self.assertIn(int(val), range(20, 56))

    def test_dni_es_numero_largo(self):
        val = infer_text_value("Ingresa tu DNI")
        self.assertTrue(val.isdigit())
        self.assertEqual(len(val), 8)

    def test_telefono_empieza_con_9(self):
        val = infer_text_value("Celular")
        self.assertTrue(val.startswith("9"))

    def test_email_formato(self):
        val = infer_text_value("Correo electrónico")
        self.assertIn("@", val)

    def test_nombre_completo_tiene_espacio(self):
        val = infer_text_value("Nombre completo")
        self.assertIn(" ", val)

    def test_nombre_simple_sin_espacio(self):
        val = infer_text_value("Nombre")
        self.assertNotIn(" ", val)

    def test_pregunta_sin_patron_retorna_respuesta(self):
        val = infer_text_value("¿Cuál es tu color favorito?")
        self.assertEqual(val, "respuesta")

    def test_año_es_numero(self):
        val = infer_text_value("¿En qué año nació?")
        self.assertTrue(val.isdigit())
        self.assertIn(int(val), range(2015, 2026))


if __name__ == "__main__":
    unittest.main()
