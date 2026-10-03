# Product Requirement Document (PRD):
 an open-source, local-first, multi-agent development orchestration platform for Windows, macOS, and Linux. It takes high-level user specifications, decomposes them into parallel execution paths, isolates them across separate Git worktrees, dispatches tasks across installed IDEs and AI coding tools on the user's host machine, and manages testing and conflict-free code merging.

---

## 1. System Objectives & Architecture Principles

* **100% Local-First & Air-Gapped Capable:** All orchestration, task dispatching, and code manipulation occur strictly on the user's local machine. Zero codebase leakage to remote telemetry servers.
* **Provider-Agnostic LLM Routing:** Native support for local engines via **Ollama**, **vLLM**, and **LM Studio**, alongside external API endpoints via **OpenRouter**, **Groq**, **OpenAI**, and **Anthropic**.
* **Worktree-Based File System Isolation:** Prevents concurrent file access locks and race conditions by isolating each agent/IDE into dedicated `git worktree` instances on distinct branches rather than sharing the root working directory.
* **Multi-Modal Perception Layer:** Combines OS-level process manipulation, Language Server Protocol / IPC bridges, and optical screen perception (OCR + multi-modal models) to supervise code editor windows lacking headless APIs.

---

## 2. Technical Stack Recommendation

| Component | Selected Technology | Technical Rationale |
| --- | --- | --- |
| **Host Runtime & Process Control** | **Rust** (or **Python 3.12+ / FastAPI / Asyncio**) | High-performance OS-level process spawning, minimal memory overhead, zero runtime bloat. |
| **Desktop Shell / Client GUI** | **Tauri (v2) + React / Tailwind CSS** | Sub-30MB binaries, minimal RAM footprint compared to Electron, deep native OS API integration. |
| **LLM Interface Abstraction** | **LiteLLM** (Python) or **Rig** (Rust) | Unified, hot-swappable schema for 100+ providers (Ollama, Groq, OpenRouter, OpenAI). |
| **Multi-Agent Orchestration** | **LangGraph** or Custom State Machine | Handles cyclic execution loops, automated task breakdown, inter-agent debates, and human-in-the-loop escalations. |
| **Version Control & Worktrees** | Native `git` CLI (Subprocess) / `libgit2` | Fast branch provisioning, checkout isolation, and automated merge rebase loops. |
| **Screen Perception & Window Telemetry** | **Tesseract OCR / Windows UI Automation / PyAutoGUI / AppleScript** | Non-invasive screen capture and OCR fallback for monitoring IDE state and terminal errors. |

---

## 3. Core Engine Modules

### Module A: Host Environment Discovery

* Probes the system path (`PATH`, Registry on Windows, `/Applications` on macOS) to detect installed development environments: VS Code, Cursor, Android Studio, JetBrains Fleet/IntelliJ, Windsurf, Neovim, and terminal emulators.
* Allows manual override and user configuration via a JSON/YAML configuration file (`devorchestrator.config.json`).

### Module B: Multi-LLM Consensus & Task Decomposition

* Uses a Planner model (e.g., Claude 3.5 Sonnet, DeepSeek-R1, or local Qwen-2.5-Coder) to decompose the primary user prompt into decoupled sub-tasks.
* Runs a "Debate/Verification" step where secondary models (e.g., Llama 3 via Ollama) challenge edge cases, interface contracts, and dependency structures before implementation starts.

### Module C: Git Worktree Provisioning Engine

* For each parallel task $T_i$, creates an isolated Git worktree:
```bash
git worktree add -b feature/task-i .worktrees/task-i main

```


* Associates each worktree with a target IDE:
* Task A (Backend API) $\rightarrow$ Opened in VS Code / Cursor on `.worktrees/task-auth`
* Task B (Android View / Mobile) $\rightarrow$ Opened in Android Studio on `.worktrees/task-ui`



### Module D: IDE Injection & Autonomous Worker Bridge

* Launches IDE instances pointing directly to the generated worktree folders.
* Injects task-specific system prompts and constraints via:
1. Temporary `.cursorrules`, `.vscode/settings.json`, or root `AGENT_INSTRUCTIONS.md` files.
2. Direct terminal/IPC commands.
3. Window automation and clipboard injection as a secondary fallback.



### Module E: Screen Perception & OCR Context Engine

* Takes periodic window screenshots of running IDEs when direct API monitoring is unavailable.
* Uses lightweight OCR and vision models to parse compilation errors, build logs, and completion states directly from IDE terminal outputs.

### Module F: Integration, Testing & Merge Engine

