import { useState } from 'react'
import { useApplyConfig } from '../../hooks/useAnalysis'
import type { Perfil, Regla, Tendencia } from '../../types'
import { Modal } from '../ui/Modal'

interface IAPreviewModalProps {
  projectId: number
  preview: { perfiles: Perfil[]; tendencias_escalas: Tendencia[]; reglas_dependencia: Regla[] }
  onClose: () => void
  onApplied: () => void
}

export function IAPreviewModal({ projectId, preview, onClose, onApplied }: IAPreviewModalProps) {
  const [nombre, setNombre] = useState(`IA - ${new Date().toLocaleDateString('es-PE')}`)
  const { mutate, isPending, error } = useApplyConfig(projectId)

  const { perfiles, tendencias_escalas: tendencias, reglas_dependencia: reglas } = preview

  const totalFreqP = perfiles.reduce((s, p) => s + (p.frecuencia || 0), 0)
  const totalFreqT = tendencias.reduce((s, t) => s + (t.frecuencia || 0), 0)
  const warnings: string[] = []
  if (perfiles.length < 3 || perfiles.length > 4) warnings.push('Se necesitan entre 3 y 4 perfiles')
  if (tendencias.length < 3 || tendencias.length > 4) warnings.push('Se necesitan entre 3 y 4 tendencias')
  if (totalFreqP !== 100) warnings.push(`Frecuencia perfiles suma ${totalFreqP}% (debe ser 100%)`)
  if (totalFreqT !== 100) warnings.push(`Frecuencia tendencias suma ${totalFreqT}% (debe ser 100%)`)

  const apply = () => {
    mutate({ nombre, perfiles, reglas_dependencia: reglas, tendencias_escalas: tendencias }, {
      onSuccess: onApplied,
    })
  }

  return (
    <Modal title="Preview — resultado de la IA" onClose={onClose} onConfirm={apply} confirmLabel="Aplicar configuración" confirmDisabled={isPending || warnings.length > 0} large>
      <div className="ia-preview-summary">
        <div className="ia-preview-stat"><strong>{perfiles.length}</strong> perfiles</div>
        <div className="ia-preview-stat"><strong>{tendencias.length}</strong> tendencias</div>
        <div className="ia-preview-stat"><strong>{reglas.length}</strong> reglas</div>
      </div>

      <h3 style={{ fontSize: 14, color: 'var(--accent)', margin: '16px 0 8px', paddingBottom: 4, borderBottom: '1px solid var(--border)' }}>Perfiles</h3>
      {perfiles.map((p, i) => (
        <div key={i} className="ia-preview-item">
          <strong>{p.nombre}</strong> ({p.frecuencia}%)
          <span className="hint"> — {p.descripcion || ''} | {Object.keys(p.respuestas || {}).length} respuestas</span>
        </div>
      ))}

      <h3 style={{ fontSize: 14, color: 'var(--accent)', margin: '16px 0 8px', paddingBottom: 4, borderBottom: '1px solid var(--border)' }}>Tendencias</h3>
      {tendencias.map((t, i) => (
        <div key={i} className="ia-preview-item">
          <strong>{t.nombre}</strong> ({t.frecuencia}%)
          <span className="hint"> — {t.descripcion || ''}</span>
        </div>
      ))}

      {reglas.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, color: 'var(--accent)', margin: '16px 0 8px', paddingBottom: 4, borderBottom: '1px solid var(--border)' }}>Reglas</h3>
          {reglas.map((r, i) => (
            <div key={i} className="ia-preview-item" style={{ fontSize: 12 }}>
              SI "{r.si_pregunta?.substring(0, 30)}" {r.operador} "{r.si_valor}" → {r.entonces_pregunta?.substring(0, 30)}
            </div>
          ))}
        </>
      )}

      {warnings.length > 0 && (
        <div className="alert alert-error mt-10">{warnings.join(' • ')}</div>
      )}
      {error && <div className="alert alert-error mt-10">{error.message}</div>}

      <div className="form-group mt-15">
        <label style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, display: 'block', marginBottom: 4 }}>Nombre de la configuración</label>
        <input type="text" value={nombre} onChange={e => setNombre(e.target.value)} />
      </div>
    </Modal>
  )
}
