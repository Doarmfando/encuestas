import unittest

from app.automation.navigation.waits import (
    capture_page_state,
    has_success_signal,
    wait_for_form_ready,
    wait_for_post_action,
    wait_for_submission_signal,
)


class FakeNode:
    def __init__(self, visible=False):
        self.visible = visible

    def is_visible(self, timeout=0):
        return self.visible


class FakeLocator:
    def __init__(self, count=0, visible=False):
        self._count = count
        self._visible = visible

    def count(self):
        return self._count

    def nth(self, idx):
        return FakeNode(visible=self._visible)


class ReadyPage:
    def __init__(self):
        self.url = "https://docs.google.com/forms/d/e/test/viewform"
        self.waited = []

    def wait_for_load_state(self, state):
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


if __name__ == "__main__":
    unittest.main()
