# Arquitectura general

## Flujo: usuario pide ejecutar encuestas

```
Frontend
  → POST /api/projects/<id>/execute
  → routes_execution.py : ejecutar_proyecto()
      valida: proyecto existe, tiene estructura, tiene config activa, URL soportada
      crea Execution en BD (status="ejecutando")
      lanza hilo → execution_service.execute()
          genera respuestas (generator_service)
          abre browser (browser_manager)
          por cada respuesta generada:
              google_forms_filler.fill_form() o microsoft_forms_filler.fill_form()
          guarda resultados (persistence.py)
          cierra browser
  ← retorna { execution_id }

Frontend polling → GET /api/projects/<id>/estado
  → routes_execution.py : estado_proyecto()
      lee Execution de BD
      si ejecutando: también llama execution_service.get_logs()
  ← retorna estado + logs en tiempo real
```

## Flujo: analizar formulario con IA

```
POST /api/projects/<id>/scrape
  → scraping/generic_scraper.py  (detecta plataforma)
      google_forms.py  o  strategies/microsoft_forms.py
  guarda estructura en Project.estructura (JSON)

POST /api/projects/<id>/analyze
  → analyzer_service.analyze(estructura)
      preparator → resumen compacto para la IA
      ai_service.chat_completion() → JSON con perfiles/tendencias/reglas
      _validar_y_corregir() → normaliza, completa campos faltantes
  ← retorna preview (NO guarda aún)

POST /api/projects/<id>/apply-config
  → valida perfiles/tendencias (project_service)
  → project_service.guardar_configuracion()  guarda ProjectConfig
```

## Capas y sus responsabilidades

```
app/api/          HTTP: parsear request, llamar servicio, formatear response
app/services/     Lógica de negocio: validar, orquestar, guardar
app/automation/   Playwright: abrir browser, llenar campos, navegar
app/scraping/     Playwright/requests: leer estructura del formulario
app/services/generation/  Generar respuestas sintéticas según perfiles
app/services/analysis/    Procesar respuesta de IA: corregir, normalizar
app/database/     SQLAlchemy models + conexión
app/ai/           Wrappers OpenAI / Anthropic
app/constants/    Valores fijos (límites, tipos) — fuente única de verdad
app/utils/        Utilidades sin estado (fuzzy match, normalizar texto, etc.)
```

## Principios SOLID aplicados (refactor 2025)

- **SRP**: cada blueprint maneja un dominio; cada service/ subclase hace una cosa
- **OCP**: estrategias de scraping en `strategies/` se agregan sin tocar la clase base
- **DIP**: `AnalyzerService` recibe `AIService` por constructor (no lo instancia)
- Loggers `logging.getLogger(__name__)` en todos los módulos `app.*`
- `print()` eliminado — todo pasa por logger → `ThreadLocalLogHandler` → frontend
