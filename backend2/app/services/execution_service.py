"""
Servicio de ejecución del bot - Orquesta el llenado de encuestas.
"""
import io
import sys
import time
import threading
from datetime import datetime, timezone
from flask import current_app
from playwright.sync_api import sync_playwright

from app.automation.timing import build_runtime_config, pause_between_surveys
from app.database.connection import db
from app.database.models import Execution, Response
from app.services.generator_service import GeneratorService
from app.services.export_service import ExportService
from app.automation.google_forms_filler import GoogleFormsFiller
from app.automation.generic_filler import GenericFiller
from app.automation.navigation.selectors import detectar_plataforma


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

    def get_logs(self):
        with self.lock:
            return self.buffer.getvalue()

    def get_recent(self, max_chars=50000):
        """Retorna los últimos N caracteres de logs."""
        with self.lock:
            full = self.buffer.getvalue()
            if len(full) > max_chars:
                return full[-max_chars:]
            return full


class ExecutionService:
    """Orquesta la ejecución del bot de llenado de encuestas."""

    # Máximo de fallos consecutivos antes de parar automáticamente
    MAX_FALLOS_CONSECUTIVOS = 5
    # Máximo de reintentos por encuesta
    MAX_REINTENTOS = 2
    # Cada N encuestas, renovar contexto de browser (evitar detección)
    RENOVAR_CONTEXTO_CADA = 20

    def __init__(self, ai_service=None, generator: GeneratorService = None):
        self.ai_service = ai_service
        self.generator = generator or GeneratorService()
        self.export_service = ExportService()
        self._stop_events: dict[int, threading.Event] = {}

    def execute(
        self,
        app,
        execution_id: int,
        url: str,
        configuracion: dict,
        estructura: dict,
        cantidad: int,
        headless: bool = False,
        speed_profile: str | None = None,
    ):
        """Ejecuta el bot en un hilo separado con captura de logs."""
        stop_event = threading.Event()
        self._stop_events[execution_id] = stop_event

        # Capturar logs de este hilo
        log_capture = LogCapture(sys.stdout)
        self._log_captures = getattr(self, "_log_captures", {})
        self._log_captures[execution_id] = log_capture

        with app.app_context():
            old_stdout = sys.stdout
            sys.stdout = log_capture
            try:
                self._run(execution_id, url, configuracion, estructura, cantidad, headless, speed_profile, stop_event)
            except Exception as e:
                print(f"  Error fatal en ejecución: {e}")
                self._update_execution(execution_id, status="error", mensaje=f"Error: {str(e)[:200]}")
            finally:
                sys.stdout = old_stdout
                # Guardar logs finales en BD
                try:
                    execution = db.session.get(Execution, execution_id)
                    if execution:
                        execution.logs = log_capture.get_recent()
                        db.session.commit()
                except Exception:
                    pass
                self._stop_events.pop(execution_id, None)
                self._log_captures.pop(execution_id, None)

    def get_logs(self, execution_id: int) -> str:
        """Obtiene los logs en tiempo real de una ejecución."""
        captures = getattr(self, "_log_captures", {})
        capture = captures.get(execution_id)
        if capture:
            return capture.get_recent()
        # Si no hay captura activa, leer de BD
        try:
            execution = db.session.get(Execution, execution_id)
            if execution and execution.logs:
                return execution.logs
        except Exception:
            pass
        return ""

    def stop(self, execution_id: int):
        """Detiene una ejecución en curso."""
        event = self._stop_events.get(execution_id)
        if event:
            event.set()

    def is_running(self, execution_id: int) -> bool:
        """Verifica si una ejecución tiene un hilo activo."""
        event = self._stop_events.get(execution_id)
        return event is not None and not event.is_set()

    # ========== LOOP PRINCIPAL ==========

    def _run(
        self,
        execution_id: int,
        url: str,
        configuracion: dict,
        estructura: dict,
        cantidad: int,
        headless: bool,
        speed_profile: str | None,
        stop_event: threading.Event,
    ):
        """Loop principal de ejecución con reintentos y circuit breaker."""
        filler = self._get_filler(url)
        inicio = time.time()
        exitosas = 0
        fallidas = 0
        fallos_consecutivos = 0
        registros = []

        # Configuración del browser
        browser_config = self._get_browser_config()
        runtime_config = build_runtime_config(speed_profile, headless=headless)
        metrics = {
            "generation_time": 0.0,
            "fill_time": 0.0,
            "pause_time": 0.0,
            "retry_count": 0,
        }

        self._update_execution(
            execution_id,
            status="ejecutando",
            mensaje=f"Iniciando {cantidad} encuestas ({runtime_config['speed_profile']})...",
            total=cantidad,
        )

        print(f"\n Bot - {cantidad} respuestas")
        print(f"   URL: {url[:60]}...")
        print(f"   Modo: {'Invisible' if headless else 'Visible'}")
        print(f"   Perfil velocidad: {runtime_config['speed_profile']}")
        print(f"   Inicio: {datetime.now().strftime('%H:%M:%S')}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = self._create_context(browser, browser_config)

            i = 0
            while i < cantidad:
                i += 1

                # Verificar parada
                if stop_event.is_set():
                    print(f"\n  Detenido por el usuario en #{i}")
                    self._update_execution(execution_id, status="detenido", mensaje="Detenido por el usuario")
                    break

                # Circuit breaker: demasiados fallos seguidos
                if fallos_consecutivos >= self.MAX_FALLOS_CONSECUTIVOS:
                    msg = f"Detenido: {self.MAX_FALLOS_CONSECUTIVOS} fallos consecutivos"
                    print(f"\n  {msg}")
                    self._update_execution(execution_id, status="error", mensaje=msg)
                    break

                # Renovar contexto cada N encuestas (cookies limpias)
                if (i - 1) > 0 and (i - 1) % self.RENOVAR_CONTEXTO_CADA == 0:
                    print(f"  Renovando contexto de browser...")
                    try:
                        context.close()
                    except Exception:
                        pass
                    context = self._create_context(browser, browser_config)

                # Generar respuesta
                gen_inicio = time.perf_counter()
                respuesta = self.generator.generate(configuracion, estructura)
                metrics["generation_time"] += time.perf_counter() - gen_inicio

                # Intentar llenar con reintentos
                exito, tiempo, intentos, context = self._ejecutar_con_reintentos(
                    filler, context, respuesta, url, i, browser, browser_config, runtime_config
                )
                metrics["fill_time"] += tiempo
                metrics["retry_count"] += max(0, intentos - 1)

                if exito:
                    exitosas += 1
                    fallos_consecutivos = 0
                else:
                    fallidas += 1
                    fallos_consecutivos += 1

                # Guardar en BD
                self._save_response(execution_id, i, exito, tiempo, respuesta)
                registros.append({
                    "numero": i,
                    "exito": exito,
                    "tiempo": tiempo,
                    "perfil": respuesta.get("_perfil", ""),
                    "tendencia": respuesta.get("_tendencia", ""),
                    "respuestas": respuesta,
                })

                # Actualizar progreso
                transcurrido = time.time() - inicio
                promedio = transcurrido / i
                self._update_execution(
                    execution_id,
                    progreso=i,
                    exitosas=exitosas,
                    fallidas=fallidas,
                    mensaje=f"Encuesta {i}/{cantidad}",
                    tiempo_transcurrido=self._formatear_tiempo(transcurrido),
                    tiempo_por_encuesta=self._formatear_tiempo(promedio),
                )

                print(f"  {i}/{cantidad} | exitosas: {exitosas} fallidas: {fallidas} | "
                      f"{self._formatear_tiempo(transcurrido)}")

                # Pausa interruptible entre encuestas
                if i < cantidad and not stop_event.is_set():
                    pausa = pause_between_surveys(runtime_config, stop_event=stop_event)
                    metrics["pause_time"] += pausa
                    print(f"  Pausa {pausa:.1f}s...")

            # Cerrar browser
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

        # Generar Excel y marcar completado
        self._finalizar(
            execution_id,
            registros,
            exitosas,
            fallidas,
            cantidad,
            inicio,
            estructura,
            runtime_config,
            metrics,
        )

    # ========== EJECUCIÓN CON REINTENTOS ==========

    def _ejecutar_con_reintentos(self, filler, context, respuesta, url, numero, browser, browser_config, runtime_config):
        """Ejecuta una encuesta con reintentos si falla."""
        fill_start = time.perf_counter()
        for intento in range(1, self.MAX_REINTENTOS + 1):
            page = None
            try:
                page = context.new_page()
                exito, _ = filler.fill_form(page, respuesta, url, numero, runtime_config=runtime_config)
                return exito, time.perf_counter() - fill_start, intento, context

            except Exception as e:
                error_msg = str(e)
                print(f"  Error #{numero} (intento {intento}/{self.MAX_REINTENTOS}): {error_msg[:80]}")

                # Si el browser/context crasheó, recrear
                if "closed" in error_msg.lower() or "crashed" in error_msg.lower():
                    print(f"  Recreando contexto de browser...")
                    try:
                        context.close()
                    except Exception:
                        pass
                    context = self._create_context(browser, browser_config)

                if intento == self.MAX_REINTENTOS:
                    return False, time.perf_counter() - fill_start, intento, context

            finally:
                if page:
                    try:
                        page.close()
                    except Exception:
                        pass

        return False, time.perf_counter() - fill_start, self.MAX_REINTENTOS, context

    # ========== BROWSER ==========

    def _get_browser_config(self) -> dict:
        """Obtiene configuración del browser desde Flask config."""
        try:
            return {
                "locale": current_app.config.get("BROWSER_LOCALE", "es-PE"),
                "timezone": current_app.config.get("BROWSER_TIMEZONE", "America/Lima"),
                "vp_w": current_app.config.get("BROWSER_VIEWPORT_WIDTH", 1280),
                "vp_h": current_app.config.get("BROWSER_VIEWPORT_HEIGHT", 720),
                "pausa_min": current_app.config.get("PAUSA_MIN", 3.0),
                "pausa_max": current_app.config.get("PAUSA_MAX", 8.0),
            }
        except RuntimeError:
            return {
                "locale": "es-PE",
                "timezone": "America/Lima",
                "vp_w": 1280,
                "vp_h": 720,
                "pausa_min": 3.0,
                "pausa_max": 8.0,
            }

    def _create_context(self, browser, config: dict):
        """Crea un nuevo contexto de browser (cookies limpias)."""
        return browser.new_context(
            locale=config["locale"],
            timezone_id=config["timezone"],
            viewport={"width": config["vp_w"], "height": config["vp_h"]},
        )

    def _get_filler(self, url: str):
        """Retorna el filler apropiado según la plataforma."""
        platform = detectar_plataforma(url)
        if platform["name"] == "google_forms":
            return GoogleFormsFiller()
        return GenericFiller()

    # ========== PERSISTENCIA ==========

    def _save_response(self, execution_id: int, numero: int, exito: bool, tiempo: float, respuesta: dict):
        """Guarda una respuesta individual en BD."""
        try:
            response = Response(
                execution_id=execution_id,
                numero=numero,
                exito=exito,
                tiempo=tiempo,
                perfil=respuesta.get("_perfil", ""),
                tendencia=respuesta.get("_tendencia", ""),
                data=respuesta,
            )
            db.session.add(response)
            db.session.commit()
        except Exception as e:
            print(f"  Error guardando respuesta: {e}")
            db.session.rollback()

    def _update_execution(self, execution_id: int, **kwargs):
        """Actualiza el estado de una ejecución en BD."""
        try:
            execution = db.session.get(Execution, execution_id)
            if execution:
                for key, value in kwargs.items():
                    if hasattr(execution, key):
                        setattr(execution, key, value)
                if kwargs.get("status") == "completado":
                    execution.completed_at = datetime.now(timezone.utc)
                db.session.commit()
        except Exception as e:
            print(f"  Error actualizando ejecución: {e}")
            db.session.rollback()

    def _finalizar(self, execution_id, registros, exitosas, fallidas, cantidad, inicio, estructura, runtime_config, metrics):
        """Genera Excel y marca la ejecución como completada."""
        tiempo_final = time.time() - inicio
        tasa = (exitosas / max(cantidad, 1) * 100)
        promedio_final = tiempo_final / max(len(registros), 1)
        promedio_generacion = metrics["generation_time"] / max(len(registros), 1)
        promedio_activo = metrics["fill_time"] / max(len(registros), 1)
        promedio_pausa = metrics["pause_time"] / max(len(registros), 1)

        resumen = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": cantidad,
            "exitosas": exitosas,
            "fallidas": fallidas,
            "tasa_exito": tasa,
            "tiempo_total_fmt": self._formatear_tiempo(tiempo_final),
            "tiempo_promedio_fmt": self._formatear_tiempo(promedio_final),
        }

        try:
            export_dir = current_app.config.get("EXPORT_DIR", "exports")
        except RuntimeError:
            export_dir = "exports"

        excel_path = None
        if registros:
            try:
                excel_path = self.export_service.export_excel(registros, resumen, estructura, export_dir)
                print(f"\n  Excel: {excel_path}")
            except Exception as e:
                print(f"  Error generando Excel: {e}")

        status = "completado" if exitosas > 0 else "error"
        self._update_execution(
            execution_id,
            status=status,
            mensaje=(
                f"Completado: {exitosas}/{cantidad} en {self._formatear_tiempo(tiempo_final)} "
                f"({runtime_config['speed_profile']})"
            ),
            excel_path=excel_path,
        )

        print(f"\n  Perfil velocidad: {runtime_config['speed_profile']}")
        print(f"  Generacion total: {self._formatear_tiempo(metrics['generation_time'])}")
        print(f"  Llenado activo: {self._formatear_tiempo(metrics['fill_time'])}")
        print(f"  Pausas intencionales: {self._formatear_tiempo(metrics['pause_time'])}")
        print(f"  Reintentos totales: {metrics['retry_count']}")
        print(f"  Promedio generacion: {self._formatear_tiempo(promedio_generacion)}")
        print(f"  Promedio activo: {self._formatear_tiempo(promedio_activo)}")
        print(f"  Promedio pausa: {self._formatear_tiempo(promedio_pausa)}")
        print(f"  Promedio total: {self._formatear_tiempo(promedio_final)}")
        print(f"\n{'='*55}")
        print(f"  RESUMEN: {exitosas}/{cantidad} exitosas ({tasa:.0f}%)")
        print(f"  Tiempo: {self._formatear_tiempo(tiempo_final)} total")
        print(f"{'='*55}")

    @staticmethod
    def _formatear_tiempo(segundos: float) -> str:
        if segundos < 60:
            return f"{segundos:.1f}s"
        minutos = int(segundos // 60)
        segs = segundos % 60
        if minutos < 60:
            return f"{minutos}m {segs:.0f}s"
        horas = int(minutos // 60)
        mins = minutos % 60
        return f"{horas}h {mins}m {segs:.0f}s"
