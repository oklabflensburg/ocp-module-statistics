<template>
  <ContentPageShell
    title="Kennzahlen"
    description="Öffentlich verfügbare kommunale Kennzahlen nach Name, Kategorie und Quelle durchsuchen."
    eyebrow="Statistik"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Statistik', to: '/statistik' }, { label: 'Kennzahlen' }]"
    max-width="wide"
  >
    <form class="grid gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-5 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto]" @submit.prevent="applyFilters">
      <label><span class="mb-1 block text-sm font-bold text-slate-700">Suche</span><input v-model.trim="filters.query" class="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" maxlength="120" placeholder="Name oder Schlüssel"></label>
      <label><span class="mb-1 block text-sm font-bold text-slate-700">Kategorie</span><input v-model.trim="filters.category" class="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" maxlength="80" placeholder="Alle Kategorien"></label>
      <label><span class="mb-1 block text-sm font-bold text-slate-700">Quelle</span><input v-model.trim="filters.source" class="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" maxlength="40" placeholder="Alle Quellen"></label>
      <button class="min-h-11 self-end rounded-xl bg-[#154d73] px-5 font-bold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" type="submit">Filtern</button>
    </form>

    <div v-if="error" role="alert" class="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900">Die Kennzahlen konnten nicht geladen werden.</div>
    <p v-else-if="!page?.items.length" class="mt-6 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">Für diese Auswahl wurden keine öffentlichen Kennzahlen gefunden.</p>
    <template v-else>
      <p class="mt-6 text-sm text-slate-600">{{ page.total.toLocaleString('de-DE') }} öffentliche Kennzahlen</p>
      <ul class="mt-3 divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-white">
        <li v-for="metric in page.items" :key="metric.key" class="p-5 sm:p-6">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div><p class="text-xs font-bold uppercase tracking-wide text-[#154d73]">{{ metric.category }}</p><h2 class="mt-1 text-lg font-black text-slate-950">{{ metric.name }}</h2><code class="mt-1 block text-xs text-slate-500">{{ metric.key }}</code></div>
            <OcpStatusBadge>{{ metric.unit }}</OcpStatusBadge>
          </div>
          <p v-if="metric.description" class="mt-3 leading-6 text-slate-700">{{ metric.description }}</p>
          <p class="mt-3 text-sm text-slate-500">{{ metric.dataset_name }} · {{ metric.source }}</p>
        </li>
      </ul>
      <nav class="mt-5 flex items-center justify-between gap-4" aria-label="Seitennavigation der Kennzahlen">
        <button class="min-h-11 rounded-xl border border-slate-300 px-4 font-bold disabled:cursor-not-allowed disabled:opacity-50" type="button" :disabled="page.offset === 0" @click="movePage(-page.limit)">Zurück</button>
        <span class="text-sm text-slate-600">{{ page.offset + 1 }}–{{ Math.min(page.offset + page.items.length, page.total) }} von {{ page.total }}</span>
        <button class="min-h-11 rounded-xl border border-slate-300 px-4 font-bold disabled:cursor-not-allowed disabled:opacity-50" type="button" :disabled="page.offset + page.items.length >= page.total" @click="movePage(page.limit)">Weiter</button>
      </nav>
    </template>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { useModuleSeo } from '#frontend-module-sdk'
import { OcpStatusBadge } from '#frontend-module-sdk/ui'

const filters = reactive({ query: '', category: '', source: '' })
const offset = ref(0)
const api = useStatisticsApi()
const { data: page, error, refresh } = await useAsyncData(
  'statistics-metrics',
  () => api.metrics({ ...filters, offset: offset.value, limit: 25 })
)

async function applyFilters() {
  offset.value = 0
  await refresh()
}

async function movePage(delta: number) {
  offset.value = Math.max(0, offset.value + delta)
  await refresh()
}

useModuleSeo({
  title: 'Kommunale Kennzahlen',
  description: 'Öffentliche kommunale Kennzahlen nach Kategorie und Datenquelle durchsuchen.',
  path: '/statistik/kennzahlen'
})
</script>
