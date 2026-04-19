"""Tests para ResponseNormalizer y ajustar_suma_exacta."""
import unittest
from app.services.analysis.response_normalizer import ResponseNormalizer, ajustar_suma_exacta


class AjustarSumaExactaTest(unittest.TestCase):
    def test_suma_correcta(self):
        result = ajustar_suma_exacta([30, 30, 30, 10])
        self.assertEqual(sum(result), 100)

    def test_lista_vacia(self):
        self.assertEqual(ajustar_suma_exacta([]), [])

    def test_valores_negativos_se_corrigen(self):
        result = ajustar_suma_exacta([-10, -20])
        self.assertEqual(sum(result), 100)
        self.assertTrue(all(v >= 1 for v in result))

    def test_un_solo_valor(self):
        self.assertEqual(ajustar_suma_exacta([50]), [100])


class ResponseNormalizerTest(unittest.TestCase):
    def setUp(self):
        self.norm = ResponseNormalizer()

    def test_alias_tipo_opciones(self):
        config = {"tipo": "opciones", "opciones": {"A": 50, "B": 50}}
        result = self.norm.corregir_respuesta(config)
        self.assertEqual(result["tipo"], "aleatorio")

    def test_alias_tipo_texto(self):
        config = {"tipo": "texto", "valor": "hola"}
        result = self.norm.corregir_respuesta(config)
        self.assertEqual(result["tipo"], "fijo")

    def test_config_no_dict(self):
        result = self.norm.corregir_respuesta("valor simple")
        self.assertEqual(result["tipo"], "fijo")
        self.assertEqual(result["valor"], "valor simple")

    def test_tipo_rango_defaults(self):
        config = {"tipo": "rango"}
        result = self.norm.corregir_respuesta(config)
        self.assertIn("min", result)
        self.assertIn("max", result)

    def test_tipo_fijo_valor_vacio(self):
        config = {"tipo": "fijo"}
        result = self.norm.corregir_respuesta(config)
        self.assertEqual(result["valor"], "")

    def test_aleatorio_opciones_lista_se_convierte(self):
        config = {"tipo": "aleatorio", "opciones": ["A", "B", "C"]}
        result = self.norm.corregir_respuesta(config)
        self.assertIsInstance(result["opciones"], dict)
        self.assertEqual(sum(result["opciones"].values()), 100)

    def test_aleatorio_sin_opciones_fallback_fijo(self):
        config = {"tipo": "aleatorio", "opciones": {}}
        result = self.norm.corregir_respuesta(config)
        self.assertEqual(result["tipo"], "fijo")

    def test_referencia_numero_fuerza_rango(self):
        config = {"tipo": "fijo", "valor": "25"}
        ref = {"tipo": "numero", "opciones": []}
        result = self.norm.corregir_respuesta(config, ref)
        self.assertEqual(result["tipo"], "rango")

    def test_referencia_opcion_multiple_corrige_opciones(self):
        config = {"tipo": "fijo", "valor": "Masculino"}
        ref = {"tipo": "opcion_multiple", "opciones": ["Masculino", "Femenino"]}
        result = self.norm.corregir_respuesta(config, ref)
        self.assertEqual(result["tipo"], "aleatorio")

    def test_normalizar_frecuencias_suma_100(self):
        items = [{"frecuencia": 50}, {"frecuencia": 30}, {"frecuencia": 20}]
        self.norm.normalizar_frecuencias(items)
        self.assertEqual(sum(i["frecuencia"] for i in items), 100)

    def test_corregir_nombres_fuzzy(self):
        ref_map = {"¿Cuál es tu edad?": {"tipo": "numero"}}
        respuestas = {"Cual es tu edad": {"tipo": "rango", "min": 18, "max": 65}}
        result = self.norm.corregir_nombres_preguntas(respuestas, ref_map)
        self.assertIn("¿Cuál es tu edad?", result)

    def test_generar_respuesta_default_numero(self):
        ref = {"tipo": "numero", "opciones": []}
        result = self.norm.generar_respuesta_default(ref)
        self.assertEqual(result["tipo"], "rango")

    def test_generar_respuesta_default_opcion_multiple(self):
        ref = {"tipo": "opcion_multiple", "opciones": ["A", "B"]}
        result = self.norm.generar_respuesta_default(ref)
        self.assertEqual(result["tipo"], "aleatorio")
        self.assertEqual(sum(result["opciones"].values()), 100)


if __name__ == "__main__":
    unittest.main()
