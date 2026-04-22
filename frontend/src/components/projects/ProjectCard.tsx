import type { Project } from '../../types'

interface ProjectCardProps {
  project: Project
  onOpen: (id: number) => void
  onDelete: (id: number) => void
}

const PLATFORM_ICON: Record<string, string> = { google_forms: 'G', microsoft_forms: 'M', typeform: 'T', generic: '?' }

function timeAgo(dateStr: string) {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diff < 60) return 'hace un momento'
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
  return `hace ${Math.floor(diff / 86400)}d`
}

const STATUS_COLOR: Record<string, string> = {
  ejecutando: 'var(--accent)', completado: 'var(--success)',
  error: 'var(--danger)', detenido: 'var(--warning)',
}

export function ProjectCard({ project: p, onOpen, onDelete }: ProjectCardProps) {
  return (
    <div className="project-card" onClick={() => onOpen(p.id)}>
      <div className="project-card-header">
        <span className={`platform-dot ${p.plataforma || 'generic'}`}>
          {PLATFORM_ICON[p.plataforma || 'generic'] || '?'}
        </span>
        <h3>{p.nombre}</h3>
        <span className={`project-status status-${p.status}`}>{p.status}</span>
      </div>
      <div className="project-card-meta">
        {p.total_preguntas ? `${p.total_preguntas} preguntas` : 'Sin scrapear'} |{' '}
        {p.total_configs || 0} configs | {timeAgo(p.created_at)}
      </div>
      {p.ultima_ejecucion && (
        <div className="project-card-exec">
          <span className="status-dot" style={{ background: STATUS_COLOR[p.ultima_ejecucion.status] || 'var(--text-muted)' }} />
          {p.ultima_ejecucion.exitosas}/{p.ultima_ejecucion.total} — {p.ultima_ejecucion.status}
        </div>
      )}
      <div className="project-card-url">{p.url}</div>
      <div className="project-card-actions" onClick={e => e.stopPropagation()}>
        <button className="btn btn-danger btn-sm" onClick={() => onDelete(p.id)}>Eliminar</button>
      </div>
    </div>
  )
}
