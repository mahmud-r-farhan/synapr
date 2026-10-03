"use strict";

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
