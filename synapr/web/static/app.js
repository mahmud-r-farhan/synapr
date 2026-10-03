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
