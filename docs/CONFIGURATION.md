# Synapr Configuration Guide ⚙️

Synapr can be configured three different ways — pick whichever fits your workflow.
They compose, so you can commit a project file *and* override a key from the shell
*and* tweak a model from the dashboard while the swarm is running.

```
            ┌──────────────────────────────────────────────────────────────┐
            │ 1. Built-in defaults          (synapr/config.py)             │
            ├──────────────────────────────────────────────────────────────┤
            │ 2. Project file               (synapr.config.json)           │  ← `synapr init`
            ├──────────────────────────────────────────────────────────────┤
            │ 3a. .env file                 (git-ignored, auto-loaded)     │  ← `synapr config env --example`
            ├──────────────────────────────────────────────────────────────┤
            │ 3b. Real environment vars     (SYNAPR_*)                     │  ← highest precedence
            └──────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ live edits (apply / save / declare env vars)
            ┌──────────────────────┴───────────────────────────────────────┐
            │ Visual configurator   `synapr ui` → Configuration tab        │
            └──────────────────────────────────────────────────────────────┘
```

**Precedence (last wins): defaults → `synapr.config.json` → `.env` → process environment.**

---

## 1. The visual configurator (recommended)

```bash
synapr ui              # http://127.0.0.1:8765
```

The dashboard has three tabs:

| Tab | What you can do |
| :-- | :-- |
| **🚀 Swarm** | Dispatch goals, watch worktrees, consensus debate and live telemetry. |
| **⚙️ Configuration** | Edit *every* setting through a form generated from the schema — providers, endpoints, API keys, per-role models, worktree isolation, editor mapping, perception, pipeline and dashboard options. |
| **🔐 Environment** | Inspect the full `SYNAPR_*` registry, declare variables at runtime, and optionally persist them to a git-ignored `.env`. |

Buttons in the Configuration tab:

| Button | Behaviour |
| :-- | :-- |
| **⚡ Apply** | Validates and applies to the **running** process (orchestrator sub-systems are hot-swapped). Nothing is written to disk. |
| **💾 Save** | Applies **and** writes `synapr.config.json` atomically. |
| **⟲ Defaults** | Restores built-in defaults in memory (environment variables are re-applied on top). |
| **↻ Reload** | Discards in-memory changes and re-reads the file from disk. |
| **🩺 Test Connection** | Probes the selected provider endpoint and lists the models it advertises. |

Safety properties:

* **Secrets are never returned in clear text.** The API responds with `••••••••1234`; sending that
  placeholder back is a no-op, so saving a form can never destroy a key. The *Clear* button next to
  a secret explicitly removes it.
* **Values coming from the environment are marked `ENV` and locked** in the form — the environment is
  the source of truth, and those values are *not* baked into `synapr.config.json` when you save.
* **Writes can be switched off** entirely with `ui.allow_config_writes = false`
  (`SYNAPR_UI_ALLOW_CONFIG_WRITES=false`), which makes every mutating endpoint return HTTP 403.
* **The API only accepts localhost origins** unless `ui.allow_remote_origins` is enabled.
* **No external asset is ever requested** by the dashboard (no CDN, no web fonts, no telemetry).

---

## 2. The CLI

```bash
synapr init                                   # write synapr.config.json + .env.example
synapr config show                            # effective configuration + provenance
synapr config show --json [--reveal]          # machine readable (secrets redacted unless --reveal)
synapr config get gateway.planner_model
synapr config set gateway.default_provider ollama
synapr config set ui.port 8900 --no-save      # runtime only
synapr config unset gateway.planner_model     # restore the default
synapr config path                            # which file is read/written
synapr config validate                        # exit code 1 when the file is broken
synapr config env [--all] [--example] [--write-example .env.example]
synapr config test --provider ollama          # endpoint reachability probe
synapr --config /path/to/other.json config show
```

Values are coerced to the declared type, so `"false"`, `"9123"` and `"a,b"` become
`False`, `9123` and `["a", "b"]`. Invalid values are rejected with a non-zero exit code
and a precise message — the file is never left half-written (saves are atomic).

---

## 3. Environment variables

Every field has a dedicated variable. Generate a documented template with:

```bash
synapr config env --example > .env            # or: synapr init (writes .env.example)
```

`.env` is loaded automatically from the working directory and is already git-ignored.

### Project

