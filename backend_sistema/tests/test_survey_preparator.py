"""Tests para SurveyPreparator."""
import unittest
from app.services.analysis.survey_preparator import SurveyPreparator, es_escala


def _estructura(preguntas_por_pagina: list) -> dict:
    return {"titulo": "Test", "descripcion": "", "paginas": [{"preguntas": preguntas_por_pagina}]}


class EsEscalaTest(unittest.TestCase):
    def test_tipo_escala_directo(self):
        self.assertTrue(es_escala("escala"))
        self.assertTrue(es_escala("likert"))
        self.assertTrue(es_escala("rating"))
        self.assertTrue(es_escala("nps"))
        self.assertTrue(es_escala("matriz"))

    def test_tipo_opcion_multiple_con_patron_likert(self):
        opciones = ["Nunca", "Casi nunca", "A veces", "Muchas veces", "Siempre"]
        self.assertTrue(es_escala("opcion_multiple", opciones))

    def test_tipo_opcion_multiple_sin_patron_likert(self):
        opciones = ["Hombre", "Mujer", "Prefiero no decir"]
        self.assertFalse(es_escala("opcion_multiple", opciones))

    def test_tipo_desconocido(self):
        self.assertFalse(es_escala("texto"))
        self.assertFalse(es_escala("numero"))


class SurveyPreparatorTest(unittest.TestCase):
    def setUp(self):
        self.preparator = SurveyPreparator()

    def test_ignorar_tipos_informativos(self):
        estructura = _estructura([
            {"texto": "Bienvenido", "tipo": "informativo", "opciones": []},
        ])
        resumen = self.preparator.preparar_resumen(estructura)
        self.assertEqual(len(resumen["preguntas"]), 0)

    def test_preguntas_normales_en_resumen(self):
        estructura = _estructura([
            {"texto": "¿Cuál es tu edad?", "tipo": "numero", "opciones": [], "obligatoria": True},
        ])
        resumen = self.preparator.preparar_resumen(estructura)
        self.assertEqual(len(resumen["preguntas"]), 1)
        self.assertEqual(resumen["preguntas"][0]["texto"], "¿Cuál es tu edad?")

    def test_escala_va_a_nota_no_a_preguntas(self):
        estructura = _estructura([
            {
                "texto": "¿Qué tan seguido?",
                "tipo": "opcion_multiple",
                "opciones": ["Nunca", "Casi nunca", "A veces", "Muchas veces", "Siempre"],
                "obligatoria": False,
            },
        ])
        resumen = self.preparator.preparar_resumen(estructura)
        self.assertEqual(len(resumen["preguntas"]), 0)
        self.assertIn("nota_escalas", resumen)

    def test_restriccion_cuando_no_hay_demografica(self):
        estructura = _estructura([
            {"texto": "¿Te gustó el servicio?", "tipo": "opcion_multiple", "opciones": ["Sí", "No"], "obligatoria": False},
        ])
        resumen = self.preparator.preparar_resumen(estructura)
        self.assertIn("restriccion_perfiles", resumen)

    def test_opciones_largas_se_truncan(self):
        opciones = [f"opcion{i}" for i in range(20)]
        estructura = _estructura([
            {"texto": "Pregunta larga", "tipo": "opcion_multiple", "opciones": opciones, "obligatoria": False},
        ])
        resumen = self.preparator.preparar_resumen(estructura)
        self.assertLessEqual(len(resumen["preguntas"][0]["opciones"]), 6)

    def test_extraer_preguntas_referencia(self):
        estructura = _estructura([
            {"texto": "P1", "tipo": "opcion_multiple", "opciones": ["A", "B"], "obligatoria": True},
            {"texto": "Intro", "tipo": "informativo", "opciones": []},
        ])
        refs = self.preparator.extraer_preguntas_referencia(estructura)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["texto"], "P1")

    def test_survey_supports_demographics_true(self):
        refs = [{"texto": "¿Cuál es tu edad?"}]
        self.assertTrue(self.preparator.survey_supports_demographics(refs))

    def test_survey_supports_demographics_false(self):
        refs = [{"texto": "¿Te gustan los colores?"}]
        self.assertFalse(self.preparator.survey_supports_demographics(refs))


if __name__ == "__main__":
    unittest.main()
