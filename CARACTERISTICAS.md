# Sistema de Encuestas — Características y Funcionalidades

## ¿Qué es?

Sistema web para automatizar el llenado de formularios de Google Forms mediante un bot inteligente. Permite crear proyectos, scrapeар la estructura de cualquier formulario, generar perfiles de respuesta con IA y ejecutar el bot controlando cantidad, velocidad y comportamiento.

---

## Módulos principales

### 1. Gestión de Proyectos

Cada proyecto representa un formulario específico.

- Crear proyectos con nombre, URL y descripción
- Editar nombre, descripción o URL en cualquier momento
- Eliminar proyectos (con todas sus ejecuciones y configs asociadas)
- Vista de tarjetas con estado actual, cantidad de preguntas, configs y última ejecución
- Indicador visual del estado: `nuevo` → `scrapeado` → `configurado`

---

### 2. Scraping del Formulario

El sistema detecta automáticamente la estructura completa del formulario.

**Qué extrae:**
- Todas las páginas y sus botones de navegación (Siguiente, Atrás, Enviar)
- Cada pregunta con su texto, tipo, si es obligatoria y todas sus opciones
- La plataforma detectada automáticamente (Google Forms, Microsoft Forms)

**Tipos de pregunta soportados:**
`texto`, `párrafo`, `número`, `opción múltiple`, `selección múltiple`, `desplegable`, `escala lineal`, `likert`, `NPS`, `ranking`, `matriz`, `matriz checkbox`, `fecha`, `hora`, `archivo`, `sección`, `informativo`

**Modos de scraping:**
- **Automático** — el bot navega el formulario y extrae todo solo
- **Headless** — funciona en segundo plano sin abrir ventana de navegador
- **Forzar plataforma** — útil si la detección automática falla

**Editor de estructura:**
Después del scraping se puede corregir cualquier pregunta manualmente:
- Editor visual: agregar/eliminar páginas y preguntas, editar texto, tipo, opciones y obligatoriedad
- Editor JSON: pegar o editar la estructura completa en formato JSON directamente

---

### 3. Análisis con IA

La IA analiza el formulario y genera automáticamente una configuración de respuestas coherente.

**Qué genera:**
- **Perfiles** — grupos de respondentes con características distintas (ej: entusiasta, neutral, crítico). Cada perfil tiene frecuencia de aparición y respuestas propias
- **Tendencias de escala** — distribuciones de probabilidad para preguntas de tipo escala (Siempre/A veces/Nunca, etc.)
- **Reglas de dependencia** — lógica condicional: si la pregunta X tiene valor Y, entonces la pregunta Z fuerza o excluye ciertas opciones

**Flujo:**
1. Optionally escribir instrucciones adicionales (ej: "enfocarse en perfil joven", "respuestas en español")
2. La IA genera un **preview** completo antes de guardar
3. El preview muestra perfiles, tendencias y reglas para revisión
4. Si los datos son correctos, se aplica como nueva configuración

**Alternativa sin IA:**
- Botón "Generar plantilla sin IA" crea una config base estructurada para editar manualmente

**Proveedores de IA disponibles:**
- OpenAI (GPT-4o por defecto)
- Anthropic (Claude)
- Configurable desde el panel de ajustes

---

### 4. Gestión de Configuraciones

Cada proyecto puede tener múltiples configuraciones guardadas, pero solo una activa a la vez.

**Operaciones disponibles:**
- Crear nueva config (desde IA, plantilla o importación)
- Activar cualquier config guardada con un clic
- Exportar config a archivo JSON (para reutilizar en otros proyectos)
- Importar config desde un archivo JSON externo
- Eliminar configs (excepto si es la única que existe)

**Estructura de una configuración:**
```
Config
├── Perfiles (1–4)
│   ├── nombre, descripción, frecuencia (%)
│   ├── respuestas: fijas o aleatorias por pregunta
│   └── tendencia sugerida
├── Tendencias de escala (1–4)
│   ├── nombre, frecuencia (%)
│   └── distribuciones por número de opciones
└── Reglas de dependencia
    └── si [pregunta A] = [valor] → forzar/excluir en [pregunta B]
```

**Tipos de respuesta en perfiles:**
- `fijo` — responde siempre el mismo valor
- `aleatorio` — distribuye entre opciones según pesos definidos (ej: `{"Siempre": 65, "Casi siempre": 25, "A veces": 10}`)

