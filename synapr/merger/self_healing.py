"""Self-healing merge engine with automated LLM conflict resolution."""

import asyncio
from pathlib import Path

from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.core.models import MergeResult, SubTask, WorktreeInstance
from synapr.gateway.router import ModelRouter
from synapr.merger.pipeline import TestPipeline


class SelfHealingResolver:
    """Automates Git branch integration and resolves merge conflicts via self-healing LLM loops."""

    RESOLVER_SYSTEM_PROMPT = (
        "You are an expert Git Conflict Resolution Specialist and Principal Engineer in Synapr.\n"
        "Your task is to resolve Git merge conflict markers (<<<<<<<, =======, >>>>>>>).\n"
        "Analyze both branches carefully. Combine both changes cleanly without syntax errors, "
        "regressions, or duplicated logic.\n"
        "CRITICAL: Output ONLY the complete, fully resolved file content. Do NOT include any "
        "markdown code fences (```), commentary, or explanation."
    )

    def __init__(
        self,
        repo_root: str | None = None,
        router: ModelRouter | None = None,
        pipeline: TestPipeline | None = None,
    ) -> None:
        self.repo_root = Path(repo_root or ".").resolve()
        self.router = router or ModelRouter()
        self.pipeline = pipeline or TestPipeline()

    async def _run_git(self, args: list[str]) -> tuple[int, str, str]:
        """Run git command in main repository root."""
        cmd = ["git"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )

    async def merge_task_branch(
        self,
        task: SubTask,
        feature_branch: str,
        target_branch: str = "master",
        max_attempts: int = 3,
    ) -> MergeResult:
        """Merge a verified feature branch back into the target branch with self-healing."""
        logger.info(f"Initiating merge: {feature_branch} -> {target_branch} (Task: {task.id})")
        bus.emit("merge:start", {"task_id": task.id, "feature": feature_branch, "target": target_branch})

        # Ensure target branch is checked out
        code, out, err = await self._run_git(["checkout", target_branch])
        if code != 0:
            return MergeResult(
                task_id=task.id,
                target_branch=target_branch,
                feature_branch=feature_branch,
                success=False,
                message=f"Could not checkout {target_branch}: {err}",
            )

        # Attempt merge
        code, out, err = await self._run_git(["merge", "--no-ff", feature_branch, "-m", f"feat({task.id}): merge {task.title}"])
        if code == 0:
            logger.info(f"Clean merge completed for {task.id}")
            bus.emit("merge:complete", {"task_id": task.id, "success": True, "self_healed": False})
            return MergeResult(
                task_id=task.id,
                target_branch=target_branch,
                feature_branch=feature_branch,
                success=True,
                had_conflicts=False,
                self_healed=False,
                message="Clean merge succeeded.",
            )

        # Merge conflicts detected
        logger.warning(f"Merge conflicts encountered while merging {feature_branch} into {target_branch}")
        bus.emit("merge:conflict_detected", {"task_id": task.id, "feature": feature_branch})

        # Identify conflicted files
        code, conf_out, _ = await self._run_git(["diff", "--name-only", "--diff-filter=U"])
        conflicted_files = [f.strip() for f in conf_out.splitlines() if f.strip()]

        if not conflicted_files:
            await self._run_git(["merge", "--abort"])
            return MergeResult(
                task_id=task.id,
                target_branch=target_branch,
                feature_branch=feature_branch,
                success=False,
                message=f"Merge failed with error: {err}",
            )

        # Self-healing loop
        self_healed = False
        for attempt in range(1, max_attempts + 1):
            logger.info(f"[Self-Healing] Attempt {attempt}/{max_attempts} for task {task.id}")
            resolved_all = True

            for rel_path in conflicted_files:
                file_path = self.repo_root / rel_path
                if not file_path.exists():
                    continue

                content = file_path.read_text(encoding="utf-8", errors="replace")
                if "<<<<<<<" not in content:
                    continue

                resolved_content = await self._resolve_file_conflict(
                    file_name=rel_path,
                    conflict_text=content,
                    task_info=f"Task: {task.title} ({task.description})",
                )

                if resolved_content:
                    file_path.write_text(resolved_content, encoding="utf-8")
                    await self._run_git(["add", rel_path])
                else:
                    resolved_all = False

            if not resolved_all:
                continue

            # Run test verification on resolved workspace
            test_res = await self.pipeline.run_tests(
                worktree=WorktreeInstance(
                    task_id=task.id,
                    branch=target_branch,
                    path=str(self.repo_root),
                    editor="system",
                ),
                task=task,
            )

            if test_res.passed:
                # Commit merge
                commit_msg = (
                    f"merge(self-healing): auto-resolved conflict from {feature_branch} "
                    f"for task {task.id} (attempt {attempt})"
                )
                await self._run_git(["commit", "-m", commit_msg])
                self_healed = True
                logger.info(f"Self-healing successfully resolved merge conflicts on attempt {attempt}")
                break
            else:
                logger.warning(f"Tests failed after conflict resolution on attempt {attempt}: {test_res.stderr}")

        if self_healed:
            bus.emit("merge:complete", {"task_id": task.id, "success": True, "self_healed": True})
            return MergeResult(
                task_id=task.id,
                target_branch=target_branch,
                feature_branch=feature_branch,
                success=True,
                had_conflicts=True,
                conflicted_files=conflicted_files,
                self_healed=True,
                message=f"Self-healing resolved conflicts across {len(conflicted_files)} files.",
            )
        else:
            logger.error(f"Self-healing could not automatically resolve merge conflicts for {task.id}. Aborting merge.")
            await self._run_git(["merge", "--abort"])
            bus.emit("merge:failed", {"task_id": task.id, "conflicts": conflicted_files})
            return MergeResult(
                task_id=task.id,
                target_branch=target_branch,
                feature_branch=feature_branch,
                success=False,
                had_conflicts=True,
                conflicted_files=conflicted_files,
                self_healed=False,
                message="Self-healing reached maximum attempts without passing test suite.",
            )

    async def _resolve_file_conflict(
        self, file_name: str, conflict_text: str, task_info: str
    ) -> str | None:
        """Prompt the resolver LLM to output conflict-free merged code."""
        prompt = (
            f"File: {file_name}\n"
            f"Context: {task_info}\n\n"
            f"Merge Conflict Content:\n{conflict_text}\n\n"
            "Produce the final, clean, conflict-free version of this file with zero conflict markers."
        )

        resp = await self.router.run_resolver(
            prompt=prompt,
            system_prompt=self.RESOLVER_SYSTEM_PROMPT,
        )

        clean = resp.content.strip()
        # Strip potential code block formatting if LLM wrapped it
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines).strip()

        # Sanity check: Ensure conflict markers were removed
        if "<<<<<<<" in clean or "=======" in clean or ">>>>>>>" in clean:
            logger.error(f"Resolver output still contains conflict markers for {file_name}")
            return None

        return clean
