"use strict";

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
