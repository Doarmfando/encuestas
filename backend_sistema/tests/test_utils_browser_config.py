"""Tests para app/utils/browser_config.py"""
import unittest
from app.utils.browser_config import get_browser_context_options


class BrowserContextOptionsTest(unittest.TestCase):
    def test_defaults_when_no_config(self):
        opts = get_browser_context_options()
        self.assertEqual(opts["locale"], "es-PE")
        self.assertEqual(opts["timezone_id"], "America/Lima")
        self.assertEqual(opts["viewport"]["width"], 1280)
        self.assertEqual(opts["viewport"]["height"], 720)

    def test_custom_locale(self):
        opts = get_browser_context_options({"BROWSER_LOCALE": "en-US"})
        self.assertEqual(opts["locale"], "en-US")

    def test_custom_timezone(self):
        opts = get_browser_context_options({"BROWSER_TIMEZONE": "UTC"})
        self.assertEqual(opts["timezone_id"], "UTC")

    def test_custom_viewport(self):
        opts = get_browser_context_options({
            "BROWSER_VIEWPORT_WIDTH": 1920,
            "BROWSER_VIEWPORT_HEIGHT": 1080,
        })
        self.assertEqual(opts["viewport"]["width"], 1920)
        self.assertEqual(opts["viewport"]["height"], 1080)

    def test_partial_config_uses_defaults(self):
        opts = get_browser_context_options({"BROWSER_LOCALE": "fr-FR"})
        self.assertEqual(opts["locale"], "fr-FR")
        self.assertEqual(opts["timezone_id"], "America/Lima")

    def test_returns_correct_keys_for_playwright(self):
        opts = get_browser_context_options()
        self.assertIn("locale", opts)
        self.assertIn("timezone_id", opts)
        self.assertIn("viewport", opts)

    def test_viewport_is_dict(self):
        opts = get_browser_context_options()
        self.assertIsInstance(opts["viewport"], dict)
        self.assertIn("width", opts["viewport"])
        self.assertIn("height", opts["viewport"])


if __name__ == "__main__":
    unittest.main()
