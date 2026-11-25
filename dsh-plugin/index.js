import { readdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { buildToolList } from './lib/h3-tools.mjs'

// npm tarball reads the synced copies; a repository checkout can fall back to
// the canonical skills at the repository root.
const packageRoot = dirname(fileURLToPath(import.meta.url))
const SKILL_ROOTS = [
  resolve(packageRoot, 'skills'),
  resolve(packageRoot, '..', 'skills'),
]

const DSH_NOTE = [
  '> DeepSeek Harness 已注册原生工具 `h3_generate`、`h3_status`、`h3_doctor`、`h3_list_runs`。',
  '> 常规提交、查进度和体检优先用这些工具；批量 showrunner、白模、后期和多镜合同仍按本 skill 的脚本执行。',
  '> ComfyUI 路径从 `H3LITE_COMFYUI` 或 `~/.h3lite/config.json` 读取，不依赖当前会话目录。',
  '',
  '',
].join('\n')

export const inject = ['skills', 'tools']

export function apply(ctx, config = {}) {
  const wantSkills = config.skills !== false
  const wantTools = config.tools !== false

  if (wantTools) {
    const { tools } = buildToolList(packageRoot)
    for (const tool of tools) {
      ctx.effect(() => ctx.tools.register(tool))
    }
  }

  if (!wantSkills) return
  const loaded = loadSkills()
  if (!loaded.length) {
    console.warn(`[h3lite] no SKILL.md found; tried ${SKILL_ROOTS.join(', ')}`)
    return
  }
  for (const { path: skillPath, raw } of loaded) {
    const { meta, body } = parseFrontmatter(raw)
    const name = meta.name
    const description = meta.description
    if (!name || !description) {
      console.warn(`[h3lite] skill ${skillPath} has no name or description`)
      continue
    }
    const skill = {
      name,
      description,
      source: 'runtime',
      content: `${DSH_NOTE}${body.replace(/^\s+/, '')}`,
      resourceBase: { kind: 'directory', path: dirname(skillPath) },
    }
    if (meta.whenToUse) skill.whenToUse = meta.whenToUse
    ctx.effect(() => ctx.skills.register(skill))
  }
}

function loadSkills() {
  for (const root of SKILL_ROOTS) {
    let entries
    try {
      entries = readdirSync(root, { withFileTypes: true })
    }
    catch {
      continue
    }
    const found = []
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const file = resolve(root, entry.name, 'SKILL.md')
      try {
        found.push({ path: file, raw: readFileSync(file, 'utf8') })
      }
      catch {
        // Directory without SKILL.md.
      }
    }
    if (found.length) return found
  }
  return []
}

function parseFrontmatter(raw) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(raw)
  if (!match) return { meta: {}, body: raw }
  const lines = match[1].split(/\r?\n/)
  const meta = {}
  for (let index = 0; index < lines.length; index += 1) {
    const field = /^([A-Za-z0-9_-]+):[ \t]*(.*)$/.exec(lines[index])
    if (!field) continue
    const key = field[1]
    let value = field[2].trim()
    if (/^[>|][+-]?$/.test(value)) {
      const parts = []
      while (index + 1 < lines.length && /^[ \t]+\S/.test(lines[index + 1])) {
        parts.push(lines[index + 1].trim())
        index += 1
      }
      value = (value.startsWith('|') ? parts.join('\n') : parts.join(' ')).trim()
    }
    else {
      value = value.replace(/^(['"])(.*)\1$/, '$2')
    }
    meta[key] = value
  }
  return { meta, body: raw.slice(match[0].length) }
}
