import { mkdir, mkdtemp, readFile, rm } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import os from 'node:os'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const packageMetadata = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'))
const version = process.env.VERSION ?? packageMetadata.version
if (version !== packageMetadata.version) {
  throw new Error(`Requested version ${version} does not match package.json version ${packageMetadata.version}`)
}
const output = path.join(root, 'dist', `statistics-${version}.tgz`)
await rm(path.join(root, 'dist'), { recursive: true, force: true })
await mkdir(path.dirname(output), { recursive: true })
const staging = await mkdtemp(path.join(os.tmpdir(), 'statistics-frontend-'))

try {
  const deploy = spawnSync('corepack', [
    'pnpm', '--filter', '@open-city-planner/statistics',
    'deploy', '--prod', '--legacy', '--frozen-lockfile', staging
  ], { cwd: root, stdio: 'inherit' })
  if (deploy.status !== 0) process.exit(deploy.status ?? 1)

  const archive = spawnSync('tar', [
    '--sort=name', '--mtime=UTC 1980-01-01', '--owner=0', '--group=0', '--numeric-owner',
    '-czf', output, 'package.json', 'module.json', 'layer'
  ], { cwd: staging, stdio: 'inherit' })
  if (archive.status !== 0) process.exit(archive.status ?? 1)
  console.log(output)
} finally {
  await rm(staging, { recursive: true, force: true })
}
