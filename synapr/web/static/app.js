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
  if (name === "github" && !state.githubLoaded) loadGithubIssues();
  if (name === "email" && !state.mailLoaded) loadMailMessages();
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

/* ────────────────────────── research & browser view ────────────────────────── */

let currentMarkdown = "";

async function executeSearch() {
  const query = $("#search-input").value.trim();
  if (!query) {
    toast("Please enter a search query.", "info");
    return;
  }
  const engine = $("#search-engine").value;
  const statusEl = $("#search-status-text");
  const container = $("#search-results-container");

  statusEl.textContent = `Searching ${engine}…`;
  container.innerHTML = `<div class="muted small">Querying web search engine for "${query}"…</div>`;

  try {
    const data = await api("/api/search", {
      method: "POST",
      body: { query, limit: 6, fetch_content: false },
    });

    const results = data.results || [];
    statusEl.textContent = `${results.length} results found`;
    container.innerHTML = "";

    if (!results.length) {
      container.innerHTML = '<div class="muted">No search results found. Try another query.</div>';
      return;
    }

    results.forEach((r, idx) => {
      const card = el("div", { class: "result-card" }, [
        el("div", { class: "result-title", text: `${idx + 1}. ${r.title}` }),
        el("div", { class: "result-url", text: r.url }),
        el("div", { class: "result-snippet", text: r.snippet || "No preview snippet available." }),
        el("div", { class: "result-actions" }, [
          el("button", {
            class: "btn btn-secondary btn-sm",
            text: "📄 Extract Markdown",
            onclick: () => fetchAndDisplayUrl(r.url),
          }),
          el("button", {
            class: "btn btn-ghost btn-sm",
            text: "🚀 Feed to Swarm",
            onclick: () => {
              $("#goal-input").value = `Implement feature using research on ${r.title}:\n${r.snippet || ""}\nSource: ${r.url}`;
              activateView("swarm");
              toast("Fed research into Swarm goal!", "ok");
            },
          }),
        ]),
      ]);
      container.appendChild(card);
    });
  } catch (err) {
    statusEl.textContent = "Search error";
    container.innerHTML = `<div class="notice notice-warn">Failed to execute web search: ${err.message}</div>`;
  }
}

async function fetchAndDisplayUrl(url) {
  if (!url) return;
  const readerCard = $("#article-reader-card");
  const readerTitle = $("#reader-title");
  const readerMeta = $("#reader-meta");
  const readerContent = $("#reader-content");

  readerCard.style.display = "block";
  readerTitle.textContent = "📄 Fetching webpage…";
  readerMeta.textContent = url;
  readerContent.textContent = "Extracting clean markdown text…";

  try {
    const data = await api("/api/fetch-url", {
      method: "POST",
      body: { url, max_chars: 12000 },
    });

    currentMarkdown = data.markdown || "";
    readerTitle.textContent = `📄 ${data.title || "Webpage Content"}`;
    readerMeta.textContent = `HTTP ${data.status_code} · ${currentMarkdown.length} chars · ${url}`;
    readerContent.textContent = currentMarkdown || "(No textual content extracted)";
    toast("Webpage extracted successfully.", "ok");
  } catch (err) {
    readerTitle.textContent = "✘ Extraction failed";
    readerContent.textContent = `Error: ${err.message}`;
    toast(`Extraction error: ${err.message}`, "err");
  }
}

async function probeLocalhostServer() {
  const url = $("#localhost-url").value.trim() || "http://localhost:3000";
  const box = $("#localhost-result-box");
  box.innerHTML = `<div class="muted small">Probing ${url}…</div>`;

  try {
    const data = await api("/api/browser/validate-localhost", {
      method: "POST",
      body: { url },
    });

    const isOk = data.is_healthy;
    const badgeCls = isOk ? "ok" : "err";
    const badgeText = isOk ? "HEALTHY" : "ERRORS DETECTED";

    box.innerHTML = "";
    const header = el("div", { class: "probe-header" }, [
      el("strong", { text: data.url }),
      el("span", { class: `probe-badge ${badgeCls}`, text: badgeText }),
    ]);

    const details = el("div", { class: "small muted" }, [
      el("div", { text: `Status Code: ${data.status_code} · Latency: ${data.latency_ms.toFixed(1)}ms` }),
      el("div", { text: `Page Title: ${data.title || "N/A"}` }),
    ]);

    box.appendChild(header);
    box.appendChild(details);

    if (data.errors_detected && data.errors_detected.length > 0) {
      const errorList = el("div", { class: "error-banner-list" });
      data.errors_detected.forEach((err) => {
        errorList.appendChild(el("div", { class: "error-item", text: `• ${err}` }));
      });
      box.appendChild(errorList);

      const fixBtn = el("button", {
        class: "btn btn-primary btn-sm mt",
        text: "🛠️ Auto-Fix Errors with Swarm",
        onclick: () => {
          $("#goal-input").value = `Fix runtime dev-server errors on ${data.url}:\n${data.errors_detected.join("\n")}`;
          activateView("swarm");
          toast("Dev-server errors transferred to Swarm goal!", "ok");
        },
      });
      box.appendChild(fixBtn);
    } else {
      box.appendChild(
        el("div", {
          class: "small text-muted mt",
          text: "✔ Clean runtime: No compilation or crash banners detected in server response.",
        })
      );
    }
  } catch (err) {
    box.innerHTML = `<div class="notice notice-warn">Failed to connect to ${url}: ${err.message}</div>`;
  }
}

