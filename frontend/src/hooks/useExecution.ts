import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { EstadoResponse, Execution, SpeedProfile } from '../types'

export const useExecute = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { cantidad: number; headless: boolean; speed_profile: SpeedProfile }) =>
      api.post<{ mensaje: string; execution_id: number }>(`projects/${projectId}/execute`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executions', projectId] }),
  })
}

export const useEstado = (projectId: number, enabled: boolean) =>
  useQuery({
    queryKey: ['estado', projectId],
    queryFn: () => api.get<EstadoResponse>(`projects/${projectId}/estado`),
    refetchInterval: enabled ? 1500 : false,
  })

export const useLogs = (projectId: number, executionId: number | null) =>
  useQuery({
    queryKey: ['logs', executionId],
    queryFn: () =>
      api.get<{ logs: string }>(
        `projects/${projectId}/logs${executionId ? `?execution_id=${executionId}` : ''}`
      ),
    refetchInterval: executionId ? 1500 : false,
    select: (data) => data.logs,
  })

export const useStop = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (executionId?: number) =>
      api.post<{ mensaje: string }>(
        `projects/${projectId}/stop`,
        executionId ? { execution_id: executionId } : {}
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['estado', projectId] })
      qc.invalidateQueries({ queryKey: ['executions', projectId] })
    },
  })
}

export const useExecutions = (projectId: number) =>
  useQuery({
    queryKey: ['executions', projectId],
    queryFn: () => api.get<Execution[]>(`projects/${projectId}/executions`),
  })
