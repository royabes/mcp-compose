"""MCP Compose Studio — Visual workflow builder and orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .config import DEFAULT_GLOBAL_DIR, discover_workflows, find_project_workflows_dir
from .engine import resolve_waves
from .models import parse_workflow

PORT = 37790

app = FastAPI(title="MCP Compose Studio")


def _dirs() -> tuple[Path, Path | None]:
    return DEFAULT_GLOBAL_DIR, find_project_workflows_dir()


@app.get("/api/workflows")
async def api_list_workflows():
    global_dir, project_dir = _dirs()
    workflows = discover_workflows(global_dir=global_dir, project_dir=project_dir)
    result = []
    for name, path in sorted(workflows.items()):
        try:
            wf = parse_workflow(path)
            waves = resolve_waves(wf)
            source = "project" if project_dir and path.parent == project_dir else "global"
            result.append({
                "name": name,
                "description": wf.description,
                "step_count": len(wf.steps),
                "wave_count": len(waves),
                "source": source,
            })
        except Exception as e:
            result.append({
                "name": name,
                "description": f"Parse error: {e}",
                "step_count": 0,
                "wave_count": 0,
                "source": "error",
            })
    return result


@app.get("/api/workflows/{name}")
async def api_get_workflow(name: str):
    global_dir, project_dir = _dirs()
    workflows = discover_workflows(global_dir=global_dir, project_dir=project_dir)
    if name not in workflows:
        raise HTTPException(404, f"Workflow {name!r} not found")

    path = workflows[name]
    raw_toml = path.read_text()

    try:
        wf = parse_workflow(path)
        waves = resolve_waves(wf)
        source = "project" if project_dir and path.parent == project_dir else "global"

        steps = {}
        for step_name, step in wf.steps.items():
            wave_idx = next(
                i for i, wave in enumerate(waves) if step_name in wave
            )
            steps[step_name] = {
                "tool": step.tool,
                "args": step.args,
                "depends_on": step.depends_on,
                "wave": wave_idx,
            }

        return {
            "name": wf.name,
            "description": wf.description,
            "steps": steps,
            "waves": [list(wave) for wave in waves],
            "source": source,
            "toml": raw_toml,
            "valid": True,
            "path": str(path),
        }
    except Exception as e:
        return {
            "name": name,
            "description": "",
            "steps": {},
            "waves": [],
            "source": "error",
            "toml": raw_toml,
            "valid": False,
            "error": str(e),
            "path": str(path),
        }


@app.post("/api/workflows/validate")
async def api_validate(request: Request):
    body = await request.json()
    toml_content = body.get("toml", "")
    try:
        wf = parse_workflow(toml_content)
        waves = resolve_waves(wf)
        steps = {}
        for step_name, step in wf.steps.items():
            wave_idx = next(
                i for i, wave in enumerate(waves) if step_name in wave
            )
            steps[step_name] = {
                "tool": step.tool,
                "args": step.args,
                "depends_on": step.depends_on,
                "wave": wave_idx,
            }
        return {
            "valid": True,
            "name": wf.name,
            "description": wf.description,
            "steps": steps,
            "waves": [list(wave) for wave in waves],
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/api/workflows/{name}")
async def api_save_workflow(name: str, request: Request):
    body = await request.json()
    toml_content = body.get("toml", "")
    try:
        parse_workflow(toml_content)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow: {e}")

    global_dir, _ = _dirs()
    target = global_dir / f"{name}.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(toml_content)
    return {"saved": True, "path": str(target)}


@app.delete("/api/workflows/{name}")
async def api_delete_workflow(name: str):
    global_dir, project_dir = _dirs()
    workflows = discover_workflows(global_dir=global_dir, project_dir=project_dir)
    if name not in workflows:
        raise HTTPException(404, f"Workflow {name!r} not found")
    workflows[name].unlink()
    return {"deleted": True}


@app.get("/api/mcp-servers")
async def api_mcp_servers():
    """Discover MCP servers from Claude config."""
    config_path = Path.home() / ".claude.json"
    if not config_path.exists():
        return []
    try:
        config = json.loads(config_path.read_text())
        servers = config.get("mcpServers", {})
        return [{"name": name} for name in sorted(servers)]
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
async def index():
    return STUDIO_HTML


def serve(port: int = PORT):
    """Launch the studio server."""
    print(f"MCP Compose Studio running at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


# ---------------------------------------------------------------------------
# Embedded frontend
# ---------------------------------------------------------------------------

STUDIO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MCP Compose Studio</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--bg2:#161b22;--bg3:#1c2128;--bg4:#21262d;
  --border:#30363d;--border2:#3d444d;
  --text:#e6edf3;--text2:#8b949e;--text3:#6e7681;
  --blue:#58a6ff;--green:#3fb950;--purple:#d2a8ff;
  --orange:#f0883e;--red:#f85149;--cyan:#79c0ff;
  --blue-bg:rgba(88,166,255,.12);--green-bg:rgba(63,185,80,.12);
}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text);overflow:hidden}
.app{display:grid;grid-template-columns:240px 1fr;grid-template-rows:52px 1fr 260px;height:100vh}

/* Header */
.header{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid var(--border);background:var(--bg2)}
.header h1{font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px}
.header h1 .icon{width:20px;height:20px;background:var(--blue);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:11px;color:#fff;font-weight:700}
.header-actions{display:flex;gap:8px}
.btn{padding:5px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg3);color:var(--text);font-size:12px;cursor:pointer;display:flex;align-items:center;gap:6px;transition:border-color .15s}
.btn:hover{border-color:var(--border2)}
.btn-primary{background:var(--green);border-color:var(--green);color:#fff}
.btn-primary:hover{background:#2ea043;border-color:#2ea043}
.btn-danger{color:var(--red)}
.btn-danger:hover{border-color:var(--red)}
.btn-sim{color:var(--orange)}
.btn-sim:hover{border-color:var(--orange)}

/* Sidebar */
.sidebar{grid-row:2/4;border-right:1px solid var(--border);background:var(--bg2);overflow-y:auto;display:flex;flex-direction:column}
.sidebar-title{padding:12px 16px 8px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text3)}
.wf-list{flex:1;overflow-y:auto}
.wf-item{padding:8px 16px;cursor:pointer;border-left:3px solid transparent;transition:background .1s}
.wf-item:hover{background:var(--bg3)}
.wf-item.active{background:var(--bg3);border-left-color:var(--blue)}
.wf-item .wf-name{font-size:13px;font-weight:500}
.wf-item .wf-desc{font-size:11px;color:var(--text2);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wf-item .wf-meta{font-size:10px;color:var(--text3);margin-top:3px;display:flex;gap:8px}
.wf-item.error .wf-name{color:var(--red)}
.sidebar-servers{border-top:1px solid var(--border);padding-bottom:12px}
.server-chip{display:inline-block;padding:2px 8px;margin:2px 4px 2px 16px;border-radius:10px;font-size:10px;background:var(--bg4);color:var(--text2);border:1px solid var(--border)}

/* Canvas */
.canvas{position:relative;overflow:auto;background:var(--bg)}
.canvas-header{position:sticky;top:0;z-index:2;padding:12px 20px;background:var(--bg);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
.canvas-header h2{font-size:16px;font-weight:600}
.canvas-header .badge{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500}
.badge-wave{background:var(--blue-bg);color:var(--blue)}
.badge-step{background:var(--green-bg);color:var(--green)}
.badge-source{background:var(--bg4);color:var(--text2)}
.canvas-body{position:relative;min-height:200px}
.canvas-body svg{position:absolute;top:0;left:0;pointer-events:none}
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text3);font-size:14px;gap:8px;padding:40px}
.empty-state .hint{font-size:12px}

/* Nodes */
.node{position:absolute;width:190px;background:var(--bg3);border:2px solid var(--border);border-radius:8px;padding:10px 12px;cursor:pointer;transition:all .25s ease;user-select:none}
.node:hover{border-color:var(--border2);transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.3)}
.node .step-name{font-size:13px;font-weight:600;margin-bottom:4px}
.node .tool-server{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:500;margin-bottom:3px}
.node .tool-name{font-size:11px;color:var(--text2)}
.node .step-args{font-size:10px;color:var(--text3);margin-top:4px;max-height:28px;overflow:hidden;text-overflow:ellipsis}
.node.pending{opacity:.35}
.node.running{border-color:var(--blue);box-shadow:0 0 16px rgba(88,166,255,.25)}
.node.completed{border-color:var(--green);background:rgba(63,185,80,.06)}
.node.selected{border-color:var(--purple);box-shadow:0 0 0 1px var(--purple)}

/* Wave colors for server badges */
.wave-0 .tool-server{background:rgba(88,166,255,.15);color:var(--blue)}
.wave-1 .tool-server{background:rgba(63,185,80,.15);color:var(--green)}
.wave-2 .tool-server{background:rgba(210,168,255,.15);color:var(--purple)}
.wave-3 .tool-server{background:rgba(240,136,62,.15);color:var(--orange)}
.wave-4 .tool-server{background:rgba(248,81,73,.15);color:var(--red)}
.wave-5 .tool-server{background:rgba(121,192,255,.15);color:var(--cyan)}

/* Edge animation for simulation */
@keyframes dash{to{stroke-dashoffset:0}}
.edge-active{stroke:var(--blue)!important;stroke-width:2.5!important}
.edge-done{stroke:var(--green)!important}

/* Bottom panel */
.bottom{grid-column:2;display:grid;grid-template-columns:1fr 220px;border-top:1px solid var(--border);background:var(--bg2)}
.editor-wrap{position:relative;overflow:hidden;border-right:1px solid var(--border)}
.editor-label{position:absolute;top:8px;left:12px;font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;z-index:2;pointer-events:none}
.editor-container{position:absolute;top:28px;left:0;right:0;bottom:0;overflow:hidden}
.editor-highlight,.editor-textarea{font-family:"SF Mono",SFMono-Regular,Consolas,"Liberation Mono",Menlo,monospace;font-size:12px;line-height:1.6;padding:8px 12px;white-space:pre;overflow:auto;width:100%;height:100%;tab-size:4}
.editor-highlight{position:absolute;top:0;left:0;pointer-events:none;color:var(--text)}
.editor-textarea{position:relative;color:transparent;caret-color:var(--text);background:transparent;border:none;outline:none;resize:none;z-index:1}
.editor-textarea::selection{background:rgba(88,166,255,.25);color:transparent}
/* Syntax colors */
.hl-comment{color:var(--text3)}
.hl-section{color:var(--purple)}
.hl-key{color:var(--cyan)}
.hl-string{color:#a5d6ff}
.hl-template{color:var(--orange);font-weight:500}
.hl-number{color:var(--cyan)}
.hl-bool{color:var(--red)}

/* Status panel */
.status-panel{padding:16px;display:flex;flex-direction:column;gap:12px;overflow-y:auto}
.status-panel h3{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text3)}
.status-row{display:flex;justify-content:space-between;align-items:center;font-size:12px}
.status-row .label{color:var(--text2)}
.status-row .value{font-weight:500}
.status-valid{color:var(--green)}
.status-invalid{color:var(--red)}
.status-actions{display:flex;flex-direction:column;gap:6px;margin-top:auto}
.btn-full{width:100%;justify-content:center}
.dirty-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--orange);margin-left:6px}

/* Toast */
.toast-container{position:fixed;bottom:20px;right:20px;z-index:100;display:flex;flex-direction:column;gap:8px}
.toast{padding:8px 16px;border-radius:6px;font-size:12px;background:var(--bg3);border:1px solid var(--border);box-shadow:0 4px 12px rgba(0,0,0,.4);animation:toast-in .2s ease}
.toast-success{border-color:var(--green);color:var(--green)}
.toast-error{border-color:var(--red);color:var(--red)}
@keyframes toast-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* Scrollbar */
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg4);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--border)}

/* Wave label */
.wave-label{position:absolute;font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;font-weight:600}
</style>
</head>
<body>
<div class="app">
  <header class="header">
    <h1><span class="icon">MC</span> MCP Compose Studio</h1>
    <div class="header-actions">
      <button class="btn btn-sim" onclick="App.simulate()" id="btn-sim" disabled>Simulate</button>
      <button class="btn" onclick="App.create()">+ New</button>
    </div>
  </header>
  <aside class="sidebar">
    <div class="sidebar-title">Workflows</div>
    <div class="wf-list" id="wf-list"></div>
    <div class="sidebar-servers" id="servers-section" style="display:none">
      <div class="sidebar-title">MCP Servers</div>
      <div id="server-list"></div>
    </div>
  </aside>
  <main class="canvas" id="canvas">
    <div class="empty-state" id="empty-state">
      <div>Select a workflow or create a new one</div>
      <div class="hint">Workflows are defined as TOML files in ~/.claude/workflows/</div>
    </div>
  </main>
  <div class="bottom" id="bottom" style="display:none">
    <div class="editor-wrap">
      <div class="editor-label">TOML<span class="dirty-dot" id="dirty-dot" style="display:none"></span></div>
      <div class="editor-container">
        <pre class="editor-highlight" id="highlight"></pre>
        <textarea class="editor-textarea" id="toml-editor" spellcheck="false"></textarea>
      </div>
    </div>
    <div class="status-panel" id="status-panel"></div>
  </div>
</div>
<div class="toast-container" id="toasts"></div>

<script>
const WAVE_COLORS = ['#58a6ff','#3fb950','#d2a8ff','#f0883e','#f85149','#79c0ff'];
const NODE_W = 190, NODE_H = 76, H_GAP = 100, V_GAP = 24, PAD = 50;

const App = {
  workflows: [],
  servers: [],
  active: null,
  data: null,
  toml: '',
  dirty: false,
  simulating: false,
  selectedNode: null,

  async init() {
    await Promise.all([this.loadWorkflows(), this.loadServers()]);
    this.bindEditor();
  },

  async loadWorkflows() {
    try {
      this.workflows = await api('/api/workflows');
      this.renderSidebar();
    } catch (e) { toast('Failed to load workflows', 'error'); }
  },

  async loadServers() {
    try {
      this.servers = await api('/api/mcp-servers');
      this.renderServers();
    } catch (e) { /* optional */ }
  },

  async select(name) {
    if (this.dirty && !confirm('Unsaved changes. Discard?')) return;
    try {
      this.data = await api(`/api/workflows/${name}`);
      this.active = name;
      this.toml = this.data.toml;
      this.dirty = false;
      this.selectedNode = null;
      this.renderSidebar();
      this.renderCanvas();
      this.renderEditor();
      this.renderStatus();
      document.getElementById('bottom').style.display = 'grid';
      const emptyEl = document.getElementById('empty-state');
      if (emptyEl) emptyEl.style.display = 'none';
      document.getElementById('btn-sim').disabled = !this.data.valid;
    } catch (e) { toast(`Failed to load ${name}`, 'error'); }
  },

  async validate() {
    try {
      const res = await api('/api/workflows/validate', 'POST', { toml: this.toml });
      if (res.valid) {
        this.data = { ...this.data, ...res, toml: this.toml, valid: true };
        delete this.data.error;
        this.renderCanvas();
        this.renderStatus();
        document.getElementById('btn-sim').disabled = false;
        toast('Valid workflow', 'success');
      } else {
        this.data = { ...this.data, valid: false, error: res.error };
        this.renderStatus();
        document.getElementById('btn-sim').disabled = true;
        toast(res.error, 'error');
      }
    } catch (e) { toast('Validation failed', 'error'); }
  },

  async save() {
    if (!this.active) return;
    try {
      await api(`/api/workflows/${this.active}`, 'POST', { toml: this.toml });
      this.dirty = false;
      document.getElementById('dirty-dot').style.display = 'none';
      await this.loadWorkflows();
      toast('Saved', 'success');
    } catch (e) { toast(e.message || 'Save failed', 'error'); }
  },

  async create() {
    const name = prompt('Workflow name (lowercase, hyphens):');
    if (!name || !/^[a-z][a-z0-9-]*$/.test(name)) {
      if (name) toast('Invalid name. Use lowercase + hyphens.', 'error');
      return;
    }
    const scaffold = `name = "${name}"\ndescription = ""\n\n[steps.step1]\ntool = "server.tool_name"\n# args.key = "value"\n`;
    try {
      await api(`/api/workflows/${name}`, 'POST', { toml: scaffold });
      await this.loadWorkflows();
      await this.select(name);
      toast(`Created ${name}`, 'success');
    } catch (e) { toast(e.message || 'Create failed', 'error'); }
  },

  async remove() {
    if (!this.active || !confirm(`Delete "${this.active}"?`)) return;
    try {
      await api(`/api/workflows/${this.active}`, 'DELETE');
      this.active = null;
      this.data = null;
      this.dirty = false;
      document.getElementById('bottom').style.display = 'none';
      document.getElementById('empty-state').style.display = 'flex';
      document.getElementById('canvas').innerHTML =
        '<div class="empty-state" id="empty-state"><div>Select a workflow or create a new one</div><div class="hint">Workflows live in ~/.claude/workflows/</div></div>';
      await this.loadWorkflows();
      toast('Deleted', 'success');
    } catch (e) { toast('Delete failed', 'error'); }
  },

  async simulate() {
    if (!this.data || !this.data.valid || this.simulating) return;
    this.simulating = true;
    const waves = this.data.waves;
    const nodes = document.querySelectorAll('.node');
    const edges = document.querySelectorAll('.edge');

    // Reset all to pending
    nodes.forEach(n => { n.className = n.className.replace(/running|completed|pending/g, '').trim(); n.classList.add('pending'); });
    edges.forEach(e => { e.classList.remove('edge-active', 'edge-done'); });

    for (let wi = 0; wi < waves.length; wi++) {
      // Mark wave as running
      waves[wi].forEach(name => {
        const node = document.getElementById(`node-${name}`);
        if (node) { node.classList.remove('pending'); node.classList.add('running'); }
        // Activate incoming edges
        edges.forEach(e => { if (e.dataset.to === name) e.classList.add('edge-active'); });
      });
      await sleep(1200);

      // Mark wave as completed
      waves[wi].forEach(name => {
        const node = document.getElementById(`node-${name}`);
        if (node) { node.classList.remove('running'); node.classList.add('completed'); }
        edges.forEach(e => { if (e.dataset.to === name) { e.classList.remove('edge-active'); e.classList.add('edge-done'); }});
      });
      await sleep(300);
    }
    this.simulating = false;
  },

  bindEditor() {
    const ta = document.getElementById('toml-editor');
    const hl = document.getElementById('highlight');
    let debounce = null;

    ta.addEventListener('input', () => {
      this.toml = ta.value;
      this.dirty = true;
      document.getElementById('dirty-dot').style.display = 'inline-block';
      hl.innerHTML = highlightToml(ta.value);

      clearTimeout(debounce);
      debounce = setTimeout(() => this.validate(), 600);
    });
    ta.addEventListener('scroll', () => { hl.scrollTop = ta.scrollTop; hl.scrollLeft = ta.scrollLeft; });
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const start = ta.selectionStart;
        ta.value = ta.value.substring(0, start) + '    ' + ta.value.substring(ta.selectionEnd);
        ta.selectionStart = ta.selectionEnd = start + 4;
        ta.dispatchEvent(new Event('input'));
      }
      if (e.key === 's' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.save(); }
    });
  },

  renderSidebar() {
    const el = document.getElementById('wf-list');
    el.innerHTML = this.workflows.map(wf => `
      <div class="wf-item ${wf.name === this.active ? 'active' : ''} ${wf.source === 'error' ? 'error' : ''}"
           onclick="App.select('${wf.name}')">
        <div class="wf-name">${esc(wf.name)}</div>
        <div class="wf-desc">${esc(wf.description)}</div>
        <div class="wf-meta">
          <span>${wf.step_count} steps</span>
          <span>${wf.wave_count} waves</span>
          <span>${wf.source}</span>
        </div>
      </div>
    `).join('');
  },

  renderServers() {
    if (!this.servers.length) return;
    document.getElementById('servers-section').style.display = 'block';
    document.getElementById('server-list').innerHTML =
      this.servers.map(s => `<span class="server-chip">${esc(s.name)}</span>`).join('');
  },

  renderCanvas() {
    if (!this.data) return;
    const canvas = document.getElementById('canvas');

    if (!this.data.valid) {
      canvas.innerHTML = `
        <div class="canvas-header">
          <h2>${esc(this.data.name)}</h2>
          <span class="badge" style="background:rgba(248,81,73,.12);color:var(--red)">Invalid</span>
        </div>
        <div class="empty-state">
          <div style="color:var(--red)">${esc(this.data.error || 'Parse error')}</div>
          <div class="hint">Fix the TOML below to see the DAG</div>
        </div>`;
      return;
    }

    const { steps, waves, description, source } = this.data;
    const nodes = layoutNodes(steps, waves);
    const allNodes = Object.values(nodes);
    const maxX = allNodes.length ? Math.max(...allNodes.map(n => n.x + NODE_W)) + PAD : 400;
    const maxY = allNodes.length ? Math.max(...allNodes.map(n => n.y + NODE_H)) + PAD : 200;

    let html = `
      <div class="canvas-header">
        <h2>${esc(this.data.name)}</h2>
        ${description ? `<span style="color:var(--text2);font-size:13px">${esc(description)}</span>` : ''}
        <span class="badge badge-step">${Object.keys(steps).length} steps</span>
        <span class="badge badge-wave">${waves.length} waves</span>
        <span class="badge badge-source">${source}</span>
      </div>
      <div class="canvas-body" style="min-width:${maxX}px;min-height:${maxY}px">
        <svg width="${maxX}" height="${maxY}" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <marker id="arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 3 L 0 6 z" fill="#3d444d"/>
            </marker>
            <marker id="arrow-active" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 3 L 0 6 z" fill="#58a6ff"/>
            </marker>
            <marker id="arrow-done" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 3 L 0 6 z" fill="#3fb950"/>
            </marker>
          </defs>
          ${renderEdges(nodes, steps)}
        </svg>
        ${renderWaveLabels(waves, nodes)}
        ${renderNodes(nodes, steps)}
      </div>`;
    canvas.innerHTML = html;
  },

  renderEditor() {
    const ta = document.getElementById('toml-editor');
    const hl = document.getElementById('highlight');
    ta.value = this.toml;
    hl.innerHTML = highlightToml(this.toml);
    document.getElementById('dirty-dot').style.display = 'none';
  },

  renderStatus() {
    const panel = document.getElementById('status-panel');
    if (!this.data) { panel.innerHTML = ''; return; }
    const d = this.data;
    const validClass = d.valid ? 'status-valid' : 'status-invalid';
    const validText = d.valid ? 'Valid' : 'Invalid';

    panel.innerHTML = `
      <h3>Status</h3>
      <div class="status-row"><span class="label">Validation</span><span class="value ${validClass}">${validText}</span></div>
      <div class="status-row"><span class="label">Steps</span><span class="value">${d.valid ? Object.keys(d.steps).length : '-'}</span></div>
      <div class="status-row"><span class="label">Waves</span><span class="value">${d.valid ? d.waves.length : '-'}</span></div>
      <div class="status-row"><span class="label">Source</span><span class="value">${d.source || '-'}</span></div>
      ${d.error ? `<div style="font-size:11px;color:var(--red);margin-top:4px;word-break:break-word">${esc(d.error)}</div>` : ''}
      ${this.selectedNode ? this.renderNodeDetail() : ''}
      <div class="status-actions">
        <button class="btn btn-full" onclick="App.validate()">Validate</button>
        <button class="btn btn-primary btn-full" onclick="App.save()" ${!this.dirty ? 'disabled' : ''}>Save</button>
        <button class="btn btn-danger btn-full" onclick="App.remove()">Delete</button>
      </div>`;
  },

  renderNodeDetail() {
    if (!this.selectedNode || !this.data.steps[this.selectedNode]) return '';
    const step = this.data.steps[this.selectedNode];
    const args = Object.keys(step.args).length ?
      Object.entries(step.args).map(([k,v]) => `<div style="font-size:11px;color:var(--text2)">${esc(k)}: ${esc(JSON.stringify(v))}</div>`).join('') :
      '<div style="font-size:11px;color:var(--text3)">No arguments</div>';
    return `
      <h3 style="margin-top:8px">Selected Step</h3>
      <div class="status-row"><span class="label">Name</span><span class="value">${esc(this.selectedNode)}</span></div>
      <div class="status-row"><span class="label">Tool</span><span class="value" style="font-size:11px">${esc(step.tool)}</span></div>
      <div class="status-row"><span class="label">Wave</span><span class="value">${step.wave + 1}</span></div>
      <div class="status-row"><span class="label">Deps</span><span class="value">${step.depends_on.length ? step.depends_on.join(', ') : 'none'}</span></div>
      <div style="margin-top:4px">${args}</div>`;
  },

  selectNode(name) {
    this.selectedNode = this.selectedNode === name ? null : name;
    document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
    if (this.selectedNode) {
      const el = document.getElementById(`node-${name}`);
      if (el) el.classList.add('selected');
    }
    this.renderStatus();
  }
};

// --- Layout ---

function layoutNodes(steps, waves) {
  const nodes = {};
  if (!waves.length) return nodes;
  const maxPerWave = Math.max(...waves.map(w => w.length));
  const totalH = maxPerWave * (NODE_H + V_GAP) - V_GAP;

  waves.forEach((wave, wi) => {
    const waveH = wave.length * (NODE_H + V_GAP) - V_GAP;
    const offY = (totalH - waveH) / 2;
    wave.forEach((name, si) => {
      nodes[name] = {
        x: PAD + wi * (NODE_W + H_GAP),
        y: PAD + 28 + offY + si * (NODE_H + V_GAP),
        wave: steps[name] ? steps[name].wave : wi
      };
    });
  });
  return nodes;
}

function renderNodes(nodes, steps) {
  return Object.entries(nodes).map(([name, pos]) => {
    const step = steps[name] || {};
    const [server, ...toolParts] = (step.tool || '').split('.');
    const toolName = toolParts.join('.');
    const argCount = step.args ? Object.keys(step.args).length : 0;
    return `<div class="node wave-${pos.wave}" id="node-${name}"
                style="left:${pos.x}px;top:${pos.y}px;width:${NODE_W}px"
                onclick="App.selectNode('${name}')">
      <div class="step-name">${esc(name)}</div>
      <div class="tool-server">${esc(server)}</div>
      <div class="tool-name">${esc(toolName)}</div>
      ${argCount ? `<div class="step-args">${argCount} arg${argCount > 1 ? 's' : ''}</div>` : ''}
    </div>`;
  }).join('');
}

function renderEdges(nodes, steps) {
  let paths = '';
  for (const [name, step] of Object.entries(steps)) {
    for (const dep of (step.depends_on || [])) {
      const from = nodes[dep];
      const to = nodes[name];
      if (!from || !to) continue;
      const x1 = from.x + NODE_W;
      const y1 = from.y + NODE_H / 2;
      const x2 = to.x;
      const y2 = to.y + NODE_H / 2;
      const mx = (x1 + x2) / 2;
      paths += `<path class="edge" data-from="${dep}" data-to="${name}"
                  d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"
                  stroke="#3d444d" stroke-width="2" fill="none"
                  marker-end="url(#arrow)"/>`;
    }
  }
  return paths;
}

function renderWaveLabels(waves, nodes) {
  return waves.map((wave, wi) => {
    const firstNode = nodes[wave[0]];
    if (!firstNode) return '';
    const color = WAVE_COLORS[wi % WAVE_COLORS.length];
    return `<div class="wave-label" style="left:${firstNode.x}px;top:${PAD + 6}px;color:${color}">
      Wave ${wi + 1}</div>`;
  }).join('');
}

// --- Syntax highlighting ---

function highlightToml(text) {
  return text.split('\n').map(line => {
    let h = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Full-line: comments
    if (/^\s*#/.test(h)) return '<span class="hl-comment">' + h + '</span>';
    // Full-line: section headers
    if (/^\s*\[/.test(h)) return '<span class="hl-section">' + h + '</span>';

    // Strings with nested template highlighting
    h = h.replace(/"([^"\\]*(\\.[^"\\]*)*)"/g, (m) => {
      const inner = m.replace(/({{[^}]*}})/g, '</span><span class="hl-template">$1</span><span class="hl-string">');
      return '<span class="hl-string">' + inner + '</span>';
    });
    // Booleans
    h = h.replace(/\b(true|false)\b/g, '<span class="hl-bool">$1</span>');
    // Numbers after =
    h = h.replace(/(=\s*)(\d+)/g, '$1<span class="hl-number">$2</span>');
    // Keys before =
    h = h.replace(/^(\s*)([\w][\w.-]*)(\s*=)/m, '$1<span class="hl-key">$2</span>$3');
    return h;
  }).join('\n');
}

// --- Helpers ---

async function api(url, method = 'GET', body = null) {
  const opts = { method, headers: {} };
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
</script>
</body>
</html>"""
