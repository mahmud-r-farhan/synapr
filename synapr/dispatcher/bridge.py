"""IDE Injection and Worker Dispatcher bridge."""

import json
import platform
import subprocess
from pathlib import Path

from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.core.models import SubTask, TaskStatus, WorktreeInstance
from synapr.discovery.registry import EditorRegistry


class DispatcherError(Exception):
    """Raised when IDE dispatch or instruction injection fails."""


class TaskDispatcher:
    """Injects contextual constraints and spawns targeted IDE processes into worktrees."""

    def __init__(self, registry: EditorRegistry | None = None) -> None:
        self.registry = registry or EditorRegistry()
        self._spawned_processes: dict[str, subprocess.Popen] = {}

    def inject_task_context(self, worktree_path: str, task: SubTask) -> None:
        """Inject instructions, .cursorrules, .vscode settings, and task metadata into the worktree."""
        target_dir = Path(worktree_path)
        if not target_dir.exists():
            raise DispatcherError(f"Target worktree path does not exist: {worktree_path}")

        # 1. Write AGENT_INSTRUCTIONS.md
        instructions_md = (
            f"# Synapr Task Specification: {task.title}\n\n"
            f"> **Task ID:** `{task.id}`  \n"
            f"> **Target Editor:** `{task.target_editor}`  \n"
            f"> **Status:** `{task.status.value}`  \n\n"
            f"## Objective\n{task.description}\n\n"
            f"## Permitted File Scope\n"
            f"{chr(10).join('- ' + s for s in task.file_scope) if task.file_scope else '- All files within worktree'}\n\n"
            f"## Detailed Instructions & Implementation Constraints\n"
            f"{task.instructions}\n\n"
            f"## Verification & Test Suite\n"
            f"Run: `{task.test_command or 'pytest'}`\n\n"
            "---\n*Injected autonomously by Synapr Swarm Orchestrator. Work is isolated in this Git worktree.*\n"
        )
        (target_dir / "AGENT_INSTRUCTIONS.md").write_text(instructions_md, encoding="utf-8")

        # 2. Write machine-readable .synapr_task.json
        meta_dict = task.model_dump()
        (target_dir / ".synapr_task.json").write_text(json.dumps(meta_dict, indent=2), encoding="utf-8")

        # 3. Write .cursorrules for Cursor AI
        cursorrules = (
            f"You are working on subtask {task.id}: {task.title}.\n"
            f"Scope of edits: {', '.join(task.file_scope) if task.file_scope else 'unrestricted'}.\n"
            f"Constraints: {task.instructions}\n"
            f"Test command: {task.test_command or 'default test suite'}\n"
        )
        (target_dir / ".cursorrules").write_text(cursorrules, encoding="utf-8")

        # 4. Write .vscode settings for VS Code workspace isolation
        vscode_dir = target_dir / ".vscode"
        vscode_dir.mkdir(parents=True, exist_ok=True)
        vscode_settings = {
            "window.title": f"${{dirty}} ${{activeEditorShort}} (Synapr: {task.id})",
            "git.autorefresh": True,
            "terminal.integrated.env.windows": {"SYNAPR_TASK_ID": task.id},
            "terminal.integrated.env.linux": {"SYNAPR_TASK_ID": task.id},
            "terminal.integrated.env.osx": {"SYNAPR_TASK_ID": task.id},
        }
        (vscode_dir / "settings.json").write_text(json.dumps(vscode_settings, indent=2), encoding="utf-8")

        logger.info(f"Injected task specifications and constraints into worktree {target_dir.name}")

    async def launch_editor(
        self,
        worktree: WorktreeInstance,
        task: SubTask,
        detached: bool = True,
        dry_run: bool = False,
    ) -> int | None:
        """Launch the targeted IDE attached directly to the worktree path."""
        # Inject instructions first
        self.inject_task_context(worktree.path, task)

        editor_info = self.registry.get_editor(worktree.editor)
        if not editor_info:
            editor_info = self.registry.resolve_best_editor(requested=worktree.editor)

        if dry_run or not editor_info.is_available:
            logger.info(f"[Dry Run / Headless] Simulated launch of {editor_info.name} for {worktree.path}")
            worktree.status = TaskStatus.ACTIVE
            bus.emit("dispatcher:launched", {"task_id": task.id, "editor": editor_info.name, "simulated": True})
            return 99999

        # Format launch arguments
        cmd_args = [editor_info.executable_path]
        for arg in editor_info.launch_args_template:
            cmd_args.append(arg.replace("{path}", worktree.path))

        logger.info(f"Spawning editor process: {' '.join(cmd_args)}")

        # Configure cross-platform detachment flags
        flags = 0
        if detached and platform.system() == "Windows":
            flags = (
                subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]  # Windows-only flag
                | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            )
        elif detached:
            flags = 0

        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=worktree.path,
                creationflags=flags,
                stdout=subprocess.DEVNULL if detached else None,
                stderr=subprocess.DEVNULL if detached else None,
                close_fds=platform.system() != "Windows",
            )
            self._spawned_processes[task.id] = proc
            worktree.process_pid = proc.pid
            worktree.status = TaskStatus.ACTIVE

            bus.emit(
                "dispatcher:launched",
                {
                    "task_id": task.id,
                    "editor": editor_info.name,
                    "pid": proc.pid,
                    "worktree_path": worktree.path,
                },
            )
            return proc.pid
        except Exception as e:
            logger.error(f"Failed to launch editor {editor_info.name}: {e}")
            raise DispatcherError(f"Could not launch editor {editor_info.name}: {e}") from e

    def terminate_all(self) -> None:
        """Terminate all active spawned editor processes."""
        for proc in list(self._spawned_processes.values()):
            try:
                proc.terminate()
            except Exception:
                pass
        self._spawned_processes.clear()
