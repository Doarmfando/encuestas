"""Tests para ProfileSelector."""
import unittest
from app.services.generation.profile_selector import ProfileSelector


class ProfileSelectorTest(unittest.TestCase):
    def setUp(self):
        self.selector = ProfileSelector()

    def test_elegir_perfil_sin_perfiles_retorna_default(self):
        perfil = self.selector.elegir_perfil([])
        self.assertEqual(perfil["nombre"], "default")

    def test_elegir_perfil_retorna_uno_de_la_lista(self):
        perfiles = [
            {"nombre": "A", "frecuencia": 50},
            {"nombre": "B", "frecuencia": 50},
        ]
        perfil = self.selector.elegir_perfil(perfiles)
        self.assertIn(perfil["nombre"], ["A", "B"])

    def test_elegir_tendencia_sin_tendencias_retorna_neutro(self):
        tendencia = self.selector.elegir_tendencia([])
        self.assertEqual(tendencia["nombre"], "neutro")

    def test_elegir_tendencia_retorna_una_de_la_lista(self):
        tendencias = [
            {"nombre": "Alto", "frecuencia": 50},
            {"nombre": "Bajo", "frecuencia": 50},
        ]
        tendencia = self.selector.elegir_tendencia(tendencias)
        self.assertIn(tendencia["nombre"], ["Alto", "Bajo"])

    def test_perfil_con_tendencia_sugerida_la_prefiere(self):
        tendencias = [
            {"nombre": "Alto", "frecuencia": 1},
            {"nombre": "Bajo", "frecuencia": 1},
        ]
        perfil = {"tendencia_sugerida": "Alto"}
        # Con 1000 iteraciones la sugerida debe salir con mucha más frecuencia
        conteo = {"Alto": 0, "Bajo": 0}
        for _ in range(1000):
            t = self.selector.elegir_tendencia(tendencias, perfil)
            conteo[t["nombre"]] += 1
        self.assertGreater(conteo["Alto"], conteo["Bajo"])

    def test_perfil_sin_tendencia_sugerida_funciona(self):
        tendencias = [{"nombre": "Medio", "frecuencia": 100}]
        perfil = {}
        tendencia = self.selector.elegir_tendencia(tendencias, perfil)
        self.assertEqual(tendencia["nombre"], "Medio")


if __name__ == "__main__":
    unittest.main()
