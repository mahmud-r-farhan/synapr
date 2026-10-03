# Synapr System Architecture & Specification ⚡

Synapr is an operating-system-level developer orchestration platform. It transforms single-editor AI interactions into an autonomous swarm capable of driving multiple code editors concurrently across isolated Git worktrees.

---

## 🏛️ High-Level Architectural Diagram

```text
                           [ Developer High-Level Goal ]
                                         │
                                         ▼
                     ┌───────────────────────────────────────┐
                     │   Task Decomposer & DAG Generator     │
                     │  (Breaks goal into decoupled subtasks)│
                     └───────────────────┬───────────────────┘
                                         │
                                         ▼
                     ┌───────────────────────────────────────┐
                     │   Multi-LLM Consensus Debate Arena    │
                     │  (Peer models debate contracts/risks) │
                     └───────────────────┬───────────────────┘
                                         │
                         (Verified Decoupled Plan)
                                         │
                     ┌───────────────────┴───────────────────┐
                     ▼                                       ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │  Task 1: Backend API    │             │  Task 2: Mobile UI      │
        │  Scope: src/api/*       │             │  Scope: android/*       │
        │  Target: VS Code        │             │  Target: Android Studio │
        └────────────┬────────────┘             └────────────┬────────────┘
                     │                                       │
                     ▼                                       ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │  Git Worktree Isolation │             │  Git Worktree Isolation │
        │  Path: .worktrees/api   │             │  Path: .worktrees/ui    │
        │  Branch: synapr/api     │             │  Branch: synapr/ui      │
        └────────────┬────────────┘             └────────────┬────────────┘
                     │                                       │
                     ▼                                       ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │  Context & Rule Inject  │             │  Context & Rule Inject  │
        │  AGENT_INSTRUCTIONS.md  │             │  AGENT_INSTRUCTIONS.md  │
        │  .cursorrules / settings│             │  .cursorrules / settings│
        └────────────┬────────────┘             └────────────┬────────────┘
                     │                                       │
                     ▼                                       ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │  Process Dispatcher     │             │  Process Dispatcher     │
        │  (Launches VS Code)     │             │  (Launches Studio)      │
        └────────────┬────────────┘             └────────────┬────────────┘
                     │                                       │
                     ▼                                       ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │  Optical Perception &   │             │  Optical Perception &   │
        │  Terminal Telemetry     │             │  Terminal Telemetry     │
        └────────────┬────────────┘             └────────────┬────────────┘
                     │                                       │
                     ▼                                       ▼
        ┌─────────────────────────┐             ┌─────────────────────────┐
        │  Local Test Runner      │             │  Local Test Runner      │
        │  (pytest, npm, cargo)   │             │  (gradle, test)         │
        └────────────┬────────────┘             └────────────┬────────────┘
                     │                                       │
                     └───────────────────┬───────────────────┘
                                         │
                                         ▼
                     ┌───────────────────────────────────────┐
                     │   Integration & Self-Healing Resolver │
                     │  (Sequential rebase & conflict fixes) │
                     └───────────────────┬───────────────────┘
                                         │
                                         ▼
                           [ Clean Code Merged to Main ]
```

---

## 🧩 Core Subsystem Breakdown

### 1. Universal Air-Gapped LLM Gateway (`synapr.gateway`)
* Native support for local engines:
  - **Ollama** (`http://localhost:11434`)
  - **LM Studio** (`http://localhost:1234/v1`)
  - **vLLM** (`http://localhost:8000/v1`)
  - **Deterministic Offline Simulation Engine** (dry-run & CI testing)
* Optional remote gateways:
  - **OpenRouter**, **Groq**, **OpenAI**, **Anthropic**
* Zero telemetry guarantee: all prompt payloads remain local unless explicitly routed to an external provider.

### 2. Host Environment Discovery (`synapr.discovery`)
* Dynamically locates installed developer environments:
  - Visual Studio Code (`code`)
  - Cursor AI (`cursor`)
  - Windsurf (`windsurf`)
  - AntiGravity (`antigravity` / `agy`)
  - Android Studio (`studio`, `studio64.exe`)
  - JetBrains Suite (IntelliJ, PyCharm, WebStorm, Fleet)
  - Terminal editors (Neovim, Vim, Helix)
* Configurable overrides via `synapr.config.json`.

### 3. Multi-LLM Consensus Debate Engine (`synapr.planner.consensus`)
* Multi-stage architectural validation:
  - **Lead Planner**: Decomposes high-level prompt into a DAG of subtasks.
  - **Architectural Reviewer Critic**: Examines interfaces and system contracts.
  - **Concurrency & Collision Guard Critic**: Checks for overlapping file scopes and race conditions.
  - **Chief Arbiter**: Synthesizes peer critiques and assigns consensus score before execution begins.

### 4. Git Worktree Isolation Manager (`synapr.worktree`)
* Provisions dedicated directories (`.worktrees/<task-id>`) on independent feature branches (`synapr/<task-id>`).
* Prevents file lock collisions and shared git index corruption.
* Programmatic lock/unlock, status checking, and automatic pruning.

### 5. IDE Injection & Worker Bridge (`synapr.dispatcher`)
* Injects tailored constraints into each worktree:
  - `AGENT_INSTRUCTIONS.md` (human & agent task brief)
  - `.synapr_task.json` (machine-readable task specification)
  - `.cursorrules` (Cursor AI context rules)
  - `.vscode/settings.json` (workspace title & task environment variables)
* Spawns detached or supervised editor processes pointing directly to the worktree path.

### 6. Optical Screen Perception & OCR Telemetry (`synapr.perception`)
* Inspects non-headless GUI windows:
  - Native Win32 / platform window enumeration.
  - Window capture and snapshot generation.
  - Regex & OCR extraction for compilation errors, stack traces, warnings, and test results.

### 7. Build, Test & Self-Healing Merge Pipeline (`synapr.merger`)
* Auto-detects test runners (`pytest`, `cargo test`, `npm test`, `gradle check`, `go test`).
* Merges passing branches back to the main branch.
* If merge conflicts occur:
  - Conflict hunks are extracted and submitted to the **Self-Healing Resolver**.
  - Resolver generates clean, merged source code.
  - Test suites are re-executed against the resolved tree to prevent regressions.
  - Merges are committed automatically upon passing tests, or safely aborted if unresolvable.
