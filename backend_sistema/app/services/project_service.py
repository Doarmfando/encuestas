"""
Lógica de negocio para proyectos.
Las rutas solo hacen dispatch — la validación y persistencia de configs vive aquí.
Para cambiar reglas de validación de configs: solo editar este archivo.
"""
import logging
from datetime import datetime

from app.constants.limits import MIN_PERFILES, MAX_PERFILES, MIN_TENDENCIAS, MAX_TENDENCIAS
from app.constants.question_types import TIPOS_MANUALES_VALIDOS, TIPOS_REQUIEREN_OPCIONES, TIPO_ARCHIVO
from app.database.connection import db
from app.database.models import Execution, ProjectConfig

logger = logging.getLogger(__name__)


class ProjectValidationError(ValueError):
    """Error de validación de datos de proyecto."""


class ProjectService:
    """Operaciones de negocio sobre proyectos: validación y persistencia de configs."""

    # ── validación ─────────────────────────────────────────────────────────────

    def validar_configuracion(self, perfiles: list, tendencias: list) -> None:
        """Lanza ProjectValidationError si la configuración no cumple los límites."""
        perfiles = perfiles or []
        tendencias = tendencias or []
        if not (MIN_PERFILES <= len(perfiles) <= MAX_PERFILES):
            raise ProjectValidationError(
                f"Se requieren entre {MIN_PERFILES} y {MAX_PERFILES} perfiles"
            )
        if not (MIN_TENDENCIAS <= len(tendencias) <= MAX_TENDENCIAS):
            raise ProjectValidationError(
                f"Se requieren entre {MIN_TENDENCIAS} y {MAX_TENDENCIAS} tendencias"
            )

    def normalizar_paginas_manual(self, paginas: list) -> list:
        """Valida y normaliza la estructura de páginas enviada manualmente.

        Lanza ProjectValidationError con el detalle del campo inválido.
        """
        if not isinstance(paginas, list) or not paginas:
            raise ProjectValidationError("Se requiere al menos una pagina")

        total_paginas = len(paginas)
        normalizadas = []

        for idx, pag in enumerate(paginas):
            if not isinstance(pag, dict):
                raise ProjectValidationError(f"Pagina {idx + 1} invalida")

            preguntas = pag.get("preguntas") or []
            botones = pag.get("botones") or []

            if not isinstance(preguntas, list):
                raise ProjectValidationError(f"Pagina {idx + 1}: 'preguntas' debe ser una lista")
            if not isinstance(botones, list):
                raise ProjectValidationError(f"Pagina {idx + 1}: 'botones' debe ser una lista")

            preguntas_norm = []
            for q_idx, q in enumerate(preguntas):
                if not isinstance(q, dict):
                    raise ProjectValidationError(f"Pagina {idx + 1}, pregunta {q_idx + 1} invalida")

                texto = str(q.get("texto", "")).strip()
                if not texto:
                    raise ProjectValidationError(
                        f"Pagina {idx + 1}, pregunta {q_idx + 1}: texto requerido"
                    )
                tipo = str(q.get("tipo", "")).strip()
                if tipo not in TIPOS_MANUALES_VALIDOS:
                    raise ProjectValidationError(
                        f"Pagina {idx + 1}, pregunta {q_idx + 1}: tipo invalido '{tipo}'"
                    )

                opciones = q.get("opciones") or []
                if opciones and not isinstance(opciones, list):
                    raise ProjectValidationError(
                        f"Pagina {idx + 1}, pregunta {q_idx + 1}: 'opciones' debe ser lista"
                    )
                if tipo in TIPOS_REQUIEREN_OPCIONES and not opciones:
                    raise ProjectValidationError(
                        f"Pagina {idx + 1}, pregunta {q_idx + 1}: opciones requeridas para tipo '{tipo}'"
                    )

                cleaned = dict(q)
                cleaned["texto"] = texto
                cleaned["tipo"] = tipo
                cleaned["obligatoria"] = bool(q.get("obligatoria", False))
                cleaned["opciones"] = opciones
                if tipo == TIPO_ARCHIVO and "no_llenar" not in cleaned:
                    cleaned["no_llenar"] = True

                preguntas_norm.append(cleaned)

            botones_norm = [str(b).strip() for b in botones if str(b).strip()]
            if not botones_norm:
                botones_norm = ["Enviar"] if idx == total_paginas - 1 else ["Siguiente"]
            elif idx == total_paginas - 1 and "Enviar" not in botones_norm:
                botones_norm.append("Enviar")

            normalizadas.append({
                "numero": idx + 1,
                "preguntas": preguntas_norm,
                "botones": botones_norm,
            })

        return normalizadas

    # ── persistencia de configs ─────────────────────────────────────────────────

    def guardar_configuracion(
        self,
        project,
        *,
        nombre: str,
        perfiles: list,
        reglas: list,
        tendencias: list,
        ai_provider_used: str = "",
        replace_existing: bool = False,
        replace_config_id: int | None = None,
    ) -> tuple:
        """Persiste una config para el proyecto. Retorna (config, created: bool).

        Si replace_existing=True, actualiza la config activa en lugar de crear una nueva.
        """
        existing_config = None
        if replace_existing:
            if replace_config_id:
                existing_config = ProjectConfig.query.filter_by(
                    id=replace_config_id,
                    project_id=project.id,
                ).first()
            if not existing_config:
                existing_config = project.get_active_config()

        ProjectConfig.query.filter_by(project_id=project.id, is_active=True).update({"is_active": False})

        if existing_config:
            existing_config.nombre = nombre or existing_config.nombre or "Importado"
            existing_config.perfiles = perfiles
            existing_config.reglas_dependencia = reglas
            existing_config.tendencias_escalas = tendencias
            existing_config.ai_provider_used = ai_provider_used
            existing_config.is_active = True
            project.status = "configurado"
            db.session.commit()
            logger.debug("Config '%s' actualizada para proyecto %s", nombre, project.id)
            return existing_config, False

        config = ProjectConfig(
            project_id=project.id,
            nombre=nombre,
            perfiles=perfiles,
            reglas_dependencia=reglas,
            tendencias_escalas=tendencias,
            ai_provider_used=ai_provider_used,
            is_active=True,
        )
        db.session.add(config)
        project.status = "configurado"
        db.session.commit()
        logger.debug("Config '%s' creada para proyecto %s", nombre, project.id)
        return config, True

    # ── consultas ──────────────────────────────────────────────────────────────

    def tiene_balanced_exitoso(self, project_id: int) -> bool:
        """True si existe una ejecución 'balanced' completada al 100%."""
        ejecuciones = (
            Execution.query.filter_by(project_id=project_id, status="completado")
            .order_by(Execution.created_at.desc())
            .limit(30)
            .all()
        )
        for execu in ejecuciones:
            mensaje = (execu.mensaje or "").lower()
            if "(balanced)" in mensaje and execu.total and execu.exitosas == execu.total:
                return True
        return False
