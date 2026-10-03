"""Verified plan execution across isolated worktrees, tests, and merges."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.core.models import (
    ExecutionPlan,
    MergeResult,
    SubTask,
    TaskStatus,
    TestResult,
    WorktreeInstance,
)

if TYPE_CHECKING:
    from synapr.config import SynaprConfig
    from synapr.dispatcher.bridge import TaskDispatcher
    from synapr.merger.pipeline import TestPipeline
    from synapr.merger.self_healing import SelfHealingResolver
    from synapr.perception.screen import OpticalPerceptionEngine
    from synapr.worktree.manager import WorktreeManager

Tuple_TaskWorktree = tuple[SubTask, WorktreeInstance]


class PlanExecutionMixin:
    config: SynaprConfig
    worktree_mgr: WorktreeManager
    active_worktrees: dict[str, WorktreeInstance]
    dispatcher: TaskDispatcher
    perception: OpticalPerceptionEngine
    test_pipeline: TestPipeline
    resolver: SelfHealingResolver

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        dry_run: bool = False,
        launch_editors: bool = True,
    ) -> dict[str, Any]:
        """Execute a verified plan across isolated worktrees, run tests, and merge."""
        logger.info(f"--- [Phase 3: Worktree Provisioning & Dispatch] --- (Plan: {plan.id})")
        bus.emit("orchestrator:execution_started", {"plan_id": plan.id, "tasks": len(plan.subtasks)})

        base_branch = await self.worktree_mgr.detect_base_branch()
        tasks_to_run = plan.subtasks

        # 1. Provision worktrees and dispatch IDEs in parallel
        provisioned: list[Tuple_TaskWorktree] = []
        for task in tasks_to_run:
            try:
                wt = await self.worktree_mgr.provision_worktree(
                    task_id=task.id,
                    editor=task.target_editor,
                    base_branch=base_branch,
                )
                self.active_worktrees[task.id] = wt
                task.worktree_path = wt.path
                task.branch_name = wt.branch
                task.status = TaskStatus.PROVISIONED

                if launch_editors:
                    await self.dispatcher.launch_editor(
                        worktree=wt,
                        task=task,
                        detached=self.config.editor.launch_detached,
                        dry_run=dry_run,
                    )
                else:
                    self.dispatcher.inject_task_context(wt.path, task)

                provisioned.append((task, wt))
            except Exception as e:
                logger.error(f"Failed to provision/dispatch task {task.id}: {e}")
                task.status = TaskStatus.FAILED

        # 2. Perception & Telemetry check (brief inspection)
        if self.config.perception.enabled:
            logger.info("--- [Phase 4: Optical Window Perception & Telemetry] ---")
            for task, _wt in provisioned:
                perception_res = await self.perception.inspect_task_window(task.id, task.target_editor)
                logger.debug(
                    f"Perception report for {task.id}: found={perception_res.window_found}, "
                    f"errors={len(perception_res.detected_errors)}"
                )

        # 3. Test verification per worktree
        logger.info("--- [Phase 5: Automated Build & Test Suites] ---")
        test_results: dict[str, TestResult] = {}
        for task, wt in provisioned:
            if self.config.pipeline.auto_test:
                t_res = await self.test_pipeline.run_tests(wt, task)
                test_results[task.id] = t_res
                if t_res.passed:
                    task.status = TaskStatus.TESTS_PASSED
                else:
                    task.status = TaskStatus.TESTS_FAILED
            else:
                task.status = TaskStatus.TESTS_PASSED

        # 4. Sequential merge and self-healing
        logger.info("--- [Phase 6: Integration & Self-Healing Merge] ---")
        merge_results: dict[str, MergeResult] = {}
        if self.config.pipeline.auto_merge:
            for task, wt in provisioned:
                # Merge if tests passed or dry run
                if task.status == TaskStatus.TESTS_PASSED or dry_run:
                    m_res = await self.resolver.merge_task_branch(
                        task=task,
                        feature_branch=wt.branch,
                        target_branch=base_branch,
                        max_attempts=self.config.pipeline.max_self_healing_attempts,
                    )
                    merge_results[task.id] = m_res
                    task.status = TaskStatus.COMPLETED if m_res.success else TaskStatus.FAILED

                    # Cleanup worktree if auto-cleanup enabled and successful
                    if m_res.success and self.config.worktree.auto_cleanup_on_success:
                        await self.worktree_mgr.cleanup_worktree(task.id, force=True, delete_branch=True)
                        if task.id in self.active_worktrees:
                            del self.active_worktrees[task.id]

        summary = {
            "plan_id": plan.id,
            "goal": plan.goal,
            "total_tasks": len(plan.subtasks),
            "completed": sum(1 for t in plan.subtasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in plan.subtasks if t.status == TaskStatus.FAILED),
            "subtasks": [t.model_dump() for t in plan.subtasks],
            "test_results": {k: v.model_dump() for k, v in test_results.items()},
            "merge_results": {k: v.model_dump() for k, v in merge_results.items()},
        }

        bus.emit("orchestrator:execution_complete", summary)
        logger.info(
            f"Execution finished: {summary['completed']}/{summary['total_tasks']} tasks completed successfully."
        )
        return summary
