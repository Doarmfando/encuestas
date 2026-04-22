"""
Documentación interactiva y utilidades de operación.
GET /docs         → Swagger UI
GET /openapi.json → Especificación OpenAPI 3.0
GET /health       → Estado del sistema (BD + servicios)
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify

docs_bp = Blueprint("docs", __name__)
logger = logging.getLogger(__name__)


@docs_bp.route("/docs")
def swagger_ui():
    """Sirve la interfaz Swagger UI usando CDN."""
    html = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Sistema Encuestas — API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      deepLinking: true,
    });
  </script>
</body>
</html>"""
    from flask import Response
    return Response(html, mimetype="text/html")


@docs_bp.route("/health")
def health():
    """Estado del sistema: BD + timestamp."""
    db_status = "ok"
    db_detail = None
    try:
        from app.database.connection import db
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        db_detail = str(e)
        logger.error("Health check: fallo de BD: %s", e)

    status = "ok" if db_status == "ok" else "degraded"
    response = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {"database": db_status},
    }
    if db_detail:
        response["services"]["database_detail"] = db_detail

    return jsonify(response), 200 if status == "ok" else 503


@docs_bp.route("/openapi.json")
def openapi_spec():
    """Retorna la especificación OpenAPI 3.0 completa."""
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Sistema de Encuestas API",
            "version": "1.0.0",
            "description": "API para gestión de proyectos de encuestas automatizadas.",
        },
        "servers": [{"url": "/api", "description": "API principal"}],
        "tags": [
            {"name": "Proyectos", "description": "CRUD de proyectos"},
            {"name": "Scraping", "description": "Extracción de estructura del formulario"},
            {"name": "Análisis IA", "description": "Generación de configuración con IA"},
            {"name": "Configs", "description": "Gestión de configuraciones de perfiles"},
            {"name": "Ejecución", "description": "Control del bot de llenado"},
            {"name": "Dashboard", "description": "Estado global"},
            {"name": "Configuración", "description": "Proveedores IA y settings"},
            {"name": "Prompts", "description": "Prompts editables de IA"},
        ],
        "paths": {
            "/health": {
                "get": {
                    "tags": ["Dashboard"],
                    "summary": "Health check",
                    "description": "Verifica BD. Retorna 200 ok o 503 degraded.",
                    "responses": {
                        "200": {"description": "Sistema operativo"},
                        "503": {"description": "BD no disponible"},
                    },
                },
            },
            # ── Proyectos ──────────────────────────────────────────────────────
            "/projects": {
                "get": {
                    "tags": ["Proyectos"],
                    "summary": "Listar proyectos",
                    "responses": {"200": {"description": "Lista de proyectos"}},
                },
                "post": {
                    "tags": ["Proyectos"],
                    "summary": "Crear proyecto",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "required": ["nombre", "url"],
                            "properties": {
                                "nombre": {"type": "string", "example": "Mi Encuesta"},
                                "url": {"type": "string", "example": "https://forms.gle/abc"},
                                "descripcion": {"type": "string"},
                            },
                        }}},
                    },
                    "responses": {
                        "201": {"description": "Proyecto creado"},
                        "400": {"description": "Datos inválidos o URL no soportada"},
                    },
                },
            },
            "/projects/{project_id}": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "get": {"tags": ["Proyectos"], "summary": "Obtener proyecto", "responses": {"200": {"description": "Detalle del proyecto"}, "404": {"description": "No encontrado"}}},
                "put": {
                    "tags": ["Proyectos"],
                    "summary": "Actualizar nombre / URL / descripción",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"nombre": {"type": "string"}, "url": {"type": "string"}, "descripcion": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Proyecto actualizado"}, "400": {"description": "URL no soportada"}, "404": {"description": "No encontrado"}},
                },
                "delete": {"tags": ["Proyectos"], "summary": "Eliminar proyecto", "responses": {"200": {"description": "Eliminado"}, "400": {"description": "Tiene ejecución activa"}, "404": {"description": "No encontrado"}}},
            },
            # ── Scraping ──────────────────────────────────────────────────────
            "/projects/{project_id}/scrape": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {
                    "tags": ["Scraping"],
                    "summary": "Scrapear formulario",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"headless": {"type": "boolean", "default": True}, "force_platform": {"type": "string", "enum": ["google_forms", "microsoft_forms"]}}}}}},
                    "responses": {"200": {"description": "Estructura extraída"}, "400": {"description": "URL no soportada o requiere login"}, "500": {"description": "Error de scraping"}},
                },
            },
            "/projects/{project_id}/manual-structure": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {
                    "tags": ["Scraping"],
                    "summary": "Guardar estructura manual",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["paginas"], "properties": {"paginas": {"type": "array"}}}}}},
                    "responses": {"200": {"description": "Estructura guardada"}, "400": {"description": "Estructura inválida"}},
                },
            },
            # ── Análisis IA ───────────────────────────────────────────────────
            "/projects/{project_id}/analyze": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {
                    "tags": ["Análisis IA"],
                    "summary": "Analizar con IA (preview)",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"instrucciones": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Config generada (preview)"}, "400": {"description": "Sin estructura scrapeada"}, "500": {"description": "Error IA"}},
                },
            },
            "/projects/{project_id}/apply-config": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {
                    "tags": ["Análisis IA"],
                    "summary": "Aplicar config de IA",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["perfiles", "tendencias_escalas"], "properties": {"perfiles": {"type": "array"}, "tendencias_escalas": {"type": "array"}, "reglas_dependencia": {"type": "array"}, "nombre": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Config actualizada"}, "201": {"description": "Config creada"}, "400": {"description": "Validación fallida"}},
                },
            },
            "/projects/{project_id}/template-config": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {
                    "tags": ["Análisis IA"],
                    "summary": "Generar config plantilla (sin IA)",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"nombre": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Config plantilla creada"}, "400": {"description": "Sin estructura"}},
                },
            },
            # ── Configs ───────────────────────────────────────────────────────
            "/projects/{project_id}/configs": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "get": {"tags": ["Configs"], "summary": "Listar configs", "responses": {"200": {"description": "Lista de configs"}}},
                "post": {
                    "tags": ["Configs"],
                    "summary": "Crear / importar config",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["perfiles", "tendencias_escalas"], "properties": {"nombre": {"type": "string"}, "perfiles": {"type": "array"}, "tendencias_escalas": {"type": "array"}, "reglas_dependencia": {"type": "array"}, "replace_existing": {"type": "boolean"}}}}}},
                    "responses": {"200": {"description": "Config actualizada"}, "201": {"description": "Config creada"}, "400": {"description": "Validación fallida"}},
                },
            },
            "/projects/{project_id}/configs/{config_id}": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}, {"name": "config_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "put": {"tags": ["Configs"], "summary": "Actualizar config", "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}}, "responses": {"200": {"description": "Actualizada"}, "404": {"description": "No encontrada"}}},
                "delete": {"tags": ["Configs"], "summary": "Eliminar config", "responses": {"200": {"description": "Eliminada"}, "400": {"description": "Es la única config"}}},
            },
            "/projects/{project_id}/configs/{config_id}/activate": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}, {"name": "config_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "put": {"tags": ["Configs"], "summary": "Activar config", "responses": {"200": {"description": "Config activada"}, "404": {"description": "No encontrada"}}},
            },
            # ── Ejecución ─────────────────────────────────────────────────────
            "/projects/{project_id}/execute": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {
                    "tags": ["Ejecución"],
                    "summary": "Iniciar bot",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"cantidad": {"type": "integer", "default": 10, "minimum": 1, "maximum": 500}, "headless": {"type": "boolean", "default": True}, "speed_profile": {"type": "string", "default": "balanced", "enum": ["slow", "balanced", "fast", "turbo", "turbo_plus"]}}}}}},
                    "responses": {"200": {"description": "Bot iniciado"}, "400": {"description": "Sin estructura o config / URL no soportada"}},
                },
            },
            "/projects/{project_id}/estado": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}, {"name": "execution_id", "in": "query", "schema": {"type": "integer"}}],
                "get": {"tags": ["Ejecución"], "summary": "Estado de ejecución", "responses": {"200": {"description": "Estado actual"}}},
            },
            "/projects/{project_id}/stop": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "post": {"tags": ["Ejecución"], "summary": "Detener bot", "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"execution_id": {"type": "integer"}}}}}}, "responses": {"200": {"description": "Detenido"}}},
            },
            "/projects/{project_id}/executions": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "get": {"tags": ["Ejecución"], "summary": "Historial de ejecuciones", "responses": {"200": {"description": "Lista (últimas 50)"}}},
            },
            "/projects/{project_id}/logs": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}, {"name": "execution_id", "in": "query", "schema": {"type": "integer"}}],
                "get": {"tags": ["Ejecución"], "summary": "Logs en tiempo real", "responses": {"200": {"description": "Logs como texto"}}},
            },
            "/projects/{project_id}/download": {
                "parameters": [{"name": "project_id", "in": "path", "required": True, "schema": {"type": "integer"}}, {"name": "execution_id", "in": "query", "schema": {"type": "integer"}}],
                "get": {"tags": ["Ejecución"], "summary": "Descargar Excel", "responses": {"200": {"description": "Archivo .xlsx"}, "404": {"description": "Sin Excel disponible"}}},
            },
            # ── Dashboard ─────────────────────────────────────────────────────
            "/dashboard": {
                "get": {"tags": ["Dashboard"], "summary": "Estado global (proyectos activos)", "responses": {"200": {"description": "Lista de ejecuciones en curso"}}},
            },
            # ── Configuración ─────────────────────────────────────────────────
            "/config/ai-providers": {
                "get": {"tags": ["Configuración"], "summary": "Listar proveedores IA", "responses": {"200": {"description": "Proveedores disponibles"}}},
                "post": {
                    "tags": ["Configuración"],
                    "summary": "Agregar / actualizar proveedor IA",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["provider_name", "api_key"], "properties": {"provider_name": {"type": "string", "enum": ["openai", "anthropic"]}, "api_key": {"type": "string"}, "model": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Proveedor configurado"}, "400": {"description": "Proveedor no soportado"}},
                },
            },
            "/config/ai-providers/{name}/activate": {
                "parameters": [{"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}],
                "put": {"tags": ["Configuración"], "summary": "Activar proveedor IA", "responses": {"200": {"description": "Activado"}, "400": {"description": "No disponible"}}},
            },
            "/config/settings": {
                "get": {"tags": ["Configuración"], "summary": "Obtener settings globales", "responses": {"200": {"description": "Configuración del sistema"}}},
            },
            # ── Prompts ───────────────────────────────────────────────────────
            "/prompts": {
                "get": {"tags": ["Prompts"], "summary": "Listar prompts editables", "responses": {"200": {"description": "Lista de prompts"}}},
            },
            "/prompts/{slug}": {
                "parameters": [{"name": "slug", "in": "path", "required": True, "schema": {"type": "string", "enum": ["system_analysis", "user_analysis", "system_scraping", "user_scraping"]}}],
                "get": {"tags": ["Prompts"], "summary": "Obtener prompt", "responses": {"200": {"description": "Contenido del prompt"}, "404": {"description": "No encontrado"}}},
                "put": {
                    "tags": ["Prompts"],
                    "summary": "Editar prompt",
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"contenido": {"type": "string"}, "nombre": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Actualizado"}, "404": {"description": "No encontrado"}},
                },
            },
            "/prompts/{slug}/reset": {
                "parameters": [{"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}}],
                "post": {"tags": ["Prompts"], "summary": "Restaurar prompt a default", "responses": {"200": {"description": "Restaurado"}, "404": {"description": "Sin default"}}},
            },
        },
    }
    return jsonify(spec)
