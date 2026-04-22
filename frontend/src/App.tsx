import { useAppStore } from './store/useAppStore'
import { Header } from './components/layout/Header'
import { SettingsPanel } from './components/layout/SettingsPanel'
import { ProjectsView } from './views/ProjectsView'
import { ProjectView } from './views/ProjectView'
import { DashboardView } from './views/DashboardView'

const VIEW_TITLE: Record<string, string> = {
  proyectos: 'Sistema de Encuestas',
  proyecto: 'Proyecto',
  dashboard: 'Dashboard',
}
const VIEW_SUBTITLE: Record<string, string> = {
  proyectos: 'Gestiona tus proyectos de encuestas con IA',
  dashboard: 'Ejecuciones en tiempo real',
}

export default function App() {
  const { view, settingsPanelOpen } = useAppStore()

  return (
    <div className="app">
      <Header title={VIEW_TITLE[view] || ''} subtitle={VIEW_SUBTITLE[view]} />

      {view === 'proyectos' && <ProjectsView />}
      {view === 'proyecto' && <ProjectView />}
      {view === 'dashboard' && <DashboardView />}

      {settingsPanelOpen && <SettingsPanel />}
    </div>
  )
}
