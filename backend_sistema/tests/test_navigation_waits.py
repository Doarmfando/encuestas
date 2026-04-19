import unittest

from app.automation.navigation.waits import (
    capture_page_state,
    has_success_signal,
    wait_for_form_ready,
    wait_for_post_action,
    wait_for_submission_signal,
)


class FakeNode:
    def __init__(self, visible=False, text=""):
        self.visible = visible
        self.text = text

    def is_visible(self, timeout=0):
        return self.visible

    def inner_text(self, timeout=0):
        return self.text


class FakeLocator:
    def __init__(self, count=0, visible=False, items=None):
        self._count = count
        self._visible = visible
        self._items = items or []

    def count(self):
        return len(self._items) if self._items else self._count

    def nth(self, idx):
        if self._items:
            return self._items[idx]
        return FakeNode(visible=self._visible)

    def all(self):
        if self._items:
            return self._items
        return [FakeNode(visible=self._visible) for _ in range(self._count)]


class ReadyPage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/viewform"
        self.waited = []
        self.last_state = None

    def wait_for_load_state(self, state, timeout=None):
        self.last_state = state

    def wait_for_selector(self, selector, timeout=None):
        self.waited.append((selector, timeout))
        if selector == '[role="listitem"]':
            return True
        raise RuntimeError("selector missing")


class TransitionPage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/viewform"
        self._content_calls = 0

    def content(self):
        self._content_calls += 1
        if self._content_calls >= 2:
            self.url = "https://docs.google.com/forms/d/e/test/viewform?page=2"
            return "<body>after</body>"
        return "<body>before</body>"

    def locator(self, selector):
        return FakeLocator(count=1, visible=False)


class SubmitPage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/formResponse"

    def content(self):
        return "<body>Tu respuesta se ha registrado</body>"

    def locator(self, selector):
        return FakeLocator(count=0, visible=False)


class GoogleFormResponseWithoutSubmitPage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/formResponse"

    def evaluate(self, script):
        if "document.body ? document.body.innerText" in script:
            return "Municipio de Santiago\nSexo\nMasculino\nFemenino\nSiguiente"
        return ""

    def locator(self, selector):
        if '[role="button"]' in selector or 'button:has-text' in selector or 'input[type="submit"]' in selector:
            return FakeLocator(count=1, visible=True)
        if '[role="listitem"]' in selector or '[role="radio"]' in selector:
            return FakeLocator(count=1, visible=True)
        return FakeLocator(count=0, visible=False)


class MicrosoftSubmitPage:
    def __init__(self):
        self.url = "https://forms.office.com/Pages/ResponsePage.aspx?id=test"

    def evaluate(self, script):
        if "document.body ? document.body.innerText" in script:
            return "Las respuestas se han enviado correctamente.\nGuardar mi respuesta\nEnviar otra respuesta"
        return ""

    def locator(self, selector):
        return FakeLocator(count=0, visible=False)


class ValidationPage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/viewform"
        self._content_calls = 0

    def content(self):
        self._content_calls += 1
        if self._content_calls >= 2:
            return "<body>Esta pregunta es obligatoria</body>"
        return "<body>before</body>"

    def locator(self, selector):
        if selector == '[role="listitem"]':
            items = [
                FakeNode(visible=True, text="Edad *\nElige"),
                FakeNode(visible=True, text="Sexo *\nMasculino"),
            ]
            return FakeLocator(items=items)
        if '[role="button"]' in selector or 'button:has-text' in selector or 'input[type="submit"]' in selector:
            return FakeLocator(count=1, visible=True)
        if 'input:not([type="hidden"])' in selector or '[role="listbox"]' in selector:
            return FakeLocator(count=3, visible=True)
        return FakeLocator(count=0, visible=False)


class NavigationWaitsTest(unittest.TestCase):
    def test_wait_for_form_ready_uses_ready_selector(self):
        page = ReadyPage()
        ready = wait_for_form_ready(page, page.url, {"timing": {"ready_wait_timeout_s": 1.0, "settle_pause_min": 0, "settle_pause_max": 0}})
        self.assertTrue(ready)
        self.assertEqual(page.last_state, "domcontentloaded")
        self.assertTrue(any(selector == '[role="listitem"]' for selector, _ in page.waited))

    def test_wait_for_post_action_detects_url_change(self):
        page = TransitionPage()
        before_state = capture_page_state(page, page.url)
        changed = wait_for_post_action(
            page,
            before_state,
            page.url,
            {"timing": {"nav_wait_timeout_s": 0.4, "poll_interval_s": 0.01, "settle_pause_min": 0, "settle_pause_max": 0}},
        )
        self.assertTrue(changed)

    def test_submission_signal_detects_success_text_or_url(self):
        page = SubmitPage()
        self.assertTrue(has_success_signal(page, page.url, submit_clicked=True))
        self.assertTrue(
            wait_for_submission_signal(
                page,
                page.url,
                {"timing": {"submit_confirm_timeout_s": 0.2, "poll_interval_s": 0.01, "settle_pause_min": 0, "settle_pause_max": 0}},
                submit_clicked=True,
            )
        )

    def test_google_formresponse_url_does_not_count_as_success_before_submit(self):
        page = GoogleFormResponseWithoutSubmitPage()
        self.assertFalse(has_success_signal(page, page.url, submit_clicked=False))

    def test_submission_signal_detects_microsoft_forms_spanish_confirmation_text(self):
        page = MicrosoftSubmitPage()
        self.assertTrue(has_success_signal(page, page.url, submit_clicked=True))

    def test_wait_for_post_action_does_not_treat_validation_as_navigation(self):
        page = ValidationPage()
        before_state = capture_page_state(page, page.url)
        changed = wait_for_post_action(
            page,
            before_state,
            page.url,
            {"timing": {"nav_wait_timeout_s": 0.08, "poll_interval_s": 0.01, "settle_pause_min": 0, "settle_pause_max": 0}},
        )
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
