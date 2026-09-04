<template>
  <ContentPageShell
    title="Statistik"
    description="Kommunale Statistikdaten, ihre Quellen und die veröffentlichten Kennzahlen im Überblick."
    eyebrow="Datenkatalog"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Statistik' }]"
    max-width="wide"
  >
    <div v-if="error" role="alert" class="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900">
      Der Statistikdienst ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut.
    </div>

    <div v-else class="grid gap-5 md:grid-cols-2">
      <NuxtLink class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-[#154d73] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/statistik/datenquellen">
        <p class="text-sm font-bold uppercase tracking-wide text-[#154d73]">Datenquellen</p>
        <p class="mt-3 text-3xl font-black text-slate-950">{{ sources?.length || 0 }}</p>
        <p class="mt-2 leading-6 text-slate-600">Veröffentlichte Datensätze mit Lizenz, Herkunft und Datenstand.</p>
        <span class="mt-5 inline-flex font-bold text-[#154d73]">Datenquellen ansehen <span class="ml-1" aria-hidden="true">→</span></span>
      </NuxtLink>

      <NuxtLink class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-[#154d73] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" to="/statistik/kennzahlen">
        <p class="text-sm font-bold uppercase tracking-wide text-[#154d73]">Kennzahlen</p>
        <p class="mt-3 text-3xl font-black text-slate-950">{{ metrics?.total || 0 }}</p>
        <p class="mt-2 leading-6 text-slate-600">Öffentlich verfügbare Metriken nach Kategorie und Quelle.</p>
        <span class="mt-5 inline-flex font-bold text-[#154d73]">Kennzahlen durchsuchen <span class="ml-1" aria-hidden="true">→</span></span>
      </NuxtLink>
    </div>

    <section class="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-6" aria-labelledby="area-statistics-owner">
      <h2 id="area-statistics-owner" class="text-xl font-black text-slate-950">Statistik für ein konkretes Gebiet</h2>
      <p class="mt-3 max-w-3xl leading-7 text-slate-700">
        Zusammenfassungen, Zeitreihen und Vergleiche für Gemeinden, Stadtteile und Quartiere
        gehören zu den Gebietsprofilen des eigenständigen Analysis-Areas-Moduls.
      </p>
    </section>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { useModuleSeo } from '#frontend-module-sdk'

const api = useStatisticsApi()
const { data, error } = await useAsyncData('statistics-overview', async () => {
  const [sources, metrics] = await Promise.all([api.sources(), api.metrics({ limit: 1 })])
  return { sources, metrics }
})
const sources = computed(() => data.value?.sources)
const metrics = computed(() => data.value?.metrics)

useModuleSeo({
  title: 'Kommunale Statistik',
  description: 'Datenquellen und veröffentlichte kommunale Kennzahlen im Stadtplaner.',
  path: '/statistik'
})
</script>
