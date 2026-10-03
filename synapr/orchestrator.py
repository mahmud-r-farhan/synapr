"""Main Orchestrator coordinating all Synapr sub-systems into a cohesive swarm OS."""

import asyncio
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from synapr.config import SynaprConfig
from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.core.models import (
    EditorInfo,
    ExecutionPlan,
    MergeResult,
    SubTask,
    TaskStatus,
    TestResult,
    WorktreeInstance,
)
from synapr.discovery.detector import EditorDetector
from synapr.discovery.registry import EditorRegistry
from synapr.dispatcher.bridge import TaskDispatcher
from synapr.gateway.client import LLMGateway
from synapr.gateway.router import ModelRouter
from synapr.merger.pipeline import TestPipeline
from synapr.merger.self_healing import SelfHealingResolver
from synapr.perception.screen import OpticalPerceptionEngine, PerceptionResult
from synapr.planner.consensus import ConsensusEngine
from synapr.planner.decomposer import TaskDecomposer
from synapr.worktree.manager import WorktreeManager


class SynaprOrchestrator:
    """Master operating coordinator for autonomous multi-IDE software development."""

    def __init__(self, config: Optional[SynaprConfig] = None, repo_root: Optional[str] = None) -> None:
        self.config = config or SynaprConfig.load()
        self.repo_root = Path(repo_root or ".").resolve()

        # Initialize sub-systems
        self.gateway = LLMGateway(self.config.gateway)
        self.router = ModelRouter(self.config.gateway)

        self.detector = EditorDetector(self.config.editor.custom_editor_paths)
        self.registry = EditorRegistry(self.detector)

        self.worktree_mgr = WorktreeManager(str(self.repo_root), self.config.worktree)
        self.decomposer = TaskDecomposer(self.gateway, self.registry)
        self.consensus = ConsensusEngine(self.gateway, self.router)
        self.dispatcher = TaskDispatcher(self.registry)
        self.perception = OpticalPerceptionEngine(self.config.perception)
        self.test_pipeline = TestPipeline(self.config.pipeline.default_test_command)
        self.resolver = SelfHealingResolver(str(self.repo_root), self.router, self.test_pipeline)

        # Active state
        self.active_plan: Optional[ExecutionPlan] = None
        self.active_worktrees: Dict[str, WorktreeInstance] = {}
        self.task_results: Dict[str, Dict[str, Any]] = {}

    def get_installed_editors(self) -> List[EditorInfo]:
        """Return list of detected development tools."""
        return self.registry.list_available()

    async def plan_goal(self, goal: str, context: Optional[str] = None) -> ExecutionPlan:
        """Decompose a high-level goal and verify through multi-LLM debate."""
        logger.info(f"--- [Phase 1: Planning & Decomposition] --- Goal: '{goal}'")
        subtasks = await self.decomposer.decompose(goal, context)

        logger.info("--- [Phase 2: Multi-LLM Consensus Debate] ---")
        plan = await self.consensus.verify_plan(goal, subtasks)
        self.active_plan = plan
        return plan

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        dry_run: bool = False,
        launch_editors: bool = True,
    ) -> Dict[str, Any]:
        """Execute a verified plan across isolated worktrees, run tests, and merge."""
        logger.info(f"--- [Phase 3: Worktree Provisioning & Dispatch] --- (Plan: {plan.id})")
        bus.emit("orchestrator:execution_started", {"plan_id": plan.id, "tasks": len(plan.subtasks)})

        base_branch = await self.worktree_mgr.detect_base_branch()
        tasks_to_run = plan.subtasks

        # 1. Provision worktrees and dispatch IDEs in parallel
        provisioned: List[Tuple_TaskWorktree] = []
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
            for task, wt in provisioned:
                perception_res = await self.perception.inspect_task_window(task.id, task.target_editor)
                logger.debug(
                    f"Perception report for {task.id}: found={perception_res.window_found}, "
                    f"errors={len(perception_res.detected_errors)}"
                )

        # 3. Test verification per worktree
        logger.info("--- [Phase 5: Automated Build & Test Suites] ---")
        test_results: Dict[str, TestResult] = {}
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
        merge_results: Dict[str, MergeResult] = {}
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

    async def run_goal(
        self,
        goal: str,
        context: Optional[str] = None,
        dry_run: bool = False,
        launch_editors: bool = True,
    ) -> Dict[str, Any]:
        """Execute end-to-end swarm loop from user goal to merged code."""
        plan = await self.plan_goal(goal, context)
        return await self.execute_plan(plan, dry_run=dry_run, launch_editors=launch_editors)


Tuple_TaskWorktree = tuple[SubTask, WorktreeInstance]
