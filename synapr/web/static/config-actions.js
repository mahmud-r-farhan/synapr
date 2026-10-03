"use strict";


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
