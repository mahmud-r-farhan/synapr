/*
 * Synapr dashboard — vanilla JS, zero external dependencies, 100% local.
 *
 * Views:
 *   • Swarm         – goal dispatch, worktrees, consensus debate, live telemetry (SSE)
 *   • Configuration – auto-generated form for every field declared in synapr/config.py
 *   • Environment   – declare SYNAPR_* variables at runtime, optionally persisted to .env
 */
"use strict";

const state = {
  schema: null,
  meta: null,
  pending: {},        // dotted path -> value staged for the next Apply/Save
  clearedSecrets: {},
  envVars: [],
  busy: false,
};

/* ──────────────────────────────── helpers ──────────────────────────────── */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

async function api(path, options = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...options };
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  const res = await fetch(path, init);
  const text = await res.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch (_) { payload = text; }
  if (!res.ok) {
    const detail = payload && payload.detail ? payload.detail : `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function toast(message, kind = "info", timeout = 4800) {
  const node = el("div", { class: `toast ${kind}`, text: message });
  $("#toast-stack").appendChild(node);
  setTimeout(() => {
    node.style.opacity = "0";
    setTimeout(() => node.remove(), 250);
  }, timeout);
}

function logTerminal(text, cls = "log-info") {
  const box = $("#terminal-logs");
  if (!box) return;
  const line = el("div", { class: `terminal-line ${cls}`, text });
  box.appendChild(line);
  while (box.childElementCount > 500) box.removeChild(box.firstElementChild);
  box.scrollTop = box.scrollHeight;
}

function setByPath(target, path, value) {
  const parts = path.split(".");
  let node = target;
  for (const part of parts.slice(0, -1)) {
    if (typeof node[part] !== "object" || node[part] === null) node[part] = {};
    node = node[part];
  }
  node[parts[parts.length - 1]] = value;
  return target;
}

/* ──────────────────────────────── tabs ──────────────────────────────── */

function activateView(name) {
  $$(".tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.view === name));
  $$(".view").forEach((view) => view.classList.toggle("is-active", view.id === `view-${name}`));
  if (name === "config" && !state.schema) loadConfig();
  if (name === "env" && state.envVars.length === 0) loadEnv();
}

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

/* ──────────────────────────────── configuration view ──────────────────────────────── */

function markDirty() {
  const dirty = Object.keys(state.pending).length > 0;
  $("#config-dirty").hidden = !dirty;
}

function stagedValue(field) {
  return Object.prototype.hasOwnProperty.call(state.pending, field.path)
    ? state.pending[field.path]
    : field.value;
}

function buildField(field) {
  const wrapper = el("div", { class: `field${field.widget === "keyvalue" || field.widget === "list" ? " is-wide" : ""}` });
  const label = el("div", { class: "field-label" }, [el("span", { text: field.label })]);
  if (field.env_locked) {
    label.appendChild(el("span", { class: "tag tag-env", text: `ENV ${field.env_locked_by}` }));
  } else if (field.env) {
    label.appendChild(el("span", { class: "field-env", text: field.env }));
  }
  wrapper.appendChild(label);

  const disabled = field.env_locked === true;
  let input;

  switch (field.widget) {
    case "boolean": {
      input = el("input", { type: "checkbox", disabled });
      input.checked = Boolean(stagedValue(field));
      input.addEventListener("change", () => {
        state.pending[field.path] = input.checked;
        markDirty();
      });
      wrapper.appendChild(el("label", { class: "switch toggle-row" }, [
        input, el("span", { text: input.checked ? "Enabled" : "Disabled" }),
      ]));
      input.addEventListener("change", () => {
        input.nextElementSibling.textContent = input.checked ? "Enabled" : "Disabled";
      });
      break;
    }
    case "select": {
      input = el("select", { class: "select", disabled });
      (field.options || []).forEach((option) => {
        const node = el("option", { value: option, text: option === "" ? "— auto —" : option });
        if (String(stagedValue(field) ?? "") === String(option)) node.selected = true;
        input.appendChild(node);
      });
      input.addEventListener("change", () => {
        state.pending[field.path] = input.value === "" && field.nullable ? null : input.value;
        markDirty();
      });
      wrapper.appendChild(input);
      break;
    }
    case "number": {
      const value = stagedValue(field);
      input = el("input", {
        class: "input", type: "number", disabled,
        step: Number.isInteger(value) && !String(field.path).includes("temperature") ? "1" : "any",
        placeholder: field.placeholder || "",
      });
      if (field.min !== undefined) input.min = field.min;
      if (field.max !== undefined) input.max = field.max;
      input.value = value === null || value === undefined ? "" : value;
      input.addEventListener("change", () => {
        if (input.value === "") {
          state.pending[field.path] = field.nullable ? null : field.value;
        } else {
          state.pending[field.path] = Number(input.value);
        }
        markDirty();
      });
      wrapper.appendChild(input);
      break;
    }
    case "password": {
      input = el("input", {
        class: "input", type: "password", disabled,
        placeholder: stagedValue(field) ? String(stagedValue(field)) : "not configured",
        autocomplete: "off",
      });
      input.addEventListener("input", () => {
        if (input.value === "") delete state.pending[field.path];
        else state.pending[field.path] = input.value;
        markDirty();
      });
      const clear = el("button", {
        class: "btn btn-ghost", type: "button", text: "Clear", disabled,
        onclick: () => {
          input.value = "";
          state.pending[field.path] = "";
          toast(`${field.label} will be cleared on save.`, "info");
          markDirty();
        },
      });
      wrapper.appendChild(el("div", { class: "input-row" }, [input, clear]));
      break;
    }
    case "list": {
      input = el("input", {
        class: "input", type: "text", disabled,
        placeholder: field.placeholder || "comma,separated,values",
      });
      input.value = (stagedValue(field) || []).join(", ");
      input.addEventListener("change", () => {
        state.pending[field.path] = input.value.split(",").map((item) => item.trim()).filter(Boolean);
        markDirty();
      });
      wrapper.appendChild(input);
      break;
    }
    case "keyvalue": {
      input = el("textarea", { class: "textarea", disabled, spellcheck: "false" });
      input.value = JSON.stringify(stagedValue(field) || {}, null, 2);
      input.addEventListener("change", () => {
        try {
          state.pending[field.path] = JSON.parse(input.value || "{}");
          input.style.borderColor = "";
          markDirty();
        } catch (err) {
          input.style.borderColor = "var(--accent-rose)";
          toast(`${field.label}: invalid JSON`, "err");
        }
      });
      wrapper.appendChild(input);
      break;
    }
    default: {
      const value = stagedValue(field);
      input = el("input", { class: "input", type: "text", disabled, placeholder: field.placeholder || "" });
      input.value = value === null || value === undefined ? "" : value;
      input.addEventListener("change", () => {
        state.pending[field.path] = input.value === "" && field.nullable ? null : input.value;
        markDirty();
      });
      wrapper.appendChild(input);
    }
  }

  if (field.help) wrapper.appendChild(el("div", { class: "field-help", text: field.help }));
  if (field.env_locked) {
    wrapper.appendChild(el("div", {
      class: "field-help",
      text: `Locked by environment variable ${field.env_locked_by}. Unset it in the Environment tab to edit here.`,
    }));
  }
  return wrapper;
}

function renderConfig() {
  const container = $("#config-sections");
  container.innerHTML = "";
  (state.schema.sections || []).forEach((section) => {
    const card = el("div", { class: "card" });
    card.appendChild(el("div", { class: "config-card-head" }, [
      el("span", { style: "font-size:1.2rem", text: section.icon || "⚙️" }),
      el("h3", { text: section.title || section.key }),
    ]));
    if (section.description) card.appendChild(el("div", { class: "config-card-desc", text: section.description }));
    const grid = el("div", { class: "field-grid" });
    (section.fields || []).forEach((field) => grid.appendChild(buildField(field)));
    card.appendChild(grid);
    container.appendChild(card);
  });

  const meta = state.meta || {};
  const source = meta.source_path || `${meta.target_path} (not created yet)`;
  const overrides = Object.keys(meta.env_overrides || {}).length;
  $("#config-source").textContent =
    `File: ${source} · ${overrides} value(s) provided by environment variables · provider: ${meta.provider}`;

  const errors = (meta.errors || []).join("\n");
  $("#config-errors").hidden = !errors;
  $("#config-errors").textContent = errors;

  const writable = meta.writes_allowed !== false;
  ["#btn-config-save", "#btn-config-apply", "#btn-config-reset"].forEach((sel) => {
    $(sel).disabled = !writable;
    $(sel).title = writable ? $(sel).title : "Disabled by ui.allow_config_writes = false";
  });
}

async function loadConfig() {
  try {
    const [schema, snapshot] = await Promise.all([api("/api/config/schema"), api("/api/config")]);
    state.schema = schema;
    state.meta = snapshot.meta;
    state.pending = {};
    markDirty();
    renderConfig();
  } catch (err) {
    toast(`Failed to load configuration: ${err.message}`, "err");
  }
}

function pendingPayload() {
  const payload = {};
  for (const [path, value] of Object.entries(state.pending)) setByPath(payload, path, value);
  return payload;
}

async function submitConfig(persist) {
  if (state.busy) return;
  const payload = pendingPayload();
  if (!Object.keys(payload).length) {
    toast("No changes to apply.", "info");
    return;
  }
  state.busy = true;
  try {
    const snapshot = await api("/api/config", { method: "PUT", body: { config: payload, persist } });
    state.meta = snapshot.meta;
    state.pending = {};
    markDirty();
    await loadConfig();
    await fetchStatus();
    toast(persist ? `Saved to ${snapshot.meta.target_path}` : "Applied to the running process.", "ok");
  } catch (err) {
    toast(`Update rejected: ${err.message}`, "err");
  } finally {
    state.busy = false;
  }
}

async function resetConfig() {
  if (!window.confirm("Restore built-in defaults? Environment variables stay applied.")) return;
  try {
    await api("/api/config/reset", { method: "POST" });
    await loadConfig();
    await fetchStatus();
    toast("Defaults restored (not yet written to disk).", "ok");
  } catch (err) {
    toast(`Reset failed: ${err.message}`, "err");
  }
}

async function reloadConfig() {
  try {
    await api("/api/config/reload", { method: "POST" });
    await loadConfig();
    await fetchStatus();
    toast("Configuration reloaded from disk.", "ok");
  } catch (err) {
    toast(`Reload failed: ${err.message}`, "err");
  }
}

async function testProvider() {
  const button = $("#btn-test-provider");
  button.disabled = true;
  button.textContent = "🩺 Testing…";
  try {
    const provider = state.pending["gateway.default_provider"] || (state.meta && state.meta.provider) || null;
    const result = await api("/api/config/test-provider", { method: "POST", body: { provider } });
    $("#provider-detail").textContent =
      `${result.provider}: ${result.detail}${result.latency_ms ? ` (${result.latency_ms} ms)` : ""}`;
    toast(`${result.provider}: ${result.ok ? "reachable" : "unreachable"}`, result.ok ? "ok" : "err");
  } catch (err) {
    toast(`Provider test failed: ${err.message}`, "err");
  } finally {
    button.disabled = false;
    button.textContent = "🩺 Test Connection";
  }
}

/* ──────────────────────────────── environment view ──────────────────────────────── */

function renderEnv() {
  const card = $("#env-table-card");
  card.innerHTML = "";
  const table = el("table", { class: "env-table" });
  table.appendChild(el("thead", {}, [
    el("tr", {}, [
      el("th", { text: "Variable" }),
      el("th", { text: "Maps to" }),
      el("th", { text: "State" }),
      el("th", { text: "Value" }),
    ]),
  ]));

  const body = el("tbody");
  state.envVars.forEach((variable) => {
    const input = el("input", {
      class: "input env-input", type: variable.secret ? "password" : "text",
      placeholder: variable.example || "value", autocomplete: "off",
    });
    const setButton = el("button", {
      class: "btn btn-secondary", type: "button", text: "Set",
      onclick: () => applyEnv({ [variable.name]: input.value }, []),
    });
    const unsetButton = el("button", {
      class: "btn btn-ghost", type: "button", text: "Unset",
      onclick: () => applyEnv({}, [variable.name, ...(variable.aliases || [])]),
    });

    body.appendChild(el("tr", {}, [
      el("td", {}, [
        el("div", { class: "env-name", text: variable.name }),
        variable.aliases && variable.aliases.length
          ? el("div", { class: "muted small", text: `alias: ${variable.aliases.join(", ")}` })
          : null,
        el("div", { class: "env-desc", text: variable.description || "" }),
      ]),
      el("td", {}, [el("code", { text: variable.path }), el("div", { class: "muted small", text: variable.kind })]),
      el("td", {}, [
        variable.is_set
          ? el("span", { class: "tag tag-ok", text: `SET via ${variable.set_via}` })
          : el("span", { class: "tag tag-off", text: "unset" }),
        el("div", { class: "muted small", style: "margin-top:0.35rem", text: `current: ${formatEffective(variable)}` }),
      ]),
      el("td", {}, [el("div", { class: "env-actions" }, [input, setButton, unsetButton])]),
    ]));
  });

  table.appendChild(body);
  card.appendChild(table);
}

function formatEffective(variable) {
  const value = variable.effective_value;
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

async function loadEnv() {
  try {
    const data = await api("/api/config/env");
    state.envVars = data.variables || [];
    state.meta = data.meta || state.meta;
    renderEnv();
  } catch (err) {
    toast(`Failed to load environment registry: ${err.message}`, "err");
  }
}

async function applyEnv(values, unset) {
  const persist = $("#env-persist").checked;
  const payload = { values: {}, unset: unset || [], persist };
  for (const [key, value] of Object.entries(values)) {
    if (value === "" || value === null || value === undefined) {
      toast(`Provide a value for ${key} first.`, "err");
      return;
    }
    payload.values[key] = value;
  }
  try {
    const data = await api("/api/config/env", { method: "POST", body: payload });
    state.envVars = data.variables || [];
    state.meta = data.meta || state.meta;
    state.schema = null;          // values changed → rebuild the config form lazily
    renderEnv();
    await fetchStatus();
    const action = Object.keys(payload.values).length ? "applied" : "removed";
    toast(`Environment ${action}${persist ? " and written to .env" : " for this process"}.`, "ok");
  } catch (err) {
    toast(`Environment update failed: ${err.message}`, "err");
  }
}

/* ──────────────────────────────── bootstrap ──────────────────────────────── */

window.addEventListener("DOMContentLoaded", () => {
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => activateView(tab.dataset.view)));

  $("#btn-launch").addEventListener("click", () => launchSwarm(false));
  $("#btn-dry-run").addEventListener("click", () => launchSwarm(true));
  $("#goal-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") launchSwarm(false);
  });

  $("#btn-config-save").addEventListener("click", () => submitConfig(true));
  $("#btn-config-apply").addEventListener("click", () => submitConfig(false));
  $("#btn-config-reset").addEventListener("click", resetConfig);
  $("#btn-config-reload").addEventListener("click", reloadConfig);
  $("#btn-test-provider").addEventListener("click", testProvider);

  fetchStatus();
  fetchEditors();
  initSSE();
  setInterval(fetchStatus, 15000);

  window.addEventListener("beforeunload", (event) => {
    if (Object.keys(state.pending).length) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
});
