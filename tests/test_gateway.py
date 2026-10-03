"""Unit tests for Universal LLM Gateway and ModelRouter."""

import asyncio
from synapr.config import GatewayConfig
from synapr.gateway.client import LLMGateway
from synapr.gateway.router import ModelRouter


def test_mock_gateway_completion() -> None:
    """Test deterministic mock completions."""
    async def _test() -> None:
        cfg = GatewayConfig(default_provider="mock")
        gw = LLMGateway(cfg)

        # 1. Planner decomposition mock
        res_plan = await gw.complete("Decompose goal: Build REST API", system_prompt="planner")
        assert "subtasks" in res_plan.content
        assert res_plan.provider == "mock"

        # 2. Critic critique mock
        res_crit = await gw.complete("Debate this proposal", system_prompt="critic")
        assert "APPROVED" in res_crit.content or "verdict" in res_crit.content

        # 3. Conflict resolver mock
        res_res = await gw.complete("Resolve conflict in code", system_prompt="resolver")
        assert "def get_status" in res_res.content

    asyncio.run(_test())


def test_model_router() -> None:
    """Test role-based routing."""
    async def _test() -> None:
        cfg = GatewayConfig(default_provider="mock")
        router = ModelRouter(cfg)

        p_resp = await router.run_planner("Goal prompt")
        assert p_resp is not None

        c_resp = await router.run_critic("Critic prompt")
        assert c_resp is not None

        a_resp = await router.run_arbiter("Synthesis prompt")
        assert a_resp is not None

    asyncio.run(_test())
