"""
Infraestructura de captura de logs por hilo.
Redirige prints al buffer del hilo activo para enviarlos al frontend.
"""
import io
import threading

thread_local = threading.local()


class ThreadLocalStdout:
    """Stdout que redirige al LogCapture del hilo actual, si existe."""

    def __init__(self, original):
        self.original = original

    def write(self, text):
        capture = getattr(thread_local, "log_capture", None)
        if capture:
            capture.write(text)
        else:
            self.original.write(text)

    def flush(self):
        self.original.flush()


class LogCapture:
    """Captura prints y los almacena para enviarlos al frontend."""

    def __init__(self, original_stdout):
        self.original = original_stdout
        self.buffer = io.StringIO()
        self.lock = threading.Lock()

    def write(self, text):
        self.original.write(text)
        with self.lock:
            self.buffer.write(text)

    def flush(self):
        self.original.flush()

    def get_logs(self) -> str:
        with self.lock:
            return self.buffer.getvalue()

    def get_recent(self, max_chars: int = 50000) -> str:
        with self.lock:
            full = self.buffer.getvalue()
            return full[-max_chars:] if len(full) > max_chars else full
