import { useState } from 'react'
import { useEstado, useExecute, useStop } from '../../hooks/useExecution'
import { useAppStore } from '../../store/useAppStore'
import type { SpeedProfile } from '../../types'
import { ExecutionHistory } from './ExecutionHistory'
import { LogStream } from './LogStream'

interface ExecutionPanelProps {
  projectId: number
}

const PROFILES: { id: SpeedProfile; label: string }[] = [
  { id: 'balanced', label: 'Balanced — pausas humanas' },
  { id: 'turbo', label: 'Turbo — pausas mínimas' },
  { id: 'turbo_plus', label: 'Turbo+ — sin pausas' },
]

export function ExecutionPanel({ projectId }: ExecutionPanelProps) {
  const [cantidad, setCantidad] = useState(10)
  const [headless, setHeadless] = useState(true)
  const [speedProfile, setSpeedProfile] = useState<SpeedProfile>('balanced')
  const [error, setError] = useState('')

  const { currentExecutionId, setExecutionId } = useAppStore()
  const { mutate: execute, isPending: launching } = useExecute(projectId)
  const { mutate: stop } = useStop(projectId)
  const { data: estado } = useEstado(projectId, true)

  const isRunning = estado?.fase === 'ejecutando'
  const pct = estado && estado.total > 0 ? Math.round(((estado.progreso ?? 0) / estado.total) * 100) : 0

  const barColor = () => {
    if (!estado || !estado.progreso) return ''
    const tasa = (estado.exitosas || 0) / estado.progreso
    if (tasa >= 0.8) return 'var(--gradient-success)'
    if (tasa >= 0.5) return 'var(--gradient-primary)'
    return 'var(--gradient-danger)'
  }

  const launch = () => {
    setError('')
    execute({ cantidad, headless, speed_profile: speedProfile }, {
      onSuccess: (r) => setExecutionId(r.execution_id),
      onError: (e: Error) => setError(e.message),
    })
  }

  const handleStop = () => stop(currentExecutionId ?? undefined)

  return (
    <div className="card">
      <h2>4. Ejecutar</h2>

      <div className="exec-controls">
        <div className="exec-field">
          <label>Cantidad (1-500)</label>
          <input type="number" min={1} max={500} value={cantidad} onChange={e => setCantidad(Number(e.target.value))} />
        </div>
        <div className="exec-field">
          <label>Velocidad</label>
          <select value={speedProfile} onChange={e => setSpeedProfile(e.target.value as SpeedProfile)}>
            {PROFILES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>
        <label className="checkbox-label">
          <input type="checkbox" checked={headless} onChange={e => setHeadless(e.target.checked)} />
          Headless
        </label>
      </div>

      {error && <div className="alert alert-error mt-10">{error}</div>}

      <div className="flex-gap mt-10">
        {!isRunning && (
          <button className="btn btn-primary" onClick={launch} disabled={launching}>
            {launching ? 'Iniciando...' : 'Ejecutar'}
          </button>
        )}
        {isRunning && (
          <button className="btn btn-danger" onClick={handleStop}>Detener</button>
        )}
      </div>

      {estado && (estado.total > 0 || isRunning) && (
        <div className="mt-15">
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${pct}%`, background: barColor() || undefined }}>
              {pct}%
            </div>
          </div>
          <div className="stats">
            <div className="stat ok"><div className="num">{estado.exitosas || 0}</div><div className="lbl">OK</div></div>
            <div className="stat fail"><div className="num">{estado.fallidas || 0}</div><div className="lbl">Fail</div></div>
            <div className="stat prog"><div className="num">{estado.progreso || 0}/{estado.total || 0}</div><div className="lbl">Progreso</div></div>
            <div className="stat time"><div className="num">{estado.tiempo_transcurrido || '0s'}</div><div className="lbl">Tiempo</div></div>
            <div className="stat avg"><div className="num">{estado.tiempo_por_encuesta || '0s'}</div><div className="lbl">Promedio</div></div>
          </div>
          <div className={`mensaje${isRunning ? ' pulse' : ''}`}>{estado.mensaje}</div>

          {estado.excel && (
            <a
              className="btn btn-success btn-sm mt-10"
              href={`/api/projects/${projectId}/download${currentExecutionId ? `?execution_id=${currentExecutionId}` : ''}`}
              target="_blank" rel="noopener noreferrer"
              style={{ display: 'inline-block', textDecoration: 'none' }}
            >
              Descargar Excel
            </a>
          )}

          <div className="mt-10">
            <p className="hint" style={{ marginBottom: 6 }}>Logs</p>
            <LogStream projectId={projectId} executionId={currentExecutionId} active={isRunning} />
          </div>
        </div>
      )}

      <hr className="divider" />
      <p className="hint" style={{ marginBottom: 8 }}>Historial</p>
      <ExecutionHistory projectId={projectId} />
    </div>
  )
}
