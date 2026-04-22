# Capa de Automatización (Playwright)

## Punto de entrada por plataforma

```
google_forms_filler.py   → GoogleFormsFiller.fill_form(page, respuesta, url, numero)
microsoft_forms_filler.py → MicrosoftFormsFiller.fill_form(page, respuesta, url, numero)
```

`fill_form` retorna `(exito: bool, mensaje: str)`

---

## Google Forms — árbol de clases

```
GoogleFormsFiller                     (google_forms_filler.py)
  usa → GFormBase                     (gforms/_base.py)
           usa → QuestionFinder       (gforms/question_finder.py)   ← encontrar el div
                 OptionClicker        (gforms/option_clicker.py)    ← radio/checkbox
                 DropdownHandler      (gforms/dropdown_handler.py)  ← select nativo
                 TextWriter           (gforms/text_writer.py)       ← input/textarea
                 SpecialInputs        (gforms/special_inputs.py)    ← fecha, hora, lineal
  usa → ButtonDetector                (navigation/button_detector.py) ← Siguiente/Enviar
  usa → wait_for_form_ready           (navigation/waits.py)
```

### Tipos de pregunta → handler

| tipo | handler |
|---|---|
| `texto`, `parrafo` | `TextWriter.write()` |
| `opcion_multiple` | `OptionClicker.click_option()` |
| `casillas` | `OptionClicker.click_checkboxes()` |
| `desplegable` | `DropdownHandler.select()` |
| `escala_lineal` | `SpecialInputs.fill_lineal()` |
| `fecha` | `SpecialInputs.fill_date()` |
| `hora` | `SpecialInputs.fill_time()` |
| `grilla_multiple`, `grilla_casillas` | `SpecialInputs.fill_grid()` |

---

## Microsoft Forms — árbol de clases

```
MicrosoftFormsFiller                  (microsoft_forms_filler.py)
  contiene → MSFormsFiller            (ms_forms_filler.py)
               .fill_page(page, preguntas, runtime_config)  → {"ok", "filled", "failed"}
               .click_next(page)
               ._find_question(page, pregunta)
               ._fill_element(element, tipo, valor)
```

---

## Estrategias comunes (ambas plataformas)

```
app/automation/strategies/
  text_filler.py      → llenar texto con typing humano (pausa entre chars)
  option_clicker.py   → click en opciones con retry
  special_fields.py   → campos de fecha/select nativos
  form_utils.py       → utilidades DOM compartidas
```

---

## Navegación y esperas

```
navigation/selectors.py
  validar_plataforma_soportada(url) → dict | lanza ValueError
  SUPPORTED_PLATFORM_NAMES          → set de nombres válidos

navigation/waits.py
  wait_for_form_ready(page, timeout)  → bool

navigation/button_detector.py
  click_boton(page, texto)  → bool
  Estrategias en orden:
    1. aria-label exact match
    2. texto visible exact
    3. texto visible contains
    4. data-automation-id (MS Forms)
```

---

## Timing / velocidad

`app/automation/timing.py`

```python
DEFAULT_EXECUTION_PROFILE = "balanced"
resolve_execution_profile(name)  → {"id", "timing": {...}}
```

| Perfil | Descripción |
|---|---|
| `balanced` | Pausas humanas normales |
| `turbo` | Pausas mínimas — requiere balanced 100% previo |
| `turbo_plus` | Sin pausas — requiere balanced 100% previo |

`turbo`/`turbo_plus` bloqueados hasta tener `tiene_balanced_exitoso() == True`

---

## Scraping

```
scraping/__init__.py
  get_scraper(url, ai_service, force_platform) → BaseScraper

scraping/generic_scraper.py    ← detecta plataforma, delega
scraping/google_forms.py       ← scraping específico Google Forms
scraping/strategies/
  microsoft_forms.py           ← MS Forms via Playwright
  ms_forms_dom.py              ← MS Forms via DOM directo
  requests_html.py             ← fallback sin browser
  ai_analysis.py               ← analiza HTML con IA si falla scraping normal
  playwright_nav.py            ← navegación Playwright compartida
  fb_data.py                   ← extrae __FB_DATA__ de Google Forms
```

`scrape()` retorna:
```json
{
  "paginas": [...],
  "total_preguntas": N,
  "plataforma": "google_forms",
  "titulo": "...",
  "requiere_login": false
}
```