---

### 5. Ejecución del Bot

El bot llena el formulario automáticamente simulando comportamiento humano.

**Configuración de ejecución:**
- **Cantidad** — de 1 a 500 respuestas por ejecución
- **Velocidad:**
  - `Balanced` — pausas naturales entre acciones, máxima credibilidad
  - `Turbo` — pausas mínimas, más rápido *(requiere una ejecución Balanced 100% exitosa previa)*
  - `Turbo+` — sin pausas, velocidad máxima *(requiere una ejecución Balanced 100% exitosa previa)*
- **Headless** — ejecutar con o sin ventana visible del navegador

**Durante la ejecución:**
- Barra de progreso en tiempo real
- Contadores de respuestas exitosas y fallidas
- Tiempo transcurrido y tiempo promedio por encuesta
- Stream de logs en vivo con detalle de cada acción del bot
- Botón de detener en cualquier momento

**Al finalizar:**
- Descarga de resultados en archivo Excel (`.xlsx`) con todas las respuestas registradas

---

### 6. Dashboard Global

Vista centralizada de todas las ejecuciones activas en tiempo real.

- Muestra todos los proyectos ejecutándose simultáneamente
- Barra de progreso, contadores OK/Fail y mensaje de estado por cada uno
- Botón de detener individual para cada ejecución activa
- Se actualiza automáticamente cada 2 segundos

---

### 7. Historial de Ejecuciones

Por cada proyecto se guarda un historial completo de las últimas 50 ejecuciones.

- Estado final: completado, detenido o error
- Cantidad de respuestas exitosas y totales
- Tiempo total de la ejecución
- Enlace directo para descargar el Excel de esa ejecución específica

---

### 8. Configuración Global del Sistema

Panel accesible desde el encabezado en todo momento.

**Proveedores de IA:**
- Agregar API keys de OpenAI o Anthropic
- Seleccionar modelo (ej: `gpt-4o`, `claude-sonnet-4-20250514`)
- Cambiar el proveedor activo con un clic

**Configuración del servidor (solo lectura):**
- Idioma y zona horaria del navegador usado por el bot
- Resolución de pantalla (viewport)
- Límite máximo de encuestas
- Pausas mínima y máxima entre acciones
- Perfil de ejecución por defecto
- Parámetros de IA (temperatura, tokens máximos)

---

### 9. Documentación de la API

El backend expone documentación interactiva integrada.

- **Swagger UI**: `http://localhost:5105/docs` — prueba endpoints directamente desde el navegador
- **OpenAPI JSON**: `http://localhost:5105/openapi.json` — especificación completa de la API
- **Health check**: `http://localhost:5105/health` — estado de la base de datos y el servidor

---

## Cómo funciona internamente

```
Usuario
  │
  ├─ Crea proyecto con URL del formulario
  │
  ├─ Scraping
  │    └─ Playwright abre el formulario en un navegador (visible o headless)
  │         └─ Extrae estructura: páginas, preguntas, tipos, opciones
  │
  ├─ Análisis IA
  │    └─ GPT / Claude recibe la estructura del formulario + instrucciones
  │         └─ Genera perfiles, tendencias y reglas de dependencia
  │
  ├─ Configuración
  │    └─ Se guarda en PostgreSQL, múltiples versiones por proyecto
  │
  └─ Ejecución
       └─ Por cada respuesta:
            ├─ Selecciona un perfil según su frecuencia
            ├─ Selecciona una tendencia según su frecuencia
            ├─ Para cada pregunta: determina la respuesta (fija, aleatoria o por distribución)
            ├─ Aplica reglas de dependencia si corresponde
            ├─ Playwright navega y llena el formulario
            └─ Registra resultado (exitoso/fallido) y avanza
```

---

## Plataformas soportadas

| Plataforma | Soporte |
|---|---|
| Google Forms | Completo |
| Microsoft Forms | Completo |
| Typeform | Parcial |

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | React 19, TypeScript, Vite, TanStack Query, Zustand |
| Backend | Python, Flask, SQLAlchemy |
| Base de datos | PostgreSQL |
| Automatización | Playwright (Chromium) |
| IA | OpenAI API / Anthropic API |
| Exportación | OpenPyXL (Excel) |
