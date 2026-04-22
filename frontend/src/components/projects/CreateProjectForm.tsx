import { useState } from 'react'
import { useCreateProject } from '../../hooks/useProjects'
import { useAppStore } from '../../store/useAppStore'

interface CreateProjectFormProps {
  onClose: () => void
}

export function CreateProjectForm({ onClose }: CreateProjectFormProps) {
  const [nombre, setNombre] = useState('')
  const [url, setUrl] = useState('')
  const [desc, setDesc] = useState('')
  const { mutate, isPending, error } = useCreateProject()
  const { openProject } = useAppStore()

  const submit = () => {
    if (!nombre.trim() || !url.trim()) return
    mutate({ nombre: nombre.trim(), url: url.trim(), descripcion: desc.trim() }, {
      onSuccess: (p) => { onClose(); openProject(p.id) },
    })
  }

  return (
    <div className="card">
      <h3 style={{ marginBottom: 16 }}>Crear nuevo proyecto</h3>
      <div className="form-group">
        <label>Nombre del proyecto</label>
        <input type="text" value={nombre} onChange={e => setNombre(e.target.value)} placeholder="Ej: Encuesta Satisfacción" autoFocus />
      </div>
      <div className="form-group">
        <label>URL del formulario</label>
        <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://forms.gle/..." />
      </div>
      <div className="form-group">
        <label>Descripción (opcional)</label>
        <input type="text" value={desc} onChange={e => setDesc(e.target.value)} placeholder="Descripción breve" />
      </div>
      {error && <div className="alert alert-error mt-10">{error.message}</div>}
      <div className="flex-gap mt-10">
        <button className="btn btn-primary" onClick={submit} disabled={isPending || !nombre || !url}>
          {isPending ? 'Creando...' : 'Crear'}
        </button>
        <button className="btn btn-outline" onClick={onClose}>Cancelar</button>
      </div>
    </div>
  )
}
