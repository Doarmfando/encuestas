import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Perfil, ProjectConfig, Regla, Tendencia } from '../types'

export const useConfigs = (projectId: number) =>
  useQuery({
    queryKey: ['configs', projectId],
    queryFn: () => api.get<ProjectConfig[]>(`projects/${projectId}/configs`),
  })

interface SaveConfigParams {
  nombre: string
  perfiles: Perfil[]
  reglas_dependencia: Regla[]
  tendencias_escalas: Tendencia[]
  replace_existing?: boolean
  replace_config_id?: number | null
}

export const useCreateConfig = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: SaveConfigParams) =>
      api.post<ProjectConfig>(`projects/${projectId}/configs`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['configs', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })
}

export const useActivateConfig = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (configId: number) =>
      api.put<{ mensaje: string }>(`projects/${projectId}/configs/${configId}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['configs', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })
}

export const useDeleteConfig = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (configId: number) =>
      api.delete<{ mensaje: string }>(`projects/${projectId}/configs/${configId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['configs', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })
}
