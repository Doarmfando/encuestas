import { useAppStore } from '../store/useAppStore'
import { useProject } from '../hooks/useProject'
import { StepsIndicator } from '../components/ui/StepsIndicator'
import { ScrapePanel } from '../components/scraping/ScrapePanel'
import { AnalysisPanel } from '../components/analysis/AnalysisPanel'
import { ConfigSelector } from '../components/configs/ConfigSelector'
import { ExecutionPanel } from '../components/execution/ExecutionPanel'

function currentStep(status?: string, hasConfig?: boolean): number {
  if (!status || status === 'nuevo') return 1
  if (status === 'scrapeado') return 2
  if (status === 'configurado' || hasConfig) return 4
  return 2
}

export function ProjectView() {
  const { currentProjectId } = useAppStore()
  const { data: project, isLoading, error } = useProject(currentProjectId)

  if (isLoading) return <div className="empty-state">Cargando proyecto...</div>
  if (error || !project) return <div className="alert alert-error">{error?.message || 'Proyecto no encontrado'}</div>

  const step = currentStep(project.status, !!project.config_activa)
  const paginas = project.estructura?.paginas ?? []

  return (
    <div>
      <StepsIndicator current={step} />

      <ScrapePanel
        projectId={project.id}
        projectUrl={project.url}
        initialPaginas={paginas}
        plataforma={project.plataforma}
        onDone={() => {}}
      />

      {step >= 2 && (
        <AnalysisPanel projectId={project.id} onDone={() => {}} />
      )}

      {step >= 2 && (
        <ConfigSelector projectId={project.id} onDone={() => {}} />
      )}

      {step >= 4 && (
        <ExecutionPanel projectId={project.id} />
      )}
    </div>
  )
}
