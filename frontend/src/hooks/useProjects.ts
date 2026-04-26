import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Project, ProjectSimple } from '../types'

export const useProjects = () =>
  useQuery({ queryKey: ['projects'], queryFn: () => api.get<ProjectSimple[]>('projects') })

export const useCreateProject = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { nombre: string; url: string; descripcion: string }) =>
      api.post<{ id: number }>('projects', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export const useDeleteProject = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete<{ mensaje: string }>(`projects/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export const useUpdateProject = (id: number) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Pick<Project, 'nombre' | 'descripcion' | 'url'>>) =>
      api.put<Project>(`projects/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}
