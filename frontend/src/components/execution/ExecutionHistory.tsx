import { useExecutions } from '../../hooks/useExecution'

interface ExecutionHistoryProps {
  projectId: number
}

const STATUS_COLOR: Record<string, string> = {
  ejecutando: 'var(--accent)', completado: 'var(--success)',
  error: 'var(--danger)', detenido: 'var(--warning)',
}

function timeAgo(dateStr: string) {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
  return `hace ${Math.floor(diff / 86400)}d`
}

export function ExecutionHistory({ projectId }: ExecutionHistoryProps) {
  const { data: execs } = useExecutions(projectId)

  if (!execs?.length) return <div className="empty-state-sm">Sin ejecuciones previas</div>

  return (
    <div style={{ display: 'grid', gap: 6, marginTop: 12 }}>
      {execs.map(e => (
        <div key={e.id} className="history-item" style={{ cursor: 'default' }}>
          <div className="history-title">
            <span className="status-dot" style={{ background: STATUS_COLOR[e.status] || 'var(--text-muted)' }} />
            {e.exitosas || 0}/{e.total || 0} exitosas
          </div>
          <div className="history-meta">
            <span>{e.tiempo_transcurrido || '?'}</span>
            <span>{e.status}</span>
            <span>{timeAgo(e.created_at)}</span>
            {e.excel && (
              <a
                className="download-link"
                href={`/api/projects/${projectId}/download?execution_id=${e.id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Excel
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
