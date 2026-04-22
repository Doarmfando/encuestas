import { useAppStore } from '../../store/useAppStore'

interface HeaderProps {
  title: string
  subtitle?: string
}

export function Header({ title, subtitle }: HeaderProps) {
  const { view, goBack, showDashboard, toggleSettings } = useAppStore()

  return (
    <div className="app-header">
      <h1>{title}</h1>
      {subtitle && <p className="subtitle">{subtitle}</p>}
      <div className="header-actions">
        <button className="btn btn-outline btn-sm" onClick={showDashboard}>Dashboard</button>
        <button className="btn btn-outline btn-sm" onClick={toggleSettings}>Config</button>
        {(view === 'proyecto' || view === 'dashboard') && (
          <button className="btn btn-outline btn-sm" onClick={goBack}>Volver</button>
        )}
      </div>
    </div>
  )
}
