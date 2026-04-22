import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Perfil, ProjectConfig, Regla, Tendencia } from '../types'

interface AnalyzeResult {
  preview: boolean
  project_id: number
  perfiles: Perfil[]
  reglas_dependencia: Regla[]
  tendencias_escalas: Tendencia[]
}

export const useAnalyze = (projectId: number) =>
  useMutation({
    mutationFn: (instrucciones: string) =>
      api.post<AnalyzeResult>(`projects/${projectId}/analyze`, { instrucciones }),
  })

export const useApplyConfig = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      nombre: string
      perfiles: Perfil[]
      reglas_dependencia: Regla[]
      tendencias_escalas: Tendencia[]
    }) => api.post<ProjectConfig>(`projects/${projectId}/apply-config`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['configs', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })
}

export const useTemplateConfig = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (nombre: string) =>
      api.post<ProjectConfig>(`projects/${projectId}/template-config`, { nombre }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['configs', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })
}
