# Synapr ⚡

> **The Autonomous Local Multi-IDE AI Orchestrator.**  
> Orchestrate multiple installed IDEs, isolated Git worktrees, and local LLMs simultaneously to build complex features in parallel — 100% on your local machine with zero external data leakage.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)]()
[![Privacy: 100% Local](https://img.shields.io/badge/Privacy-100%25%20Local-success.svg)]()
[![Tests: 30 Passed](https://img.shields.io/badge/Tests-30%20Passed-brightgreen.svg)]()

---

## 💡 What is Synapr?

Modern AI coding agents usually work inside a single terminal window or a single IDE extension. When you have a complex feature spanning backend APIs, frontend interfaces, and mobile clients, doing everything sequentially in one workspace leads to context bloat, file lock collisions, and slow turnarounds.

**Synapr** functions as an **operating-system-level development swarm**. You provide a high-level development goal; Synapr decomposes it into decoupled subtasks, verifies the architecture through a **multi-LLM peer debate**, creates isolated **Git Worktrees** for each subtask, and launches your installed development environments (VS Code, Cursor, Android Studio, Windsurf, AntiGravity) in parallel. Each agent works in isolation, and Synapr automates test validation and conflict-free code merging back into `main`.

---

## 🚀 Key Features

* **🔒 100% Local-First & Air-Gapped Capable:** Zero external telemetry. Full native support for local engines via **Ollama**, **vLLM**, **LM Studio**, or deterministic offline simulation.
* **🌐 Universal LLM Gateway:** Toggle between local Ollama instances and remote providers (**OpenRouter**, **Groq**, **OpenAI**, **Anthropic**) with unified routing.
* **🌿 Zero Race Conditions with Git Worktrees:** Provisions independent `.worktrees/<task-id>` directories on isolated feature branches rather than sharing the working tree.
* **🖥️ Host Environment Discovery:** Automatically scans Windows, macOS, and Linux system paths to discover installed editors:
  * Visual Studio Code (`code`) & VS Code Insiders
  * Cursor AI (`cursor`)
  * Windsurf Editor (`windsurf`)
  * AntiGravity IDE (`antigravity`)
  * Android Studio (`studio`, `studio64.exe`)
  * JetBrains Suite (IntelliJ IDEA, PyCharm, WebStorm, Fleet)
  * Terminal Editors (Neovim, Vim, Helix)
* **🧠 Multi-Agent Consensus Debate:** Subtasks are evaluated by a planner model and cross-examined by adversarial reviewer models before execution begins to prevent flawed architectural designs.
* **👁️ Optical Screen Perception:** Native window inspection, screen capture, and OCR pattern extraction for compiler warnings, syntax errors, and test pass/fail signals.
* **🧪 Automated Test & Self-Healing Merge Pipeline:** Runs local test suites per worktree (`pytest`, `cargo test`, `npm test`, `gradle check`) and auto-resolves merge conflicts using an LLM self-healing loop.
* **💻 Dual Control Interfaces:** High-productivity Click CLI + Real-Time SSE Web Dashboard.

---

## 🏛️ System Architecture

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

## 📦 Quick Start

### 1. Installation
Clone the repository and install with pip:
```bash
git clone https://github.com/mahmud-r-farhan/synapr
cd synapr
pip install -e .
```

### 2. Discover Your Installed Editors
Scan your machine to verify discovered development tools:
```bash
synapr scan
```

### 3. Initialize Project Configuration
Generate a customized `synapr.config.json` in your project root:
```bash
synapr init
```

### 4. Execute a Goal
Launch the autonomous orchestrator on a feature prompt:
```bash
# Dry-run simulation (runs debate, worktree provisioning, and mock tests)
synapr run "Build OAuth2 JWT auth with refresh tokens" --dry-run

# Live execution across installed IDEs
synapr run "Build OAuth2 JWT auth with refresh tokens"
```

### 5. Launch the Web Dashboard
Start the real-time local control center in your browser:
```bash
synapr ui
```
Navigate to `http://127.0.0.1:8765` to monitor active worktrees, live consensus debate rounds, and streaming telemetry logs.

---

## 🕹️ CLI Command Reference

| Command | Description |
| :--- | :--- |
| `synapr scan` | Scans OS for installed IDEs (VS Code, Cursor, Android Studio, Windsurf, AntiGravity). |
| `synapr init` | Generates a `synapr.config.json` configuration file. |
| `synapr status` | Prints current git branch, active worktree count, and LLM provider status. |
| `synapr plan "<goal>"` | Runs planning decomposition & multi-LLM debate without launching IDEs. |
| `synapr run "<goal>"` | Executes end-to-end swarm loop (plan, debate, provision, dispatch, test, merge). |
| `synapr worktree list` | Lists all active git worktrees tracked by Synapr. |
| `synapr worktree clean` | Prunes and cleans stale worktree directories. |
| `synapr ui` | Boots up the local FastAPI web dashboard on port `8765`. |

---

## ⚙️ Configuration (`synapr.config.json`)

```json
{
  "project_name": "Synapr Swarm",
  "gateway": {
    "default_provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "planner_model": "qwen2.5-coder:7b",
    "critic_models": ["llama3.2:latest", "mistral:latest"],
    "arbiter_model": "qwen2.5-coder:7b",
    "resolver_model": "qwen2.5-coder:7b"
  },
  "worktree": {
    "worktree_root": ".worktrees",
    "base_branch": "master",
    "branch_prefix": "synapr/",
    "auto_cleanup_on_success": false
  },
  "editor": {
    "preferred_editor": "vscode",
    "editor_overrides": {
      "backend": "cursor",
      "frontend": "vscode",
      "mobile": "android_studio"
    },
    "launch_detached": true
  },
  "perception": {
    "enabled": true,
    "poll_interval_seconds": 2.5,
    "capture_screenshots": true
  },
  "pipeline": {
    "auto_test": true,
    "auto_merge": true,
    "max_self_healing_attempts": 3
  }
}
```

---

## 🧪 Running Tests

Run the complete 30-test suite locally:
```bash
pytest tests/ -v
```

---

## 🤝 Contributing

We welcome contributions from the open-source community! Check out [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) to get started.

---

## 📄 License

Synapr is released under the [MIT License](LICENSE).
