# Capa de Servicios

## project_service.py  —  `app/services/project_service.py`

Punto de entrada para todas las operaciones sobre proyectos y configs.

```python
ProjectService()
  .validar_configuracion(perfiles, tendencias)   # lanza ProjectValidationError
  .normalizar_paginas_manual(paginas)            # lanza ProjectValidationError
  .guardar_configuracion(project, nombre, ...)   # retorna (config, created: bool)
  .tiene_balanced_exitoso(project_id)            # bool — requerido para turbo
```

**Límites** (en `app/constants/limits.py`):
- `MIN_PERFILES = 3`, `MAX_PERFILES = 4`
- `MIN_TENDENCIAS = 3`, `MAX_TENDENCIAS = 4`

**`normalizar_paginas_manual` valida:**
- Lista no vacía, cada elemento es dict
- Cada pregunta tiene `texto` no vacío
- `tipo` debe estar en `QUESTION_TYPES` (`app/constants/question_types.py`)
- `opcion_multiple` requiere al menos 1 opción
- Asigna `obligatoria=False` por defecto, strip al texto
- Asigna botones `Siguiente`/`Enviar` automáticamente

---

## analyzer_service.py  —  `app/services/analyzer_service.py`

Orquesta el análisis con IA. **Nunca lanza excepción** — siempre usa fallback.

```
analyze(estructura)
  → preparator.preparar_resumen()
  → ai_service.chat_completion()   ← puede fallar → _generar_fallback()
  → _validar_y_corregir()
      normalizer.corregir_nombres_preguntas()
      normalizer.corregir_respuesta()
      profile_manager.asegurar_cantidad()   ← asegura MIN 3 perfiles
      tendency_manager.corregir()
      enricher.enriquecer()                 ← agrega tendencia_sugerida
      rules_manager.corregir_reglas()
```

**Sub-servicios** en `app/services/analysis/`:

| Clase | Archivo | Responsabilidad |
|---|---|---|
| `SurveyPreparator` | `survey_preparator.py` | Resumen compacto para IA |
| `ResponseNormalizer` | `response_normalizer.py` | Corregir/completar respuestas |
| `ProfileManager` | `profile_manager.py` | Cantidad, defaults, sanitizar |
| `ProfileEnricher` | `profile_enricher.py` | Agregar tendencia_sugerida y reglas_coherencia |
| `TendencyManager` | `tendency_manager.py` | Crear/corregir tendencias de escala |
| `RulesManager` | `rules_manager.py` | Validar reglas de dependencia |

---

## generator_service.py  —  `app/services/generator_service.py`

Genera respuestas sintéticas para cada encuesta.

```
GeneratorService(config, estructura, reglas)
  .generar(cantidad)   → lista de dicts con respuestas por página
```

**Sub-servicios** en `app/services/generation/`:

| Clase | Archivo | Responsabilidad |
|---|---|---|
| `ProfileSelector` | `profile_selector.py` | Elige perfil según frecuencias |
| `ResponseGenerator` | `response_generator.py` | Genera respuesta por tipo de pregunta |
| `RulesEngine` | `rules_engine.py` | Aplica reglas de dependencia |
| `TextInferrer` | `text_inferrer.py` | Infiere texto libre coherente |

---

## execution_service.py  —  `app/services/execution_service.py`

Corre en hilo separado. No tiene estado entre llamadas.

```python
ExecutionService()
  .execute(app, execution_id, url, config, estructura, cantidad, headless, speed_profile)
  .stop(execution_id)     # señal de parada al hilo
  .get_logs(execution_id) # retorna logs capturados del hilo
```

**Sub-módulos** en `app/services/execution/`:
- `log_capture.py` — `LogCapture`, `ThreadLocalLogHandler`, `ThreadLocalStdout`
- `browser_manager.py` — abre/cierra Playwright browser por hilo
- `persistence.py` — guarda resultados en BD y genera Excel

---

## ai_service.py  —  `app/services/ai_service.py`

Fachada sobre OpenAI / Anthropic.

```python
AIService(config)
  .get_provider()               # retorna el provider activo
  .active_provider_name         # "openai" | "anthropic"
  provider.chat_completion(system_prompt, user_prompt, temperature, max_tokens, json_mode)
```

Providers en `app/ai/`: `openai_provider.py`, `anthropic_provider.py`  
Interface base: `app/ai/provider.py`
