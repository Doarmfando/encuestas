"""Tests de integración para los 5 blueprints de rutas."""
import os
import shutil
import unittest
from pathlib import Path

from sqlalchemy.pool import StaticPool

from app import create_app
from app.database.connection import db
from app.database.models import Project, ProjectConfig, Execution


def _perfiles(n=3):
    return [{"nombre": f"P{i}", "descripcion": "", "frecuencia": 100 // n, "respuestas": {}} for i in range(n)]


def _tendencias(n=3):
    dist = {"5": [20, 20, 20, 20, 20]}
    return [{"nombre": f"T{i}", "descripcion": "", "frecuencia": 100 // n, "distribuciones": dist} for i in range(n)]


class _Base(unittest.TestCase):
    """Configura app con SQLite en memoria y un proyecto de prueba."""

    def setUp(self):
        self.export_dir = Path(__file__).resolve().parent / "_test_exports_bp"
        os.makedirs(self.export_dir, exist_ok=True)

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
            OPENAI_API_KEY = ""
            OPENAI_MODEL = "gpt-4o"
            ANTHROPIC_API_KEY = ""
            ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            DEFAULT_AI_PROVIDER = "openai"
            AI_TEMPERATURE = 0.7
            AI_MAX_TOKENS = 4000
            EXPORT_DIR = str(self.export_dir)

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            project = Project(
                nombre="Proyecto test",
                url="https://docs.google.com/forms/d/test/viewform",
                status="scrapeado",
                estructura={"paginas": [{"preguntas": [{"texto": "¿Nombre?", "tipo": "texto"}]}]},
                total_preguntas=1,
            )
            db.session.add(project)
            db.session.commit()

            config = ProjectConfig(
                project_id=project.id,
                nombre="Config base",
                perfiles=_perfiles(),
                reglas_dependencia=[],
                tendencias_escalas=_tendencias(),
                ai_provider_used="test",
                is_active=True,
            )
            db.session.add(config)
            db.session.commit()

            self.project_id = project.id
            self.config_id = config.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        shutil.rmtree(self.export_dir, ignore_errors=True)


# ── routes_projects ──────────────────────────────────────────────────────────

class ProjectsRoutesTest(_Base):

    def test_listar_proyectos_returns_200(self):
        r = self.client.get("/api/projects")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_obtener_proyecto_returns_estructura(self):
        r = self.client.get(f"/api/projects/{self.project_id}")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("estructura", data)

    def test_obtener_proyecto_unknown_returns_404(self):
        r = self.client.get("/api/projects/9999")
        self.assertEqual(r.status_code, 404)

    def test_crear_proyecto_sin_nombre_returns_400(self):
        r = self.client.post("/api/projects", json={"url": "https://docs.google.com/forms/d/x/viewform"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Nombre", r.get_json()["error"])

    def test_crear_proyecto_sin_url_returns_400(self):
        r = self.client.post("/api/projects", json={"nombre": "P"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("URL", r.get_json()["error"])

    def test_crear_proyecto_url_invalida_returns_400(self):
        r = self.client.post("/api/projects", json={"nombre": "P", "url": "https://example.com/nope"})
        self.assertEqual(r.status_code, 400)

    def test_crear_proyecto_valido_returns_201(self):
        r = self.client.post("/api/projects", json={
            "nombre": "Nuevo",
            "url": "https://docs.google.com/forms/d/abc/viewform",
        })
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["nombre"], "Nuevo")

    def test_actualizar_proyecto_unknown_returns_404(self):
        r = self.client.put("/api/projects/9999", json={"nombre": "X"})
        self.assertEqual(r.status_code, 404)

    def test_actualizar_proyecto_nombre(self):
        r = self.client.put(f"/api/projects/{self.project_id}", json={"nombre": "Renombrado"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["nombre"], "Renombrado")

    def test_actualizar_proyecto_url_invalida_returns_400(self):
        r = self.client.put(f"/api/projects/{self.project_id}", json={"url": "https://bad.com"})
        self.assertEqual(r.status_code, 400)

    def test_eliminar_proyecto_unknown_returns_404(self):
        r = self.client.delete("/api/projects/9999")
        self.assertEqual(r.status_code, 404)

    def test_eliminar_proyecto_returns_200(self):
        r = self.client.delete(f"/api/projects/{self.project_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("eliminado", r.get_json()["mensaje"])

    def test_dashboard_returns_activos(self):
        r = self.client.get("/api/dashboard")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("activos", data)
        self.assertIn("proyectos", data)


# ── routes_scraping ──────────────────────────────────────────────────────────

class ScrapingRoutesTest(_Base):

    def test_scrape_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/scrape", json={})
        self.assertEqual(r.status_code, 404)

    def test_scrape_invalid_force_platform_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/scrape", json={"force_platform": "plataforma_xyz"})
        self.assertEqual(r.status_code, 400)

    def test_manual_structure_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/manual-structure", json={"paginas": []})
        self.assertEqual(r.status_code, 404)

    def test_manual_structure_empty_paginas_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/manual-structure", json={"paginas": []})
        self.assertEqual(r.status_code, 400)

    def test_manual_structure_invalid_pagina_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/manual-structure", json={"paginas": ["not_a_dict"]})
        self.assertEqual(r.status_code, 400)

    def test_manual_structure_valid_saves_and_returns_200(self):
        paginas = [{"preguntas": [{"texto": "¿Algo?", "tipo": "texto"}]}]
        r = self.client.post(f"/api/projects/{self.project_id}/manual-structure", json={"paginas": paginas})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["project_id"], self.project_id)
        self.assertEqual(data["total_preguntas"], 1)


# ── routes_analysis ───────────────────────────────────────────────────────────

class AnalysisRoutesTest(_Base):

    def test_analyze_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/analyze", json={})
        self.assertEqual(r.status_code, 404)

    def test_analyze_project_without_estructura_returns_400(self):
        with self.app.app_context():
            p = db.session.get(Project, self.project_id)
            p.estructura = None
            db.session.commit()
        r = self.client.post(f"/api/projects/{self.project_id}/analyze", json={})
        self.assertEqual(r.status_code, 400)

    def test_analyze_with_no_keys_uses_fallback_and_returns_200(self):
        r = self.client.post(f"/api/projects/{self.project_id}/analyze", json={})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("perfiles", data)
        self.assertIn("tendencias_escalas", data)

    def test_apply_config_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/apply-config", json={})
        self.assertEqual(r.status_code, 404)

    def test_apply_config_too_few_perfiles_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/apply-config", json={
            "perfiles": [{"nombre": "Solo uno", "frecuencia": 100, "respuestas": {}}],
            "tendencias_escalas": _tendencias(),
        })
        self.assertEqual(r.status_code, 400)

    def test_apply_config_valid_creates_config(self):
        r = self.client.post(f"/api/projects/{self.project_id}/apply-config", json={
            "nombre": "Config IA",
            "perfiles": _perfiles(),
            "reglas_dependencia": [],
            "tendencias_escalas": _tendencias(),
        })
        self.assertIn(r.status_code, (200, 201))
        data = r.get_json()
        self.assertEqual(data["nombre"], "Config IA")

    def test_template_config_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/template-config", json={})
        self.assertEqual(r.status_code, 404)

    def test_template_config_without_estructura_returns_400(self):
        with self.app.app_context():
            p = db.session.get(Project, self.project_id)
            p.estructura = None
            db.session.commit()
        r = self.client.post(f"/api/projects/{self.project_id}/template-config", json={})
        self.assertEqual(r.status_code, 400)


# ── routes_configs ────────────────────────────────────────────────────────────

class ConfigsRoutesTest(_Base):

    def test_listar_configs_returns_list(self):
        r = self.client.get(f"/api/projects/{self.project_id}/configs")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["is_active"])

    def test_crear_config_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/configs", json={
            "perfiles": _perfiles(), "tendencias_escalas": _tendencias()
        })
        self.assertEqual(r.status_code, 404)

    def test_crear_config_too_few_perfiles_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/configs", json={
            "perfiles": [{"nombre": "Solo", "frecuencia": 100, "respuestas": {}}],
            "tendencias_escalas": _tendencias(),
        })
        self.assertEqual(r.status_code, 400)

    def test_actualizar_config_unknown_returns_404(self):
        r = self.client.put(f"/api/projects/{self.project_id}/configs/9999", json={"nombre": "X"})
        self.assertEqual(r.status_code, 404)

    def test_actualizar_config_nombre(self):
        r = self.client.put(f"/api/projects/{self.project_id}/configs/{self.config_id}", json={"nombre": "Renombrada"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["nombre"], "Renombrada")

    def test_activar_config_unknown_returns_404(self):
        r = self.client.put(f"/api/projects/{self.project_id}/configs/9999/activate")
        self.assertEqual(r.status_code, 404)

    def test_activar_config_returns_mensaje(self):
        r = self.client.put(f"/api/projects/{self.project_id}/configs/{self.config_id}/activate")
        self.assertEqual(r.status_code, 200)
        self.assertIn("mensaje", r.get_json())

    def test_eliminar_unica_config_returns_400(self):
        r = self.client.delete(f"/api/projects/{self.project_id}/configs/{self.config_id}")
        self.assertEqual(r.status_code, 400)
        self.assertIn("última", r.get_json()["error"])

    def test_eliminar_config_unknown_returns_404(self):
        with self.app.app_context():
            extra = ProjectConfig(
                project_id=self.project_id,
                nombre="Extra",
                perfiles=_perfiles(),
                reglas_dependencia=[],
                tendencias_escalas=_tendencias(),
                ai_provider_used="test",
                is_active=False,
            )
            db.session.add(extra)
            db.session.commit()
        r = self.client.delete(f"/api/projects/{self.project_id}/configs/9999")
        self.assertEqual(r.status_code, 404)

    def test_eliminar_config_no_activa_returns_200(self):
        with self.app.app_context():
            extra = ProjectConfig(
                project_id=self.project_id,
                nombre="Extra",
                perfiles=_perfiles(),
                reglas_dependencia=[],
                tendencias_escalas=_tendencias(),
                ai_provider_used="test",
                is_active=False,
            )
            db.session.add(extra)
            db.session.commit()
            extra_id = extra.id

        r = self.client.delete(f"/api/projects/{self.project_id}/configs/{extra_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("eliminada", r.get_json()["mensaje"])


# ── routes_execution ──────────────────────────────────────────────────────────

class ExecutionRoutesTest(_Base):

    def test_ejecutar_unknown_project_returns_404(self):
        r = self.client.post("/api/projects/9999/execute", json={})
        self.assertEqual(r.status_code, 404)

    def test_ejecutar_project_without_estructura_returns_400(self):
        with self.app.app_context():
            p = db.session.get(Project, self.project_id)
            p.estructura = None
            db.session.commit()
        r = self.client.post(f"/api/projects/{self.project_id}/execute", json={})
        self.assertEqual(r.status_code, 400)

    def test_ejecutar_project_without_config_returns_400(self):
        with self.app.app_context():
            ProjectConfig.query.filter_by(project_id=self.project_id).delete()
            db.session.commit()
        r = self.client.post(f"/api/projects/{self.project_id}/execute", json={})
        self.assertEqual(r.status_code, 400)

    def test_ejecutar_cantidad_cero_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/execute", json={"cantidad": 0})
        self.assertEqual(r.status_code, 400)

    def test_ejecutar_cantidad_excesiva_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/execute", json={"cantidad": 501})
        self.assertEqual(r.status_code, 400)

    def test_ejecutar_speed_profile_invalido_returns_400(self):
        r = self.client.post(f"/api/projects/{self.project_id}/execute", json={"speed_profile": "perfil_xyz"})
        self.assertEqual(r.status_code, 400)

    def test_estado_sin_ejecuciones_returns_idle(self):
        r = self.client.get(f"/api/projects/{self.project_id}/estado")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["fase"], "idle")
        self.assertIsNone(data["execution_id"])

    def test_listar_ejecuciones_vacio_returns_empty_list(self):
        r = self.client.get(f"/api/projects/{self.project_id}/executions")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

    def test_download_sin_excel_returns_404(self):
        r = self.client.get(f"/api/projects/{self.project_id}/download")
        self.assertEqual(r.status_code, 404)

    def test_logs_sin_execution_service_returns_empty(self):
        r = self.client.get(f"/api/projects/{self.project_id}/logs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["logs"], "")

    def test_detener_sin_ejecucion_activa_returns_200(self):
        r = self.client.post(f"/api/projects/{self.project_id}/stop", json={})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Detenido", r.get_json()["mensaje"])


if __name__ == "__main__":
    unittest.main()
