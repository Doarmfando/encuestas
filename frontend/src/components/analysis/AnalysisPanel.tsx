import { useState } from 'react'
import { useAnalyze, useTemplateConfig } from '../../hooks/useAnalysis'
import type { Perfil, Regla, Tendencia } from '../../types'
import { IAPreviewModal } from './IAPreviewModal'

interface AnalysisPanelProps {
  projectId: number
  onDone: () => void
}

interface Preview {
  perfiles: Perfil[]
  tendencias_escalas: Tendencia[]
  reglas_dependencia: Regla[]
}

export function AnalysisPanel({ projectId, onDone }: AnalysisPanelProps) {
  const [instrucciones, setInstrucciones] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const { mutate: analyze, isPending: analyzing, error: analyzeError } = useAnalyze(projectId)
  const { mutate: genTemplate, isPending: genPending, error: templateError } = useTemplateConfig(projectId)

  const error = analyzeError || templateError

  return (
    <div className="card">
      <h2>2. Analizar con IA</h2>
      <div className="section-help">
        La IA analiza el formulario y genera perfiles de respuesta, tendencias y reglas de dependencia.
        El resultado es un <strong>preview</strong> — puedes revisar antes de guardar.
      </div>
      <div className="form-group">
        <label style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, display: 'block', marginBottom: 4 }}>
          Instrucciones adicionales (opcional)
        </label>
        <textarea
          rows={2}
          value={instrucciones}
          onChange={e => setInstrucciones(e.target.value)}
          placeholder="Ej: enfocarse en perfil joven, generar respuestas en español..."
          style={{ minHeight: 60 }}
        />
      </div>
      {error && <div className="alert alert-error mt-10">{error.message}</div>}
      <div className="flex-gap mt-10">
        <button
          className="btn btn-primary"
          onClick={() => analyze(instrucciones, { onSuccess: (d) => setPreview(d) })}
          disabled={analyzing}
        >
          {analyzing ? 'Analizando...' : 'Analizar con IA'}
        </button>
        <button
          className="btn btn-outline"
          onClick={() => genTemplate(`Plantilla - ${new Date().toLocaleDateString('es-PE')}`, { onSuccess: onDone })}
          disabled={genPending}
        >
          {genPending ? 'Generando...' : 'Generar plantilla sin IA'}
        </button>
      </div>

      {preview && (
        <IAPreviewModal
          projectId={projectId}
          preview={preview}
          onClose={() => setPreview(null)}
          onApplied={() => { setPreview(null); onDone() }}
        />
      )}
    </div>
  )
}
