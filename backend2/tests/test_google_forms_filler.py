import unittest
from unittest.mock import Mock, patch

from app.automation.google_forms_filler import GoogleFormsFiller


ZERO_RUNTIME = {"timing": {"action_pause_min": 0, "action_pause_max": 0}}


class FakeLocator:
    def __init__(self, items=None):
        self._items = items or []

    def all(self):
        return self._items


class FakeKeyboard:
    def __init__(self, page):
        self.page = page
        self.presses = []

    def press(self, key):
        self.presses.append(key)
        if key == "Enter" and self.page.focused_option_text:
            self.page.listbox.selected_value = self.page.focused_option_text


class FakeOption:
    def __init__(self, page, text):
        self.page = page
        self.text = text

    def is_visible(self, timeout=0):
        return True

    def inner_text(self, timeout=0):
        return self.text

    def scroll_into_view_if_needed(self):
        return None

    def click(self, force=False):
        raise RuntimeError("click no confirma seleccion")

    def evaluate(self, script):
        raise RuntimeError("js click no confirma seleccion")

    def focus(self):
        self.page.focused_option_text = self.text

    def hover(self):
        self.page.focused_option_text = self.text


class FakeSelectedOption:
    def __init__(self, page):
        self.page = page

    def inner_text(self, timeout=0):
        return self.page.listbox.selected_value


class FakeListbox:
    def __init__(self):
        self.selected_value = ""

    def evaluate(self, script):
        return [self.selected_value or "Elige"]

    def get_attribute(self, name):
        if name == "aria-expanded":
            return "true"
        return ""

    def focus(self):
        return None

    def click(self, force=False):
        return None


class FakePage:
    def __init__(self, url="https://docs.google.com/forms/d/e/test/viewform"):
        self.url = url
        self.goto_calls = []
        self.focused_option_text = None
        self.listbox = None
        self.option_items = []
        self.keyboard = FakeKeyboard(self)

    def goto(self, url, wait_until=None):
        self.url = url
        self.goto_calls.append((url, wait_until))

    def locator(self, selector):
        if selector == '[role="option"]':
            return FakeLocator(self.option_items)
        if selector == '[role="option"][aria-selected="true"], [role="option"][aria-checked="true"]':
            if self.listbox and self.listbox.selected_value:
                return FakeLocator([FakeSelectedOption(self)])
            return FakeLocator([])
        return FakeLocator()


class GoogleFormsFillerTest(unittest.TestCase):
    @patch("app.automation.google_forms_filler.verificar_envio", return_value=False)
    @patch("app.automation.google_forms_filler.click_boton")
    @patch("app.automation.google_forms_filler.wait_for_form_ready", return_value=True)
    def test_does_not_advance_when_required_dropdown_fails(
        self,
        _wait_ready,
        click_boton_mock,
        _verificar_envio,
    ):
        filler = GoogleFormsFiller()
        filler._find_question_container = Mock(return_value=object())
        filler._seleccionar_dropdown = Mock(return_value=False)

        fake_page = FakePage()
        response = {
            "_perfil": "test",
            "paginas": [
                {
                    "numero": 1,
                    "respuestas": [{"tipo": "desplegable", "valor": "32 - 38", "pregunta": "Edad"}],
                    "botones": ["Siguiente"],
                }
            ],
        }

        exito, _ = filler.fill_form(
            fake_page,
            response,
            fake_page.url,
            numero=1,
            runtime_config=ZERO_RUNTIME,
        )

        self.assertFalse(exito)
        click_boton_mock.assert_not_called()

    def test_dropdown_falls_back_to_enter_when_click_does_not_confirm(self):
        filler = GoogleFormsFiller()
        page = FakePage()
        listbox = FakeListbox()
        page.listbox = listbox
        page.option_items = [FakeOption(page, "32 - 38")]

        selected = filler._click_dropdown_option(page, listbox, filler._normalize_match_text("32 - 38"), ZERO_RUNTIME)

        self.assertTrue(selected)
        self.assertIn("Enter", page.keyboard.presses)
        self.assertEqual(listbox.selected_value, "32 - 38")

    def test_scale_response_does_not_select_random_option_when_target_missing(self):
        filler = GoogleFormsFiller()

        class MissingRadio:
            def __init__(self):
                self.clicked = False

            def get_attribute(self, name):
                return ""

            def click(self):
                self.clicked = True

        class MissingScope:
            def __init__(self):
                self.radios = [MissingRadio(), MissingRadio()]

            def locator(self, selector):
                if selector == '[role="radio"]':
                    return FakeLocator(self.radios)
                return FakeLocator([])

        scope = MissingScope()
        count = filler._responder_escalas_scoped(FakePage(), [("Totalmente de acuerdo", scope)], ZERO_RUNTIME)

        self.assertEqual(count, 0)
        self.assertFalse(any(r.clicked for r in scope.radios))


if __name__ == "__main__":
    unittest.main()
