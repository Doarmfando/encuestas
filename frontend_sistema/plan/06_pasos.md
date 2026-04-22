# Plan de acción — pasos de implementación

Orden diseñado para tener algo funcional lo antes posible e ir agregando features encima.

---

## Paso 1 — Setup del proyecto

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install zustand @tanstack/react-query
```

Configurar `vite.config.ts` con proxy a Flask:
```ts
proxy: { '/api': 'http://localhost:5000' }
```

Copiar CSS actuales a `src/styles/`.  
Crear `src/types.ts` con todos los tipos del dominio.  
Crear `src/api/client.ts`.

**Resultado:** app en blanco que puede hablar con el backend.

---

## Paso 2 — Store + layout base

- `src/store/useAppStore.ts` con `view`, `currentProjectId`, `currentExecutionId`
- `src/App.tsx` que renderiza vista según `view`
- `src/components/layout/Header.tsx`

**Resultado:** navegación entre vistas funciona, Header visible.

---

## Paso 3 — Vista Proyectos

- `hooks/useProjects.ts` — query lista + mutations crear/eliminar
- `views/ProjectsView.tsx`
- `components/projects/ProjectCard.tsx`
- `components/projects/CreateProjectForm.tsx`

**Resultado:** se pueden crear, listar y eliminar proyectos.

---

## Paso 4 — Vista Proyecto: Scraping (paso 1)

- `hooks/useProject.ts`
- `components/scraping/ScrapePanel.tsx` — botón scrape, opciones headless/plataforma
- `components/scraping/StructureViewer.tsx` — lista de páginas/preguntas
- `components/ui/Modal.tsx` — modal genérico para editar preguntas
- `components/ui/StepsIndicator.tsx`

**Resultado:** se puede scrapear y ver la estructura detectada.

---

## Paso 5 — Vista Proyecto: Editor manual

- `components/scraping/ManualEditor.tsx` con tabs Form / JSON / Detectada

**Resultado:** se puede cargar estructura manual completa.

---

## Paso 6 — Análisis IA (paso 2)

- `hooks/useAnalysis.ts` — mutations analyze, apply-config, template-config
- `components/analysis/AnalysisPanel.tsx`
- `components/analysis/IAPreviewModal.tsx`

**Resultado:** flujo completo IA: analizar → preview → aplicar.

---

## Paso 7 — Configs (paso 3)

- `hooks/useConfigs.ts`
- `components/configs/ConfigSelector.tsx`
- `components/configs/ConfigList.tsx`
- Import/export de configs (file input)

**Resultado:** gestión completa de configuraciones.

---

## Paso 8 — Ejecución (paso 4)

- `hooks/useExecution.ts` — execute, estado polling, logs polling, stop
- `components/execution/ExecutionPanel.tsx`
- `components/execution/LogStream.tsx`
- `components/execution/ExecutionHistory.tsx`

**Resultado:** flujo completo de ejecución con logs en tiempo real.

---

## Paso 9 — Dashboard

- `hooks/useDashboard.ts` — polling de `/dashboard`
- `views/DashboardView.tsx`
- `components/execution/DashboardCard.tsx`

---

## Paso 10 — Settings panel

- `components/layout/SettingsPanel.tsx` — providers IA + settings

---

## Paso 11 — Pulido final

- Remover todos los `alert()` → errores inline
- Revisar estados de loading (skeletons o spinners) en cada fetch
- Verificar que el proxy funcione en dev y el build en prod
- Eliminar `frontend_sistema/` (vanilla) una vez todo migrado

---

## Estimación de tamaño

| Categoría | Archivos aprox. |
|---|---|
| Tipos + API + Store | 3 archivos |
| Hooks | 5 archivos |
| Vistas | 3 archivos |
| Componentes | ~18 archivos |
| Estilos | 4-5 archivos (migrados) |
| **Total** | **~30 archivos** vs 18 actuales |

El código será más archivos pero cada uno hace una sola cosa — agregar una nueva feature
no requiere tocar nada existente.

---

## Señal de que está listo para producción

```
✓ npm run build  →  sin errores TypeScript
✓ Los 275 tests del backend siguen pasando (API no cambió)
✓ Flujo completo funciona: crear → scrape → IA → config → ejecutar → ver logs
```
