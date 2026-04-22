import { useState } from 'react'
import { useManualStructure } from '../../hooks/useProject'
import type { Pagina, Pregunta } from '../../types'
import { Modal } from '../ui/Modal'

const TIPOS = ['informativo','texto','parrafo','numero','opcion_multiple','seleccion_multiple','desplegable','escala_lineal','likert','nps','ranking','matriz','matriz_checkbox','fecha','hora','archivo','seccion','desconocido']
const CON_OPCIONES = new Set(['opcion_multiple','seleccion_multiple','desplegable','escala_lineal','likert','nps','ranking','matriz','matriz_checkbox'])

const TIPO_CLASS: Record<string, string> = {
  escala_lineal: 'likert', likert: 'likert', nps: 'likert',
  opcion_multiple: 'radio', seleccion_multiple: 'check',
  texto: 'text', parrafo: 'text', numero: 'text',
  desplegable: 'drop',
}

interface StructureViewerProps {
  projectId: number
  paginas: Pagina[]
  onSaved: () => void
}

interface EditState {
  pageIdx: number
  qIdx: number
  pregunta: Pregunta
}

export function StructureViewer({ projectId, paginas, onSaved }: StructureViewerProps) {
  const [editing, setEditing] = useState<EditState | null>(null)
  const [editData, setEditData] = useState<Pregunta | null>(null)
  const [localPaginas, setLocalPaginas] = useState<Pagina[]>(paginas)
  const { mutate, isPending, error } = useManualStructure(projectId)

  const persist = (updated: Pagina[]) => {
    mutate({ paginas: updated }, { onSuccess: (r) => { setLocalPaginas(r.paginas); onSaved() } })
  }

  const openEdit = (pageIdx: number, qIdx: number) => {
    const p = localPaginas[pageIdx].preguntas[qIdx]
    setEditing({ pageIdx, qIdx, pregunta: p })
    setEditData({ ...p, opciones: [...(p.opciones ?? [])] })
  }

  const saveEdit = () => {
    if (!editing || !editData) return
    const updated = localPaginas.map((p, pi) =>
      pi !== editing.pageIdx ? p : {
        ...p,
        preguntas: p.preguntas.map((q, qi) => qi !== editing.qIdx ? q : editData),
      }
    )
    setLocalPaginas(updated)
    setEditing(null)
    persist(updated)
  }

  const deleteQ = (pageIdx: number, qIdx: number) => {
    const updated = localPaginas.map((p, pi) =>
      pi !== pageIdx ? p : { ...p, preguntas: p.preguntas.filter((_, qi) => qi !== qIdx) }
    )
    setLocalPaginas(updated)
    persist(updated)
  }

  let nGlobal = 0
  return (
    <div>
      {localPaginas.map((pag, pIdx) => (
        <div key={pIdx}>
          <div className="page-header">
            <span>Página {pag.numero}</span>
            <span className="page-buttons">{(pag.botones || []).join(', ') || 'sin botones'}</span>
          </div>
          {pag.preguntas.map((p, qIdx) => {
            nGlobal++
            const n = nGlobal
            return (
              <div key={qIdx} className="pregunta-item">
                <div className="pregunta-text">
                  <span className="pregunta-num">{n}.</span>
                  {p.texto}{p.obligatoria && <span className="obligatoria">*</span>}
                  {p.opciones?.length ? (
                    <div className="opciones-preview">
                      {p.opciones.slice(0, 6).join(' | ')}{p.opciones.length > 6 ? ` (+${p.opciones.length - 6})` : ''}
                    </div>
                  ) : null}
                </div>
                <span className={`tipo ${TIPO_CLASS[p.tipo] || ''}`}>{p.tipo}</span>
                <div className="pregunta-actions flex-gap">
                  <button className="btn btn-outline btn-sm" onClick={() => openEdit(pIdx, qIdx)}>Editar</button>
                  <button className="btn btn-danger btn-sm" onClick={() => deleteQ(pIdx, qIdx)} disabled={isPending}>Eliminar</button>
                </div>
              </div>
            )
          })}
        </div>
      ))}

      {error && <div className="alert alert-error mt-10">{error.message}</div>}

      {editing && editData && (
        <Modal title="Editar pregunta" onClose={() => setEditing(null)} onConfirm={saveEdit} confirmDisabled={!editData.texto.trim()}>
          <div className="form-group">
            <label>Texto</label>
            <input type="text" value={editData.texto} onChange={e => setEditData({ ...editData, texto: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Tipo</label>
            <select value={editData.tipo} onChange={e => setEditData({ ...editData, tipo: e.target.value })}>
              {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <label className="checkbox-label" style={{ marginBottom: 14 }}>
            <input type="checkbox" checked={editData.obligatoria} onChange={e => setEditData({ ...editData, obligatoria: e.target.checked })} />
            Obligatoria
          </label>
          {CON_OPCIONES.has(editData.tipo) && (
            <div className="form-group">
              <label>Opciones (una por línea)</label>
              <textarea
                rows={6}
                value={(editData.opciones ?? []).join('\n')}
                onChange={e => setEditData({ ...editData, opciones: e.target.value.split('\n').map(s => s.trim()).filter(Boolean) })}
              />
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
