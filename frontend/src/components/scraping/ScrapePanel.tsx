import { useState } from 'react'
import { useScrape } from '../../hooks/useProject'
import type { Pagina } from '../../types'
import { StructureViewer } from './StructureViewer'
import { ManualEditor } from './ManualEditor'

const PLATFORMS = ['auto', 'google_forms', 'microsoft_forms']

interface ScrapePanelProps {
  projectId: number
  projectUrl: string
  initialPaginas?: Pagina[]
  plataforma?: string | null
  onDone: () => void
}

export function ScrapePanel({ projectId, projectUrl, initialPaginas, plataforma, onDone }: ScrapePanelProps) {
  const [headless, setHeadless] = useState(true)
  const [manual, setManual] = useState(false)
  const [platform, setPlatform] = useState('auto')
  const [tab, setTab] = useState<'detected' | 'manual'>('detected')

  const { mutate, isPending, error, data } = useScrape(projectId)
  const paginas = data?.paginas ?? initialPaginas ?? []
  const currentPlat = data?.plataforma ?? plataforma

  const scrape = () => {
    if (manual) { setTab('manual'); return }
    mutate(
      { headless, force_platform: platform !== 'auto' ? platform : undefined },
      { onSuccess: () => { setTab('detected'); onDone() } }
    )
  }

  return (
    <div className="card">
      <div className="flex-between">
        <h2>1. Scrapear formulario</h2>
        {currentPlat && (
          <span className={`platform-badge ${currentPlat}`}>
            {currentPlat === 'google_forms' ? 'G' : 'M'} {currentPlat.replace('_', ' ')}
          </span>
        )}
      </div>
      <p className="hint">URL: <strong>{projectUrl}</strong></p>

      <div className="input-options mt-10">
        <label className="checkbox-label">
          <input type="checkbox" checked={headless} onChange={e => setHeadless(e.target.checked)} />
          Modo invisible
        </label>
        <label className="checkbox-label">
          <input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} />
          Modo manual
        </label>
        <label style={{ fontSize: 13, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
          Plataforma:
          <select style={{ width: 'auto', padding: '6px 8px', fontSize: 13 }} value={platform} onChange={e => setPlatform(e.target.value)}>
            {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
      </div>

      <div className="flex-gap mt-10">
        <button className="btn btn-primary" onClick={scrape} disabled={isPending}>
          {isPending ? 'Scrapeando...' : 'Scrapear'}
        </button>
      </div>

      {error && <div className="alert alert-error mt-10">{error.message}</div>}

      {(paginas.length > 0 || manual) && (
        <>
          <div className="config-tabs mt-15">
            <button className={`tab${tab === 'detected' ? ' active' : ''}`} onClick={() => setTab('detected')}>Detectadas</button>
            <button className={`tab${tab === 'manual' ? ' active' : ''}`} onClick={() => setTab('manual')}>Manual</button>
          </div>
          {tab === 'detected' && <StructureViewer projectId={projectId} paginas={paginas} onSaved={onDone} />}
          {tab === 'manual' && <ManualEditor projectId={projectId} initialPaginas={paginas} onSaved={onDone} />}
        </>
      )}
    </div>
  )
}
