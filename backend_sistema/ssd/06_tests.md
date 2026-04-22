# Mapa de Tests

Suite: `backend_sistema/tests/`  
Correr: `python -m pytest tests/ -q`  → **275 passed** (estado al 2026-04-22)

---

## Qué cubre cada archivo de test

| Test file | Módulo cubierto |
|---|---|
| `test_routes_blueprints.py` | Los 5 blueprints: projects, scraping, analysis, configs, execution |
| `test_project_config_import.py` | `routes_configs.py` — flujo importar/reemplazar config |
| `test_project_service.py` | `project_service.py` — validar_configuracion, normalizar_paginas_manual, tiene_balanced_exitoso |
| `test_analyzer_service.py` | `analyzer_service.py` — flujo IA + fallback |
| `test_survey_preparator.py` | `analysis/survey_preparator.py` |
| `test_response_normalizer.py` | `analysis/response_normalizer.py` |
| `test_tendency_manager.py` | `analysis/tendency_manager.py` |
| `test_generator_service.py` | `generator_service.py` — generación completa |
| `test_generation_profile_selector.py` | `generation/profile_selector.py` |
| `test_generation_rules_engine.py` | `generation/rules_engine.py` |
| `test_generation_text_inferrer.py` | `generation/text_inferrer.py` |
| `test_google_forms_filler.py` | `automation/google_forms_filler.py` |
| `test_google_forms_flow_guard.py` | Guard: no avanza si fill_page falla |
| `test_ms_forms_filler.py` | `automation/ms_forms_filler.py` + `microsoft_forms_filler.py` |
| `test_gforms_special_inputs.py` | `automation/gforms/special_inputs.py` |
| `test_strategies.py` | `automation/strategies/` |
| `test_collect_input_hints.py` | input hints / detección de campos |
| `test_navigation_waits.py` | `automation/navigation/waits.py` |
| `test_scraping_utils.py` | utilidades de scraping |
| `test_export_service.py` | `export_service.py` — generación Excel |
| `test_execution_submodules.py` | `execution/log_capture.py`, `browser_manager.py`, `persistence.py` |
| `test_timing.py` | `automation/timing.py` — perfiles de velocidad |
| `test_supported_platforms.py` | `navigation/selectors.py` — plataformas soportadas |
| `test_utils_fuzzy_matcher.py` | `utils/fuzzy_matcher.py` |
| `test_utils_text_normalizer.py` | `utils/text_normalizer.py` |
| `test_utils_browser_config.py` | `utils/browser_config.py` |

---

## Qué NO está cubierto por tests

- Flujo real con Playwright (requiere browser): `browser_manager.py` en ejecución real
- `scraping/google_forms.py` y `scraping/strategies/` — requieren Playwright
- `ai/openai_provider.py`, `ai/anthropic_provider.py` — requieren API keys reales
- `routes_config.py`, `routes_docs.py` — no testeados
- `execution_service.execute()` con hilo real

---

## Patrón de test para rutas (Flask)

```python
class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    # ... resto de keys vacías

self.app = create_app(TestConfig)
self.client = self.app.test_client()

with self.app.app_context():
    # crear datos de prueba en BD
    db.session.add(Project(...))
    db.session.commit()

def tearDown(self):
    with self.app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
```

---

## Patrón de test para servicio con mock de BD

```python
@patch("app.services.project_service.Execution")
def test_foo(self, MockExecution):
    MockExecution.query.filter_by.return_value \
        .order_by.return_value.limit.return_value.all.return_value = [...]
```
