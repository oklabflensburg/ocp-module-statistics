<template>
  <ContentPageShell
    title="Statistik-Import"
    description="Konfiguration und letzte Läufe des kommunalen Statistikimports."
    eyebrow="Betrieb"
    :breadcrumbs="[{ label: 'Statistik', to: '/statistik' }, { label: 'Importstatus' }]"
    max-width="wide"
  >
    <div v-if="error" role="alert" class="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900">
      {{ accessErrorMessage }}
    </div>
    <template v-else-if="data">
      <section class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="import-configuration">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div><h2 id="import-configuration" class="text-xl font-black text-slate-950">Importkonfiguration</h2><p class="mt-2 text-slate-600">Der Import wird ausschließlich über den registrierten Moduljob ausgeführt.</p></div>
          <OcpStatusBadge :tone="data.status.import_enabled ? 'success' : 'warning'">{{ data.status.import_enabled ? 'Aktiviert' : 'Deaktiviert' }}</OcpStatusBadge>
        </div>
        <p v-if="!data.status.import_enabled" class="mt-4 rounded-xl bg-amber-50 p-4 text-amber-900">Der automatische und manuelle Import ist in der Modulkonfiguration deaktiviert. Öffentliche Lesefunktionen bleiben verfügbar.</p>
        <p v-else-if="!data.status.job_available" class="mt-4 rounded-xl bg-rose-50 p-4 text-rose-900">Der Importjob ist nicht verfügbar.</p>
      </section>

      <section class="mt-6" aria-labelledby="import-runs">
        <h2 id="import-runs" class="text-2xl font-black text-slate-950">Importläufe</h2>
        <p v-if="!data.runs.items.length" class="mt-4 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">Es wurde noch kein Importlauf protokolliert.</p>
        <ul v-else class="mt-4 space-y-4">
          <li v-for="run in data.runs.items" :key="run.id" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div><p class="font-black text-slate-950">{{ formatStatisticsDate(run.started_at) }}</p><p class="mt-1 text-sm text-slate-500">{{ run.source }} · Lauf {{ run.id }}</p></div>
              <OcpStatusBadge :tone="importStatusTone(run.status)">{{ importStatusLabel(run.status) }}</OcpStatusBadge>
            </div>
            <dl class="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
              <div><dt class="text-slate-500">Geladen</dt><dd class="font-black">{{ run.rows_downloaded }}</dd></div><div><dt class="text-slate-500">Neu</dt><dd class="font-black">{{ run.rows_imported }}</dd></div><div><dt class="text-slate-500">Aktualisiert</dt><dd class="font-black">{{ run.rows_updated }}</dd></div><div><dt class="text-slate-500">Unverändert</dt><dd class="font-black">{{ run.rows_unchanged }}</dd></div><div><dt class="text-slate-500">Abgelehnt</dt><dd class="font-black">{{ run.rows_rejected }}</dd></div>
            </dl>
            <p v-if="run.error_summary" class="mt-4 break-words rounded-xl bg-rose-50 p-3 text-sm text-rose-900">{{ run.error_summary }}</p>
          </li>
        </ul>
      </section>
    </template>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { useModuleSeo } from '#frontend-module-sdk'
import { OcpStatusBadge } from '#frontend-module-sdk/ui'
import { formatStatisticsDate, importStatusLabel, importStatusTone } from '../../utils/statisticsFormat'

const api = useStatisticsApi()
const { data, error } = await useAsyncData('statistics-import-status', async () => {
  const [status, runs] = await Promise.all([api.importStatus(), api.importRuns()])
  return { status, runs }
})
const accessErrorMessage = computed(() => {
  const statusCode = Number((error.value as { statusCode?: number } | null)?.statusCode || 0)
  if (statusCode === 401) return 'Bitte melden Sie sich an, um den Importstatus aufzurufen.'
  if (statusCode === 403) return 'Sie haben keine Berechtigung, den Importstatus aufzurufen.'
  return 'Der Importstatus konnte nicht geladen werden.'
})

useModuleSeo({
  title: 'Statistik-Importstatus',
  description: 'Geschützter Betriebsstatus des kommunalen Statistikimports.',
  path: '/statistik/importstatus',
  robots: 'noindex,nofollow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
