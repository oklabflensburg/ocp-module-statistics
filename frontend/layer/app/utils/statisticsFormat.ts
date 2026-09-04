export function formatStatisticsDate(value: string | null | undefined) {
  if (!value) return 'Noch nicht verfügbar'
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value))
}

export function importStatusLabel(status: string) {
  return ({
    RUNNING: 'Läuft',
    SUCCESS: 'Erfolgreich',
    FAILED: 'Fehlgeschlagen'
  } as Record<string, string>)[status] || status
}

export function importStatusTone(status: string): 'info' | 'success' | 'danger' | 'neutral' {
  if (status === 'RUNNING') return 'info'
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILED') return 'danger'
  return 'neutral'
}
