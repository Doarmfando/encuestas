"""
Orquestador de ejecución del bot.
Delega logs, browser y persistencia a submódulos en execution/.
Para cambiar el motor de browser o la lógica de reintento, editar solo execution/browser_manager.py.
"""
import logging
import sys
import time
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

from app.automation.timing import build_runtime_config, pause_between_surveys
from app.services.generator_service import GeneratorService
from app.services.execution import (
    LogCapture, ThreadLocalStdout, thread_local,
    BrowserManager, ExecutionPersistence,
)

logger = logging.getLogger(__name__)


class ExecutionService:
    """Orquesta el llenado de encuestas: genera → llena → persiste."""

    MAX_FALLOS_CONSECUTIVOS = 5
    MAX_REINTENTOS = 2
    RENOVAR_CONTEXTO_CADA = 20

    _stdout_installed = False

    def __init__(self, ai_service=None, generator: GeneratorService = None, browser: BrowserManager = None):
        self.generator = generator or GeneratorService()
        self._browser = browser or BrowserManager()
        self._db = ExecutionPersistence()
        self._stop_events: dict[int, threading.Event] = {}
        self._log_captures: dict[int, LogCapture] = {}

    @classmethod
    def _install_thread_local_stdout(cls):
        if not cls._stdout_installed:
            sys.stdout = ThreadLocalStdout(sys.stdout)
            cls._stdout_installed = True

    # ── API pública ────────────────────────────────────────────────────────────

    def execute(self, app, execution_id: int, url: str, configuracion: dict,
                estructura: dict, cantidad: int, headless: bool = False,
                speed_profile: str | None = None):
        self._install_thread_local_stdout()

        stop_event = threading.Event()
        self._stop_events[execution_id] = stop_event

        original = sys.stdout.original if isinstance(sys.stdout, ThreadLocalStdout) else sys.stdout
        log_capture = LogCapture(original)
        self._log_captures[execution_id] = log_capture

        with app.app_context():
            thread_local.log_capture = log_capture
            try:
                self._run(execution_id, url, configuracion, estructura,
                          cantidad, headless, speed_profile, stop_event)
            except Exception as e:
                logger.error("Error fatal en ejecución %s: %s", execution_id, e, exc_info=True)
                self._db.update_execution(execution_id, status="error", mensaje=f"Error: {str(e)[:200]}")
            finally:
                thread_local.log_capture = None
                self._db.save_logs(execution_id, log_capture.get_recent())
                self._stop_events.pop(execution_id, None)
                self._log_captures.pop(execution_id, None)

    def get_logs(self, execution_id: int) -> str:
        capture = self._log_captures.get(execution_id)
        return capture.get_recent() if capture else self._db.read_logs(execution_id)

    def stop(self, execution_id: int):
        event = self._stop_events.get(execution_id)
        if event:
            event.set()

    def is_running(self, execution_id: int) -> bool:
        event = self._stop_events.get(execution_id)
        return event is not None and not event.is_set()

    # ── loop principal ─────────────────────────────────────────────────────────

    def _run(self, execution_id, url, configuracion, estructura, cantidad,
             headless, speed_profile, stop_event):
        filler = self._browser.get_filler(url)
        runtime_config = build_runtime_config(speed_profile, headless=headless)
        metrics = {"generation_time": 0.0, "fill_time": 0.0, "pause_time": 0.0,
                   "retry_count": 0, "speed_profile": runtime_config["speed_profile"]}

        self._db.update_execution(
            execution_id, status="ejecutando",
            mensaje=f"Iniciando {cantidad} encuestas ({runtime_config['speed_profile']})...",
            total=cantidad,
        )
        logger.info("Bot - %s respuestas | URL: %s... | Modo: %s | Perfil: %s | Inicio: %s",
                    cantidad, url[:60],
                    "Invisible" if headless else "Visible",
                    runtime_config["speed_profile"],
                    datetime.now().strftime("%H:%M:%S"))

        inicio = time.time()
        exitosas = fallidas = fallos_consecutivos = 0
        registros = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = self._browser.create_context(browser)

            for i in range(1, cantidad + 1):
                if stop_event.is_set():
                    logger.info("Detenido por el usuario en #%s", i)
                    self._db.update_execution(execution_id, status="detenido", mensaje="Detenido por el usuario")
                    break

                if fallos_consecutivos >= self.MAX_FALLOS_CONSECUTIVOS:
                    msg = f"Detenido: {self.MAX_FALLOS_CONSECUTIVOS} fallos consecutivos"
                    logger.warning(msg)
                    self._db.update_execution(execution_id, status="error", mensaje=msg)
                    break

                if (i - 1) > 0 and (i - 1) % self.RENOVAR_CONTEXTO_CADA == 0:
                    logger.info("Renovando contexto de browser...")
                    try:
                        context.close()
                    except Exception:
                        pass
                    context = self._browser.create_context(browser)

                gen_inicio = time.perf_counter()
                respuesta = self.generator.generate(configuracion, estructura)
                metrics["generation_time"] += time.perf_counter() - gen_inicio

                exito, tiempo, intentos, context = self._ejecutar_con_reintentos(
                    filler, context, respuesta, url, i, browser, runtime_config
                )
                metrics["fill_time"] += tiempo
                metrics["retry_count"] += max(0, intentos - 1)

                if exito:
                    exitosas += 1
                    fallos_consecutivos = 0
                else:
                    fallidas += 1
                    fallos_consecutivos += 1

                self._db.save_response(execution_id, i, exito, tiempo, respuesta)
                registros.append({
                    "numero": i, "exito": exito, "tiempo": tiempo,
                    "perfil": respuesta.get("_perfil", ""),
                    "tendencia": respuesta.get("_tendencia", ""),
                    "respuestas": respuesta,
                })

                transcurrido = time.time() - inicio
                self._db.update_execution(
                    execution_id, progreso=i, exitosas=exitosas, fallidas=fallidas,
                    mensaje=f"Encuesta {i}/{cantidad}",
                    tiempo_transcurrido=_fmt(transcurrido),
                    tiempo_por_encuesta=_fmt(transcurrido / i),
                )
                logger.info("%s/%s | exitosas: %s fallidas: %s | %s",
                            i, cantidad, exitosas, fallidas, _fmt(transcurrido))

                if i < cantidad and not stop_event.is_set():
                    pausa = pause_between_surveys(runtime_config, stop_event=stop_event)
                    metrics["pause_time"] += pausa
                    logger.debug("Pausa %.1fs...", pausa)

            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

        self._db.finalize(
            execution_id, registros, exitosas, fallidas, cantidad,
            inicio, estructura, runtime_config, metrics,
        )

    # ── reintentos ─────────────────────────────────────────────────────────────

    def _ejecutar_con_reintentos(self, filler, context, respuesta, url, numero,
                                  browser, runtime_config):
        fill_start = time.perf_counter()
        for intento in range(1, self.MAX_REINTENTOS + 1):
            page = None
            try:
                page = context.new_page()
                exito, _ = filler.fill_form(page, respuesta, url, numero, runtime_config=runtime_config)
                return exito, time.perf_counter() - fill_start, intento, context
            except Exception as e:
                error_msg = str(e)
                logger.warning("Error #%s (intento %s/%s): %s", numero, intento, self.MAX_REINTENTOS, error_msg[:80])
                if "closed" in error_msg.lower() or "crashed" in error_msg.lower():
                    logger.info("Recreando contexto de browser...")
                    try:
                        context.close()
                    except Exception:
                        pass
                    context = self._browser.create_context(browser)
                if intento == self.MAX_REINTENTOS:
                    return False, time.perf_counter() - fill_start, intento, context
            finally:
                if page:
                    try:
                        page.close()
                    except Exception:
                        pass
        return False, time.perf_counter() - fill_start, self.MAX_REINTENTOS, context


def _fmt(segundos: float) -> str:
    if segundos < 60:
        return f"{segundos:.1f}s"
    minutos = int(segundos // 60)
    segs = segundos % 60
    if minutos < 60:
        return f"{minutos}m {segs:.0f}s"
    horas = int(minutos // 60)
    return f"{horas}h {minutos % 60}m {segs:.0f}s"
