import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { DashboardResponse } from '../types'

export const useDashboard = (enabled: boolean) =>
  useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardResponse>('dashboard'),
    refetchInterval: enabled ? 2000 : false,
  })
