"""Tests para ProjectService: validación y normalización de configuraciones."""
import unittest
from unittest.mock import MagicMock, patch

from app.services.project_service import ProjectService, ProjectValidationError
from app.constants.limits import MIN_PERFILES, MAX_PERFILES, MIN_TENDENCIAS, MAX_TENDENCIAS


def _perfiles(n):
    return [{"nombre": f"P{i}", "frecuencia": 100 // n, "respuestas": {}} for i in range(n)]


def _tendencias(n):
    dist = {"5": [20, 20, 20, 20, 20]}
    return [{"nombre": f"T{i}", "frecuencia": 100 // n, "distribuciones": dist} for i in range(n)]


class ValidarConfiguracionTest(unittest.TestCase):

    def setUp(self):
        self.svc = ProjectService()

    def test_valid_min_counts_does_not_raise(self):
        self.svc.validar_configuracion(_perfiles(MIN_PERFILES), _tendencias(MIN_TENDENCIAS))

    def test_valid_max_counts_does_not_raise(self):
        self.svc.validar_configuracion(_perfiles(MAX_PERFILES), _tendencias(MAX_TENDENCIAS))

    def test_too_few_perfiles_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.validar_configuracion(_perfiles(MIN_PERFILES - 1), _tendencias(MIN_TENDENCIAS))

    def test_too_many_perfiles_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.validar_configuracion(_perfiles(MAX_PERFILES + 1), _tendencias(MIN_TENDENCIAS))

    def test_too_few_tendencias_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.validar_configuracion(_perfiles(MIN_PERFILES), _tendencias(MIN_TENDENCIAS - 1))

    def test_too_many_tendencias_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.validar_configuracion(_perfiles(MIN_PERFILES), _tendencias(MAX_TENDENCIAS + 1))

    def test_empty_lists_raise(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.validar_configuracion([], [])

    def test_none_treated_as_empty(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.validar_configuracion(None, None)


class NormalizarPaginasManualTest(unittest.TestCase):

    def setUp(self):
        self.svc = ProjectService()

    def _pagina(self, preguntas, botones=None):
        p = {"preguntas": preguntas}
        if botones is not None:
            p["botones"] = botones
        return p

    def _pregunta(self, texto="¿Algo?", tipo="texto", opciones=None):
        q = {"texto": texto, "tipo": tipo}
        if opciones is not None:
            q["opciones"] = opciones
        return q

    def test_valid_single_page_returns_normalized(self):
        result = self.svc.normalizar_paginas_manual([
            self._pagina([self._pregunta()])
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["numero"], 1)
        self.assertIn("Enviar", result[0]["botones"])

    def test_multiple_pages_last_gets_enviar(self):
        result = self.svc.normalizar_paginas_manual([
            self._pagina([self._pregunta()]),
            self._pagina([self._pregunta("¿Algo más?")]),
        ])
        self.assertIn("Siguiente", result[0]["botones"])
        self.assertIn("Enviar", result[1]["botones"])

    def test_empty_list_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.normalizar_paginas_manual([])

    def test_none_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.normalizar_paginas_manual(None)

    def test_pagina_not_dict_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.normalizar_paginas_manual(["not_a_dict"])

    def test_pregunta_without_texto_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.normalizar_paginas_manual([
                self._pagina([{"texto": "  ", "tipo": "texto"}])
            ])

    def test_invalid_tipo_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.normalizar_paginas_manual([
                self._pagina([self._pregunta(tipo="tipo_invalido_xyz")])
            ])

    def test_opcion_multiple_without_opciones_raises(self):
        with self.assertRaises(ProjectValidationError):
            self.svc.normalizar_paginas_manual([
                self._pagina([self._pregunta(tipo="opcion_multiple", opciones=[])])
            ])

    def test_opcion_multiple_with_opciones_passes(self):
        result = self.svc.normalizar_paginas_manual([
            self._pagina([self._pregunta(tipo="opcion_multiple", opciones=["A", "B"])])
        ])
        self.assertEqual(result[0]["preguntas"][0]["opciones"], ["A", "B"])

    def test_obligatoria_defaults_to_false(self):
        result = self.svc.normalizar_paginas_manual([
            self._pagina([self._pregunta()])
        ])
        self.assertFalse(result[0]["preguntas"][0]["obligatoria"])

    def test_texto_stripped(self):
        result = self.svc.normalizar_paginas_manual([
            self._pagina([self._pregunta(texto="  ¿Nombre?  ")])
        ])
        self.assertEqual(result[0]["preguntas"][0]["texto"], "¿Nombre?")

    def test_empty_botones_auto_assigned(self):
        result = self.svc.normalizar_paginas_manual([
            self._pagina([self._pregunta()], botones=[])
        ])
        self.assertIn("Enviar", result[0]["botones"])


class TieneBalancedExitosoTest(unittest.TestCase):

    def setUp(self):
        self.svc = ProjectService()

    def _mock_exec(self, mensaje, total, exitosas, status="completado"):
        e = MagicMock()
        e.mensaje = mensaje
        e.total = total
        e.exitosas = exitosas
        e.status = status
        return e

    @patch("app.services.project_service.Execution")
    def test_returns_true_when_balanced_and_100_percent(self, MockExecution):
        MockExecution.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            self._mock_exec("Completado: 10/10 en 5s (balanced)", total=10, exitosas=10)
        ]
        self.assertTrue(self.svc.tiene_balanced_exitoso(1))

    @patch("app.services.project_service.Execution")
    def test_returns_false_when_no_executions(self, MockExecution):
        MockExecution.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        self.assertFalse(self.svc.tiene_balanced_exitoso(1))

    @patch("app.services.project_service.Execution")
    def test_returns_false_when_not_100_percent(self, MockExecution):
        MockExecution.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            self._mock_exec("Completado: 8/10 en 5s (balanced)", total=10, exitosas=8)
        ]
        self.assertFalse(self.svc.tiene_balanced_exitoso(1))

    @patch("app.services.project_service.Execution")
    def test_returns_false_when_not_balanced_profile(self, MockExecution):
        MockExecution.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            self._mock_exec("Completado: 10/10 en 5s (turbo)", total=10, exitosas=10)
        ]
        self.assertFalse(self.svc.tiene_balanced_exitoso(1))


if __name__ == "__main__":
    unittest.main()
