import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Pagina, Project } from '../types'

export const useProject = (id: number | null) =>
  useQuery({
    queryKey: ['project', id],
    queryFn: () => api.get<Project>(`projects/${id}`),
    enabled: id !== null,
  })

export const useScrape = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { headless: boolean; force_platform?: string }) =>
      api.post<{ paginas: Pagina[]; total_preguntas: number; plataforma: string; titulo: string; project_id: number }>(
        `projects/${projectId}/scrape`, data
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project', projectId] }),
  })
}

export const useManualStructure = (projectId: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { paginas: Pagina[] }) =>
      api.post<{ paginas: Pagina[]; total_preguntas: number; plataforma: string; project_id: number }>(
        `projects/${projectId}/manual-structure`, data
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project', projectId] }),
  })
}
