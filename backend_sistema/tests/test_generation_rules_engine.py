"""Tests para RulesEngine."""
import unittest
from app.services.generation.rules_engine import RulesEngine


def _respuesta(preguntas: list[dict]) -> dict:
    return {"paginas": [{"numero": 1, "respuestas": preguntas, "botones": []}]}


class RulesEngineEvaluarCondicionTest(unittest.TestCase):
    def setUp(self):
        self.engine = RulesEngine()

    def test_igual_true(self):
        self.assertTrue(self.engine._evaluar_condicion("No", "igual", "No"))

    def test_igual_false(self):
        self.assertFalse(self.engine._evaluar_condicion("Sí", "igual", "No"))

    def test_diferente_true(self):
        self.assertTrue(self.engine._evaluar_condicion("Sí", "diferente", "No"))

    def test_menor_true(self):
        self.assertTrue(self.engine._evaluar_condicion("5", "menor", "10"))

    def test_mayor_true(self):
        self.assertTrue(self.engine._evaluar_condicion("15", "mayor", "10"))

    def test_contiene_lista(self):
        self.assertTrue(self.engine._evaluar_condicion(["Lunes", "Martes"], "contiene", "Lunes"))

    def test_no_contiene(self):
        self.assertTrue(self.engine._evaluar_condicion(["Lunes"], "no_contiene", "Martes"))

    def test_cardinalidad_igual(self):
        self.assertTrue(self.engine._evaluar_condicion(["a", "b"], "cardinalidad_igual", "2"))

    def test_operador_desconocido_false(self):
        self.assertFalse(self.engine._evaluar_condicion("x", "operador_inventado", "x"))

    def test_acento_insensible(self):
        self.assertTrue(self.engine._evaluar_condicion("Sí", "igual", "Si"))


class RulesEngineAplicarTest(unittest.TestCase):
    def setUp(self):
        self.engine = RulesEngine()

    def _build(self, preg1_val, preg2_val, opciones2=None):
        return _respuesta([
            {"pregunta": "¿Tiene hijos?", "tipo": "opcion_multiple", "valor": preg1_val, "opciones_disponibles": ["Sí", "No"]},
            {"pregunta": "¿Cuántos hijos?", "tipo": "numero", "valor": preg2_val, "opciones_disponibles": opciones2 or []},
        ])

    def test_forzar_aplicado(self):
        respuesta = self._build("No", "3")
        reglas = [{
            "si_pregunta": "¿Tiene hijos?",
            "si_valor": "No",
            "operador": "igual",
            "entonces_pregunta": "¿Cuántos hijos?",
            "entonces_forzar": "0",
            "entonces_excluir": [],
        }]
        result = self.engine.aplicar(respuesta, reglas)
        valor = result["paginas"][0]["respuestas"][1]["valor"]
        self.assertEqual(valor, "0")

    def test_no_aplica_cuando_condicion_falsa(self):
        respuesta = self._build("Sí", "3")
        reglas = [{
            "si_pregunta": "¿Tiene hijos?",
            "si_valor": "No",
            "operador": "igual",
            "entonces_pregunta": "¿Cuántos hijos?",
            "entonces_forzar": "0",
            "entonces_excluir": [],
        }]
        result = self.engine.aplicar(respuesta, reglas)
        valor = result["paginas"][0]["respuestas"][1]["valor"]
        self.assertEqual(valor, "3")

    def test_excluir_opcion(self):
        respuesta = _respuesta([
            {"pregunta": "Trabaja", "tipo": "opcion_multiple", "valor": "No", "opciones_disponibles": ["Sí", "No"]},
            {"pregunta": "Empresa", "tipo": "texto", "valor": "ACME", "opciones_disponibles": ["ACME", "Beta", "Gamma"]},
        ])
        reglas = [{
            "si_pregunta": "Trabaja",
            "si_valor": "No",
            "operador": "igual",
            "entonces_pregunta": "Empresa",
            "entonces_forzar": "No aplica",
            "entonces_excluir": [],
        }]
        result = self.engine.aplicar(respuesta, reglas)
        valor = result["paginas"][0]["respuestas"][1]["valor"]
        self.assertEqual(valor, "No aplica")

    def test_sin_reglas_sin_cambios(self):
        respuesta = self._build("Sí", "2")
        result = self.engine.aplicar(respuesta, [])
        self.assertEqual(result["paginas"][0]["respuestas"][1]["valor"], "2")

    def test_forzar_rango_numerico(self):
        resultado = self.engine._resolver_forzar("10-20")
        self.assertIn(int(resultado), range(10, 21))

    def test_forzar_lista(self):
        resultado = self.engine._resolver_forzar(["a", "b"])
        self.assertEqual(resultado, ["a", "b"])

    def test_forzar_entero(self):
        self.assertEqual(self.engine._resolver_forzar(5), "5")


class RulesEngineEquivalentesTest(unittest.TestCase):
    def setUp(self):
        self.engine = RulesEngine()

    def test_listas_equivalentes(self):
        self.assertTrue(self.engine._equivalentes(["A", "B"], ["B", "A"]))

    def test_listas_no_equivalentes(self):
        self.assertFalse(self.engine._equivalentes(["A"], ["B"]))

    def test_strings_normalizados(self):
        self.assertTrue(self.engine._equivalentes("Si", "Sí"))


if __name__ == "__main__":
    unittest.main()
