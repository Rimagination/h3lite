#!/usr/bin/env node
/*
 * h3lite MCP server (dependency-free, stdio JSON-RPC 2.0).
 *
 * Thin, agent-facing wrapper over the existing h3lite Python CLIs. It does NOT
 * reimplement generation logic: every tool shells out to the same scripts the
 * skills already use (h3_fastpath / h3_generate / h3_status / h3_doctor) with
 * --json and returns the parsed result. h3_list_runs is served natively by
 * reading the run manifests, so an agent can see global pipeline state cheaply.
 *
 * Transport: newline-delimited JSON-RPC over stdin/stdout (MCP stdio).
 * No npm dependencies; Node builtins only.
 *
 * Configuration (env, all optional with sane fallbacks):
 *   H3LITE_PYTHON    python interpreter that runs the scripts
 *   H3LITE_COMFYUI   ComfyUI root (locates bundled ffmpeg/ffprobe, input/, output/)
 *   H3LITE_OUTPUT    ComfyUI output dir (default <comfyui>/output)
 *   H3LITE_RUN_ROOT  run-manifest root (default <comfyui>/user/h3lite_runs)
 *   H3LITE_BASE_URL  ComfyUI server URL (default http://127.0.0.1:8188)
 *   H3LITE_SCRIPTS   scripts dir (default <plugin>/skills/h3-generate/scripts)
 */
'use strict';

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const PLUGIN_ROOT = process.env.QODER_PLUGIN_ROOT || path.resolve(__dirname, '..');
const SCRIPTS_DIR = process.env.H3LITE_SCRIPTS || path.join(PLUGIN_ROOT, 'skills', 'h3-generate', 'scripts');

// Optional local config file supplies machine-specific paths when the host does
// not inject env values. Env vars always win over the file.
function loadConfigFile() {
  const p = process.env.H3LITE_CONFIG || path.join(__dirname, 'h3-mcp-config.json');
  try { return JSON.parse(fs.readFileSync(p, 'utf-8')) || {}; } catch (_) { return {}; }
}
const CFG = loadConfigFile();
function cfg(envKey, cfgKey, fallback) {
  if (process.env[envKey]) return process.env[envKey];
  if (CFG[cfgKey]) return CFG[cfgKey];
  return fallback;
}

const COMFYUI = cfg('H3LITE_COMFYUI', 'comfyui', '');
const OUTPUT_DIR = cfg('H3LITE_OUTPUT', 'output_dir', COMFYUI ? path.join(COMFYUI, 'output') : '');
const RUN_ROOT = cfg('H3LITE_RUN_ROOT', 'run_root', COMFYUI ? path.join(COMFYUI, 'user', 'h3lite_runs') : '');
const BASE_URL = cfg('H3LITE_BASE_URL', 'base_url', 'http://127.0.0.1:8188');

function resolvePython() {
  if (process.env.H3LITE_PYTHON) return process.env.H3LITE_PYTHON;
  if (COMFYUI) {
    const venvWin = path.join(COMFYUI, 'venv', 'Scripts', 'python.exe');
    const venvNix = path.join(COMFYUI, 'venv', 'bin', 'python');
    if (fs.existsSync(venvWin)) return venvWin;
    if (fs.existsSync(venvNix)) return venvNix;
  }
  return process.platform.startsWith('win') ? 'python' : 'python3';
}
const PYTHON = resolvePython();

// ---------------------------------------------------------------------------
// JSON-RPC / MCP plumbing
// ---------------------------------------------------------------------------
const PROTOCOL_VERSION = '2024-11-05';
const SERVER_INFO = { name: 'h3lite', version: '0.2.0' };

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}
function result(id, res) {
  send({ jsonrpc: '2.0', id, result: res });
}
function error(id, code, message, data) {
  send({ jsonrpc: '2.0', id, error: { code, message, data } });
}
function textContent(text, isError) {
  return { content: [{ type: 'text', text }], isError: !!isError };
}

