"""Tests para TendencyManager."""
import unittest
from app.services.analysis.tendency_manager import TendencyManager


class TendencyManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = TendencyManager()

    def test_crear_defaults_retorna_3(self):
        defaults = self.manager.crear_defaults({5})
        self.assertEqual(len(defaults), 3)

    def test_defaults_suman_100_frecuencias(self):
        defaults = self.manager.crear_defaults({5})
        total = sum(t["frecuencia"] for t in defaults)
        self.assertEqual(total, 100)

    def test_distribuciones_suman_100(self):
        defaults = self.manager.crear_defaults({5, 7})
        for tendencia in defaults:
            for tam_str, dist in tendencia["distribuciones"].items():
                self.assertEqual(sum(dist), 100, f"Distribución {tam_str} no suma 100")

    def test_distribuciones_para_cada_tamano(self):
        defaults = self.manager.crear_defaults({5, 7, 11})
        for tendencia in defaults:
            for tam in [5, 7, 11]:
                self.assertIn(str(tam), tendencia["distribuciones"])

    def test_asegurar_cantidad_completa_si_faltan(self):
        tendencias = [{"nombre": "Una sola", "frecuencia": 100, "distribuciones": {}}]
        result = self.manager.asegurar_cantidad(tendencias, {5})
        self.assertGreaterEqual(len(result), 3)

    def test_asegurar_cantidad_no_duplica(self):
        defaults = self.manager.crear_defaults({5})
        result = self.manager.asegurar_cantidad(defaults, {5})
        nombres = [t["nombre"] for t in result]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_corregir_convierte_distribucion_a_distribuciones(self):
        resultado = {
            "tendencias_escalas": [
                {"nombre": "Test", "frecuencia": 100, "distribucion": [20, 20, 20, 20, 20]},
            ]
        }
        self.manager.corregir(resultado, True, {5})
        tendencia = resultado["tendencias_escalas"][0]
        self.assertIn("distribuciones", tendencia)
        self.assertNotIn("distribucion", tendencia)

    def test_corregir_agrega_tamanos_faltantes(self):
        resultado = {
            "tendencias_escalas": [
                {"nombre": "Test", "frecuencia": 100, "distribuciones": {"5": [20, 20, 20, 20, 20]}},
            ]
        }
        self.manager.corregir(resultado, True, {5, 7})
        tendencia = resultado["tendencias_escalas"][0]
        self.assertIn("7", tendencia["distribuciones"])

    def test_corregir_sin_tendencias_crea_defaults(self):
        resultado = {"tendencias_escalas": []}
        self.manager.corregir(resultado, False, {5})
        self.assertGreater(len(resultado["tendencias_escalas"]), 0)

    def test_dist_centrada_len_correcto(self):
        for tam in [5, 7, 11]:
            dist = self.manager._dist_centrada(tam)
            self.assertEqual(len(dist), tam)
            self.assertEqual(sum(dist), 100)

    def test_dist_sesgada_alta_sesgada(self):
        dist_alta = self.manager._dist_sesgada_alta(5)
        dist_baja = self.manager._dist_sesgada_baja(5)
        # Alta debe tener más peso en últimas posiciones, baja en primeras
        suma_alta = sum(dist_alta[3:])
        suma_baja = sum(dist_baja[:2])
        self.assertGreater(suma_alta, sum(dist_alta[:2]))
        self.assertGreater(suma_baja, sum(dist_baja[3:]))


if __name__ == "__main__":
    unittest.main()
