# `FUTURE_EXPANSIONS.md`

This document outlines the architectural roadmap and system design for extending **Synapr** beyond terminal and IDE orchestration. These forward-looking capabilities expand Synapr into a multi-device, autonomous development operator with peripheral access, teleoperation, and external communication channels.

---

## 1. Remote Teleoperation via Mobile Device

A low-latency companion interface allowing developers to monitor worktrees, review test outputs, approve destructive operations, and dispatch parallel tasks while away from their primary workstation.

### Architecture Overview

```
 ┌──────────────────────────┐             Tailscale / WireGuard (P2P Encrypted Mesh)
 │       Mobile App         │ ◄────────────────────────────────────────────────────────┐
 │ (React Native / Flutter)     │                                                          │
 └────────────┬─────────────┘                                                          │
              │                                                                        ▼
              │ WebSocket (Live Stream & Terminal I/O)                     ┌─────────────────────────┐
              │ HTTPS (Task Dispatch & Approval Gates)                     │     Synapr Gateway      │
              └──────────────────────────────────────────────────────────► │  (FastAPI / Rust Axum)  │
                                                                           └───────────┬─────────────┘
                                                                                       │ IPC / Subprocess
                                                                                       ▼
                                                                           ┌─────────────────────────┐
                                                                           │  Local Host Worktrees   │
                                                                           │  (IDE & Agent Clusters) │
                                                                           └─────────────────────────┘

```

### Core Specifications

* **Transport & Security:**
* **Peer-to-Peer Encryption:** Uses Tailscale or WireGuard mesh networking. No public IP exposure or open inbound router ports required.
* **WebRTC Data Channel:** Real-time bi-directional streaming for terminal outputs and lightweight IDE viewport snapshots.


* **Capabilities:**
* **Human-in-the-Loop Gates:** Push alerts for approval before executing critical Git rebases, dependency installations, or remote pushes.
* **Remote Task Dispatch:** Queue complex subtasks and branch allocations using text or voice from the mobile interface.



---

## 2. Hands-Free Voice Control System

An offline-first, low-latency audio processing loop to drive development commands, query progress, and confirm code merges through natural speech.

### Processing Pipeline

```
[Microphone In] ──► [Silero VAD] ──► [Whisper.cpp (STT)] ──► [Local SLM Intent Parser] ──► [Synapr CLI Action] ──► [Piper TTS Audio Out]

```

### Core Components

* **Wake-Word Detection:** Lightweight `openWakeWord` daemon tuned to trigger phrases like `"Hey Synapr"`. Sub-100MB RAM footprint, runs fully on host CPU.
* **Local STT & Intent Extraction:** Transcribes speech locally via quantized `whisper.cpp` (`base.en` or `small.en`) in under 200ms. An SLM (such as Qwen 2.5 3B or Llama 3.2 3B via Ollama) maps natural language directly into structured CLI flags:
* *"Synapr, create a new branch in VS Code and implement Stripe webhook validation."*
* $\rightarrow$ `synapr run --ide vscode --branch feat/stripe-webhook --prompt "Implement Stripe webhook validation"`


* **Auditory Status Feedback:** Natural voice synthesis through **Piper TTS** or **Kokoro** to announce milestone completion, broken builds, or merge conflicts.

---

## 3. Autonomous Browser Automation & Live Web Research Engine `[STATUS: IMPLEMENTED]`

A programmatic browser bridge and live search engine providing zero-API-key web navigation, dev-server verification, and documentation research capabilities to running agents and LLMs.

### Implementation Details
* **Zero-API-Key Search Engine:** DuckDuckGo HTML Lite scraping + Instant Answer API fallback (`search_duckduckgo`) and local/remote SearXNG support (`search_searxng`).
* **Web Content Extraction:** Clean HTML parsing stripping script/style/svg, producing structured markdown text for prompt injection (`fetch_webpage`).
* **Localhost Validation:** Probes local development servers (`http://localhost:3000`, `:8000`, `:5173`), computes latency, extracts titles, and scans for runtime crash/compilation error signatures (`validate_localhost`).
* **CLI Commands:**
  * `synapr search <query>`: live web research.
  * `synapr fetch <url>`: extract clean markdown from online documentation.
  * `synapr test-url <url>`: probe and validate local dev server health.
