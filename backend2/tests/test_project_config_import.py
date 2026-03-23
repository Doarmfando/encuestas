import os
import shutil
import unittest
from pathlib import Path

from app import create_app
from app.database.connection import db
from app.database.models import Project, ProjectConfig
from sqlalchemy.pool import StaticPool


def _build_perfiles(prefix):
    return [
        {"nombre": f"{prefix} A", "descripcion": "", "frecuencia": 40, "respuestas": {}},
        {"nombre": f"{prefix} B", "descripcion": "", "frecuencia": 35, "respuestas": {}},
        {"nombre": f"{prefix} C", "descripcion": "", "frecuencia": 25, "respuestas": {}},
    ]


def _build_tendencias(prefix):
    base = {"5": [20, 20, 20, 20, 20]}
    return [
        {"nombre": f"{prefix} 1", "descripcion": "", "frecuencia": 40, "distribuciones": base},
        {"nombre": f"{prefix} 2", "descripcion": "", "frecuencia": 35, "distribuciones": base},
        {"nombre": f"{prefix} 3", "descripcion": "", "frecuencia": 25, "distribuciones": base},
    ]


def _build_reglas():
    return [
        {
            "si_pregunta": "Edad",
            "si_valor": "18 - 24",
            "operador": "igual",
            "entonces_pregunta": "¿Tiene hijos?",
            "entonces_forzar": "No",
            "entonces_excluir": [],
        }
    ]


class ProjectConfigImportRoutesTest(unittest.TestCase):
    def setUp(self):
        self.export_dir = Path(__file__).resolve().parent / "_test_exports"
        os.makedirs(self.export_dir, exist_ok=True)
        export_dir = str(self.export_dir)

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
            EXPORT_DIR = export_dir

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            project = Project(
                nombre="Proyecto prueba",
                url="https://example.com/form",
                status="configurado",
                estructura={"paginas": []},
                total_preguntas=5,
            )
            db.session.add(project)
            db.session.commit()

            active = ProjectConfig(
                project_id=project.id,
                nombre="Config activa",
                perfiles=_build_perfiles("Base"),
                reglas_dependencia=_build_reglas(),
                tendencias_escalas=_build_tendencias("Base"),
                ai_provider_used="importado",
                is_active=True,
            )
            archived = ProjectConfig(
                project_id=project.id,
                nombre="Config archivada",
                perfiles=_build_perfiles("Archivada"),
                reglas_dependencia=_build_reglas(),
                tendencias_escalas=_build_tendencias("Archivada"),
                ai_provider_used="importado",
                is_active=False,
            )
            db.session.add_all([active, archived])
            db.session.commit()

            self.project_id = project.id
            self.active_config_id = active.id
            self.archived_config_id = archived.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        shutil.rmtree(self.export_dir, ignore_errors=True)

    def test_import_with_replace_existing_updates_active_config(self):
        response = self.client.post(
            f"/api/projects/{self.project_id}/configs",
            json={
                "nombre": "Config importada",
                "perfiles": _build_perfiles("Importada"),
                "reglas_dependencia": _build_reglas(),
                "tendencias_escalas": _build_tendencias("Importada"),
                "replace_existing": True,
                "replace_config_id": self.active_config_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], self.active_config_id)
        self.assertEqual(data["nombre"], "Config importada")
        self.assertTrue(data["is_active"])

        with self.app.app_context():
            configs = ProjectConfig.query.filter_by(project_id=self.project_id).order_by(ProjectConfig.id.asc()).all()
            self.assertEqual(len(configs), 2)

            active = db.session.get(ProjectConfig, self.active_config_id)
            archived = db.session.get(ProjectConfig, self.archived_config_id)

            self.assertEqual(active.nombre, "Config importada")
            self.assertEqual(active.perfiles[0]["nombre"], "Importada A")
            self.assertTrue(active.is_active)
            self.assertFalse(archived.is_active)

    def test_list_configs_returns_active_first_with_summary_fields(self):
        response = self.client.get(f"/api/projects/{self.project_id}/configs")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], self.active_config_id)
        self.assertTrue(data[0]["is_active"])
        self.assertIn("updated_at", data[0])
        self.assertEqual(data[0]["total_perfiles"], 3)
        self.assertEqual(data[0]["total_tendencias"], 3)
        self.assertEqual(data[0]["total_reglas"], 1)


if __name__ == "__main__":
    unittest.main()