// ---------------------------------------------------------------------------
// Tool: run a python CLI script and return its (JSON) stdout
// ---------------------------------------------------------------------------
function runScript(scriptName, args, timeoutMs) {
  return new Promise((resolve) => {
    const scriptPath = path.join(SCRIPTS_DIR, scriptName);
    if (!fs.existsSync(scriptPath)) {
      resolve({ ok: false, text: `script not found: ${scriptPath}`, code: 1 });
      return;
    }
    const child = spawn(PYTHON, [scriptPath, ...args], {
      cwd: path.join(SCRIPTS_DIR, '..'),
      env: Object.assign({}, process.env, { PYTHONIOENCODING: 'utf-8' }),
      windowsHide: true,
    });
    let stdout = '';
    let stderr = '';
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try { child.kill('SIGKILL'); } catch (_) {}
      resolve({ ok: false, text: `timeout after ${timeoutMs}ms\npartial stdout:\n${stdout}\nstderr:\n${stderr}`, code: 124 });
    }, timeoutMs);
    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    child.on('error', (err) => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      resolve({ ok: false, text: `spawn error: ${err.message}`, code: 1 });
    });
    child.on('close', (code) => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      const text = stdout.trim() || stderr.trim() || `(no output, exit ${code})`;
      resolve({ ok: code === 0, text, code });
    });
  });
}

// Extract the last balanced JSON object from mixed stdout (scripts may log lines).
function extractJson(text) {
  const trimmed = (text || '').trim();
  try { const v = JSON.parse(trimmed); if (v && typeof v === 'object') return v; } catch (_) {}
  let depth = 0, start = -1;
  for (let i = trimmed.length - 1; i >= 0; i--) {
    const c = trimmed[i];
    if (c === '}') { if (depth === 0) start = i; depth++; }
    else if (c === '{') { depth--; if (depth === 0 && start >= 0) {
      try { const v = JSON.parse(trimmed.slice(i, start + 1)); if (v && typeof v === 'object') return v; } catch (_) {}
      start = -1;
    } }
  }
  return null;
}

