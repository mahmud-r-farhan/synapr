"use strict";

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
