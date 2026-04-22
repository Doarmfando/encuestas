# Árbol de componentes

## Vista general

```
App
├── Header
│   └── SettingsPanel (slide-in)
│
├── ProjectsView          (cuando view === "proyectos")
│   ├── CreateProjectForm (inline, toggle)
│   └── ProjectCard[]
│
├── ProjectView           (cuando view === "proyecto")
│   ├── StepsIndicator    (pasos 1-4)
│   ├── ScrapePanel       (paso 1)
│   │   ├── StructureViewer
│   │   └── ManualEditor
│   │       ├── ManualFormTab
│   │       ├── ManualJsonTab
│   │       └── DetectedTab
│   ├── AnalysisPanel     (paso 2)
│   │   └── IAPreviewModal
│   ├── ConfigSelector    (paso 3)
│   │   └── ConfigList
│   ├── ExecutionPanel    (paso 4)
│   │   ├── LogStream
│   │   └── ExecutionHistory
│   └── Modal             (genérico, para editar pregunta, etc.)
│
└── DashboardView         (cuando view === "dashboard")
    └── DashboardCard[]
```

---

## Responsabilidad de cada componente clave

### `App.tsx`
Lee `view` del store Zustand y renderiza la vista correspondiente. No tiene lógica propia.

### `Header.tsx`
Muestra título, subtítulo (del store) y botones de navegación. Sin lógica de negocio.

### `ProjectCard.tsx`
Recibe un `Project` como prop. Muestra nombre, status, URL, última ejecución.
Llama `onOpen(id)` y `onDelete(id)` — no hace fetch directamente.

### `ScrapePanel.tsx`
- Botón Scrapear → mutation `POST /scrape`
- Checkbox headless, selector de plataforma
- Cuando termina, renderiza `StructureViewer`
- Toggle "modo manual" → renderiza `ManualEditor`

### `StructureViewer.tsx`
Recibe `paginas[]` como prop. Renderiza la lista de páginas/preguntas.
Botón Editar → abre `Modal` con form inline.
Botón Eliminar → llama callback del padre.
**No hace fetch** — toda la persistencia la delega al padre.

### `ManualEditor.tsx`
Editor visual de estructura. Tiene 3 tabs: Form / JSON / Detectada.
Estado local del editor (antes de guardar). Al guardar → mutation `POST /manual-structure`.

### `IAPreviewModal.tsx`
Recibe el preview de IA como prop. Muestra perfiles/tendencias/reglas.
Botón "Aplicar" → mutation `POST /apply-config`.
Botón "Descartar" → cierra sin guardar.

### `ConfigSelector.tsx`
Lista las configs guardadas. Click en una → mutation `PUT /activate`.
Muestra badge "Activa" en la config activa.

### `ExecutionPanel.tsx`
- Input cantidad, selector speed profile
- Botón Ejecutar → mutation `POST /execute`
- Mientras ejecuta: muestra `LogStream` + barra de progreso + botón Detener

### `LogStream.tsx`
Recibe `executionId`. Usa query con `refetchInterval` para polling de `/logs`.
Muestra el texto en un `<pre>` con auto-scroll al final.

### `Modal.tsx`
Componente genérico:
```tsx
<Modal title="..." onConfirm={() => ...} onClose={() => ...}>
  {children}
</Modal>
```
Reemplaza el sistema `abrirModal()` / `innerHTML` actual.

---

## Componentes UI reutilizables (`ui/`)

| Componente | Reemplaza |
|---|---|
| `Modal` | `abrirModal()` en modal.js |
| `StepsIndicator` | función `setStep()` en app.js |
| `StatusBadge` | función `statusColor()` + clases CSS manuales |
