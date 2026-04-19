import unittest
from unittest.mock import patch

from app.automation.google_forms_filler import GoogleFormsFiller


class FakePage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/formResponse"

    def goto(self, url, wait_until=None):
        self.url = url


class GoogleFormsFlowGuardTest(unittest.TestCase):
    @patch("app.automation.google_forms_filler.verificar_envio", return_value=True)
    @patch("app.automation.google_forms_filler.wait_for_form_ready", return_value=True)
    @patch.object(GoogleFormsFiller, "_skip_informational_pages", return_value=None)
    @patch.object(GoogleFormsFiller, "_fill_page", return_value=(False, True))
    def test_aborted_navigation_does_not_report_success(
        self,
        _fill_page,
        _skip_intro,
        _wait_ready,
        verificar_envio_mock,
    ):
        filler = GoogleFormsFiller()
        page = FakePage()

        exito, _ = filler.fill_form(
            page,
            {"_perfil": "test", "_tendencia": "test", "paginas": [{"respuestas": [{"pregunta": "Sexo"}]}]},
            page.url,
            numero=1,
            runtime_config={"speed_profile": "balanced", "timing": {"ready_wait_timeout_s": 0.1, "action_pause_min": 0, "action_pause_max": 0}},
        )

        self.assertFalse(exito)
        verificar_envio_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
