import { spawn } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, isAbsolute, join, resolve } from 'node:path'

const DEFAULT_BASE_URL = 'http://127.0.0.1:8188'

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'))
  }
  catch {
    return {}
  }
}

function readConfig() {
  const file = process.env.H3LITE_CONFIG || join(homedir(), '.h3lite', 'config.json')
  const value = readJson(file)
  if (value && typeof value === 'object') value._configFile = file
  return value && typeof value === 'object' ? value : {}
}

function resolveMaybeRelative(value, baseFile) {
  if (typeof value !== 'string' || !value.trim()) return ''
  return isAbsolute(value) ? value : resolve(dirname(baseFile), value)
}

function findScriptsDir(packageRoot) {
  const candidates = [
    process.env.H3LITE_SCRIPTS,
    join(packageRoot, 'skills', 'h3-generate', 'scripts'),
    resolve(packageRoot, '..', 'skills', 'h3-generate', 'scripts'),
  ].filter(Boolean)
  return candidates.find((candidate) => existsSync(join(candidate, 'h3_fastpath.py')))
    || join(packageRoot, 'skills', 'h3-generate', 'scripts')
}

function resolvePython(comfyui) {
  if (process.env.H3LITE_PYTHON) return process.env.H3LITE_PYTHON
  if (comfyui) {
    const win = join(comfyui, 'venv', 'Scripts', 'python.exe')
    const nix = join(comfyui, 'venv', 'bin', 'python')
    if (existsSync(win)) return win
    if (existsSync(nix)) return nix
  }
  return process.platform === 'win32' ? 'python' : 'python3'
}

export function createRuntime(packageRoot) {
  const config = readConfig()
  const configFile = config._configFile || join(homedir(), '.h3lite', 'config.json')
  const comfyui = resolveMaybeRelative(
    process.env.H3LITE_COMFYUI || config.comfyui,
    configFile,
  )
  const outputDir = resolveMaybeRelative(
    process.env.H3LITE_OUTPUT || config.output_dir,
    configFile,
  ) || (comfyui ? join(comfyui, 'output') : '')
  const runRoot = resolveMaybeRelative(
    process.env.H3LITE_RUN_ROOT || config.run_root,
    configFile,
  ) || (comfyui ? join(comfyui, 'user', 'h3lite_runs') : '')
  const baseUrl = process.env.H3LITE_BASE_URL || config.base_url || DEFAULT_BASE_URL
  const scriptsDir = findScriptsDir(packageRoot)
  const python = resolvePython(comfyui)
  return { packageRoot, configFile, comfyui, outputDir, runRoot, baseUrl, scriptsDir, python }
}

function runScript(runtime, scriptName, args, timeoutMs) {
  return new Promise((resolvePromise, reject) => {
    const script = join(runtime.scriptsDir, scriptName)
    if (!existsSync(script)) {
      reject(new Error(`script not found: ${script}`))
      return
    }
    const child = spawn(runtime.python, [script, ...args], {
      cwd: dirname(script),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      windowsHide: true,
    })
    let stdout = ''
    let stderr = ''
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      try { child.kill('SIGKILL') } catch {}
      reject(new Error(`timeout after ${timeoutMs}ms\npartial stdout:\n${stdout}\nstderr:\n${stderr}`))
    }, timeoutMs)
    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })
    child.on('error', (error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      reject(new Error(`spawn error: ${error.message}. Set H3LITE_PYTHON to the Python that can run H3Lite scripts.`))
    })
    child.on('close', (code) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      const text = stdout.trim() || stderr.trim() || `(no output, exit ${code})`
      if (code === 0) {
        resolvePromise(text)
      }
      else {
        reject(new Error(`H3Lite script exited ${code}\n${text}`))
      }
    })
  })
}

function commonPathArgs(runtime) {
  const args = ['--base-url', runtime.baseUrl]
  if (runtime.comfyui) args.push('--comfyui', runtime.comfyui)
  if (runtime.outputDir) args.push('--output-dir', runtime.outputDir)
  if (runtime.runRoot) args.push('--run-root', runtime.runRoot)
  return args
}

