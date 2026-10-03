"""FastAPI application providing REST APIs and Server-Sent Events for the web dashboard."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from synapr import __version__
from synapr.core.events import Event, bus
from synapr.core.logger import logger
from synapr.orchestrator import SynaprOrchestrator

app = FastAPI(
    title="Synapr Swarm Orchestrator",
    version=__version__,
    description="Local Autonomous Multi-IDE AI Orchestration Gateway & Control Center",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator = SynaprOrchestrator()


class GoalRequest(BaseModel):
    goal: str
    context: str | None = None
    dry_run: bool = False
    launch_editors: bool = True


class WorktreeActionRequest(BaseModel):
    task_id: str | None = None
    force: bool = True
    delete_branch: bool = False


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Retrieve active system state, base branch, and orchestrator metrics."""
    base_branch = await orchestrator.worktree_mgr.detect_base_branch()
    worktrees = await orchestrator.worktree_mgr.list_worktrees()
    editors = orchestrator.get_installed_editors()
    return {
        "status": "online",
        "version": __version__,
        "repo_root": str(orchestrator.repo_root),
        "base_branch": base_branch,
        "active_worktrees_count": len(worktrees),
        "discovered_editors_count": len(editors),
        "active_plan": orchestrator.active_plan.model_dump() if orchestrator.active_plan else None,
        "provider": orchestrator.config.gateway.default_provider,
    }


@app.get("/api/editors")
async def list_editors() -> list[dict[str, Any]]:
    """List all detected and configured code editors."""
    return [e.model_dump() for e in orchestrator.get_installed_editors()]


@app.get("/api/worktrees")
async def list_worktrees() -> list[dict[str, Any]]:
    """Query git worktree allocations."""
    return await orchestrator.worktree_mgr.list_worktrees()


@app.post("/api/plan")
async def create_plan(req: GoalRequest) -> dict[str, Any]:
    """Decompose goal and run multi-LLM debate without launching editors."""
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    plan = await orchestrator.plan_goal(req.goal, req.context)
    return plan.model_dump()


@app.post("/api/execute")
async def execute_goal(req: GoalRequest, bg_tasks: BackgroundTasks) -> dict[str, Any]:
    """Execute end-to-end swarm loop."""
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")

    # Run in background to maintain responsive API
    async def _run() -> None:
        try:
            await orchestrator.run_goal(
                goal=req.goal,
                context=req.context,
                dry_run=req.dry_run,
                launch_editors=req.launch_editors,
            )
        except Exception as e:
            logger.error(f"Background swarm execution failed: {e}")
            bus.emit("orchestrator:error", {"error": str(e)})

    bg_tasks.add_task(_run)
    return {"message": "Swarm execution initiated in background", "goal": req.goal}


@app.post("/api/worktrees/clean")
async def cleanup_worktrees(req: WorktreeActionRequest) -> dict[str, Any]:
    """Clean specific or all stale worktrees."""
    if req.task_id:
        await orchestrator.worktree_mgr.cleanup_worktree(
            req.task_id, force=req.force, delete_branch=req.delete_branch
        )
        return {"status": "cleaned", "task_id": req.task_id}
    else:
        await orchestrator.worktree_mgr.prune_all()
        return {"status": "pruned_all"}


