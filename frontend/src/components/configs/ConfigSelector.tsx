import { useRef } from 'react'
import { useActivateConfig, useConfigs, useCreateConfig, useDeleteConfig } from '../../hooks/useConfigs'
import type { Perfil, ProjectConfig, Regla, Tendencia } from '../../types'

interface ConfigSelectorProps {
  projectId: number
  onDone: () => void
}

function timeAgo(dateStr: string) {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
  return `hace ${Math.floor(diff / 86400)}d`
}

export function ConfigSelector({ projectId, onDone }: ConfigSelectorProps) {
  const { data: configs, isLoading } = useConfigs(projectId)
  const { mutate: activate, error: activateError } = useActivateConfig(projectId)
  const { mutate: deleteConfig, error: deleteError } = useDeleteConfig(projectId)
  const { mutate: createConfig, error: importError } = useCreateConfig(projectId)
  const fileRef = useRef<HTMLInputElement>(null)

  const error = activateError || deleteError || importError

  const handleActivate = (c: ProjectConfig) => {
    if (c.is_active) return
    activate(c.id, { onSuccess: onDone })
  }

  const handleDelete = (c: ProjectConfig) => {
    if ((configs?.length ?? 0) <= 1) return
    deleteConfig(c.id)
  }

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target?.result as string)
        const activeConfig = configs?.find(c => c.is_active)
        createConfig({
          nombre: file.name.replace(/\.json$/i, ''),
          perfiles: data.perfiles as Perfil[],
          reglas_dependencia: data.reglas_dependencia as Regla[],
          tendencias_escalas: data.tendencias_escalas as Tendencia[],
          replace_existing: !!activeConfig,
          replace_config_id: activeConfig?.id ?? null,
        }, { onSuccess: onDone })
      } catch {
        /* invalid json handled via importError */
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const handleExport = (c: ProjectConfig) => {
    const data = { perfiles: c.perfiles, reglas_dependencia: c.reglas_dependencia, tendencias_escalas: c.tendencias_escalas }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `config_${c.nombre.replace(/\s+/g, '_')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) return <div className="hint">Cargando configs...</div>

  return (
    <div className="card">
      <div className="flex-between">
        <h2>3. Configuración</h2>
        <div className="flex-gap">
          <button className="btn btn-outline btn-sm" onClick={() => fileRef.current?.click()}>Importar</button>
          <input ref={fileRef} type="file" accept=".json" style={{ display: 'none' }} onChange={handleImport} />
        </div>
      </div>

      {error && <div className="alert alert-error mt-10">{error.message}</div>}

      {!configs?.length ? (
        <div className="empty-state-sm">Sin configuraciones. Usa "Analizar con IA" o importa un JSON.</div>
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {configs.map(c => (
            <div
              key={c.id}
              className="history-item"
              onClick={() => handleActivate(c)}
            >
              <div className="history-title">
                <span className={`config-badge ${c.is_active ? 'active' : 'inactive'}`}>
                  {c.is_active ? 'Activa' : 'Guardada'}
                </span>
                {c.nombre}
              </div>
              <div className="history-meta">
                <span>{c.total_perfiles} perfiles</span>
                <span>{c.total_tendencias} tendencias</span>
                <span>{c.total_reglas} reglas</span>
                <span>{c.ai_provider_used || 'manual'}</span>
                <span>{timeAgo(c.updated_at || c.created_at)}</span>
                <span onClick={e => { e.stopPropagation(); handleExport(c) }} style={{ color: 'var(--accent)', cursor: 'pointer' }}>
                  Exportar
                </span>
                {(configs.length > 1) && (
                  <span onClick={e => { e.stopPropagation(); handleDelete(c) }} style={{ color: 'var(--danger)', cursor: 'pointer' }}>
                    Eliminar
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
