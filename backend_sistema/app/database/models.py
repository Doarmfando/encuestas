"""
Modelos de base de datos para el sistema de encuestas.
Rediseño: Project como entidad central que agrupa todo.
"""
from datetime import datetime, timezone
from app.database.connection import db


class Project(db.Model):
    """Proyecto: entidad principal que encapsula URL, scraping, configs y ejecuciones."""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(300), nullable=False)
    descripcion = db.Column(db.Text, default="")
    url = db.Column(db.String(2048), nullable=False)
    plataforma = db.Column(db.String(50), default="google_forms")
    estructura = db.Column(db.JSON, nullable=True)  # resultado del scraping
    total_preguntas = db.Column(db.Integer, default=0)
    requiere_login = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="nuevo")  # nuevo, scrapeado, configurado, listo
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relaciones
    configs = db.relationship("ProjectConfig", backref="project", lazy=True, cascade="all, delete-orphan")
    executions = db.relationship("Execution", backref="project", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        active_config = self.get_active_config()
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "url": self.url,
            "plataforma": self.plataforma,
            "total_preguntas": self.total_preguntas,
            "requiere_login": self.requiere_login,
            "status": self.status,
            "tiene_estructura": self.estructura is not None,
            "config_activa": active_config.to_dict() if active_config else None,
            "total_configs": len(self.configs),
            "total_ejecuciones": len(self.executions),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_dict_simple(self):
        """Version ligera para listados."""
        last_exec = Execution.query.filter_by(project_id=self.id).order_by(Execution.created_at.desc()).first()
        return {
            "id": self.id,
            "nombre": self.nombre,
            "url": self.url,
            "plataforma": self.plataforma,
            "status": self.status,
            "total_preguntas": self.total_preguntas,
            "total_configs": len(self.configs),
            "ultima_ejecucion": last_exec.to_dict_simple() if last_exec else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_estructura(self):
        """Retorna la estructura en formato del scraper."""
        return {
            "url": self.url,
            "titulo": self.nombre,
            "descripcion": self.descripcion,
            "paginas": (self.estructura or {}).get("paginas", []),
            "total_preguntas": self.total_preguntas,
            "requiere_login": self.requiere_login,
        }

    def get_active_config(self):
        """Retorna la config activa del proyecto."""
        return ProjectConfig.query.filter_by(project_id=self.id, is_active=True).first()


class ProjectConfig(db.Model):
    """Configuración de perfiles/reglas/tendencias para un proyecto."""
    __tablename__ = "project_configs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    nombre = db.Column(db.String(200), default="default")
    perfiles = db.Column(db.JSON, default=list)
    reglas_dependencia = db.Column(db.JSON, default=list)
    tendencias_escalas = db.Column(db.JSON, default=list)
    ai_provider_used = db.Column(db.String(50), default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "nombre": self.nombre,
            "perfiles": self.perfiles,
            "reglas_dependencia": self.reglas_dependencia,
            "tendencias_escalas": self.tendencias_escalas,
            "total_perfiles": len(self.perfiles or []),
            "total_reglas": len(self.reglas_dependencia or []),
            "total_tendencias": len(self.tendencias_escalas or []),
            "ai_provider_used": self.ai_provider_used,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_configuracion(self):
        """Formato para el generador."""
        return {
            "perfiles": self.perfiles or [],
            "reglas_dependencia": self.reglas_dependencia or [],
            "tendencias_escalas": self.tendencias_escalas or [],
        }


class Execution(db.Model):
    """Ejecución del bot dentro de un proyecto."""
    __tablename__ = "executions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    config_id = db.Column(db.Integer, db.ForeignKey("project_configs.id"), nullable=True)
    status = db.Column(db.String(20), default="idle")  # idle, ejecutando, completado, error, detenido
    mensaje = db.Column(db.String(500), default="Listo")
    total = db.Column(db.Integer, default=0)
    progreso = db.Column(db.Integer, default=0)
    exitosas = db.Column(db.Integer, default=0)
    fallidas = db.Column(db.Integer, default=0)
    tiempo_transcurrido = db.Column(db.String(50), default="0s")
    tiempo_por_encuesta = db.Column(db.String(50), default="0s")
    headless = db.Column(db.Boolean, default=False)
    excel_path = db.Column(db.String(1024), nullable=True)
    logs = db.Column(db.Text, default="")
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    responses = db.relationship("Response", backref="execution", lazy=True, cascade="all, delete-orphan")
    config = db.relationship("ProjectConfig", backref="executions_using")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "config_id": self.config_id,
            "status": self.status,
            "mensaje": self.mensaje,
            "total": self.total,
            "progreso": self.progreso,
            "exitosas": self.exitosas,
            "fallidas": self.fallidas,
            "tiempo_transcurrido": self.tiempo_transcurrido,
            "tiempo_por_encuesta": self.tiempo_por_encuesta,
            "excel": self.excel_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict_simple(self):
        """Version ligera para listados."""
        return {
            "id": self.id,
            "status": self.status,
            "exitosas": self.exitosas,
            "fallidas": self.fallidas,
            "total": self.total,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_estado(self):
        """Formato para polling de estado."""
        return {
            "execution_id": self.id,
            "project_id": self.project_id,
            "fase": self.status,
            "mensaje": self.mensaje,
            "progreso": self.progreso,
            "total": self.total,
            "exitosas": self.exitosas,
            "fallidas": self.fallidas,
            "tiempo_transcurrido": self.tiempo_transcurrido,
            "tiempo_por_encuesta": self.tiempo_por_encuesta,
            "excel": self.excel_path,
            "logs": self.logs or "",
        }


class Response(db.Model):
    """Respuesta individual de una ejecución."""
    __tablename__ = "responses"

    id = db.Column(db.Integer, primary_key=True)
    execution_id = db.Column(db.Integer, db.ForeignKey("executions.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    exito = db.Column(db.Boolean, default=False)
    tiempo = db.Column(db.Float, default=0.0)
    perfil = db.Column(db.String(200), default="")
    tendencia = db.Column(db.String(200), default="")
    data = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "numero": self.numero,
            "exito": self.exito,
            "tiempo": self.tiempo,
            "perfil": self.perfil,
            "tendencia": self.tendencia,
            "respuestas": self.data,
        }


class PromptTemplate(db.Model):
    """Plantillas de prompts editables."""
    __tablename__ = "prompt_templates"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, default="")
    contenido = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "contenido": self.contenido,
            "is_default": self.is_default,
        }


class AIProviderConfig(db.Model):
    """Configuración de proveedores de IA."""
    __tablename__ = "ai_provider_configs"

    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(50), nullable=False)
    api_key = db.Column(db.String(500), default="")
    model = db.Column(db.String(100), default="")
    temperature = db.Column(db.Float, default=0.7)
    max_tokens = db.Column(db.Integer, default=4000)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "provider_name": self.provider_name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "is_active": self.is_active,
            "has_api_key": bool(self.api_key),
        }
