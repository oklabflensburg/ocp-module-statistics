import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { formatStatisticsDate, importStatusLabel, importStatusTone } from '../layer/app/utils/statisticsFormat'

const root = fileURLToPath(new URL('..', import.meta.url))
const definition = JSON.parse(readFileSync(`${root}/module.json`, 'utf8'))
const page = (name: string) => readFileSync(`${root}/layer/app/pages/statistik/${name}`, 'utf8')

describe('Statistics frontend module contract', () => {
  it('declares compatible versioned module-owned routes', () => {
    expect(definition.version).toBe('0.4.0')
    expect(definition.backendModuleId).toBe('statistics')
    expect(definition.compatibility).toEqual({
      host: '>=1.0.0 <2.0.0',
      sdk: '>=1.5.0 <2.0.0',
      backend: '>=0.4.0 <0.5.0'
    })
    expect(definition.publicContributions.routes.map((route: { path: string }) => route.path)).toEqual([
      '/statistik',
      '/statistik/datenquellen',
      '/statistik/kennzahlen',
      '/statistik/importstatus'
    ])
    expect(definition.publicContributions.sitemap.staticRoutes).toEqual([
      '/statistik',
      '/statistik/datenquellen',
      '/statistik/kennzahlen'
    ])
  })

  it('owns public and permission-aware navigation contributions', () => {
    const [primary, operator] = definition.publicContributions.ui
    expect(primary).toMatchObject({
      id: 'statistics.primary-navigation',
      slot: 'navigation.primary',
      label: 'Statistik',
      to: '/statistik',
      visibility: { auth: 'public', module: 'statistics' }
    })
    expect(operator).toMatchObject({
      id: 'statistics.import-status-navigation',
      slot: 'navigation.admin',
      to: '/statistik/importstatus',
      visibility: {
        auth: 'authenticated',
        permission: 'statistics.import',
        module: 'statistics'
      }
    })
    expect(definition.publicContributions.map).toEqual({ sources: [], layers: [] })
  })

  it('ships SSR SEO plus explicit empty and error states', () => {
    for (const source of ['index.vue', 'datenquellen.vue', 'kennzahlen.vue', 'importstatus.vue']) {
      expect(page(source)).toContain('await useAsyncData')
      expect(page(source)).toContain('useModuleSeo')
      expect(page(source)).toContain('v-if="error"')
    }
    expect(page('datenquellen.vue')).toContain('keine Statistik-Datenquellen')
    expect(page('kennzahlen.vue')).toContain('keine öffentlichen Kennzahlen')
    expect(page('importstatus.vue')).toContain('noch kein Importlauf')
    expect(page('importstatus.vue')).toContain('keine Berechtigung')
  })

  it('does not recreate area, comparison, polygon, or private host imports', () => {
    const sources = ['index.vue', 'datenquellen.vue', 'kennzahlen.vue', 'importstatus.vue']
      .map(page)
      .join('\n')
    expect(sources).not.toMatch(/~\/(?:stores|composables|types|utils)/)
    expect(sources).not.toContain('/vergleich')
    expect(sources).not.toContain('/polygons')
    expect(sources).not.toContain('to="/gebiete"')
    expect(sources).not.toContain('/analysis-areas/by-slug')
  })
})

describe('Statistics presentation formatting', () => {
  it('formats import status and missing dates in German', () => {
    expect(formatStatisticsDate(null)).toBe('Noch nicht verfügbar')
    expect(importStatusLabel('SUCCESS')).toBe('Erfolgreich')
    expect(importStatusTone('FAILED')).toBe('danger')
  })
})
