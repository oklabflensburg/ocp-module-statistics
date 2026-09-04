import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const root = fileURLToPath(new URL('..', import.meta.url))
const definition = JSON.parse(readFileSync(`${root}/module.json`, 'utf8'))

describe('Statistics frontend module contract', () => {
  it('declares the current backend module shape', () => {
    expect(definition).toEqual({
      schemaVersion: 1,
      id: 'statistics',
      version: '0.3.0',
      backendModuleId: 'statistics',
      compatibility: {
        host: '>=1.0.0 <2.0.0',
        sdk: '>=1.5.0 <2.0.0',
        backend: '>=0.3.0 <0.4.0'
      },
      layer: 'layer',
      requires: { modules: {} },
      publicContributions: {
        routes: [],
        ui: [],
        map: { sources: [], layers: [] },
        sitemap: { staticRoutes: [], dynamicRoutes: [] }
      }
    })
  })

  it('does not claim Statistics UI or route contributions', () => {
    expect(definition.publicContributions.routes).toEqual([])
    expect(definition.publicContributions.ui).toEqual([])
    expect(definition.publicContributions.map).toEqual({ sources: [], layers: [] })
  })
})
