import unittest
from unittest.mock import Mock, patch

from app.automation.microsoft_forms_filler import MicrosoftFormsFiller
from app.automation.ms_forms_filler import MSFormsFiller


ZERO_RUNTIME = {"timing": {"action_pause_min": 0, "action_pause_max": 0}}


class FakePage:
    def __init__(self, url="https://forms.office.com/r/test-form"):
        self.url = url
        self.goto_calls = []

    def goto(self, url, wait_until=None):
        self.url = url
        self.goto_calls.append((url, wait_until))


class MSFormsFillerTest(unittest.TestCase):
    @patch("app.automation.ms_forms_filler.wait_for_form_ready", return_value=True)
    def test_fill_page_reports_missing_question_as_failure(self, _wait_ready):
        filler = MSFormsFiller()
        filler._find_question = Mock(return_value=None)

        result = filler.fill_page(
            FakePage(),
            [{"tipo": "texto", "valor": "Juan", "pregunta": "Nombre completo"}],
            runtime_config=ZERO_RUNTIME,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failed_questions"], ["Nombre completo"])

    @patch("app.automation.ms_forms_filler.wait_for_form_ready", return_value=True)
    def test_fill_page_counts_successful_fills(self, _wait_ready):
        filler = MSFormsFiller()
        filler._find_question = Mock(return_value=object())
        filler._fill_element = Mock(return_value=True)

        result = filler.fill_page(
            FakePage(),
            [{"tipo": "texto", "valor": "Juan", "pregunta": "Nombre completo"}],
            runtime_config=ZERO_RUNTIME,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["filled"], 1)
        self.assertEqual(result["failed"], 0)


class MicrosoftFormsFillerFlowTest(unittest.TestCase):
    @patch("app.automation.microsoft_forms_filler.wait_for_form_ready", return_value=True)
    def test_ms_flow_does_not_advance_when_page_fill_fails(self, _wait_ready):
        filler = MicrosoftFormsFiller()
        filler.ms_filler.fill_page = Mock(return_value={
            "ok": False,
            "filled": 0,
            "failed": 1,
            "failed_questions": ["Nombre completo"],
        })
        filler.ms_filler.click_next = Mock(return_value=True)

        fake_page = FakePage()
        response = {
            "_perfil": "test",
            "paginas": [{
                "numero": 1,
                "respuestas": [{"tipo": "texto", "valor": "Juan", "pregunta": "Nombre completo"}],
                "botones": ["Siguiente"],
            }],
        }

        exito, _ = filler.fill_form(
            fake_page,
            response,
            fake_page.url,
            numero=1,
            runtime_config=ZERO_RUNTIME,
        )

        self.assertFalse(exito)
        filler.ms_filler.click_next.assert_not_called()


if __name__ == "__main__":
    unittest.main()
