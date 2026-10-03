"use strict";

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
