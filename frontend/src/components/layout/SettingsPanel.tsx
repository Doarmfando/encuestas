import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useAppStore } from '../../store/useAppStore'
import type { AIProvider, AppSettings } from '../../types'

export function SettingsPanel() {
  const { closeSettings } = useAppStore()
  const qc = useQueryClient()
  const [providerName, setProviderName] = useState('openai')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [error, setError] = useState('')

  const { data: providers } = useQuery({
    queryKey: ['ai-providers'],
    queryFn: () => api.get<AIProvider[]>('config/ai-providers'),
  })

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<AppSettings>('config/settings'),
  })

  const activate = useMutation({
    mutationFn: (name: string) => api.put(`config/ai-providers/${name}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-providers'] }),
  })

  const addProvider = useMutation({
    mutationFn: () => api.post('config/ai-providers', { provider_name: providerName, api_key: apiKey, model: model || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-providers'] })
      setApiKey('')
      setModel('')
      setError('')
    },
    onError: (e: Error) => setError(e.message),
  })

  return (
    <div className="side-panel">
      <div className="panel-header">
        <h3>Configuración</h3>
        <button className="btn btn-outline btn-sm" onClick={closeSettings}>✕</button>
      </div>
      <div className="panel-body">
        <h4 style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>Proveedores IA</h4>
        <div className="provider-list">
          {providers?.map(p => (
            <div
              key={p.name}
              className={`provider-item${p.is_active ? ' active' : ''}`}
              onClick={() => activate.mutate(p.name)}
            >
              <span className="provider-name">{p.name}</span>
              <span className="provider-model">{p.model}</span>
              {p.is_active && <span className="provider-badge">Activo</span>}
            </div>
          ))}
        </div>

        <div className="form-group">
          <label>Proveedor</label>
          <select value={providerName} onChange={e => setProviderName(e.target.value)}>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>
        <div className="form-group">
          <label>API Key</label>
          <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-..." />
        </div>
        <div className="form-group">
          <label>Modelo (opcional)</label>
          <input type="text" value={model} onChange={e => setModel(e.target.value)} placeholder="gpt-4o / claude-sonnet..." />
        </div>
        {error && <div className="alert alert-error mt-10">{error}</div>}
        <button className="btn btn-primary btn-sm" onClick={() => addProvider.mutate()} disabled={!apiKey}>
          Agregar proveedor
        </button>

        {settings && (
          <>
            <hr className="divider" />
            <h4 style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>Settings del servidor</h4>
            <div className="settings-grid">
              {[
                ['Idioma browser', settings.browser_locale],
                ['Zona horaria', settings.browser_timezone],
                ['Viewport', `${settings.browser_viewport?.width}x${settings.browser_viewport?.height}`],
                ['Max encuestas', String(settings.max_encuestas)],
                ['Headless default', settings.default_headless ? 'Sí' : 'No'],
                ['Perfil default', settings.default_execution_profile],
                ['IA Temperature', String(settings.ai_temperature)],
                ['IA Max tokens', String(settings.ai_max_tokens)],
              ].map(([label, value]) => (
                <div key={label} className="setting-item">
                  <span className="setting-label">{label}</span>
                  <span className="setting-value">{value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
