export interface Project {
  id: number
  nombre: string
  descripcion: string
  url: string
  status: 'nuevo' | 'scrapeado' | 'configurado' | 'ejecutando'
  plataforma: 'google_forms' | 'microsoft_forms' | 'typeform' | 'generic' | null
  estructura: { paginas: Pagina[] } | null
  total_preguntas: number
  config_activa: ProjectConfig | null
  total_configs: number
  ultima_ejecucion: EjecucionSimple | null
  created_at: string
}

export interface Pregunta {
  texto: string
  tipo: string
  obligatoria: boolean
  opciones?: string[]
  filas?: string[]
}

export interface Pagina {
  numero: number
  preguntas: Pregunta[]
  botones: string[]
}

export interface ProjectConfig {
  id: number
  project_id: number
  nombre: string
  perfiles: Perfil[]
  tendencias_escalas: Tendencia[]
  reglas_dependencia: Regla[]
  ai_provider_used: string
  is_active: boolean
  total_perfiles: number
  total_tendencias: number
  total_reglas: number
  updated_at: string
  created_at: string
}

export interface Perfil {
  nombre: string
  descripcion: string
  frecuencia: number
  respuestas: Record<string, unknown>
  tendencia_sugerida?: string
  reglas_coherencia?: string[]
}

export interface Tendencia {
  nombre: string
  descripcion: string
  frecuencia: number
  distribuciones: Record<string, number[]>
}

export interface Regla {
  si_pregunta: string
  si_valor: string
  operador: string
  entonces_pregunta: string
  entonces_forzar?: string
  entonces_excluir?: string[]
}

export interface Execution {
  id: number
  project_id: number
  config_id: number
  status: 'ejecutando' | 'completado' | 'detenido' | 'error'
  mensaje: string
  total: number
  exitosas: number
  fallidas: number
  progreso: number
  tiempo_transcurrido: string
  tiempo_por_encuesta: string
  excel: string | null
  logs?: string
  created_at: string
}

export interface EjecucionSimple {
  status: string
  exitosas: number
  total: number
}

export interface EstadoResponse extends Execution {
  fase: string
  execution_id: number | null
}

export interface DashboardItem {
  project: Pick<Project, 'id' | 'nombre' | 'plataforma' | 'url'>
  execution: EstadoResponse
}

export interface DashboardResponse {
  activos: number
  proyectos: DashboardItem[]
}

export interface AIProvider {
  name: string
  model: string
  is_active: boolean
}

export interface AppSettings {
  browser_locale: string
  browser_timezone: string
  browser_viewport: { width: number; height: number }
  max_encuestas: number
  pausa_min: number
  pausa_max: number
  default_headless: boolean
  default_execution_profile: string
  execution_profiles: { id: string; label: string; description: string }[]
  ai_temperature: number
  ai_max_tokens: number
  default_ai_provider: string
}

export type SpeedProfile = 'balanced' | 'turbo' | 'turbo_plus'
export type View = 'proyectos' | 'proyecto' | 'dashboard'
