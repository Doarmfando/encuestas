import unittest

from sqlalchemy.pool import StaticPool

from app import create_app
from app.automation.navigation.selectors import (
    detectar_plataforma,
    es_plataforma_soportada,
)
from app.database.connection import db
from app.database.models import Project
from app.services.execution_service import ExecutionService
from app.services.execution.browser_manager import BrowserManager


class SupportedPlatformsTest(unittest.TestCase):
    def setUp(self):
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
            EXPORT_DIR = "_test_exports"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_detectar_plataforma_soporta_google_y_microsoft(self):
        self.assertEqual(
            detectar_plataforma("https://docs.google.com/forms/d/e/test/viewform")["name"],
            "google_forms",
        )
        self.assertEqual(
            detectar_plataforma("https://forms.office.com/r/test")["name"],
            "microsoft_forms",
        )
        self.assertEqual(
            detectar_plataforma("https://typeform.com/to/demo")["name"],
            "unsupported",
        )
        self.assertTrue(es_plataforma_soportada("https://forms.gle/demo"))
        self.assertFalse(es_plataforma_soportada("https://example.com/form"))

    def test_create_project_rejects_unsupported_url(self):
        response = self.client.post(
            "/api/projects",
            json={"nombre": "Proyecto malo", "url": "https://typeform.com/to/demo"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Google Forms y Microsoft Forms", response.get_json()["error"])

    def test_update_project_rejects_unsupported_url(self):
        with self.app.app_context():
            project = Project(nombre="Proyecto", url="https://forms.gle/demo", status="nuevo")
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        response = self.client.put(
            f"/api/projects/{project_id}",
            json={"url": "https://surveymonkey.com/r/demo"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Google Forms y Microsoft Forms", response.get_json()["error"])

    def test_scrape_existing_unsupported_project_returns_400(self):
        with self.app.app_context():
            project = Project(nombre="Legacy", url="https://example.com/form", status="nuevo")
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        response = self.client.post(f"/api/projects/{project_id}/scrape", json={"headless": True})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Google Forms y Microsoft Forms", response.get_json()["error"])

    def test_settings_exposes_supported_platforms(self):
        response = self.client.get("/api/config/settings")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(
            data["supported_platforms"],
            [
                {"id": "google_forms", "label": "Google Forms"},
                {"id": "microsoft_forms", "label": "Microsoft Forms"},
            ],
        )

    def test_execution_service_rejects_unsupported_platform(self):
        manager = BrowserManager()

        with self.assertRaises(ValueError):
            manager.get_filler("https://typeform.com/to/demo")


if __name__ == "__main__":
    unittest.main()
