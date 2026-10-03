"""Main coordinator wiring Synapr subsystems into a cohesive swarm OS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from synapr.config import SynaprConfig
from synapr.core.config_service import get_config_service
from synapr.core.events import bus  # noqa: F401 - preserve the former module export
from synapr.core.logger import logger
from synapr.core.models import EditorInfo, ExecutionPlan, WorktreeInstance
from synapr.discovery.detector import EditorDetector
from synapr.discovery.registry import EditorRegistry
from synapr.dispatcher.bridge import TaskDispatcher
from synapr.gateway.client import LLMGateway
from synapr.gateway.router import ModelRouter
from synapr.merger.pipeline import TestPipeline
from synapr.merger.self_healing import SelfHealingResolver
from synapr.orchestrator_execution import PlanExecutionMixin, Tuple_TaskWorktree  # noqa: F401
from synapr.perception.screen import OpticalPerceptionEngine
from synapr.planner.consensus import ConsensusEngine
from synapr.planner.decomposer import TaskDecomposer
from synapr.worktree.manager import WorktreeManager


class SynaprOrchestrator(PlanExecutionMixin):
    """Master operating coordinator for autonomous multi-IDE software development."""
    def __init__(self, config: SynaprConfig | None = None, repo_root: str | None = None) -> None:
        self.config = config or get_config_service().config
        self.repo_root = Path(repo_root or ".").resolve()

        # Active state (declared before sub-systems so apply_config can reuse them)
        self.active_plan: ExecutionPlan | None = None
        self.active_worktrees: dict[str, WorktreeInstance] = {}
        self.task_results: dict[str, dict[str, Any]] = {}

        self._build_subsystems()

    def _build_subsystems(self) -> None:
        """(Re)create every sub-system from the current configuration."""
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

    def apply_config(self, config: SynaprConfig) -> None:
        """Hot-swap the configuration and rebuild sub-systems without losing state.

        Called by the visual configurator so settings edited in the dashboard take
        effect immediately, without restarting the process.
        """
        self.config = config
        self._build_subsystems()
        logger.info(
            "Configuration reloaded: provider="
            f"{config.gateway.default_provider}, worktree_root={config.worktree.worktree_root}"
        )

    def get_installed_editors(self) -> list[EditorInfo]:
        """Return list of detected development tools."""
        return self.registry.list_available()

    async def plan_goal(self, goal: str, context: str | None = None) -> ExecutionPlan:
        """Decompose a high-level goal and verify through multi-LLM debate."""
        logger.info(f"--- [Phase 1: Planning & Decomposition] --- Goal: '{goal}'")
        subtasks = await self.decomposer.decompose(goal, context)

        logger.info("--- [Phase 2: Multi-LLM Consensus Debate] ---")
        plan = await self.consensus.verify_plan(goal, subtasks)
        self.active_plan = plan
        return plan

    async def run_goal(
        self,
        goal: str,
        context: str | None = None,
        dry_run: bool = False,
        launch_editors: bool = True,
    ) -> dict[str, Any]:
        """Execute end-to-end swarm loop from user goal to merged code."""
        plan = await self.plan_goal(goal, context)
        return await self.execute_plan(plan, dry_run=dry_run, launch_editors=launch_editors)