* Automatically triggers configured test commands (e.g., `pytest`, `cargo test`, `npm run test`, `gradle check`) in each worktree upon task completion.
* Merges passing branches back to `main`. If merge conflicts occur, passes conflict markers to a Resolver Agent to auto-rebase and resolve.

---

## 4. System Flowchart

```
                 [User Feature Request]
                            │
                            ▼
           ┌───────────────────────────────────┐
           │ Master Planner & Debate Engine   │
           │ (Multi-LLM Strategy Verification) │
           └────────────────┬──────────────────┘
                            │
                 (Task Decomposition)
               ┌────────────┴────────────┐
               ▼                         ▼
    ┌───────────────────────┐ ┌───────────────────────┐
    │ Task 1: API Layer     │ │ Task 2: Mobile Client │
    │ Target: VS Code       │ │ Target: Android Studio│
    │ Branch: feat/api      │ │ Branch: feat/mobile   │
    │ Path: .worktrees/api  │ │ Path: .worktrees/mob  │
    └──────────┬────────────┘ └──────────┬────────────┘
               │                         │
               ▼                         ▼
    ┌───────────────────────┐ ┌───────────────────────┐
    │ Autonomous Dev Loop   │ │ Autonomous Dev Loop   │
    │ (Code, Edit, OCR Mon) │ │ (Code, Edit, OCR Mon) │
    └──────────┬────────────┘ └──────────┬────────────┘
               │                         │
               ▼                         ▼
         [Run Unit Tests]          [Run Unit Tests]
               │                         │
               └────────────┬────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │ Code Reviewer Agent       │
              │ Conflict-Free Git Merge   │
              └─────────────┬─────────────┘
                            ▼
                      [Target: main]

```

---

## 5. Development Roadmap (Open Source Milestones)

* **Phase 1: CLI Core Engine**
* Git worktree automation module.
* Multi-provider LLM connector using LiteLLM (Ollama, Groq, OpenAI, OpenRouter).
* System-level process dispatcher to open folders in specified IDEs via CLI flags (`code .`, `cursor .`, `studio .`).


* **Phase 2: Context, Telemetry & Vision**
* Automated file system change-watcher per worktree.
* Desktop screen capture + OCR fallback for terminal and compiler error extraction.
* Inter-model debate and planner engine with auto-rollback on build failure.


* **Phase 3: GUI & Ecosystem**
* Cross-platform desktop interface built with Tauri and React.
* Plugin framework allowing contributors to write custom adapters for any niche editor or terminal tool.



---

## 6. Ready-to-Use AI Agent Prompt

Copy and paste the following prompt into an advanced AI coding assistant (like Claude 4.8 Sonnet, GPT-5o, or a local agent) to bootstrap the project repository:

```markdown
You are a Principal Systems Architect and Staff Software Engineer. 

Build the foundation for an open-source, local-first developer automation tool .

System Overview:
DevOrchestrator coordinates multiple code editors (e.g., VS Code, Cursor, Android Studio) simultaneously on a single host machine (Windows, macOS, Linux). It takes a complex development goal, breaks it down using an LLM consensus/planner model, isolates subtasks into distinct Git Worktrees, launches appropriate editors with injected instructions, tracks progress via file system watchers and OS/OCR fallbacks, and executes test-driven merges back to the primary branch.

Core Specifications:
1. Tech Stack: Python 3.12+ (Asyncio, Click/Typer for CLI, Pydantic, LiteLLM) or Rust?. Implement clean modular separation.
2. Zero Data Leaks: Local execution only. LiteLLM handles provider switching across local Ollama instances, Groq, OpenRouter, and OpenAI.
3. Git Worktree Engine: Programmatic creation, tracking, and pruning of independent `.worktrees/<task-id>` directories on unique Git branches to avoid concurrent workspace access conflicts.
4. IDE Launcher: OS-agnostic path discovery and process spawner for VS Code (`code`), Cursor (`cursor`), Android Studio, and custom CLI binaries.

Deliverables:
1. Provide the complete project directory structure suitable for a high-standard open-source GitHub repository.
2. Write a production-ready, fully functional Python prototype containing: example,
   - `config.py`: Configuration schema using Pydantic.
   - `worktree_manager.py`: Complete async implementation of Git worktree creation, tracking, status checks, and cleanup.
   - `dispatcher.py`: Logic to assign subtasks, write a task-specific `INSTRUCTIONS.md` inside the worktree, and launch the requested editor process attached to that directory.
   - `main.py`: Interactive CLI entry point demonstrating task allocation across two parallel worktrees.

```