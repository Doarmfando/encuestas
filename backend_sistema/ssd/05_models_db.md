# Modelos de Base de Datos

Archivo: `app/database/models.py`  
Conexión: `app/database/connection.py` → `db = SQLAlchemy()`

---

## Project

| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| nombre | String | |
| descripcion | String | |
| url | String | URL del formulario |
| status | String | `nuevo` → `scrapeado` → `configurado` → `ejecutando` |
| plataforma | String | `google_forms`, `microsoft_forms` |
| estructura | JSON | `{"paginas": [...]}` — resultado del scraping |
| total_preguntas | Integer | |
| requiere_login | Boolean | |
| created_at | DateTime | |

**Métodos útiles:**
```python
project.to_dict()          # completo
project.to_dict_simple()   # sin estructura (para listas)
project.to_estructura()    # alias de estructura para analyzer
project.get_active_config() # retorna ProjectConfig activa o None
```

---

## ProjectConfig

| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| project_id | FK → Project | cascade delete |
| nombre | String | |
| perfiles | JSON | lista de dicts |
| reglas_dependencia | JSON | lista de dicts |
| tendencias_escalas | JSON | lista de dicts |
| ai_provider_used | String | `openai`, `anthropic`, `importado`, `manual` |
| is_active | Boolean | solo una activa por proyecto |
| created_at / updated_at | DateTime | |

**Estructura de un perfil:**
```json
{
  "nombre": "Estudiante",
  "descripcion": "...",
  "frecuencia": 40,
  "respuestas": { "¿Nombre?": {"tipo": "texto", "valor": "..."} },
  "tendencia_sugerida": "Término Medio",
  "reglas_coherencia": ["..."]
}
```

**Estructura de una tendencia:**
```json
{
  "nombre": "Término Medio",
  "descripcion": "...",
  "frecuencia": 40,
  "distribuciones": { "5": [5, 15, 60, 15, 5] }
}
```

**Métodos útiles:**
```python
config.to_dict()           # para respuesta HTTP
config.to_configuracion()  # formato que usa execution_service
```

---

## Execution

| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| project_id | FK → Project | |
| config_id | FK → ProjectConfig | |
| status | String | `ejecutando`, `completado`, `detenido`, `error` |
| mensaje | String | mensaje de progreso/resultado |
| total | Integer | encuestas pedidas |
| exitosas | Integer | encuestas completadas |
| fallidas | Integer | |
| excel_path | String | ruta al archivo xlsx generado |
| headless | Boolean | |
| started_at / finished_at | DateTime | |
| logs | Text | logs guardados al terminar |

**Métodos útiles:**
```python
execution.to_dict()    # historial
execution.to_estado()  # estado en tiempo real (incluye progreso)
```

---

## Relaciones

```
Project  1──N  ProjectConfig
Project  1──N  Execution
ProjectConfig  1──N  Execution
```

Cascade: eliminar `Project` elimina sus `ProjectConfig` y `Execution`.

---

## Inicialización

```python
# app/__init__.py
with app.app_context():
    db.create_all()
    seed_prompts()   # inserta prompts default si no existen
```

Base de datos: SQLite en desarrollo (`instance/encuestas.db`)  
En tests: `sqlite:///:memory:` con `StaticPool`
