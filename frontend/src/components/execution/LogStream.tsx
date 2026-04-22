import { useEffect, useRef } from 'react'
import { useLogs } from '../../hooks/useExecution'

interface LogStreamProps {
  projectId: number
  executionId: number | null
  active: boolean
}

export function LogStream({ projectId, executionId, active }: LogStreamProps) {
  const { data: logs } = useLogs(projectId, active ? executionId : null)
  const ref = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [logs])

  return (
    <pre className="console-output" ref={ref}>
      {logs || 'Esperando logs...'}
    </pre>
  )
}
