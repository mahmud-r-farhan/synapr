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

## 3. Autonomous Browser Automation Engine

A programmatic browser bridge providing web navigation, UI testing, and documentation research capabilities to running agents.

### Implementation Blueprint

* **Engine:** Built upon **Playwright** and **Browser-Use** primitives operating in headless or headful mode.
* **Use Cases:**
* **Localhost Validation:** Automatically opens `http://localhost:3000` (or configured dev servers) after code edits to verify that routes render without console errors.
* **Live Documentation Scraping:** Ingests live API docs, package changelogs, and SDK references when training context is outdated.
* **End-to-End Visual Verification:** Drives browser forms, submits sample payloads, and snaps viewport screenshots for vision model verification.



---

## 4. Intelligent Email Processing & Draft Generation

A privacy-focused communication gateway that parses client requirements, updates, or bug reports from incoming emails and prepares drafted responses.

### Operational Design

* **Secure Mail Connectors:**
* Uses local IMAP/SMTP protocols or official OAuth2 token exchanges (e.g., Google Workspace / Gmail API).
* Credentials remain encrypted locally on the host machine.


* **Inbox Monitoring & Triage:**
* Polls unread threads matching user-defined project labels or sender filters.
* Extracts customer bug reports, feature requests, or deployment queries into structured markdown briefs.


* **Draft Generation & Safe Dispatch:**
* Synthesizes technical context, current repository state, and relevant logs to draft a professional response.
* **Strict Safety Rule:** Saves responses exclusively to the **Drafts** folder. Outbound delivery requires explicit developer confirmation via CLI or the companion mobile app.



---

## 5. GitHub Repository & Issue Lifecycle Tracker

A native integration to map remote GitHub issues directly into autonomous local development loops without leaving the IDE workspace.

### Key Capabilities

* **Bi-directional Issue Sync:**
* Utilizes GitHub CLI (`gh`) or REST/GraphQL APIs to fetch assigned issues and labels (`bug`, `enhancement`, `help wanted`).


* **Issue-to-Branch Orchestration:**
* Running `synapr issue #142` automatically clones issue context, provisions worktree `.worktrees/issue-142`, opens the assigned IDE, and seeds the agent's task prompt with the issue description and reproduction steps.


* **Automated PR & Status Reporting:**
* Upon passing test verification, Synapr generates an explanatory pull request linking to `Closes #142`, including a machine-generated changelog and test results.


* **Issue Comment Triage:**
* Monitors PR review comments; automatically pulls reviewer feedback back into the isolated worktree to patch flagged code.



---

## 6. Implementation Milestones

| Milestone | Target Deliverable | Core Libraries & Tooling |
| --- | --- | --- |
| **Phase 1** | Local Voice Controller & Intent Parser | `openwakeword`, `faster-whisper`, `piper-tts` |
| **Phase 2** | GitHub Issue Sync & PR Automator | `gh` CLI bridge, `PyGithub` / `octokit` |
| **Phase 3** | Headless Browser Agent & UI Tester | `playwright`, `browser-use` |
| **Phase 4** | Email Reader & Draft Assistant | `imaplib`, `email`, Gmail REST API |
| **Phase 5** | Encrypted Mobile Gateway & Companion App | `FastAPI`, `WebSockets`, `Tailscale`, `React Native` |