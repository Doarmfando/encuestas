"""
Rutas API para configuración global y proveedores de IA.
"""
from flask import Blueprint, jsonify, request, current_app
from app.automation.timing import DEFAULT_EXECUTION_PROFILE, get_execution_profile_options
from app.database.connection import db
from app.database.models import AIProviderConfig, PromptTemplate

config_bp = Blueprint("config", __name__)


@config_bp.route("/config/ai-providers", methods=["GET"])
def listar_providers():
    """Lista los proveedores de IA disponibles."""
    ai_service = current_app.config.get("AI_SERVICE")
    if ai_service:
        return jsonify(ai_service.list_providers())
    return jsonify([])


@config_bp.route("/config/ai-providers", methods=["POST"])
def configurar_provider():
    """Agrega o actualiza un proveedor de IA."""
    data = request.json or {}
    name = data.get("provider_name", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "")

    if not name or not api_key:
        return jsonify({"error": "provider_name y api_key son requeridos"}), 400

    ai_service = current_app.config.get("AI_SERVICE")
    if not ai_service:
        return jsonify({"error": "Servicio de IA no disponible"}), 500

    try:
        ai_service.add_provider(name, api_key, model)

        # Guardar en BD
        existing = AIProviderConfig.query.filter_by(provider_name=name).first()
        if existing:
            existing.api_key = api_key
            existing.model = model or existing.model
        else:
            provider_config = AIProviderConfig(
                provider_name=name,
                api_key=api_key,
                model=model,
                is_active=False,
            )
            db.session.add(provider_config)

        db.session.commit()
        return jsonify({"mensaje": f"Proveedor '{name}' configurado"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@config_bp.route("/config/ai-providers/<name>/activate", methods=["PUT"])
def activar_provider(name):
    """Activa un proveedor de IA como el predeterminado."""
    ai_service = current_app.config.get("AI_SERVICE")
    if not ai_service:
        return jsonify({"error": "Servicio de IA no disponible"}), 500

    try:
        ai_service.set_active_provider(name)

        # Actualizar BD
        AIProviderConfig.query.update({"is_active": False})
        provider = AIProviderConfig.query.filter_by(provider_name=name).first()
        if provider:
            provider.is_active = True
        db.session.commit()

        return jsonify({"mensaje": f"Proveedor '{name}' activado"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@config_bp.route("/config/settings", methods=["GET"])
def obtener_settings():
    """Devuelve la configuración global."""
    return jsonify({
        "browser_locale": current_app.config.get("BROWSER_LOCALE"),
        "browser_timezone": current_app.config.get("BROWSER_TIMEZONE"),
        "browser_viewport": {
            "width": current_app.config.get("BROWSER_VIEWPORT_WIDTH"),
            "height": current_app.config.get("BROWSER_VIEWPORT_HEIGHT"),
        },
        "max_encuestas": current_app.config.get("MAX_ENCUESTAS"),
        "pausa_min": current_app.config.get("PAUSA_MIN"),
        "pausa_max": current_app.config.get("PAUSA_MAX"),
        "ai_temperature": current_app.config.get("AI_TEMPERATURE"),
        "ai_max_tokens": current_app.config.get("AI_MAX_TOKENS"),
        "default_ai_provider": current_app.config.get("DEFAULT_AI_PROVIDER"),
        "default_headless": True,
        "default_execution_profile": DEFAULT_EXECUTION_PROFILE,
        "execution_profiles": get_execution_profile_options(),
    })


# ============ PROMPTS ============

@config_bp.route("/prompts", methods=["GET"])
def listar_prompts():
    """Lista todos los prompts editables."""
    prompts = PromptTemplate.query.order_by(PromptTemplate.slug).all()
    return jsonify([p.to_dict() for p in prompts])


@config_bp.route("/prompts/<slug>", methods=["GET"])
def obtener_prompt(slug):
    """Obtiene un prompt por su slug."""
    prompt = PromptTemplate.query.filter_by(slug=slug).first()
    if not prompt:
        return jsonify({"error": "Prompt no encontrado"}), 404
    return jsonify(prompt.to_dict())


@config_bp.route("/prompts/<slug>", methods=["PUT"])
def actualizar_prompt(slug):
    """Actualiza el contenido de un prompt."""
    data = request.json or {}
    prompt = PromptTemplate.query.filter_by(slug=slug).first()
    if not prompt:
        return jsonify({"error": "Prompt no encontrado"}), 404

    if "contenido" in data:
        prompt.contenido = data["contenido"]
        prompt.is_default = False
    if "nombre" in data:
        prompt.nombre = data["nombre"]

    db.session.commit()
    return jsonify({"mensaje": "Prompt actualizado", "prompt": prompt.to_dict()})


@config_bp.route("/prompts/<slug>/reset", methods=["POST"])
def resetear_prompt(slug):
    """Restaura un prompt a su valor por defecto."""
    from app.database.seed_prompts import DEFAULT_PROMPTS

    prompt = PromptTemplate.query.filter_by(slug=slug).first()
    if not prompt:
        return jsonify({"error": "Prompt no encontrado"}), 404

    default = DEFAULT_PROMPTS.get(slug)
    if default:
        prompt.contenido = default["contenido"]
        prompt.is_default = True
        db.session.commit()
        return jsonify({"mensaje": "Prompt restaurado", "prompt": prompt.to_dict()})

    return jsonify({"error": "No hay default para este prompt"}), 404
