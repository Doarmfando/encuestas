import { useState } from 'react'
import { useManualStructure } from '../../hooks/useProject'
import type { Pagina, Pregunta } from '../../types'

const TIPOS = ['informativo','texto','parrafo','numero','opcion_multiple','seleccion_multiple','desplegable','escala_lineal','likert','nps','ranking','matriz','matriz_checkbox','fecha','hora','archivo','seccion','desconocido']
const BOTONES = ['Siguiente', 'Atrás', 'Enviar', 'Borrar formulario']
const CON_OPCIONES = new Set(['opcion_multiple','seleccion_multiple','desplegable','escala_lineal','likert','nps','ranking','matriz','matriz_checkbox'])

interface ManualEditorProps {
  projectId: number
  initialPaginas: Pagina[]
  onSaved: () => void
}

function emptyPagina(n: number): Pagina {
  return { numero: n, botones: ['Siguiente'], preguntas: [] }
}

function emptyPregunta(): Pregunta {
  return { texto: '', tipo: 'texto', obligatoria: false, opciones: [] }
}

export function ManualEditor({ projectId, initialPaginas, onSaved }: ManualEditorProps) {
  const [tab, setTab] = useState<'form' | 'json'>('form')
  const [paginas, setPaginas] = useState<Pagina[]>(
    initialPaginas.length ? initialPaginas : [emptyPagina(1)]
  )
  const [jsonText, setJsonText] = useState('')
  const [jsonError, setJsonError] = useState('')
  const { mutate, isPending, error } = useManualStructure(projectId)

  const save = (pags: Pagina[]) => mutate({ paginas: pags }, { onSuccess: () => onSaved() })

  const addPagina = () => setPaginas(p => [...p, emptyPagina(p.length + 1)])
  const delPagina = (i: number) => { if (paginas.length <= 1) return; setPaginas(p => p.filter((_, pi) => pi !== i)) }
  const addPregunta = (pi: number) => setPaginas(p => p.map((pg, i) => i !== pi ? pg : { ...pg, preguntas: [...pg.preguntas, emptyPregunta()] }))
  const delPregunta = (pi: number, qi: number) => setPaginas(p => p.map((pg, i) => i !== pi ? pg : { ...pg, preguntas: pg.preguntas.filter((_, j) => j !== qi) }))

  const updateQ = (pi: number, qi: number, field: keyof Pregunta, value: unknown) =>
    setPaginas(p => p.map((pg, i) => i !== pi ? pg : {
      ...pg,
      preguntas: pg.preguntas.map((q, j) => j !== qi ? q : { ...q, [field]: value }),
    }))

  const toggleBoton = (pi: number, btn: string, checked: boolean) =>
    setPaginas(p => p.map((pg, i) => {
      if (i !== pi) return pg
      const set = new Set(pg.botones)
      checked ? set.add(btn) : set.delete(btn)
      return { ...pg, botones: Array.from(set) }
    }))

  const saveJson = () => {
    setJsonError('')
    try {
      const parsed = JSON.parse(jsonText)
      if (!Array.isArray(parsed?.paginas)) { setJsonError("Debe incluir un array 'paginas'"); return }
      setPaginas(parsed.paginas)
      save(parsed.paginas)
    } catch (e: unknown) {
      setJsonError(`JSON inválido: ${(e as Error).message}`)
    }
  }

  let nGlobal = 0
  return (
    <div>
      <div className="config-tabs">
        <button className={`tab${tab === 'form' ? ' active' : ''}`} onClick={() => setTab('form')}>Editor visual</button>
        <button className={`tab${tab === 'json' ? ' active' : ''}`} onClick={() => {
          setJsonText(JSON.stringify({ paginas }, null, 2))
          setTab('json')
        }}>JSON</button>
      </div>

      {tab === 'form' && (
        <>
          {paginas.map((pag, pi) => (
            <div key={pi} className="manual-page">
              <div className="manual-page-head">
                <strong>Página {pi + 1}</strong>
                <div className="flex-gap">
                  <button className="btn btn-outline btn-sm" onClick={() => addPregunta(pi)}>+ Pregunta</button>
                  <button className="btn btn-danger btn-sm" onClick={() => delPagina(pi)}>Eliminar página</button>
                </div>
              </div>
              <div className="manual-badges">
                {BOTONES.map(btn => (
                  <label key={btn}>
                    <input type="checkbox" checked={pag.botones?.includes(btn)} onChange={e => toggleBoton(pi, btn, e.target.checked)} />
                    {btn}
                  </label>
                ))}
              </div>
              {pag.preguntas.length === 0 && <div className="empty-state-sm">Sin preguntas</div>}
              {pag.preguntas.map((preg, qi) => {
                nGlobal++
                const n = nGlobal
                return (
                  <div key={qi} className="manual-question">
                    <div className="row">
                      <span className="pregunta-num">{n}.</span>
                      <input type="text" placeholder="Texto de la pregunta" value={preg.texto}
                        onChange={e => updateQ(pi, qi, 'texto', e.target.value)} />
                      <select value={preg.tipo} onChange={e => updateQ(pi, qi, 'tipo', e.target.value)}>
                        {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                      <label className="checkbox-label">
                        <input type="checkbox" checked={preg.obligatoria} onChange={e => updateQ(pi, qi, 'obligatoria', e.target.checked)} />
                        Obligatoria
                      </label>
                    </div>
                    <div className="row" style={{ marginTop: 6 }}>
                      <textarea
                        placeholder="Opciones (una por línea)"
                        disabled={!CON_OPCIONES.has(preg.tipo)}
                        value={(preg.opciones ?? []).join('\n')}
                        onChange={e => updateQ(pi, qi, 'opciones', e.target.value.split('\n').map(s => s.trim()).filter(Boolean))}
                      />
                      <div />
                      <button className="btn btn-outline btn-sm" onClick={() => delPregunta(pi, qi)}>Eliminar</button>
                    </div>
                  </div>
                )
              })}
            </div>
          ))}
          {error && <div className="alert alert-error mt-10">{error.message}</div>}
          <div className="flex-gap mt-10">
            <button className="btn btn-outline btn-sm" onClick={addPagina}>+ Página</button>
            <button className="btn btn-success" onClick={() => save(paginas)} disabled={isPending}>
              {isPending ? 'Guardando...' : 'Guardar estructura'}
            </button>
          </div>
        </>
      )}

      {tab === 'json' && (
        <>
          <textarea className="code-input" value={jsonText} onChange={e => setJsonText(e.target.value)} />
          {jsonError && <div className="alert alert-error mt-10">{jsonError}</div>}
          {error && <div className="alert alert-error mt-10">{error.message}</div>}
          <button className="btn btn-success mt-10" onClick={saveJson} disabled={isPending}>
            {isPending ? 'Guardando...' : 'Guardar JSON'}
          </button>
        </>
      )}
    </div>
  )
}
