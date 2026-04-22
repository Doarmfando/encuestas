# API Routes — todos los endpoints

Prefijo global: `/api`  (registrado en `app/__init__.py`)

## Blueprint: project_bp  →  `app/api/routes_projects.py`

| Método | URL | Qué hace | Errores posibles |
|---|---|---|---|
| GET | /projects | Lista todos | — |
| POST | /projects | Crea proyecto | 400 sin nombre/URL, 400 URL no soportada |
| GET | /projects/`<id>` | Detalle + estructura | 404 |
| PUT | /projects/`<id>` | Renombra / cambia URL | 404, 400 URL inválida |
| DELETE | /projects/`<id>` | Elimina | 404, 400 si hay ejecución activa |
| GET | /dashboard | Ejecuciones activas ahora | — |

## Blueprint: scraping_bp  →  `app/api/routes_scraping.py`

| Método | URL | Qué hace | Errores posibles |
|---|---|---|---|
| POST | /projects/`<id>`/scrape | Scrapea con Playwright | 404, 400 plataforma, 400 requiere login, 500 crash |
| POST | /projects/`<id>`/manual-structure | Carga estructura JSON manual | 404, 400 validación de páginas |

Body de `/scrape`: `{ headless: bool, force_platform: "google_forms"|"microsoft_forms" }`  
Body de `/manual-structure`: `{ paginas: [...] }` — ver validación en `project_service.normalizar_paginas_manual()`

## Blueprint: analysis_bp  →  `app/api/routes_analysis.py`

| Método | URL | Qué hace | Errores posibles |
|---|---|---|---|
| POST | /projects/`<id>`/analyze | Llama IA, retorna preview | 404, 400 sin estructura, 500 IA crash (usa fallback) |
| POST | /projects/`<id>`/apply-config | Guarda config desde preview | 404, 400 perfiles inválidos |
| POST | /projects/`<id>`/template-config | Genera plantilla sin IA | 404, 400 sin estructura |

`/analyze` NUNCA guarda — solo retorna preview. Para guardar, usar `/apply-config`.

## Blueprint: configs_bp  →  `app/api/routes_configs.py`

| Método | URL | Qué hace | Errores posibles |
|---|---|---|---|
| GET | /projects/`<id>`/configs | Lista configs (activa primero) | — |
| POST | /projects/`<id>`/configs | Crea / reemplaza config | 404, 400 perfiles inválidos |
| PUT | /projects/`<id>`/configs/`<cid>` | Edita nombre/perfiles | 404, 400 fuera de rango |
| PUT | /projects/`<id>`/configs/`<cid>`/activate | Activa config | 404 |
| DELETE | /projects/`<id>`/configs/`<cid>` | Elimina config | 400 si es la última, 404 |

POST con `replace_existing: true, replace_config_id: <id>` actualiza en lugar de crear.

## Blueprint: execution_bp  →  `app/api/routes_execution.py`

| Método | URL | Qué hace | Errores posibles |
|---|---|---|---|
| POST | /projects/`<id>`/execute | Lanza ejecución en hilo | 404, 400 sin estructura/config/URL, 400 cantidad 1-500, 400 speed inválido, 400 turbo sin balanced |
| GET | /projects/`<id>`/estado | Estado actual + logs | idle si no hay ejecuciones |
| POST | /projects/`<id>`/stop | Detiene ejecución activa | 200 siempre |
| GET | /projects/`<id>`/executions | Historial (últimas 50) | — |
| GET | /projects/`<id>`/download | Descarga Excel | 404 si no existe |
| GET | /projects/`<id>`/logs | Logs de ejecución activa | `{"logs": ""}` si no hay servicio |

Speed profiles válidos: `balanced`, `turbo`, `turbo_plus` — definidos en `app/automation/timing.py`

## Otros blueprints

- `routes_config.py` — configuración global de la app (API keys, prompts)
- `routes_docs.py` — documentación interna / prompts templates
- `error_handlers.py` — handlers 404/500 globales
