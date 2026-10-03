"use strict";

/* ──────────────────────────────── swarm view ──────────────────────────────── */

async function fetchStatus() {
  try {
    const data = await api("/api/status");
    $("#system-status-text").textContent =
      `${String(data.provider || "mock").toUpperCase()} · ${data.base_branch} · ${data.active_worktrees_count} worktrees`;
    $("#status-badge").classList.toggle("is-remote", data.local_only === false);
    $("#status-badge").title = data.local_only === false
      ? "A remote provider is active — prompts leave this machine."
      : "Air-gapped: inference stays on this machine.";
    if (data.version) $("#brand-version").textContent = `v${data.version}`;
  } catch (err) {
    $("#system-status-text").textContent = "Offline";
  }
}

async function fetchEditors() {
  const container = $("#editors-container");
  try {
    const editors = await api("/api/editors");
    if (!editors.length) {
      container.innerHTML = "";
      container.appendChild(el("div", {
        class: "muted small",
        text: "No GUI editors detected in PATH. CLI fallback active.",
      }));
      return;
    }
    container.innerHTML = "";
    editors.forEach((editor) => {
      container.appendChild(el("div", { class: "editor-pill" }, [
        el("div", {}, [
          el("div", { style: "font-weight:700;font-size:0.9rem;", text: editor.name }),
          el("div", { class: "muted small", style: "font-family:var(--mono)", text: editor.version || "Detected" }),
        ]),
        el("span", { class: "tag tag-vscode", text: editor.editor_type }),
      ]));
    });
  } catch (err) {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "muted small", text: `Editor scan failed: ${err.message}` }));
  }
}

async function launchSwarm(dryRun) {
  const input = $("#goal-input");
  const goal = input.value.trim();
  if (!goal) {
    toast("Please enter a goal first.", "err");
    input.focus();
    return;
  }
  logTerminal(`[USER] Dispatching goal: "${goal}" (dry_run=${dryRun})`, "log-info");
  try {
    const data = await api("/api/execute", { method: "POST", body: { goal, dry_run: dryRun } });
    logTerminal(`[SWARM] Execution queued: ${data.message}`, "log-success");
    toast(dryRun ? "Dry-run simulation started." : "Swarm execution started.", "ok");
  } catch (err) {
    logTerminal(`[ERROR] Failed to start swarm: ${err.message}`, "log-err");
    toast(`Failed to start swarm: ${err.message}`, "err");
  }
}

function renderTasks(subtasks) {
  const container = $("#tasks-container");
  if (!Array.isArray(subtasks) || !subtasks.length) return;
  container.innerHTML = "";
  subtasks.forEach((task) => {
    container.appendChild(el("div", { class: "task-card" }, [
      el("div", { class: "task-header" }, [
        el("div", { class: "task-title", text: task.title || task.id }),
        el("span", { class: "tag tag-cursor", text: (task.status || "pending").toUpperCase() }),
      ]),
      el("p", { class: "muted", text: task.description || "" }),
      el("p", { class: "muted small", style: "margin-top:0.5rem;font-family:var(--mono)",
        text: `${task.target_editor || "editor"} · ${(task.file_scope || []).join(", ") || "all files"}` }),
    ]));
  });
}

function initSSE() {
  const source = new EventSource("/api/events");

  source.addEventListener("consensus:start", (event) => {
    const data = JSON.parse(event.data);
    logTerminal(`[CONSENSUS] Debate started for plan ${data.plan_id}`, "log-warn");
  });

  source.addEventListener("consensus:round_complete", (event) => {
    const data = JSON.parse(event.data);
    const score = Math.round((data.consensus_score || 0) * 100);
    logTerminal(`[CONSENSUS] Round ${data.round} verified | Score: ${score}%`, "log-success");
    const panel = $("#debate-panel");
    panel.innerHTML = "";
    panel.appendChild(el("div", { style: "font-weight:700;color:#a78bfa;margin-bottom:0.5rem;",
      text: `Round ${data.round} Consensus: ${score}%` }));
    panel.appendChild(el("div", { class: "muted small",
      text: `Peer models challenged edge cases, file scopes and contracts. Approved: ${data.approved}.` }));
  });

  source.addEventListener("orchestrator:execution_started", (event) => {
    const data = JSON.parse(event.data);
    logTerminal(`[SWARM] Executing plan ${data.plan_id} across ${data.tasks} worktrees`, "log-info");
  });

  source.addEventListener("orchestrator:execution_complete", (event) => {
    const data = JSON.parse(event.data);
    renderTasks(data.subtasks);
    logTerminal(`[SWARM] Finished: ${data.completed}/${data.total_tasks} tasks completed`, "log-success");
    fetchStatus();
  });

  source.addEventListener("dispatcher:launched", (event) => {
    const data = JSON.parse(event.data);
    logTerminal(`[DISPATCH] Editor ${data.editor} spawned for task ${data.task_id}`, "log-info");
  });

  source.addEventListener("tests:complete", (event) => {
    const data = JSON.parse(event.data);
    const duration = typeof data.duration === "number" ? data.duration.toFixed(2) : "?";
    logTerminal(`[TESTS] Task ${data.task_id} tests ${data.passed ? "PASSED" : "FAILED"} (${duration}s)`,
      data.passed ? "log-success" : "log-err");
  });

  source.addEventListener("merge:complete", (event) => {
    const data = JSON.parse(event.data);
    logTerminal(`[MERGE] Merged ${data.task_id} into ${data.target_branch || "base"}. Self-healed: ${data.self_healed}`, "log-success");
  });

  source.addEventListener("config:updated", (event) => {
    const data = JSON.parse(event.data);
    logTerminal(`[CONFIG] Configuration updated (${data.reason || "change"})`, "log-warn");
    fetchStatus();
  });

  source.addEventListener("orchestrator:error", (event) => {
    const data = JSON.parse(event.data);
    logTerminal(`[ERROR] ${data.error}`, "log-err");
  });

  source.onerror = () => logTerminal("[SYSTEM] Telemetry stream interrupted — retrying…", "log-warn");
}
