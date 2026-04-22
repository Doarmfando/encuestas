# Índice rápido — sistema-encuestas backend

Leer este archivo primero. Ir al MD específico según el área del error.

## Archivos de este directorio

| Archivo | Cuándo leerlo |
|---|---|
| `01_architecture.md` | Para entender el flujo completo de una operación |
| `02_api_routes.md` | Error en un endpoint HTTP / status incorrecto |
| `03_services.md` | Error en lógica de negocio (validación, guardar, ejecutar) |
| `04_automation.md` | Error llenando formularios / scraping |
| `05_models_db.md` | Error de BD, campo faltante, relación rota |
| `06_tests.md` | Qué test cubre qué módulo / qué NO está testeado |
| `07_log_streaming.md` | Logs no llegan al frontend durante ejecución |

## Mapa rápido error → archivo fuente

```
HTTP 404/400/500 en /api/projects/*  → app/api/routes_projects.py
HTTP en /scrape o /manual-structure  → app/api/routes_scraping.py
HTTP en /analyze /apply-config       → app/api/routes_analysis.py
HTTP en /configs/*                   → app/api/routes_configs.py
HTTP en /execute /estado /logs       → app/api/routes_execution.py

Validación perfiles/tendencias       → app/services/project_service.py
Guardar/activar config               → app/services/project_service.py

IA no responde / respuesta inválida  → app/services/analyzer_service.py
Fallback sin IA                      → app/services/analyzer_service.py:_generar_fallback

Generación de respuestas             → app/services/generator_service.py
Selección de perfil                  → app/services/generation/profile_selector.py
Reglas de dependencia                → app/services/generation/rules_engine.py

Google Forms: llenar pregunta        → app/automation/google_forms_filler.py
Google Forms: dropdown               → app/automation/gforms/dropdown_handler.py
Google Forms: opción múltiple        → app/automation/gforms/option_clicker.py
Google Forms: texto                  → app/automation/gforms/text_writer.py
Google Forms: especiales (fecha,etc) → app/automation/gforms/special_inputs.py
Google Forms: botón Siguiente/Enviar → app/automation/navigation/button_detector.py

Microsoft Forms: llenar              → app/automation/ms_forms_filler.py
Microsoft Forms: flujo completo      → app/automation/microsoft_forms_filler.py

Scraping Google Forms                → app/scraping/google_forms.py
Scraping genérico / detección auto   → app/scraping/generic_scraper.py
Scraping MS Forms                    → app/scraping/strategies/microsoft_forms.py

Excel no se genera                   → app/services/execution/persistence.py
Excel ruta / descarga                → app/services/export_service.py

Logs no llegan al frontend           → app/services/execution/log_capture.py
                                       app/__init__.py (ThreadLocalLogHandler setup)

Browser no abre / Playwright crash   → app/services/execution/browser_manager.py
                                       app/utils/browser_config.py

Límites perfiles/tendencias          → app/constants/limits.py  (MIN/MAX)
Tipos de pregunta soportados         → app/constants/question_types.py
Plataformas soportadas               → app/automation/navigation/selectors.py
```

## Tests: correr suite completa

```bash
cd backend_sistema
python -m pytest tests/ -q
# debe marcar 275 passed
```
