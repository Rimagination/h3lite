#!/usr/bin/env node
// Copy the canonical H3Lite skills into the npm/DSH bundle.
// Run by prepack; --check verifies that committed copies have not drifted.

import { cpSync, existsSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const canonicalRoot = resolve(pluginRoot, '..', 'qoder-plugin', 'skills')
const legacyRoot = resolve(pluginRoot, '..', 'skills')
const sourceRoot = existsSync(canonicalRoot) ? canonicalRoot : legacyRoot
const targetRoot = join(pluginRoot, 'skills')
const check = process.argv.includes('--check')

function filesUnder(root) {
  const files = []
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue
    const value = join(root, entry.name)
    if (entry.isDirectory()) files.push(...filesUnder(value))
    else files.push(value)
  }
  return files
}

if (!existsSync(sourceRoot)) {
  console.error(`[h3lite] missing canonical skills: ${sourceRoot}`)
  process.exit(1)
}

if (check) {
  if (!existsSync(targetRoot)) {
    console.error(`[h3lite] missing synced skills: ${targetRoot}`)
    process.exit(1)
  }
  const sourceFiles = filesUnder(sourceRoot)
  const drifted = []
  for (const source of sourceFiles) {
    const target = join(targetRoot, relative(sourceRoot, source))
    try {
      const a = readFileSync(source, 'utf8').replace(/\r\n/g, '\n')
      const b = readFileSync(target, 'utf8').replace(/\r\n/g, '\n')
      if (a !== b) drifted.push(relative(sourceRoot, source))
    }
    catch {
      drifted.push(relative(sourceRoot, source))
    }
  }
  if (drifted.length) {
    console.error(`[h3lite] skills out of sync (${drifted.length}):`)
    for (const file of drifted.slice(0, 30)) console.error(`  ${file}`)
    process.exit(1)
  }
  console.log(`[h3lite] skills in sync (${sourceFiles.length} files)`)
  process.exit(0)
}

rmSync(targetRoot, { recursive: true, force: true })
cpSync(sourceRoot, targetRoot, {
  recursive: true,
  filter: (source) => !source.includes('__pycache__') && !source.endsWith('.pyc'),
})
const count = filesUnder(targetRoot).length
console.log(`[h3lite] synced ${count} skill files to ${targetRoot}`)
