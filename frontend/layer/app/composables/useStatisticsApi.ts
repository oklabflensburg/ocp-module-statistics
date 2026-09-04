import type {
  StatisticsImportRunPage,
  StatisticsImportStatus,
  StatisticsMetricPage,
  StatisticsSource
} from '../types/statistics'
import { useModuleHttp } from '#frontend-module-sdk'

type MetricFilters = {
  query?: string
  category?: string
  source?: string
  offset?: number
  limit?: number
}

function queryString(values: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return query.size ? `?${query}` : ''
}

export function useStatisticsApi() {
  const { request } = useModuleHttp()
  return {
    sources: () => request<StatisticsSource[]>('/statistics/sources'),
    metrics: (filters: MetricFilters = {}) => request<StatisticsMetricPage>(
      `/statistics/metrics${queryString(filters)}`
    ),
    importStatus: () => request<StatisticsImportStatus>(
      '/statistics/import-status', { cache: 'no-store' }
    ),
    importRuns: (offset = 0, limit = 25) => request<StatisticsImportRunPage>(
      `/statistics/import-runs${queryString({ offset, limit })}`,
      { cache: 'no-store' }
    )
  }
}
