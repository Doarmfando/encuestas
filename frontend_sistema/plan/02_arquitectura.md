# Arquitectura y estructura de carpetas

## Estructura propuesta

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
│
└── src/
    ├── main.tsx              ← entrada, QueryClientProvider + render
    ├── App.tsx               ← enrutador de vistas (proyectos / proyecto / dashboard)
    ├── types.ts              ← TODOS los tipos del dominio en un solo lugar
    │
    ├── api/
    │   └── client.ts         ← fetch wrapper (reemplaza api.js)
    │
    ├── store/
    │   └── useAppStore.ts    ← Zustand: currentProject, view, currentExecutionId
    │
    ├── hooks/
    │   ├── useProjects.ts    ← queries de proyectos
    │   ├── useProject.ts     ← query de un proyecto
    │   ├── useConfigs.ts     ← queries de configs
    │   ├── useExecution.ts   ← mutation ejecutar + query polling estado
    │   └── useDashboard.ts   ← query polling dashboard
    │
    ├── views/
    │   ├── ProjectsView.tsx  ← lista de proyectos
    │   ├── ProjectView.tsx   ← detalle de proyecto (steps 1-4)
    │   └── DashboardView.tsx ← ejecuciones activas
    │
    ├── components/
    │   ├── layout/
    │   │   ├── Header.tsx
    │   │   └── SettingsPanel.tsx
    │   ├── projects/
    │   │   ├── ProjectCard.tsx
    │   │   └── CreateProjectForm.tsx
    │   ├── scraping/
    │   │   ├── ScrapePanel.tsx
    │   │   ├── StructureViewer.tsx    ← lista de páginas/preguntas
    │   │   └── ManualEditor.tsx       ← editor manual de estructura
    │   ├── analysis/
    │   │   ├── AnalysisPanel.tsx
    │   │   └── IAPreviewModal.tsx
    │   ├── configs/
    │   │   ├── ConfigSelector.tsx
    │   │   └── ConfigList.tsx
    │   ├── execution/
    │   │   ├── ExecutionPanel.tsx
    │   │   ├── LogStream.tsx
    │   │   └── ExecutionHistory.tsx
    │   └── ui/
    │       ├── Modal.tsx             ← modal genérico reutilizable
    │       ├── StepsIndicator.tsx
    │       └── StatusBadge.tsx
    │
    └── styles/
        ├── variables.css             ← copiado del frontend actual
        ├── components.css
        └── layout.css
```

## Convenciones

**Naming:**
- Componentes: PascalCase (`ProjectCard.tsx`)
- Hooks: camelCase con prefijo `use` (`useProjects.ts`)
- Tipos: PascalCase (`Project`, `ProjectConfig`, `Execution`)
- Archivos CSS: `NombreComponente.module.css`

**Un componente = un archivo.** No hay componentes definidos en el mismo archivo que otro componente, salvo subcomponentes pequeños (<20 líneas) que solo usa el padre.

**Props tipadas siempre:**
```tsx
interface ProjectCardProps {
  project: Project;
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
}
```

**Sin prop drilling profundo.** Si un dato necesita bajar más de 2 niveles, va al store de Zustand.

## Integración con el backend

El frontend corre en `localhost:5173` (dev) y consume la API en `localhost:5000`.

`vite.config.ts` configura el proxy:
```ts
server: {
  proxy: {
    '/api': 'http://localhost:5000'
  }
}
```

En producción, el build de `dist/` puede ser servido por Flask o por cualquier servidor estático.
