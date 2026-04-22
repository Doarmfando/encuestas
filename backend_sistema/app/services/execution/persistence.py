"""
Persistencia y finalización de ejecuciones: BD, Excel y resumen de métricas.
Para agregar un nuevo formato de exportación: inyectar otro export_service en __init__.
"""
import logging
import time
from datetime import datetime, timezone

from flask import current_app

from app.database.connection import db
from app.database.models import Execution, Response
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)


class ExecutionPersistence:
    """Guarda respuestas, actualiza ejecuciones y genera el Excel final."""

    def __init__(self):
        self._export = ExportService()

    def save_response(self, execution_id: int, numero: int, exito: bool, tiempo: float, respuesta: dict):
        try:
            db.session.add(Response(
                execution_id=execution_id,
                numero=numero,
                exito=exito,
                tiempo=tiempo,
                perfil=respuesta.get("_perfil", ""),
                tendencia=respuesta.get("_tendencia", ""),
                data=respuesta,
            ))
            db.session.commit()
        except Exception as e:
            logger.error("Error guardando respuesta %s: %s", numero, e, exc_info=True)
            db.session.rollback()

    def update_execution(self, execution_id: int, **kwargs):
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
            logger.error("Error actualizando ejecución %s: %s", execution_id, e, exc_info=True)
            db.session.rollback()

    def save_logs(self, execution_id: int, logs: str):
        try:
            execution = db.session.get(Execution, execution_id)
            if execution:
                execution.logs = logs
                db.session.commit()
        except Exception as e:
            logger.warning("No se pudieron guardar logs para ejecución %s: %s", execution_id, e)

    def read_logs(self, execution_id: int) -> str:
        try:
            execution = db.session.get(Execution, execution_id)
            if execution and execution.logs:
                return execution.logs
        except Exception as e:
            logger.warning("No se pudieron leer logs para ejecución %s: %s", execution_id, e)
        return ""

    def finalize(
        self,
        execution_id: int,
        registros: list,
        exitosas: int,
        fallidas: int,
        cantidad: int,
        inicio: float,
        estructura: dict,
        runtime_config: dict,
        metrics: dict,
    ):
        tiempo_final = time.time() - inicio
        tasa = exitosas / max(cantidad, 1) * 100
        n = max(len(registros), 1)

        resumen = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": cantidad,
            "exitosas": exitosas,
            "fallidas": fallidas,
            "tasa_exito": tasa,
            "tiempo_total_fmt": _fmt(tiempo_final),
            "tiempo_promedio_fmt": _fmt(tiempo_final / n),
        }

        try:
            export_dir = current_app.config.get("EXPORT_DIR", "exports")
        except RuntimeError:
            export_dir = "exports"

        excel_path = None
        if registros:
            try:
                excel_path = self._export.export_excel(registros, resumen, estructura, export_dir)
                logger.info("Excel generado: %s", excel_path)
            except Exception as e:
                logger.error("Error generando Excel para ejecución %s: %s", execution_id, e, exc_info=True)

        self.update_execution(
            execution_id,
            status="completado" if exitosas > 0 else "error",
            mensaje=(
                f"Completado: {exitosas}/{cantidad} en {_fmt(tiempo_final)} "
                f"({runtime_config['speed_profile']})"
            ),
            excel_path=excel_path,
        )

        _print_summary(exitosas, cantidad, tasa, tiempo_final, metrics, n)


def _fmt(segundos: float) -> str:
    if segundos < 60:
        return f"{segundos:.1f}s"
    minutos = int(segundos // 60)
    segs = segundos % 60
    if minutos < 60:
        return f"{minutos}m {segs:.0f}s"
    horas = int(minutos // 60)
    return f"{horas}h {minutos % 60}m {segs:.0f}s"


_summary_logger = logging.getLogger(__name__)


def _print_summary(exitosas: int, cantidad: int, tasa: float, tiempo_final: float, metrics: dict, n: int):
    _summary_logger.info(
        "RESUMEN: %s/%s exitosas (%.0f%%) en %s | perfil=%s gen=%s fill=%s pausas=%s reintentos=%s",
        exitosas, cantidad, tasa, _fmt(tiempo_final),
        metrics.get("speed_profile", "?"),
        _fmt(metrics["generation_time"]),
        _fmt(metrics["fill_time"]),
        _fmt(metrics["pause_time"]),
        metrics["retry_count"],
    )