// ---------------------------------------------------------------------------
// h3_list_runs: native manifest scan (no python needed)
// ---------------------------------------------------------------------------
function listRuns(limit) {
  if (!RUN_ROOT || !fs.existsSync(RUN_ROOT)) {
    return { ok: false, error: `run-root not found: ${RUN_ROOT || '(unset H3LITE_RUN_ROOT/H3LITE_COMFYUI)'}` };
  }
  let dirs;
  try { dirs = fs.readdirSync(RUN_ROOT, { withFileTypes: true }).filter((d) => d.isDirectory()); }
  catch (e) { return { ok: false, error: `cannot read run-root: ${e.message}` }; }
  dirs.sort((a, b) => (a.name < b.name ? 1 : -1)); // newest first (timestamped names)
  const max = Math.max(1, limit || 40);
  const runs = [];
  for (const d of dirs) {
    if (runs.length >= max) break;
    const mp = path.join(RUN_ROOT, d.name, 'manifest.json');
    let m = null;
    // Skip non-run directories (prompts/, _hotpath/, _environment/, ...).
    try { m = JSON.parse(fs.readFileSync(mp, 'utf-8')); } catch (_) { continue; }
    if (!m || typeof m !== 'object') continue;
    const outputs = Array.isArray(m.outputs) ? m.outputs : [];
    runs.push({
      run_id: d.name,
      prompt_id: m.prompt_id || null,
      state: m.state || null,
      filename_prefix: m.filename_prefix || null,
      length: (m.effective_settings && m.effective_settings.length) || m.length || null,
      reference_mode: (m.effective_settings && m.effective_settings.reference_mode) || null,
      elapsed_seconds: m.elapsed_seconds || null,
      warnings: m.warnings || [],
      output_paths: outputs.map((o) => o && o.path).filter(Boolean),
      manifest_path: mp,
    });
  }
  return { ok: true, run_root: RUN_ROOT, count: runs.length, runs };
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------
const TOOLS = [
  {
    name: 'h3_status',
    description: 'Query and verify an H3 generation task by ComfyUI prompt_id. Returns state (queued/running/success/verification_failed/error), output paths, hard-check results (duration/frames/fps/audio) and dynamic-QA classification. An unavailable dynamic smoke test is advisory by default and does not fail an otherwise-valid render.',
    inputSchema: {
      type: 'object',
      properties: {
        prompt_id: { type: 'string', description: 'ComfyUI prompt_id (UUID) returned at submit time' },
        watch: { type: 'boolean', description: 'poll until the prompt completes (default false)' },
        watch_interval: { type: 'number', description: 'seconds between watch polls (default 20)' },
        watch_timeout: { type: 'number', description: 'max seconds for watch (default 3600)' },
        dynamic_check: { type: 'boolean', description: 'run first/middle/last frame smoke test (default true)' },
        dynamic_check_strict: { type: 'boolean', description: 'treat an unavailable smoke test as a hard failure (default false)' },
        require_audio: { type: 'boolean', description: 'fail when the MP4 has no audio stream (default true)' },
      },
      required: ['prompt_id'],
    },
  },
  {
    name: 'h3_generate',
    description: 'Submit an H3 generation job via the fastpath (plans, preflights, submits, optionally watches). Modes: t2va (text), i2va (first frame), fl2va (first+last frame), l2va (last frame), ref2va (reference images/audio). Returns prompt_id, run manifest path and verification status.',
    inputSchema: {
      type: 'object',
      properties: {
        prompt_text: { type: 'string', description: 'finalized prompt text (alternative to prompt_file)' },
        prompt_file: { type: 'string', description: 'path to a prompt .txt file' },
        mode: { type: 'string', enum: ['auto', 't2va', 'i2va', 'fl2va', 'l2va', 'ref2va'], description: 'generation mode (default auto-infer from frames)' },
        resolution: { type: 'string', description: 'WxH, 32-pixel aligned, e.g. 640x352, 768x1344, 1344x768' },
        video_seconds: { type: 'number', description: 'target duration in seconds (alternative to length)' },
        length: { type: 'integer', description: 'target frame count, e.g. 124 (~5s), 244 (~10s), 362 (~15s)' },
        seed: { type: 'integer', description: ' RNG seed for reproducibility' },
        first_frame: { type: 'string', description: 'path to first-frame image (i2va/fl2va)' },
        last_frame: { type: 'string', description: 'path to last-frame image (fl2va/l2va)' },
        ref_image: { type: 'array', items: { type: 'string' }, description: 'reference identity images in <Picture N> order (ref2va)' },
        ref_audio: { type: 'array', items: { type: 'string' }, description: 'reference voice audio in <Audio N> order (ref2va only)' },
        ref_video: { type: 'array', items: { type: 'string' }, description: 'motion/camera reference video in <Video N> order (ref2va only)' },
        workflow_template: { type: 'string', description: 'template name, e.g. h3_c_speed640, h3_c_fl2va768, h3_c_ref2va768' },
        component_set: { type: 'string', description: 'component set; Set C templates must use "auto"' },
        filename_prefix: { type: 'string', description: 'output filename prefix, e.g. ep02/u19_' },
        video_vae: { type: 'string', description: 'override the video VAE filename, e.g. minimax_h3_video_vae_fp16.safetensors' },
        watch_timeout: { type: 'number', description: 'max seconds for the end-to-end watch (default 3600)' },
      },
    },
  },
  {
    name: 'h3_doctor',
    description: 'Environment health check for the local MiniMax H3 / ComfyUI install: ComfyUI reachability, bundled ffmpeg/ffprobe, models, VRAM and page-file. Run before diagnosing slow or failing generations.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'h3_list_runs',
    description: 'List recent h3lite run manifests (newest first) with state, prompt_id, filename_prefix, warnings and output paths. Native scan, cheap; use it to get global pipeline state before acting.',
    inputSchema: {
      type: 'object',
      properties: { limit: { type: 'integer', description: 'max runs to return (default 40)' } },
    },
  },
];

// ---------------------------------------------------------------------------
// Tool dispatch
// ---------------------------------------------------------------------------
function commonPathArgs() {
  const a = ['--base-url', BASE_URL];
  if (COMFYUI) a.push('--comfyui', COMFYUI);
  if (OUTPUT_DIR) a.push('--output-dir', OUTPUT_DIR);
  if (RUN_ROOT) a.push('--run-root', RUN_ROOT);
  return a;
}

async function callTool(name, args) {
  args = args || {};
  if (name === 'h3_list_runs') {
    const r = listRuns(args.limit);
    return textContent(JSON.stringify(r, null, 2), !r.ok);
  }

  if (name === 'h3_status') {
    if (!args.prompt_id) return textContent('error: prompt_id is required', true);
    const a = commonPathArgs();
    a.push('--prompt-id', String(args.prompt_id));
    if (args.require_audio !== false) a.push('--require-audio');
    if (args.dynamic_check !== false) a.push('--dynamic-check');
    if (args.dynamic_check_strict) a.push('--dynamic-check-strict');
    a.push('--compact', '--json');
    let timeout = 120000;
    if (args.watch) {
      a.push('--watch');
      if (args.watch_interval != null) a.push('--watch-interval', String(args.watch_interval));
      const wt = args.watch_timeout != null ? Number(args.watch_timeout) : 3600;
      a.push('--watch-timeout', String(wt));
      timeout = (wt + 60) * 1000;
    }
    const r = await runScript('h3_status.py', a, timeout);
    return textContent(r.text, !r.ok);
  }

  if (name === 'h3_doctor') {
    const a = [];
    if (COMFYUI) a.push('--comfyui', COMFYUI);
    a.push('--json');
    const r = await runScript('h3_doctor.py', a, 180000);
    return textContent(r.text, !r.ok);
  }

  if (name === 'h3_generate') {
    if (!args.prompt_text && !args.prompt_file) {
      return textContent('error: provide prompt_text or prompt_file', true);
    }
    const a = commonPathArgs();
    if (args.prompt_file) a.push('--prompt-file', String(args.prompt_file));
    else a.push('--prompt-text', String(args.prompt_text));
    if (args.mode && args.mode !== 'auto') a.push('--mode', String(args.mode));
    if (args.resolution) a.push('--resolution', String(args.resolution));
    if (args.video_seconds != null) a.push('--video-seconds', String(args.video_seconds));
    if (args.length != null) a.push('--length', String(args.length));
    if (args.seed != null) a.push('--seed', String(args.seed));
    if (args.first_frame) a.push('--first-frame', String(args.first_frame));
    if (args.last_frame) a.push('--last-frame', String(args.last_frame));
    for (const r of args.ref_image || []) a.push('--ref-image', String(r));
    for (const r of args.ref_audio || []) a.push('--ref-audio', String(r));
    for (const r of args.ref_video || []) a.push('--ref-video', String(r));
    if (args.workflow_template) a.push('--workflow-template', String(args.workflow_template));
    if (args.component_set) a.push('--component-set', String(args.component_set));
    if (args.filename_prefix) a.push('--filename-prefix', String(args.filename_prefix));
    if (args.video_vae) a.push('--video-vae', String(args.video_vae));
    if (args.watch_timeout != null) a.push('--watch-timeout', String(args.watch_timeout));
    a.push('--json');
    // The fastpath submits and watches end-to-end.
    const timeout = 3700000;
    const r = await runScript('h3_fastpath.py', a, timeout);
    return textContent(r.text, !r.ok);
  }

  return textContent(`error: unknown tool "${name}"`, true);
}

// ---------------------------------------------------------------------------
// stdio loop
// ---------------------------------------------------------------------------
const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', async (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  let msg;
  try { msg = JSON.parse(trimmed); } catch (_) { return; }
  const { id, method, params } = msg;

  if (method === 'initialize') {
    result(id, {
      protocolVersion: (params && params.protocolVersion) || PROTOCOL_VERSION,
      capabilities: { tools: {} },
      serverInfo: SERVER_INFO,
    });
    return;
  }
  if (method === 'notifications/initialized' || method === 'initialized') return;
  if (method === 'ping') { result(id, {}); return; }
  if (method === 'tools/list') { result(id, { tools: TOOLS }); return; }
  if (method === 'tools/call') {
    const toolName = params && params.name;
    const toolArgs = (params && params.arguments) || {};
    try {
      const res = await callTool(toolName, toolArgs);
      result(id, res);
    } catch (e) {
      result(id, textContent(`error: ${e && e.message ? e.message : String(e)}`, true));
    }
    return;
  }
  if (id !== undefined && id !== null) error(id, -32601, `method not found: ${method}`);
});
rl.on('close', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));
