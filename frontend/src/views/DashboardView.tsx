import { useMutation } from '@tanstack/react-query'
import { useDashboard } from '../hooks/useDashboard'
import { api } from '../api/client'

export function DashboardView() {
  const { data, isLoading } = useDashboard(true)
  const stop = useMutation({ mutationFn: (id: number) => api.post(`projects/${id}/stop`, {}) })

  if (isLoading) return <div className="empty-state">Cargando...</div>

  if (!data?.activos) {
    return <div className="empty-state">No hay ejecuciones activas en este momento.</div>
  }

  return (
    <div>
      {data.proyectos.map(({ project: p, execution: e }) => {
        const pct = e.total > 0 ? Math.round(((e.progreso ?? 0) / e.total) * 100) : 0
        return (
          <div key={p.id} className="dashboard-card">
            <div className="dashboard-card-header">
              <h3>{p.nombre}</h3>
              <span className="project-status status-ejecutando">Ejecutando</span>
            </div>
            <div className="progress-bar-bg">
              <div className="progress-bar-fill" style={{ width: `${pct}%` }}>{pct}%</div>
            </div>
            <div className="stats mini">
              <div className="stat ok"><div className="num">{e.exitosas}</div><div className="lbl">OK</div></div>
              <div className="stat fail"><div className="num">{e.fallidas}</div><div className="lbl">Fail</div></div>
              <div className="stat prog"><div className="num">{e.progreso}/{e.total}</div><div className="lbl">Progreso</div></div>
            </div>
            <div className="mensaje">{e.mensaje}</div>
            <button className="btn btn-danger btn-sm mt-10" onClick={() => stop.mutate(p.id)}>Detener</button>
          </div>
        )
      })}
    </div>
  )
}
