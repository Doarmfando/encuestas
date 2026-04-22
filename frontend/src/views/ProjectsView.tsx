import { useState } from 'react'
import { useDeleteProject, useProjects } from '../hooks/useProjects'
import { useAppStore } from '../store/useAppStore'
import { CreateProjectForm } from '../components/projects/CreateProjectForm'
import { ProjectCard } from '../components/projects/ProjectCard'

export function ProjectsView() {
  const [showCreate, setShowCreate] = useState(false)
  const { data: projects, isLoading, error } = useProjects()
  const { mutate: deleteProject } = useDeleteProject()
  const { openProject } = useAppStore()

  const handleDelete = (id: number) => {
    if (!confirm('¿Eliminar este proyecto y todo su contenido?')) return
    deleteProject(id)
  }

  return (
    <div>
      <div className="projects-header">
        <h2>Mis Proyectos</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(v => !v)}>
          {showCreate ? 'Cancelar' : '+ Nuevo Proyecto'}
        </button>
      </div>

      {showCreate && <CreateProjectForm onClose={() => setShowCreate(false)} />}

      {isLoading && <div className="empty-state">Cargando proyectos...</div>}
      {error && <div className="alert alert-error">{error.message}</div>}

      {!isLoading && !error && (
        projects?.length === 0 ? (
          <div className="empty-state">No hay proyectos. Crea uno para empezar.</div>
        ) : (
          <div className="projects-grid">
            {projects?.map(p => (
              <ProjectCard key={p.id} project={p} onOpen={openProject} onDelete={handleDelete} />
            ))}
          </div>
        )
      )}
    </div>
  )
}
