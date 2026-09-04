export type StatisticsSource = {
  source: string
  dataset: string
  name: string
  description: string | null
  source_url: string
  license: string
  update_frequency: string
  last_import_at: string | null
  source_updated_at: string | null
}

export type StatisticsMetric = {
  key: string
  name: string
  description: string | null
  category: string
  unit: string
  value_type: string
  aggregation_method: string | null
  source: string
  dataset: string
  dataset_name: string
  public: boolean
}

export type StatisticsMetricPage = {
  items: StatisticsMetric[]
  total: number
  offset: number
  limit: number
}

export type StatisticsImportRun = {
  id: number
  source: string
  started_at: string
  finished_at: string | null
  status: string
  rows_downloaded: number
  rows_imported: number
  rows_updated: number
  rows_unchanged: number
  rows_rejected: number
  error_summary: string | null
}

export type StatisticsImportRunPage = {
  items: StatisticsImportRun[]
  total: number
  offset: number
  limit: number
}

export type StatisticsImportStatus = {
  import_enabled: boolean
  job_available: boolean
  last_run: StatisticsImportRun | null
}
