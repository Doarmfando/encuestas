# Capa de API

## `src/api/client.ts`

Reemplaza `js/api.js` actual. Un wrapper delgado sobre `fetch`.

```ts
const BASE = "/api";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  get:    <T>(path: string)                    => request<T>("GET", path),
  post:   <T>(path: string, body: unknown)     => request<T>("POST", path, body),
  put:    <T>(path: string, body?: unknown)    => request<T>("PUT", path, body),
  delete: <T>(path: string)                   => request<T>("DELETE", path),
};
```

---

## `src/types.ts`

Un solo archivo con todos los tipos del dominio. Se deriva del backend (`models.py`).

```ts
export interface Project {
  id: number;
  nombre: string;
  descripcion: string;
  url: string;
  status: "nuevo" | "scrapeado" | "configurado" | "ejecutando";
  plataforma: "google_forms" | "microsoft_forms" | null;
  estructura: { paginas: Pagina[] } | null;
  total_preguntas: number;
  config_activa: ProjectConfig | null;
  total_configs: number;
  ultima_ejecucion: EjecucionSimple | null;
  created_at: string;
}

export interface Pregunta {
  texto: string;
  tipo: string;
  obligatoria: boolean;
  opciones?: string[];
  filas?: string[];
}

export interface Pagina {
  numero: number;
  preguntas: Pregunta[];
  botones: string[];
}

export interface ProjectConfig {
  id: number;
  project_id: number;
  nombre: string;
  perfiles: Perfil[];
  tendencias_escalas: Tendencia[];
  reglas_dependencia: Regla[];
  ai_provider_used: string;
  is_active: boolean;
  total_perfiles: number;
  total_tendencias: number;
  total_reglas: number;
  updated_at: string;
  created_at: string;
}

export interface Perfil {
  nombre: string;
  descripcion: string;
  frecuencia: number;
  respuestas: Record<string, unknown>;
  tendencia_sugerida?: string;
}

export interface Tendencia {
  nombre: string;
  descripcion: string;
  frecuencia: number;
  distribuciones: Record<string, number[]>;
}

export interface Regla {
  si_pregunta: string;
  si_valor: string;
  operador: string;
  entonces_pregunta: string;
  entonces_forzar?: string;
  entonces_excluir?: string[];
}

export interface Execution {
  id: number;
  project_id: number;
  status: "ejecutando" | "completado" | "detenido" | "error";
  mensaje: string;
  total: number;
  exitosas: number;
  fallidas: number;
  progreso: number;
  tiempo_transcurrido: string;
  excel: string | null;
  logs?: string;
  created_at: string;
}

export interface EjecucionSimple {
  status: string;
  exitosas: number;
  total: number;
}

export type SpeedProfile = "balanced" | "turbo" | "turbo_plus";
```

---

## Manejo de errores

Los errores del `client.ts` siempre son `Error` con el mensaje del backend.
TanStack Query los expone como `error.message` en cada hook.

En los componentes:
```tsx
const { mutate, isPending, error } = useCreateProject();

// Mostrar error inline — sin alert()
{error && <div className="alert alert-error">{error.message}</div>}
```

**No se usan `alert()` en el frontend nuevo.** Todo error se muestra en el UI como elemento inline.
