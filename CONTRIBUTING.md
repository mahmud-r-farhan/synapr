# Contributing to Synapr ⚡

Thank you for your interest in contributing to **Synapr**! Synapr is an open-source, local-first multi-IDE AI swarm orchestrator designed to run without data leakage.

---

## 🛠️ Development Setup

### Prerequisites
- **Python 3.11+** (tested on 3.12, 3.13, 3.14)
- **Git 2.25+** (with support for `git worktree`)
- Any installed code editor (VS Code, Cursor, Android Studio, Windsurf, AntiGravity, Neovim)

### Installation
1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-username/Synapr.git
   cd Synapr
   ```

2. Install in editable development mode:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run the test suite:
   ```bash
   pytest tests/ -v
   ```

4. Run the full local quality gate before opening a pull request:
   ```bash
   ruff check .                 # lint & import order
   mypy synapr                  # static types (must stay clean)
   pytest tests/ --cov=synapr   # unit & integration tests
   python scripts/smoke_test.py # end-to-end CLI + dashboard smoke test
   ```

---

## 🏗️ Architecture & Guidelines

Synapr is architected with strict modular boundaries:
- `synapr/core/`: Domain models (`SubTask`, `ExecutionPlan`), events, and privacy-preserving logging.
- `synapr/gateway/`: Universal LLM gateway supporting local air-gapped engines (Ollama, LM Studio, vLLM) and external providers (OpenRouter, Groq, OpenAI).
- `synapr/discovery/`: Cross-platform host environment detector for installed IDEs and AI tools.
- `synapr/planner/`: Goal decomposer and multi-LLM debate & consensus verification engine.
- `synapr/worktree/`: Programmatic Git worktree lifecycle management.
- `synapr/dispatcher/`: Task specification injection and IDE process spawner.
- `synapr/perception/`: Optical screen perception, native window telemetry, and OCR log extraction.
- `synapr/merger/`: Build/test suite execution and self-healing merge conflict resolution.
- `synapr/web/`: FastAPI REST API and real-time SSE Web Dashboard.
- `synapr/cli/`: Click-based terminal control center.
- `synapr/config.py`: Pydantic configuration schema **and** the `SYNAPR_*` environment registry — add a
  field here and the CLI, the env layer and the dashboard form pick it up automatically.
- `synapr/core/config_service.py`: Runtime configuration service (validation, persistence, env
  injection, provider probes, UI schema) shared by every entry point.
- `synapr/web/static/`: Dashboard assets. They must stay dependency-free and fully local — CI fails
  if a remote URL is introduced.

---

## 📝 Commit Conventions

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation improvements
- `test:` Adding or updating tests
- `refactor:` Code changes that neither fix a bug nor add a feature
- `ci:` Changes to CI/CD workflows

---

## 🧪 Testing Requirements

All pull requests must:
1. Pass all unit and integration tests (`pytest tests/ -v`).
2. Add new tests for newly introduced functionality or bug fixes.
3. Preserve the 100% air-gap security guarantee (no external network leaks unless user explicitly configures an external API key).
4. Never log, serialise or return secrets in clear text — `security.yml` enforces this.
5. Keep `ruff check .` and `mypy synapr` clean; both run in CI (`lint.yml`).

### Continuous integration

| Workflow | Purpose |
| :--- | :--- |
| `ci.yml` | Test matrix (3.11–3.14 × Linux/macOS/Windows), coverage gate (≥75%), wheel build & packaged-asset verification. |
| `lint.yml` | Ruff, mypy, dashboard JS syntax check, air-gap asset check. |
| `smoke.yml` | Installs the package and runs the real CLI + dashboard end-to-end, plus an environment-variable matrix. |
| `security.yml` | `pip-audit`, `bandit`, secret-leak guard, committed-`.env` guard. |
| `codeql.yml` | CodeQL security & quality analysis. |
| `dependency-review.yml` | Fails PRs introducing high-severity dependency advisories. |

---

## 📜 License

By contributing to Synapr, you agree that your contributions will be licensed under the [MIT License](LICENSE).