* **REST Endpoints:** `/api/search`, `/api/fetch-url`, `/api/browser/validate-localhost`.
* **Dashboard Interface:** Dedicated **🌐 Research & Browser** tab with interactive query execution, reader drawer, and 1-click dev-server error auto-fix in Swarm.

---

## 4. Intelligent Email Processing & Safe Draft Generation `[STATUS: IMPLEMENTED]`

A privacy-focused communication gateway that triages customer bug reports and client requirements from incoming emails, extracts structured tasks, and prepares context-aware technical drafts.

### Implementation Details
* **Local Storage & IMAP Bridges:** Local JSON storage (`.synapr/mail/`) with incoming mailbox management and IMAP connector capabilities.
* **AI-Powered Email Triage:** Classifies urgency (`critical`, `high`, `medium`, `low`), categorizes (`bug_report`, `feature_request`, `task_brief`), generates executive summaries, and extracts actionable development tasks (`EmailGatewayService.triage_message`).
* **Context-Aware Technical Drafts:** Ingests active Git branches, provider summaries, and developer notes to prepare professional client responses (`generate_draft`).
* **Mandatory Safety Dispatch Gate:** Responses are saved strictly to the `Drafts` directory. Outbound dispatch is locked and raises a `RuntimeError` unless `confirm=True` (or `--confirm` in CLI) is explicitly authorized by the developer (`send_draft`).
* **CLI Commands:**
  * `synapr mail list [--folder inbox|drafts|sent]`
  * `synapr mail triage <message_id>`
  * `synapr mail draft <message_id> [--notes "..."]`
  * `synapr mail send <draft_id> [--confirm]`
* **REST Endpoints:** `/api/mail/messages`, `/api/mail/messages/{id}/triage`, `/api/mail/messages/{id}/draft`, `/api/mail/drafts`, `/api/mail/drafts/{id}/send`.
* **Dashboard Interface:** Dedicated **✉️ Email Hub** tab with triage classification badges, draft composer, and safety dispatch confirmation gate.

---

## 5. GitHub Repository & Issue Lifecycle Tracker `[STATUS: IMPLEMENTED]`

A native integration to map remote GitHub issues directly into autonomous local development loops without leaving the IDE workspace.

### Implementation Details
* **Bi-directional Issue Sync:** Connects via `gh` CLI or GitHub REST API with offline caching and automatic repository detection from git remotes (`GitHubClient`, `detect_repository`).
* **Issue-to-Worktree Autonomous Provisioning:** Automatically clones issue context, provisions dedicated isolated worktree `.worktrees/issue-<number>`, checks out feature branch `synapr/issue-<number>`, launches the target IDE, and seeds `AGENT_INSTRUCTIONS.md` with issue description, objectives, and test requirements (`solve_issue_in_worktree`).
* **Automated PR Description Generator:** Generates structured pull request drafts with issue closing references (`Closes #<number>`), change summaries, and verification checklists (`prepare_pr_for_issue`).
* **CLI Commands:**
  * `synapr issue list [--state open|closed|all]`
  * `synapr issue solve <number> [--editor vscode|cursor|...]`
  * `synapr issue pr <number>`
* **REST Endpoints:** `/api/github/issues`, `/api/github/issues/{number}`, `/api/github/issues/{number}/solve`, `/api/github/issues/{number}/pr`.
* **Dashboard Interface:** Dedicated **🐙 GitHub Issues** tab with real-time issue browsing, 1-click worktree provisioning, PR preview, and transfer to Swarm.

---

## 6. Implementation Milestones

| Milestone | Target Deliverable | Core Libraries & Tooling | Status |
| --- | --- | --- | --- |
| **Phase 1** | Local Voice Controller & Intent Parser | `openwakeword`, `faster-whisper`, `piper-tts` | Planned |
| **Phase 2** | GitHub Issue Sync & PR Automator | `gh` CLI bridge, REST API, Worktree Manager | **Completed (v0.2.0)** |
| **Phase 3** | Live Web Research & Dev-Server Validator | DuckDuckGo HTML parser, SearXNG, Loopback Inspector | **Completed (v0.2.0)** |
| **Phase 4** | Email Triage & Safe Draft Assistant | Local Mailbox, AI Triage, Safety Lock Dispatch | **Completed (v0.2.0)** |
| **Phase 5** | Encrypted Mobile Gateway & Companion App | `FastAPI`, `WebSockets`, `Tailscale`, `React Native` | Planned |