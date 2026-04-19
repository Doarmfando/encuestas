"""Tests para los submódulos de execution/."""
import threading
import unittest
from unittest.mock import MagicMock, patch


class LogCaptureTest(unittest.TestCase):

    def setUp(self):
        from app.services.execution.log_capture import LogCapture
        self.LogCapture = LogCapture

    def test_write_stores_text(self):
        original = MagicMock()
        cap = self.LogCapture(original)
        cap.write("hola mundo")
        self.assertIn("hola mundo", cap.get_logs())

    def test_write_also_forwards_to_original(self):
        original = MagicMock()
        cap = self.LogCapture(original)
        cap.write("forward")
        original.write.assert_called_once_with("forward")

    def test_get_recent_truncates_to_max_chars(self):
        original = MagicMock()
        cap = self.LogCapture(original)
        long_text = "x" * 200
        cap.write(long_text)
        result = cap.get_recent(max_chars=100)
        self.assertEqual(len(result), 100)
        self.assertEqual(result, "x" * 100)

    def test_get_recent_returns_full_if_under_limit(self):
        original = MagicMock()
        cap = self.LogCapture(original)
        cap.write("short")
        self.assertEqual(cap.get_recent(max_chars=1000), "short")

    def test_thread_safe_concurrent_writes(self):
        original = MagicMock()
        cap = self.LogCapture(original)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    cap.write("data")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertIn("data", cap.get_logs())


class ThreadLocalStdoutTest(unittest.TestCase):

    def test_forwards_to_original_when_no_capture(self):
        from app.services.execution.log_capture import ThreadLocalStdout, thread_local
        original = MagicMock()
        stdout = ThreadLocalStdout(original)
        thread_local.log_capture = None
        stdout.write("texto")
        original.write.assert_called_once_with("texto")

    def test_redirects_to_capture_when_set(self):
        from app.services.execution.log_capture import ThreadLocalStdout, thread_local, LogCapture
        original = MagicMock()
        capture = LogCapture(MagicMock())
        thread_local.log_capture = capture
        stdout = ThreadLocalStdout(original)
        stdout.write("capturado")
        self.assertIn("capturado", capture.get_logs())
        thread_local.log_capture = None


class BrowserManagerTest(unittest.TestCase):

    def test_get_config_returns_defaults_outside_flask(self):
        from app.services.execution.browser_manager import BrowserManager
        mgr = BrowserManager()
        config = mgr.get_config()
        self.assertEqual(config["locale"], "es-PE")
        self.assertIn("vp_w", config)
        self.assertIn("vp_h", config)

    def test_get_filler_raises_for_unsupported_url(self):
        from app.services.execution.browser_manager import BrowserManager
        mgr = BrowserManager()
        with self.assertRaises(ValueError):
            mgr.get_filler("https://ejemplo.com/formulario")

    def test_get_filler_returns_google_filler(self):
        from app.services.execution.browser_manager import BrowserManager
        from app.automation.google_forms_filler import GoogleFormsFiller
        mgr = BrowserManager()
        filler = mgr.get_filler("https://docs.google.com/forms/d/abc/viewform")
        self.assertIsInstance(filler, GoogleFormsFiller)


class PersistenceFormatTest(unittest.TestCase):

    def test_fmt_seconds(self):
        from app.services.execution.persistence import _fmt
        self.assertEqual(_fmt(5.3), "5.3s")

    def test_fmt_minutes(self):
        from app.services.execution.persistence import _fmt
        self.assertEqual(_fmt(90), "1m 30s")

    def test_fmt_hours(self):
        from app.services.execution.persistence import _fmt
        result = _fmt(3700)
        self.assertIn("h", result)


if __name__ == "__main__":
    unittest.main()