/* ────────────────────────── github issues view ────────────────────────── */

state.githubIssues = [];
state.githubLoaded = false;
state.selectedIssue = null;

async function loadGithubIssues() {
  const stateFilter = $("#github-state-filter").value;
  const container = $("#github-issues-container");
  container.innerHTML = '<div class="muted small">Loading repository issues…</div>';

  try {
    const issues = await api(`/api/github/issues?state=${stateFilter}`);
    state.githubIssues = issues;
    state.githubLoaded = true;
    container.innerHTML = "";

    if (!issues.length) {
      container.innerHTML = '<div class="card"><p class="muted">No issues found for this repository state.</p></div>';
      return;
    }

    issues.forEach((iss) => {
      const card = el("div", {
        class: `issue-card${state.selectedIssue?.number === iss.number ? " is-selected" : ""}`,
        onclick: () => selectGithubIssue(iss),
      });

      const topRow = el("div", { class: "issue-meta-row" }, [
        el("div", { class: "issue-title", text: `#${iss.number} ${iss.title}` }),
        el("span", {
          class: `tag ${iss.state === "open" ? "tag-ok" : "tag-off"}`,
          text: iss.state.toUpperCase(),
        }),
      ]);

      const excerptText = iss.body ? iss.body.split("\n")[0].slice(0, 100) : "No description provided.";
      const excerpt = el("p", { class: "muted small", text: excerptText });

      const labelsRow = el("div", { class: "issue-labels" });
      (iss.labels || []).forEach((lbl) => {
        labelsRow.appendChild(el("span", { class: "issue-label", text: lbl }));
      });

      card.appendChild(topRow);
      card.appendChild(excerpt);
      if (iss.labels && iss.labels.length) card.appendChild(labelsRow);
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="notice notice-warn">Failed to load GitHub issues: ${err.message}</div>`;
  }
}

function selectGithubIssue(issue) {
  state.selectedIssue = issue;
  $$(".issue-card").forEach((c) => c.classList.remove("is-selected"));
  event?.currentTarget?.classList.add("is-selected");

  const panel = $("#github-detail-body");
  panel.innerHTML = "";

  const titleEl = el("h3", { text: `#${issue.number} ${issue.title}`, class: "section-title" });
  const metaEl = el("p", {
    class: "muted small",
    text: `Author: @${issue.author} · Created: ${issue.created_at || "N/A"}`,
  });

  const bodyBox = el("pre", {
    class: "reader-content mt",
    style: "max-height: 220px;",
    text: issue.body || "(No body provided)",
  });

  const actions = el("div", { class: "action-row mt" }, [
    el("button", {
      class: "btn btn-primary btn-sm",
      text: "🌿 Solve in Worktree",
      onclick: async () => {
        try {
          toast(`Provisioning worktree for Issue #${issue.number}…`, "info");
          const res = await api(`/api/github/issues/${issue.number}/solve`, { method: "POST" });
          toast(`Worktree provisioned at branch: ${res.branch}`, "ok");
          logTerminal(`[GITHUB] Provisioned isolated worktree: ${res.worktree_path} (${res.branch})`, "log-success");
        } catch (err) {
          toast(`Failed to solve issue: ${err.message}`, "err");
        }
      },
    }),
    el("button", {
      class: "btn btn-secondary btn-sm",
      text: "📦 Generate PR Draft",
      onclick: async () => {
        try {
          const pr = await api(`/api/github/issues/${issue.number}/pr`);
          bodyBox.textContent = `### PR Title: ${pr.title}\nBranch: ${pr.head_branch} -> ${pr.base_branch}\n\n${pr.body}`;
          toast("Generated pull request draft!", "ok");
        } catch (err) {
          toast(`Failed to generate PR draft: ${err.message}`, "err");
        }
      },
    }),
    el("button", {
      class: "btn btn-ghost btn-sm",
      text: "🚀 Launch in Swarm",
      onclick: () => {
        $("#goal-input").value = `Resolve GitHub Issue #${issue.number}: ${issue.title}\nRequirements: ${issue.body || ""}`;
        activateView("swarm");
        toast(`Transferred Issue #${issue.number} to Swarm goal!`, "ok");
      },
    }),
  ]);

  panel.appendChild(titleEl);
  panel.appendChild(metaEl);
  panel.appendChild(bodyBox);
  panel.appendChild(actions);
}

/* ────────────────────────── email hub view ────────────────────────── */

state.mailMessages = [];
state.mailLoaded = false;
state.selectedMessage = null;

async function loadMailMessages() {
  const folder = $("#mail-folder-select").value;
  const container = $("#mail-list-container");
  container.innerHTML = '<div class="muted small">Loading messages…</div>';

  try {
    const msgs = await api(`/api/mail/messages?folder=${folder}`);
    state.mailMessages = msgs;
    state.mailLoaded = true;
    container.innerHTML = "";

    if (!msgs.length) {
      container.innerHTML = '<div class="card"><p class="muted">No messages in this folder.</p></div>';
      return;
    }

    msgs.forEach((m) => {
      const card = el("div", {
        class: `mail-card${state.selectedMessage?.id === m.id ? " is-selected" : ""}`,
        onclick: () => selectMailMessage(m),
      });

      const topRow = el("div", { class: "mail-meta-row" }, [
        el("div", { class: "mail-subject", text: m.subject }),
        el("span", { class: "small muted", text: m.received_at ? m.received_at.slice(0, 10) : "" }),
      ]);

      const senderRow = el("div", { class: "muted small", text: `From: ${m.sender} <${m.sender_email}>` });
      const snippet = el("p", {
        class: "muted small mt",
        text: m.body ? m.body.slice(0, 95) + "…" : "",
      });

      card.appendChild(topRow);
      card.appendChild(senderRow);
      card.appendChild(snippet);
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="notice notice-warn">Failed to load mail messages: ${err.message}</div>`;
  }
}

function selectMailMessage(msg) {
  state.selectedMessage = msg;
  $$(".mail-card").forEach((c) => c.classList.remove("is-selected"));
  event?.currentTarget?.classList.add("is-selected");

  const panel = $("#mail-detail-body");
  panel.innerHTML = "";

  const subject = el("h3", { text: msg.subject, class: "section-title" });
  const from = el("p", { class: "muted small", text: `From: ${msg.sender} (${msg.sender_email}) · To: ${msg.recipient}` });
  const bodyText = el("pre", { class: "reader-content mt", style: "max-height: 180px;", text: msg.body });

  const triageContainer = el("div", { id: "mail-triage-container" });

  const actions = el("div", { class: "action-row mt" }, [
    el("button", {
      class: "btn btn-secondary btn-sm",
      text: "🧠 Run AI Triage",
      onclick: async () => {
        try {
          toast("Triaging message with local LLM…", "info");
          const t = await api(`/api/mail/messages/${msg.id}/triage`, { method: "POST" });
          renderMailTriage(triageContainer, t);
          toast("AI Triage complete!", "ok");
        } catch (err) {
          toast(`Triage failed: ${err.message}`, "err");
        }
      },
    }),
    el("button", {
      class: "btn btn-primary btn-sm",
      text: "✍️ Draft Safe Response",
      onclick: () => openDraftComposer(panel, msg),
    }),
  ]);

  panel.appendChild(subject);
  panel.appendChild(from);
  panel.appendChild(bodyText);
  panel.appendChild(triageContainer);
  panel.appendChild(actions);
}

function renderMailTriage(container, triage) {
  container.innerHTML = "";
  const urgencyCls = triage.urgency === "high" || triage.urgency === "critical" ? "urgent" : triage.urgency === "medium" ? "normal" : "low";

  const box = el("div", { class: "triage-box" }, [
    el("div", { class: "triage-header" }, [
      el("strong", { text: `Category: ${triage.category.toUpperCase()}` }),
      el("span", { class: `triage-badge triage-${urgencyCls}`, text: `URGENCY: ${triage.urgency}` }),
    ]),
    el("p", { class: "small", text: triage.executive_summary }),
    el("div", { class: "detail-section" }, [
      el("h4", { text: "Action Items" }),
      el("ul", { class: "action-item-list" }, (triage.action_items || []).map((item) => el("li", { text: item }))),
    ]),
  ]);
  container.appendChild(box);
}

function openDraftComposer(panel, msg) {
  const composer = el("div", { class: "card mt" }, [
    el("h4", { text: "Draft Context-Aware Technical Response", class: "section-title compact" }),
    el("p", { class: "muted small mb", text: "Add optional developer notes or technical constraints to include in the draft." }),
    el("textarea", {
      class: "textarea",
      id: "developer-notes-input",
      placeholder: "e.g. Advise that fix is deployed in branch feat/auth and will release in v0.2.0…",
    }),
    el("div", { class: "action-row mt" }, [
      el("button", {
        class: "btn btn-primary btn-sm",
        text: "⚡ Generate Draft",
        onclick: async () => {
          const notes = $("#developer-notes-input").value;
          try {
            toast("Generating response draft…", "info");
            const draft = await api(`/api/mail/messages/${msg.id}/draft`, {
              method: "POST",
              body: { developer_notes: notes },
            });
            renderDraftResult(composer, draft);
            toast("Technical draft created safely in Drafts folder!", "ok");
          } catch (err) {
            toast(`Failed to draft response: ${err.message}`, "err");
          }
        },
      }),
    ]),
  ]);
  panel.appendChild(composer);
}

function renderDraftResult(composer, draft) {
  composer.innerHTML = "";
  const header = el("div", { class: "triage-header" }, [
    el("strong", { text: `Draft Ready: [${draft.id}]` }),
    el("span", { class: "tag tag-vscode", text: "DRAFTS ONLY" }),
  ]);

  const bodyPre = el("pre", { class: "reader-content mt", style: "max-height: 180px;", text: draft.body });

  const safetyBanner = el("div", { class: "airgap-banner mt" }, [
    el("span", { class: "airgap-icon", text: "🔒" }),
    el("div", {
      text: "Safety Gate Active: Outbound transmission blocked. Check the draft before confirming dispatch.",
    }),
  ]);

  const actions = el("div", { class: "action-row mt" }, [
    el("button", {
      class: "btn btn-primary btn-sm",
      text: "✔ Authorize & Dispatch Email",
      onclick: async () => {
        if (!confirm(`Are you sure you want to dispatch this email to ${draft.recipient}?`)) return;
        try {
          const res = await api(`/api/mail/drafts/${draft.id}/send`, {
            method: "POST",
            body: { confirm: true },
          });
          toast(`Email safely dispatched to ${res.recipient}!`, "ok");
          composer.innerHTML = `<div class="notice notice-ok">Email successfully sent to ${res.recipient}.</div>`;
          loadMailMessages();
        } catch (err) {
          toast(`Dispatch failed: ${err.message}`, "err");
        }
      },
    }),
  ]);

  composer.appendChild(header);
  composer.appendChild(bodyPre);
  composer.appendChild(safetyBanner);
  composer.appendChild(actions);
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

  // Research view listeners
  $("#btn-search")?.addEventListener("click", executeSearch);
  $("#search-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") executeSearch();
  });
  $("#btn-fetch-url")?.addEventListener("click", () => fetchAndDisplayUrl($("#fetch-url-input").value.trim()));
  $("#btn-probe-localhost")?.addEventListener("click", probeLocalhostServer);
  $("#btn-probe-8000")?.addEventListener("click", () => {
    $("#localhost-url").value = "http://localhost:8000";
    probeLocalhostServer();
  });
  $("#btn-probe-5173")?.addEventListener("click", () => {
    $("#localhost-url").value = "http://localhost:5173";
    probeLocalhostServer();
  });
  $("#btn-close-reader")?.addEventListener("click", () => {
    $("#article-reader-card").style.display = "none";
  });
  $("#btn-copy-markdown")?.addEventListener("click", () => {
    navigator.clipboard.writeText(currentMarkdown);
    toast("Markdown copied to clipboard!", "ok");
  });
  $("#btn-feed-swarm")?.addEventListener("click", () => {
    $("#goal-input").value = currentMarkdown.slice(0, 500);
    activateView("swarm");
    toast("Markdown fed into Swarm goal!", "ok");
  });

  // GitHub view listeners
  $("#github-state-filter")?.addEventListener("change", loadGithubIssues);
  $("#btn-refresh-issues")?.addEventListener("click", loadGithubIssues);

  // Email view listeners
  $("#mail-folder-select")?.addEventListener("change", loadMailMessages);
  $("#btn-refresh-mail")?.addEventListener("click", loadMailMessages);

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
