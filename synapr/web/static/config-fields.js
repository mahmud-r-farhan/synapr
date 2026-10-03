"use strict";

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