| Variable | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_PROJECT_NAME` | `project_name` | string |

### LLM gateway

| Variable (aliases) | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_PROVIDER` (`SYNAPR_GATEWAY_PROVIDER`) | `gateway.default_provider` | `mock\|ollama\|openai\|openrouter\|groq\|lmstudio\|vllm` |
| `SYNAPR_OLLAMA_BASE_URL` (`OLLAMA_BASE_URL`) | `gateway.ollama_base_url` | url |
| `SYNAPR_OPENAI_BASE_URL` (`OPENAI_BASE_URL`) | `gateway.openai_base_url` | url |
| `SYNAPR_OPENROUTER_BASE_URL` | `gateway.openrouter_base_url` | url |
| `SYNAPR_GROQ_BASE_URL` | `gateway.groq_base_url` | url |
| `SYNAPR_LMSTUDIO_BASE_URL` | `gateway.lmstudio_base_url` | url |
| `SYNAPR_VLLM_BASE_URL` | `gateway.vllm_base_url` | url |
| `SYNAPR_OPENAI_API_KEY` (`OPENAI_API_KEY`) | `gateway.openai_api_key` | secret |
| `SYNAPR_OPENROUTER_API_KEY` (`OPENROUTER_API_KEY`) | `gateway.openrouter_api_key` | secret |
| `SYNAPR_GROQ_API_KEY` (`GROQ_API_KEY`) | `gateway.groq_api_key` | secret |
| `SYNAPR_PLANNER_MODEL` | `gateway.planner_model` | string |
| `SYNAPR_CRITIC_MODELS` | `gateway.critic_models` | comma separated list |
| `SYNAPR_ARBITER_MODEL` | `gateway.arbiter_model` | string |
| `SYNAPR_RESOLVER_MODEL` | `gateway.resolver_model` | string |
| `SYNAPR_VISION_MODEL` | `gateway.vision_model` | string |
| `SYNAPR_TIMEOUT_SECONDS` | `gateway.timeout_seconds` | float > 0 |
| `SYNAPR_TEMPERATURE` | `gateway.temperature` | float 0–2 |
| `SYNAPR_MAX_TOKENS` | `gateway.max_tokens` | int > 0 |

### Worktrees

| Variable | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_WORKTREE_ROOT` | `worktree.worktree_root` | path |
| `SYNAPR_BASE_BRANCH` | `worktree.base_branch` | string |
| `SYNAPR_BRANCH_PREFIX` | `worktree.branch_prefix` | string |
| `SYNAPR_AUTO_CLEANUP` | `worktree.auto_cleanup_on_success` | bool |

### Editors

| Variable | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_PREFERRED_EDITOR` | `editor.preferred_editor` | string |
| `SYNAPR_EDITOR_OVERRIDES` | `editor.editor_overrides` | JSON object |
| `SYNAPR_CUSTOM_EDITOR_PATHS` | `editor.custom_editor_paths` | JSON object |
| `SYNAPR_LAUNCH_DETACHED` | `editor.launch_detached` | bool |

### Perception

| Variable | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_PERCEPTION_ENABLED` | `perception.enabled` | bool |
| `SYNAPR_PERCEPTION_INTERVAL` | `perception.poll_interval_seconds` | float > 0 |
| `SYNAPR_OCR_ENGINE` | `perception.ocr_engine` | `auto\|tesseract\|windows_media\|regex_terminal` |
| `SYNAPR_CAPTURE_SCREENSHOTS` | `perception.capture_screenshots` | bool |
| `SYNAPR_SCREENSHOT_DIR` | `perception.screenshot_dir` | path |

### Test & merge pipeline

| Variable | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_AUTO_TEST` | `pipeline.auto_test` | bool |
| `SYNAPR_AUTO_MERGE` | `pipeline.auto_merge` | bool |
| `SYNAPR_MAX_HEALING_ATTEMPTS` | `pipeline.max_self_healing_attempts` | int 0–20 |
| `SYNAPR_TEST_COMMAND` | `pipeline.default_test_command` | string |
| `SYNAPR_ALLOW_FORCE_MERGE` | `pipeline.allow_force_merge` | bool |

### Dashboard

