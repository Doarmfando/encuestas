"""
Perfiles de velocidad y helpers de pausas para automatizacion.
"""
import random
import time


DEFAULT_EXECUTION_PROFILE = "balanced"

EXECUTION_PROFILES = {
    "fast": {
        "label": "Maxima velocidad",
        "description": "Minimiza pausas artificiales y prioriza throughput.",
        "survey_pause_min": 0.10,
        "survey_pause_max": 0.35,
        "action_pause_min": 0.02,
        "action_pause_max": 0.08,
        "settle_pause_min": 0.08,
        "settle_pause_max": 0.18,
        "ready_wait_timeout_s": 5.0,
        "nav_wait_timeout_s": 1.8,
        "submit_confirm_timeout_s": 2.5,
        "poll_interval_s": 0.10,
    },
    "balanced": {
        "label": "Rapido balanceado",
        "description": "Reduce esperas sin volver el bot fragil.",
        "survey_pause_min": 0.40,
        "survey_pause_max": 1.00,
        "action_pause_min": 0.05,
        "action_pause_max": 0.15,
        "settle_pause_min": 0.20,
        "settle_pause_max": 0.35,
        "ready_wait_timeout_s": 6.0,
        "nav_wait_timeout_s": 2.5,
        "submit_confirm_timeout_s": 4.0,
        "poll_interval_s": 0.15,
    },
    "safe": {
        "label": "Disimulado",
        "description": "Mantiene pausas mas humanas y conservadoras.",
        "survey_pause_min": 1.50,
        "survey_pause_max": 3.00,
        "action_pause_min": 0.15,
        "action_pause_max": 0.35,
        "settle_pause_min": 0.40,
        "settle_pause_max": 0.80,
        "ready_wait_timeout_s": 10.0,
        "nav_wait_timeout_s": 5.0,
        "submit_confirm_timeout_s": 8.0,
        "poll_interval_s": 0.25,
    },
}


def get_execution_profile_options() -> list[dict]:
    """Metadatos ligeros para poblar la UI."""
    return [
        {
            "id": profile_id,
            "label": profile["label"],
            "description": profile["description"],
        }
        for profile_id, profile in EXECUTION_PROFILES.items()
    ]


def resolve_execution_profile(profile: str | None = None) -> dict:
    """Resuelve un speed_profile a su configuracion concreta."""
    normalized = (profile or DEFAULT_EXECUTION_PROFILE).strip().lower()
    if normalized not in EXECUTION_PROFILES:
        valid = ", ".join(sorted(EXECUTION_PROFILES))
        raise ValueError(f"speed_profile invalido: '{profile}'. Valores permitidos: {valid}")

    resolved = dict(EXECUTION_PROFILES[normalized])
    resolved["id"] = normalized
    return resolved


def build_runtime_config(speed_profile: str | None = None, headless: bool | None = None) -> dict:
    """Empaqueta configuracion runtime compartida entre servicio y fillers."""
    timing = resolve_execution_profile(speed_profile)
    return {
        "speed_profile": timing["id"],
        "headless": bool(headless),
        "timing": timing,
    }


def get_timing_config(runtime_config: dict | None = None) -> dict:
    """Extrae la configuracion de timing desde el runtime_config."""
    if runtime_config and isinstance(runtime_config, dict):
        timing = runtime_config.get("timing")
        if isinstance(timing, dict):
            return timing
        if "survey_pause_min" in runtime_config:
            return runtime_config
    return resolve_execution_profile(DEFAULT_EXECUTION_PROFILE)


def get_timeout_ms(runtime_config: dict | None, key: str) -> int:
    """Convierte timeout en segundos del perfil a milisegundos."""
    timing = get_timing_config(runtime_config)
    return int(float(timing.get(key, 0.0)) * 1000)


def get_poll_interval(runtime_config: dict | None) -> float:
    timing = get_timing_config(runtime_config)
    return max(float(timing.get("poll_interval_s", 0.15)), 0.01)


def _sleep_duration(min_value: float, max_value: float) -> float:
    low = max(float(min_value), 0.0)
    high = max(float(max_value), low)
    if high == 0:
        return 0.0
    return random.uniform(low, high)


def _pause_with_duration(duration: float, stop_event=None) -> float:
    if duration <= 0:
        return 0.0
    start = time.perf_counter()
    if stop_event is not None:
        stop_event.wait(timeout=duration)
    else:
        time.sleep(duration)
    return time.perf_counter() - start


def pause_action(runtime_config: dict | None = None, multiplier: float = 1.0) -> float:
    timing = get_timing_config(runtime_config)
    duration = _sleep_duration(
        timing["action_pause_min"] * multiplier,
        timing["action_pause_max"] * multiplier,
    )
    return _pause_with_duration(duration)


def pause_settle(runtime_config: dict | None = None, multiplier: float = 1.0) -> float:
    timing = get_timing_config(runtime_config)
    duration = _sleep_duration(
        timing["settle_pause_min"] * multiplier,
        timing["settle_pause_max"] * multiplier,
    )
    return _pause_with_duration(duration)


def pause_between_surveys(runtime_config: dict | None = None, stop_event=None, multiplier: float = 1.0) -> float:
    timing = get_timing_config(runtime_config)
    duration = _sleep_duration(
        timing["survey_pause_min"] * multiplier,
        timing["survey_pause_max"] * multiplier,
    )
    return _pause_with_duration(duration, stop_event=stop_event)
