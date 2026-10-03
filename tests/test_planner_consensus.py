"""Unit tests for task decomposition and multi-LLM debate consensus."""

import asyncio

from synapr.config import GatewayConfig
from synapr.discovery.registry import EditorRegistry
from synapr.gateway.client import LLMGateway
from synapr.gateway.router import ModelRouter
from synapr.planner.consensus import ConsensusEngine
from synapr.planner.decomposer import TaskDecomposer


def test_task_decomposition() -> None:
    """Test breaking high-level goal into decoupled subtasks."""
    async def _test() -> None:
        gw = LLMGateway(GatewayConfig(default_provider="mock"))
        registry = EditorRegistry()
        decomposer = TaskDecomposer(gw, registry)

        subtasks = await decomposer.decompose("Build authentication layer")
        assert len(subtasks) >= 2
        assert subtasks[0].id
        assert subtasks[0].title
        assert subtasks[0].target_editor

    asyncio.run(_test())


def test_consensus_debate() -> None:
    """Test multi-model debate rounds and arbiter verification."""
    async def _test() -> None:
        gw = LLMGateway(GatewayConfig(default_provider="mock"))
        router = ModelRouter(gw.config)
        engine = ConsensusEngine(gw, router)
        decomposer = TaskDecomposer(gw)

        subtasks = await decomposer.decompose("Build data pipeline")
        plan = await engine.verify_plan("Build data pipeline", subtasks, max_rounds=2)

        assert plan.id.startswith("plan-")
        assert len(plan.subtasks) >= 2
        assert len(plan.debate_rounds) >= 1
        assert plan.final_consensus_score > 0.0

    asyncio.run(_test())
