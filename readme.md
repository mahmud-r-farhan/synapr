# Synapr ⚡

> **The Autonomous Local Multi-IDE AI Orchestrator.**  
> Orchestrate multiple IDEs, isolated Git worktrees, and local LLMs simultaneously to build complex features in parallel — 100% on your local machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)]()
[![Local-First](https://img.shields.io/badge/Privacy-100%25%20Local-success.svg)]()

---

## 💡 What is Synapr?

Modern AI coding agents usually work inside a single terminal window or a single IDE extension. When you have a complex feature spanning backend APIs, frontend interfaces, and mobile clients, doing everything sequentially in one workspace leads to context bloat, file lock collisions, and slow turnarounds.

**Synapr** acts as an operating-system-level orchestrator. You provide a high-level development goal; Synapr decomposes it into decoupled subtasks, creates isolated **Git Worktrees** for each task, and boots up your installed development environments (VS Code, Cursor, Android Studio, etc.) in parallel. Each agent works in isolation, and Synapr automates test validation and conflict-free code merging back into `main`.

---

## 🚀 Key Features

* **🔒 100% Local-First & Air-Gapped Capable:** No code leaves your computer unless you explicitly configure remote API endpoints. Full native support for local inference via **Ollama**, **vLLM**, and **LM Studio**.
* **🌐 Universal LLM Gateway:** Built on a unified provider layer — toggle between Ollama, Groq, OpenRouter, OpenAI, and Anthropic seamlessly.
* **🌿 Zero Race Conditions with Git Worktrees:** Instead of having multiple agents edit the same working directory, Synapr provisions independent `.worktrees/<task-id>` directories linked to dedicated feature branches.
* **🖥️ Host Environment Discovery:** Automatically scans your OS `PATH` to locate installed IDEs (VS Code, Cursor, Android Studio, IntelliJ, Windsurf) and dispatches tasks to the right editor.
* **🧠 Multi-Agent Swarm Debate:** Tasks are evaluated by a planner model and cross-examined by a reviewer agent before execution begins to prevent flawed architectural designs.
* **👁️ Screen & Window Perception:** Fallback screen-reading (OCR and accessibility APIs) to extract build logs, compile errors, and terminal state when direct IDE extensions are absent.
* **🧪 Automated Test & Merge Pipeline:** Runs your configured test suites (`pytest`, `npm test`, `cargo test`, `gradle check`) per worktree and rebases clean code into `main`.

---
