import { useEffect } from 'react'

interface ModalProps {
  title: string
  onClose: () => void
  onConfirm?: () => void
  confirmLabel?: string
  confirmDisabled?: boolean
  large?: boolean
  children: React.ReactNode
}

export function Modal({ title, onClose, onConfirm, confirmLabel = 'Guardar', confirmDisabled, large, children }: ModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className={`modal${large ? ' modal-lg' : ''}`}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn btn-outline btn-sm" onClick={onClose}>✕</button>
        </div>
        {children}
        {onConfirm && (
          <div className="modal-actions">
            <button className="btn btn-outline" onClick={onClose}>Cancelar</button>
            <button className="btn btn-primary" onClick={onConfirm} disabled={confirmDisabled}>{confirmLabel}</button>
          </div>
        )}
      </div>
    </div>
  )
}
