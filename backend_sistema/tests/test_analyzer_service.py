import unittest

from app.services.analysis.profile_manager import ProfileManager
from app.services.analysis.tendency_manager import TendencyManager
from app.services.analysis.response_normalizer import ResponseNormalizer


class AnalyzerServiceTest(unittest.TestCase):
    def setUp(self):
        self._normalizer = ResponseNormalizer()
        self._profile_manager = ProfileManager(self._normalizer)
        self._tendency_manager = TendencyManager()

    def test_no_demographic_questions_sanitize_demographic_profile_labels(self):
        preguntas_ref = [
            {"texto": "¿Cuánto pagaste por el servicio adquirido?", "tipo": "opcion_multiple", "opciones": []},
            {"texto": "¿Cuál fue el último servicio que contrataste?", "tipo": "texto", "opciones": []},
        ]
        perfiles = [
            {"nombre": "Amas de casa", "descripcion": "Persona que gestiona el hogar", "frecuencia": 50, "respuestas": {}},
            {"nombre": "Cliente frecuente", "descripcion": "Perfil conductual", "frecuencia": 50, "respuestas": {}},
        ]

        self._profile_manager.sanitizar_no_soportados(perfiles, preguntas_ref)

        self.assertEqual(perfiles[0]["nombre"], "Perfil conductual A")
        self.assertNotIn("ama de casa", perfiles[0]["descripcion"].lower())
        self.assertEqual(perfiles[1]["nombre"], "Cliente frecuente")

    def test_detect_demographic_questions_when_form_explicitly_asks_them(self):
        preguntas_ref = [
            {"texto": "¿Cuál es tu edad?", "tipo": "numero", "opciones": []},
        ]
        self.assertTrue(self._profile_manager._survey_supports_demographics(preguntas_ref))

    def test_no_scale_questions_still_produce_three_default_tendencies(self):
        resultado = {"tendencias_escalas": []}

        self._tendency_manager.corregir(resultado, tiene_escalas=False, tamaños=set())
        tendencias = self._tendency_manager.asegurar_cantidad(resultado["tendencias_escalas"], set())

        self.assertEqual(len(tendencias), 3)
        self.assertEqual(sum(t["frecuencia"] for t in tendencias), 100)
        for tendencia in tendencias:
            self.assertTrue({"5", "7", "11"}.issubset(set(tendencia["distribuciones"].keys())))

    def test_normalizar_frecuencias_suma_exactamente_cien(self):
        items = [
            {"frecuencia": 33},
            {"frecuencia": 33},
            {"frecuencia": 33},
        ]

        self._normalizer.normalizar_frecuencias(items)

        self.assertEqual(sum(item["frecuencia"] for item in items), 100)


if __name__ == "__main__":
    unittest.main()
