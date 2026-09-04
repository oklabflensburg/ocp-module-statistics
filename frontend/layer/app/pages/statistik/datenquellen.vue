<template>
  <ContentPageShell
    title="Datenquellen"
    description="Herkunft, Lizenz und Aktualität der kommunalen Statistikdaten."
    eyebrow="Statistik"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Statistik', to: '/statistik' }, { label: 'Datenquellen' }]"
    max-width="wide"
  >
    <div v-if="error" role="alert" class="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900">
      Die Datenquellen konnten nicht geladen werden.
    </div>
    <p v-else-if="!sources?.length" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
      Derzeit sind keine Statistik-Datenquellen veröffentlicht.
    </p>
    <ul v-else class="grid gap-5 lg:grid-cols-2">
      <li v-for="source in sources" :key="`${source.source}:${source.dataset}`" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p class="text-xs font-bold uppercase tracking-wide text-slate-500">{{ source.source }} · Datensatz {{ source.dataset }}</p>
            <h2 class="mt-2 text-xl font-black text-slate-950">{{ source.name }}</h2>
          </div>
          <OcpStatusBadge :tone="source.last_import_at ? 'success' : 'warning'">
            {{ source.last_import_at ? 'Importiert' : 'Noch kein Import' }}
          </OcpStatusBadge>
        </div>
        <p v-if="source.description" class="mt-3 leading-6 text-slate-700">{{ source.description }}</p>
        <dl class="mt-5 grid gap-4 border-t border-slate-200 pt-5 text-sm sm:grid-cols-2">
          <div><dt class="font-semibold text-slate-500">Lizenz</dt><dd class="mt-1 text-slate-900">{{ source.license }}</dd></div>
          <div><dt class="font-semibold text-slate-500">Aktualisierung</dt><dd class="mt-1 text-slate-900">{{ source.update_frequency }}</dd></div>
          <div><dt class="font-semibold text-slate-500">Stand der Quelle</dt><dd class="mt-1 text-slate-900">{{ formatStatisticsDate(source.source_updated_at) }}</dd></div>
          <div><dt class="font-semibold text-slate-500">Letzter Import</dt><dd class="mt-1 text-slate-900">{{ formatStatisticsDate(source.last_import_at) }}</dd></div>
        </dl>
        <a class="mt-5 inline-flex min-h-11 items-center font-bold text-[#154d73] underline" :href="source.source_url" target="_blank" rel="noopener noreferrer">Originalquelle öffnen <span class="ml-1" aria-hidden="true">↗</span></a>
      </li>
    </ul>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { useModuleSeo } from '#frontend-module-sdk'
import { OcpStatusBadge } from '#frontend-module-sdk/ui'
import { formatStatisticsDate } from '../../utils/statisticsFormat'

const { data: sources, error } = await useAsyncData(
  'statistics-sources',
  () => useStatisticsApi().sources()
)

useModuleSeo({
  title: 'Statistik-Datenquellen',
  description: 'Herkunft, Lizenz und Aktualität der kommunalen Statistikdaten im Stadtplaner.',
  path: '/statistik/datenquellen'
})
</script>