export function listRuns(runtime, limit) {
  if (!runtime.runRoot || !existsSync(runtime.runRoot)) {
    return {
      ok: false,
      error: `run-root not found: ${runtime.runRoot || '(set H3LITE_RUN_ROOT or H3LITE_COMFYUI)'}`,
    }
  }
  const dirs = readdirSync(runtime.runRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .sort((a, b) => (a.name < b.name ? 1 : -1))
  const max = Math.max(1, Number(limit) || 40)
  const runs = []
  for (const dir of dirs) {
    if (runs.length >= max) break
    const manifestPath = join(runtime.runRoot, dir.name, 'manifest.json')
    let manifest
    try {
      manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
    }
    catch {
      continue
    }
    if (!manifest || typeof manifest !== 'object') continue
    runs.push({
      run_id: dir.name,
      prompt_id: manifest.prompt_id || null,
      state: manifest.state || null,
      filename_prefix: manifest.filename_prefix || null,
      length: manifest.effective_settings?.length || manifest.length || null,
      reference_mode: manifest.effective_settings?.reference_mode || null,
      elapsed_seconds: manifest.elapsed_seconds || null,
      warnings: manifest.warnings || [],
      output_paths: (Array.isArray(manifest.outputs) ? manifest.outputs : [])
        .map((entry) => entry && entry.path)
        .filter(Boolean),
      manifest_path: manifestPath,
    })
  }
  return { ok: true, run_root: runtime.runRoot, count: runs.length, runs }
}

const textOutput = {
  schema: { type: 'string' },
  render: (_args, value) => [{ type: 'text', text: String(value) }],
}

function buildToolList(packageRoot) {
  const runtime = createRuntime(packageRoot)

  const doctor = {
    name: 'h3_doctor',
    description: 'Read-only health check for the local MiniMax H3 / ComfyUI install: GPU, RAM, pagefile, disk, Python/Torch, models and custom nodes. Also reports Blackwell + quantized-DiT risk and the resolved ComfyUI path.',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    output: textOutput,
    timeoutMs: 180000,
    isConcurrencySafe: () => true,
    async execute() {
      const args = []
      if (runtime.comfyui) args.push('--comfyui', runtime.comfyui)
      args.push('--json')
      return runScript(runtime, 'h3_doctor.py', args, 180000)
    },
  }

  const status = {
    name: 'h3_status',
    description: 'Query and verify a queued/running/completed H3 job by ComfyUI prompt_id. Returns output paths, duration/frame/FPS/audio checks and dynamic-QA state.',
    parameters: {
      type: 'object',
      properties: {
        prompt_id: { type: 'string', description: 'ComfyUI prompt_id returned by h3_generate' },
        watch: { type: 'boolean', description: 'Poll until the prompt completes (default false)' },
        watch_interval: { type: 'number', description: 'Seconds between watch polls (default 20)' },
        watch_timeout: { type: 'number', description: 'Maximum watch time in seconds (default 3600)' },
        dynamic_check: { type: 'boolean', description: 'Run the first/middle/last frame smoke test (default true)' },
        dynamic_check_strict: { type: 'boolean', description: 'Treat an unavailable smoke test as a hard failure' },
        require_audio: { type: 'boolean', description: 'Require an audio stream (default true)' },
      },
      required: ['prompt_id'],
      additionalProperties: false,
    },
    output: textOutput,
    timeoutMs: 3700000,
    isConcurrencySafe: () => false,
    async execute(args = {}) {
      if (!args.prompt_id) throw new Error('prompt_id is required')
      const command = commonPathArgs(runtime)
      command.push('--prompt-id', String(args.prompt_id))
      if (args.require_audio !== false) command.push('--require-audio')
      if (args.dynamic_check !== false) command.push('--dynamic-check')
      if (args.dynamic_check_strict) command.push('--dynamic-check-strict')
      command.push('--compact', '--json')
      let timeout = 120000
      if (args.watch) {
        command.push('--watch')
        if (args.watch_interval != null) command.push('--watch-interval', String(args.watch_interval))
        const watchTimeout = args.watch_timeout != null ? Number(args.watch_timeout) : 3600
        command.push('--watch-timeout', String(watchTimeout))
        timeout = (watchTimeout + 60) * 1000
      }
      return runScript(runtime, 'h3_status.py', command, timeout)
    },
  }

  const generate = {
    name: 'h3_generate',
    description: 'Plan, preflight, submit and verify one MiniMax H3 video through h3_fastpath.py. Supports T2VA/I2VA/FL2VA/L2VA/Ref2VA, reference images/audio/video, Set C templates and video-VAE override. The ComfyUI root comes from H3LITE_COMFYUI or ~/.h3lite/config.json.',
    parameters: {
      type: 'object',
      properties: {
        prompt_text: { type: 'string', description: 'Finalized prompt text (alternative to prompt_file)' },
        prompt_file: { type: 'string', description: 'Path to a UTF-8 prompt .txt file' },
        mode: { type: 'string', enum: ['auto', 't2v', 'i2va', 'fl2va', 'l2va', 'ref2va'], description: 'Generation route (default auto)' },
        resolution: { type: 'string', description: 'WxH, 32-pixel aligned, e.g. 640x352 or 1344x768' },
        video_seconds: { type: 'number', description: 'Target duration in seconds (alternative to length)' },
        length: { type: 'integer', description: 'Target frame count, e.g. 124, 244, 362' },
        seed: { type: 'integer', description: 'RNG seed' },
        first_frame: { type: 'string', description: 'First-frame image (i2va/fl2va)' },
        last_frame: { type: 'string', description: 'Last-frame image (fl2va/l2va)' },
        ref_image: { type: 'array', items: { type: 'string' }, description: 'Reference identity images in <Picture N> order' },
        ref_audio: { type: 'array', items: { type: 'string' }, description: 'Voice-timbre reference audio (Ref2VA only, max 3)' },
        ref_video: { type: 'array', items: { type: 'string' }, description: 'Motion/camera reference video (Ref2VA only, max 3)' },
        workflow_template: { type: 'string', description: 'Template name, e.g. h3_c_speed640, h3_c_fl2va768, h3_c_ref2va768' },
        component_set: { type: 'string', description: 'Component set; Set C templates must use auto' },
        filename_prefix: { type: 'string', description: 'Output filename prefix' },
        video_vae: { type: 'string', description: 'Override the video VAE filename, e.g. minimax_h3_video_vae_fp16.safetensors' },
        watch_timeout: { type: 'number', description: 'Maximum watch time in seconds (default 3600)' },
        dry_run: { type: 'boolean', description: 'Plan and print the effective workflow without submitting' },
      },
      additionalProperties: false,
    },
    output: textOutput,
    timeoutMs: 3700000,
    isConcurrencySafe: () => false,
    async execute(args = {}) {
      if (!args.prompt_text && !args.prompt_file) throw new Error('provide prompt_text or prompt_file')
      const command = commonPathArgs(runtime)
      if (args.prompt_file) command.push('--prompt-file', String(args.prompt_file))
      else command.push('--prompt-text', String(args.prompt_text))
      if (args.mode && args.mode !== 'auto') command.push('--mode', String(args.mode))
      if (args.resolution) command.push('--resolution', String(args.resolution))
      if (args.video_seconds != null) command.push('--video-seconds', String(args.video_seconds))
      if (args.length != null) command.push('--length', String(args.length))
      if (args.seed != null) command.push('--seed', String(args.seed))
      if (args.first_frame) command.push('--first-frame', String(args.first_frame))
      if (args.last_frame) command.push('--last-frame', String(args.last_frame))
      for (const value of args.ref_image || []) command.push('--ref-image', String(value))
      for (const value of args.ref_audio || []) command.push('--ref-audio', String(value))
      for (const value of args.ref_video || []) command.push('--ref-video', String(value))
      if (args.workflow_template) command.push('--workflow-template', String(args.workflow_template))
      if (args.component_set) command.push('--component-set', String(args.component_set))
      if (args.filename_prefix) command.push('--filename-prefix', String(args.filename_prefix))
      if (args.video_vae) command.push('--video-vae', String(args.video_vae))
      if (args.watch_timeout != null) command.push('--watch-timeout', String(args.watch_timeout))
      if (args.dry_run) command.push('--dry-run')
      command.push('--json')
      const timeout = 3700000
      return runScript(runtime, 'h3_fastpath.py', command, timeout)
    },
  }

  const runs = {
    name: 'h3_list_runs',
    description: 'List recent H3Lite run manifests (newest first) with state, prompt_id, prefix, warnings and output paths. Cheap native scan; use it to recover global pipeline state before acting.',
    parameters: {
      type: 'object',
      properties: { limit: { type: 'integer', description: 'Maximum runs to return (default 40)' } },
      additionalProperties: false,
    },
    output: textOutput,
    timeoutMs: 60000,
    isConcurrencySafe: () => true,
    async execute(args = {}) {
      const result = listRuns(runtime, args.limit)
      if (!result.ok) throw new Error(result.error)
      return JSON.stringify(result, null, 2)
    },
  }

  return { runtime, tools: [doctor, status, generate, runs] }
}

export { buildToolList }
