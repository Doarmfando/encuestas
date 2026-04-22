# Gestión de estado

## Regla principal

> Si el estado lo necesita un solo componente → `useState` local.  
> Si lo necesitan dos componentes hermanos o más → Zustand store.  
> Si es datos del servidor → TanStack Query (no guardarlo en Zustand).

---

## Store global — Zustand (`store/useAppStore.ts`)

Reemplaza las variables globales actuales del frontend vanilla.

```ts
interface AppState {
  // navegación
  view: "proyectos" | "proyecto" | "dashboard";
  
  // proyecto activo
  currentProjectId: number | null;
  
  // ejecución activa
  currentExecutionId: number | null;
  
  // acciones
  openProject: (id: number) => void;
  goBack: () => void;
  showDashboard: () => void;
  setExecutionId: (id: number | null) => void;
}
```

**Qué NO va en el store:**
- Los datos del proyecto (nombre, estructura, configs) → TanStack Query los maneja
- El estado del editor manual → `useState` local en `ManualEditor`
- El preview de IA → `useState` local en `AnalysisPanel`

---

## Server state — TanStack Query (`hooks/`)

### `useProjects.ts`
```ts
// Lista de proyectos
export const useProjects = () =>
  useQuery({ queryKey: ["projects"], queryFn: () => api.get("projects") });

// Crear proyecto
export const useCreateProject = () =>
  useMutation({ mutationFn: api.post("projects"), onSuccess: () => invalidate(["projects"]) });

// Eliminar proyecto  
export const useDeleteProject = () =>
  useMutation({ mutationFn: (id) => api.delete(`projects/${id}`), onSuccess: () => invalidate(["projects"]) });
```

### `useProject.ts`
```ts
// Detalle de un proyecto
export const useProject = (id: number) =>
  useQuery({ queryKey: ["project", id], queryFn: () => api.get(`projects/${id}`) });
```

### `useConfigs.ts`
```ts
export const useConfigs = (projectId: number) =>
  useQuery({ queryKey: ["configs", projectId], queryFn: () => api.get(`projects/${projectId}/configs`) });

export const useActivateConfig = (projectId: number) =>
  useMutation({ mutationFn: (configId) => api.put(`projects/${projectId}/configs/${configId}/activate`) });
```

### `useExecution.ts`
```ts
// Lanzar ejecución
export const useExecute = (projectId: number) =>
  useMutation({ mutationFn: (params) => api.post(`projects/${projectId}/execute`, params) });

// Polling de estado (mientras ejecuta)
export const useEstado = (projectId: number, enabled: boolean) =>
  useQuery({
    queryKey: ["estado", projectId],
    queryFn: () => api.get(`projects/${projectId}/estado`),
    refetchInterval: enabled ? 2000 : false,   // polling cada 2s solo si ejecutando
  });

// Polling de logs
export const useLogs = (projectId: number, executionId: number | null) =>
  useQuery({
    queryKey: ["logs", executionId],
    queryFn: () => api.get(`projects/${projectId}/logs?execution_id=${executionId}`),
    refetchInterval: executionId ? 1500 : false,
    select: (data) => data.logs,
  });
```

---

## Estado local (`useState`) — por componente

| Componente | Estado local |
|---|---|
| `ManualEditor` | `paginas[]` en edición (antes de guardar) |
| `CreateProjectForm` | `nombre`, `url`, `descripcion` del formulario |
| `AnalysisPanel` | `iaPreviewData` (preview temporal antes de aplicar) |
| `ExecutionPanel` | `cantidad`, `speedProfile`, `headless` |
| `IAPreviewModal` | `configNombre` (nombre para la config a guardar) |

---

## Comparación: antes vs después

| Antes (vanilla) | Después (React) |
|---|---|
| `let currentProject = null` (global) | `useProject(currentProjectId)` de TanStack Query |
| `let config = null` (global) | `useConfigs(projectId)` de TanStack Query |
| `let iaPreviewData = null` (global) | `useState` local en `AnalysisPanel` |
| `setInterval(update, 2000)` manual | `refetchInterval: 2000` en TanStack Query |
| `clearInterval` al salir de vista | TanStack Query para automáticamente cuando el componente se desmonta |