@app.get("/api/events")
async def stream_events(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for real-time dashboard telemetry."""
    async def event_generator() -> AsyncGenerator[str, None]:
        q: asyncio.Queue[Event] = asyncio.Queue()

        def _on_event(ev: Event) -> None:
            try:
                q.put_nowait(ev)
            except Exception:
                pass

        bus.subscribe("*", _on_event)
        try:
            # Yield initial connection event
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to Synapr SSE Stream'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"event: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
                except TimeoutError:
                    # Keep-alive heartbeat ping
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe("*", _on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> HTMLResponse:
    """Serve the single-page application dashboard."""
    html_content = DASHBOARD_HTML
    return HTMLResponse(content=html_content)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Synapr ⚡ Local Multi-IDE AI Swarm</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(19, 26, 42, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --primary: #8b5cf6;
      --primary-hover: #7c3aed;
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --glow-purple: rgba(139, 92, 246, 0.25);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: radial-gradient(circle at 15% 20%, #15102a 0%, #090d16 60%, #05070c 100%);
      color: var(--text-main);
      min-height: 100vh;
      overflow-x: hidden;
    }

    .navbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.25rem 2.5rem;
      border-bottom: 1px solid var(--card-border);
      backdrop-filter: blur(16px);
      background: rgba(9, 13, 22, 0.6);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 800;
      font-size: 1.4rem;
      letter-spacing: -0.5px;
    }

    .brand span {
      background: linear-gradient(135deg, #a78bfa, #38bdf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .badge-status {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: var(--accent-emerald);
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      font-size: 0.82rem;
      font-weight: 600;
    }

    .badge-pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 10px var(--accent-emerald);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    .container {
      max-width: 1400px;
      margin: 2rem auto;
      padding: 0 2rem;
    }

    .hero-panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 1.25rem;
      padding: 2.25rem;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 40px var(--glow-purple);
      margin-bottom: 2.5rem;
      backdrop-filter: blur(20px);
    }

    .hero-title {
      font-size: 1.85rem;
      font-weight: 800;
      margin-bottom: 0.5rem;
    }

    .hero-sub {
      color: var(--text-muted);
      margin-bottom: 1.75rem;
      font-size: 0.98rem;
    }

    .input-row {
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
    }

    .goal-input {
      flex: 1;
      min-width: 320px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 0.75rem;
      padding: 0.9rem 1.25rem;
      color: #fff;
      font-size: 1rem;
      outline: none;
      transition: all 0.2s;
    }

    .goal-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25);
    }

    .btn {
      padding: 0.9rem 1.75rem;
      border-radius: 0.75rem;
      font-weight: 700;
      font-size: 0.95rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      border: none;
      transition: all 0.2s;
    }

    .btn-primary {
      background: linear-gradient(135deg, var(--primary), #6366f1);
      color: #fff;
      box-shadow: 0 4px 15px rgba(139, 92, 246, 0.35);
    }

    .btn-primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(139, 92, 246, 0.5);
    }

    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
      border: 1px solid var(--card-border);
    }

    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.14);
    }

    .grid-2 {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 2rem;
    }

    @media (max-width: 1024px) {
      .grid-2 { grid-template-columns: 1fr; }
    }

    .section-title {
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 1rem;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      backdrop-filter: blur(16px);
    }

    .task-card {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 0.85rem;
      padding: 1.25rem;
      margin-bottom: 1rem;
      transition: all 0.2s;
    }

    .task-card:hover {
      border-color: rgba(139, 92, 246, 0.4);
      transform: translateX(4px);
    }

    .task-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }

    .task-title {
      font-weight: 700;
      font-size: 1.05rem;
    }

    .tag {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      border-radius: 0.4rem;
      font-weight: 600;
    }

    .tag-vscode { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .tag-cursor { background: rgba(167, 139, 250, 0.15); color: #a78bfa; border: 1px solid rgba(167, 139, 250, 0.3); }
    .tag-android { background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }

    .terminal-box {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      background: #05070d;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 0.85rem;
      padding: 1rem;
      height: 380px;
      overflow-y: auto;
      color: #94a3b8;
    }

    .terminal-line { margin-bottom: 0.4rem; }
    .log-info { color: #38bdf8; }
    .log-success { color: #34d399; }
    .log-warn { color: #fbbf24; }
    .log-err { color: #f87171; }

    .editor-pill {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 1rem;
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 0.75rem;
      margin-bottom: 0.6rem;
    }
  </style>
</head>
<body>
  <div class="navbar">
    <div class="brand">
      <span>⚡ Synapr Swarm OS</span>
      <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 500;">v0.1.0</span>
    </div>
    <div class="badge-status">
      <div class="badge-pulse"></div>
      <span id="system-status-text">Air-Gapped & Active</span>
    </div>
  </div>

  <div class="container">
    <div class="hero-panel">
      <div class="hero-title">Local Autonomous Multi-IDE Swarm</div>
      <div class="hero-sub">Enter a project goal. Synapr breaks it down, tests consensus via peer debate, provisions isolated Git worktrees, and launches your installed editors in parallel.</div>
      <div class="input-row">
        <input type="text" id="goal-input" class="goal-input" placeholder="e.g. Build an OAuth2 JWT authentication layer with Redis rate-limiting and unit tests">
        <button class="btn btn-primary" onclick="launchSwarm(false)">
          <span>🚀 Launch Swarm</span>
        </button>
        <button class="btn btn-secondary" onclick="launchSwarm(true)">
          <span>🔬 Dry-Run Simulation</span>
        </button>
      </div>
    </div>

    <div class="grid-2">
      <!-- Active Subtasks & Worktrees -->
      <div>
        <div class="section-title">🌿 Isolated Worktrees & Active Subtasks</div>
        <div id="tasks-container">
          <div class="task-card">
            <div class="task-header">
              <div class="task-title">Awaiting project goal...</div>
              <span class="tag tag-vscode">READY</span>
            </div>
            <p style="color: var(--text-muted); font-size: 0.9rem;">
              Provide a prompt above to trigger task decomposition and automatic worktree provisioning.
            </p>
          </div>
        </div>

        <div class="section-title" style="margin-top: 2rem;">🧠 Multi-LLM Consensus Debate</div>
        <div class="card" id="debate-panel">
          <p style="color: var(--text-muted); font-size: 0.9rem;">No active debate rounds yet. Start a goal to see peer models challenge architecture in real time.</p>
        </div>
      </div>

      <!-- Telemetry & Discovered IDEs -->
      <div>
        <div class="section-title">🖥️ Installed Host IDEs</div>
        <div class="card" id="editors-container" style="padding: 1rem;">
          <div style="color: var(--text-muted); font-size: 0.85rem;">Scanning host system...</div>
        </div>

        <div class="section-title">📡 Real-Time Swarm Telemetry</div>
        <div class="terminal-box" id="terminal-logs">
          <div class="terminal-line log-info">[SYNAPR] Initializing real-time telemetry bridge...</div>
          <div class="terminal-line log-success">[SYSTEM] Connected to local event bus. Zero external telemetry.</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('system-status-text').innerText = `${data.provider.toUpperCase()} | ${data.base_branch}`;
      } catch (e) {
        console.error(e);
      }
    }

    async function fetchEditors() {
      try {
        const res = await fetch('/api/editors');
        const editors = await res.json();
        const container = document.getElementById('editors-container');
        if (editors.length === 0) {
          container.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem;">No GUI editors detected in PATH. CLI fallback active.</div>';
          return;
        }
        container.innerHTML = editors.map(e => `
          <div class="editor-pill">
            <div>
              <div style="font-weight: 700; font-size: 0.92rem;">${e.name}</div>
              <div style="font-size: 0.75rem; color: #94a3b8; font-family: monospace;">${e.version || 'Detected'}</div>
            </div>
            <span class="tag tag-vscode">${e.editor_type}</span>
          </div>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function launchSwarm(dryRun) {
      const input = document.getElementById('goal-input');
      const goal = input.value.trim();
      if (!goal) {
        alert('Please enter a goal!');
        return;
      }
      logTerminal(`[USER] Dispatching goal: "${goal}" (dry_run=${dryRun})`, 'log-info');
      try {
        const res = await fetch('/api/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ goal: goal, dry_run: dryRun })
        });
        const data = await res.json();
        logTerminal(`[SWARM] Execution queued: ${data.message}`, 'log-success');
      } catch (e) {
        logTerminal(`[ERROR] Failed to start swarm: ${e}`, 'log-err');
      }
    }

    function logTerminal(text, cls = 'log-info') {
      const box = document.getElementById('terminal-logs');
      const line = document.createElement('div');
      line.className = `terminal-line ${cls}`;
      line.innerText = text;
      box.appendChild(line);
      box.scrollTop = box.scrollHeight;
    }

    // Connect Server-Sent Events
    function initSSE() {
      const es = new EventSource('/api/events');
      es.onmessage = (e) => {
        logTerminal(`[EVENT] ${e.data}`, 'log-info');
      };
      es.addEventListener('consensus:start', (e) => {
        const d = JSON.parse(e.data);
        logTerminal(`[CONSENSUS] Debate started for plan ${d.plan_id}`, 'log-warn');
      });
      es.addEventListener('consensus:round_complete', (e) => {
        const d = JSON.parse(e.data);
        logTerminal(`[CONSENSUS] Round ${d.round} verified | Score: ${(d.consensus_score * 100).toFixed(0)}%`, 'log-success');
        document.getElementById('debate-panel').innerHTML = `
          <div style="font-weight: 700; color: #a78bfa; margin-bottom: 0.5rem;">Round ${d.round} Consensus: ${(d.consensus_score * 100).toFixed(0)}%</div>
          <div style="color: #94a3b8; font-size: 0.85rem;">Peer models challenged edge cases, file scopes, and contracts. Approved: ${d.approved}.</div>
        `;
      });
      es.addEventListener('dispatcher:launched', (e) => {
        const d = JSON.parse(e.data);
        logTerminal(`[DISPATCH] Editor ${d.editor} spawned for task ${d.task_id}`, 'log-info');
      });
      es.addEventListener('tests:complete', (e) => {
        const d = JSON.parse(e.data);
        const st = d.passed ? 'PASSED' : 'FAILED';
        logTerminal(`[TESTS] Task ${d.task_id} tests ${st} (${d.duration.toFixed(2)}s)`, d.passed ? 'log-success' : 'log-err');
      });
      es.addEventListener('merge:complete', (e) => {
        const d = JSON.parse(e.data);
        logTerminal(`[MERGE] Merged ${d.task_id} back to master. Self-healed: ${d.self_healed}`, 'log-success');
      });
    }

    window.addEventListener('DOMContentLoaded', () => {
      fetchStatus();
      fetchEditors();
      initSSE();
    });
  </script>
</body>
</html>
"""
