"use strict";

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
