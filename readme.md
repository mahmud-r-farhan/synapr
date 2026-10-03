# Synapr ⚡

> **The Autonomous Local Multi-IDE AI Orchestrator.**  
> Orchestrate multiple installed IDEs, isolated Git worktrees, and local LLMs simultaneously to build complex features in parallel — 100% on your local machine with zero external data leakage.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)]()
[![Privacy: 100% Local](https://img.shields.io/badge/Privacy-100%25%20Local-success.svg)]()
[![Tests: 148 Passed](https://img.shields.io/badge/Tests-148%20Passed-brightgreen.svg)]()
[![Config: Visual + Env](https://img.shields.io/badge/Config-Visual%20%7C%20CLI%20%7C%20Env-8b5cf6.svg)]()

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
* **🎛️ Zero-Friction Visual Configuration:** Configure *everything* — providers, endpoints, API keys, per-role models, worktree isolation, editor mapping, perception and the merge pipeline — from the dashboard **while Synapr is running**, declare the same settings as `SYNAPR_*` environment variables, or edit `synapr.config.json`. Changes hot-swap the live orchestrator; secrets are always redacted over the wire.

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

### 5. Launch the Web Dashboard & Visual Configurator
Start the real-time local control center in your browser:
```bash
synapr ui                      # honours ui.host / ui.port, --no-open-browser to stay headless
```
Navigate to `http://127.0.0.1:8765`:

* **🚀 Swarm** — dispatch goals, watch worktrees, consensus debate rounds and streaming telemetry.
* **⚙️ Configuration** — a form generated from the live schema for every setting, with validation,
  provider connectivity tests, *Apply* (runtime only) and *Save* (writes `synapr.config.json`).
* **🔐 Environment** — browse the full `SYNAPR_*` registry and declare variables after start-up,
  optionally persisting them to a git-ignored `.env`.

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
| `synapr ui` | Boots the local dashboard + visual configurator on port `8765`. |
| `synapr config show [--json] [--reveal]` | Prints the effective configuration and where each value came from. |
| `synapr config get/set/unset <path> [value]` | Reads or edits a single setting (`gateway.planner_model`, `ui.port`, …). |
| `synapr config env [--all] [--example]` | Lists every supported environment variable or emits a `.env` template. |
| `synapr config test [--provider]` | Probes the configured LLM endpoint and lists available models. |
| `synapr config validate` / `config path` | Validates the config file / prints which file is used. |

---

## ⚙️ Configuration

Three interchangeable layers, applied in order — **defaults → `synapr.config.json` → `.env` → environment variables** —
plus a visual editor that can change anything at runtime. Full reference: **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**.

```bash
# 1. Visually, after the run (hot-applies to the live orchestrator)
synapr ui                      # → Configuration / Environment tabs

# 2. From the terminal
synapr config set gateway.default_provider ollama
synapr config set gateway.planner_model qwen2.5-coder:7b

# 3. As environment variables (or a git-ignored .env file)
export SYNAPR_PROVIDER=ollama
export SYNAPR_PLANNER_MODEL=qwen2.5-coder:7b
export SYNAPR_OLLAMA_BASE_URL=http://localhost:11434
synapr config env --example > .env      # documented template for every variable
```

Secrets (`SYNAPR_OPENAI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, …) are
redacted in every API response, log line and CLI output, and values provided by the environment are
never written into `synapr.config.json`.

### `synapr.config.json`

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
  },
  "ui": {
    "host": "127.0.0.1",
    "port": 8765,
    "auto_open_browser": true,
    "allow_config_writes": true,
    "allow_remote_origins": false
  }
}
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v                       # 148 unit & integration tests
pytest tests/ --cov=synapr             # coverage report
ruff check . && mypy synapr            # lint + static types
python scripts/smoke_test.py           # end-to-end CLI + dashboard smoke test
```

Continuous integration runs on every push and pull request:

| Workflow | What it guards |
| :--- | :--- |
| `ci.yml` | Test matrix (Python 3.11–3.14 × Linux/macOS/Windows), coverage gate, wheel build & asset packaging. |
| `lint.yml` | Ruff, mypy, dashboard JS syntax and the “no remote assets” air-gap rule. |
| `smoke.yml` | Real CLI + dashboard end-to-end run on three operating systems, plus an environment-variable matrix. |
| `security.yml` | `pip-audit`, `bandit`, secret-leakage guard and committed-`.env` check. |
| `codeql.yml` | GitHub CodeQL security & quality analysis. |
| `dependency-review.yml` | Blocks pull requests introducing high-severity dependency advisories. |

---

## 🤝 Contributing

We welcome contributions from the open-source community! Check out [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) to get started.

---

## 📄 License

Synapr is released under the [MIT License](LICENSE).