| Variable | Config path | Type |
| :-- | :-- | :-- |
| `SYNAPR_UI_HOST` | `ui.host` | string |
| `SYNAPR_UI_PORT` | `ui.port` | int 1–65535 |
| `SYNAPR_UI_OPEN_BROWSER` | `ui.auto_open_browser` | bool |
| `SYNAPR_UI_ALLOW_CONFIG_WRITES` | `ui.allow_config_writes` | bool |
| `SYNAPR_UI_ALLOW_REMOTE_ORIGINS` | `ui.allow_remote_origins` | bool |
| `SYNAPR_UI_REFRESH_SECONDS` | `ui.refresh_interval_seconds` | float > 0 |

Booleans accept `1/0`, `true/false`, `yes/no`, `on/off` (case-insensitive).
An invalid value never crashes Synapr: it is ignored, reported by
`synapr config validate`, and surfaced in the dashboard.

---

## 4. The configuration file

`synapr init` writes a complete `synapr.config.json`:

```json
{
  "project_name": "Synapr Project",
  "gateway": {
    "default_provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "planner_model": "qwen2.5-coder:7b",
    "critic_models": ["llama3.2:latest", "mistral:latest"],
    "arbiter_model": "qwen2.5-coder:7b",
    "resolver_model": "qwen2.5-coder:7b",
    "temperature": 0.2
  },
  "worktree": {
    "worktree_root": ".worktrees",
    "base_branch": "main",
    "branch_prefix": "synapr/",
    "auto_cleanup_on_success": false
  },
  "editor": {
    "preferred_editor": "vscode",
    "editor_overrides": { "backend": "cursor", "mobile": "android_studio" },
    "launch_detached": true
  },
  "perception": { "enabled": true, "poll_interval_seconds": 2.5 },
  "pipeline": { "auto_test": true, "auto_merge": true, "max_self_healing_attempts": 3 },
  "ui": { "host": "127.0.0.1", "port": 8765, "allow_config_writes": true }
}
```

Discovery order: `--config <path>` → `./synapr.config.json` → `./.synapr/config.json` →
`~/.synapr/config.json`. Unknown keys are ignored, so files written by older or newer
versions keep working. A corrupt file never prevents start-up — defaults are used and the
error is reported by `synapr config validate`, `synapr status` and the dashboard.

> Prefer **not** to commit API keys. Keys set through the environment are deliberately kept
> out of the saved file; keys typed into the dashboard are stored in `synapr.config.json`
> with `0600` permissions on POSIX hosts.

---

## 5. HTTP API reference

| Method & path | Purpose |
| :-- | :-- |
| `GET /api/config` | Effective configuration (secrets redacted) + provenance metadata. |
| `GET /api/config/schema` | Declarative form description used by the dashboard. |
| `PUT /api/config` | Deep-merge a partial update. Body: `{"config": {...}, "persist": true}`. |
| `POST /api/config/value` | Set one dotted path. Body: `{"path": "ui.port", "value": 8900}`. |
| `POST /api/config/save` | Persist the in-memory configuration. |
| `POST /api/config/reload` | Re-read the file from disk. |
| `POST /api/config/reset` | Restore defaults (env re-applied). |
| `GET /api/config/env` | Environment variable registry and current state. |
| `POST /api/config/env` | Declare/remove variables. Body: `{"values": {...}, "unset": [...], "persist": false}`. |
| `GET /api/config/env/example` | Download a documented `.env.example`. |
| `POST /api/config/test-provider` | Probe a provider endpoint. |
| `GET /api/status`, `GET /api/health` | Runtime state and liveness. |
| `GET /api/events` | Server-Sent Events stream (emits `config:updated`). |

Example:

```bash
curl -X PUT http://127.0.0.1:8765/api/config \
  -H 'Content-Type: application/json' \
  -d '{"config": {"gateway": {"default_provider": "ollama"}}, "persist": true}'
```

---

## 6. Programmatic use

```python
from synapr.config import SynaprConfig
from synapr.core.config_service import get_config_service

cfg = SynaprConfig.load()              # file + .env + environment
print(cfg.meta.source_path, cfg.meta.env_overrides)

service = get_config_service()         # shared by CLI, orchestrator and dashboard
service.update({"gateway": {"temperature": 0.1}}, persist=True)
service.subscribe(lambda new_cfg: print("config changed:", new_cfg.gateway.default_provider))
```

`SynaprOrchestrator.apply_config()` rebuilds every sub-system in place, which is how a
dashboard edit takes effect immediately without restarting the process.
