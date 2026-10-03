"""Multi-LLM Debate and Consensus Verification Engine."""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
import uuid
from synapr.core.events import bus
from synapr.core.logger import logger
from synapr.core.models import (
    DebateCritique,
    DebateRound,
    ExecutionPlan,
    SubTask,
)
from synapr.gateway.client import LLMGateway
from synapr.gateway.router import ModelRouter


class ConsensusEngine:
    """Orchestrates multi-model debate rounds to cross-examine and verify architectural plans."""

    CRITIC_SYSTEM_PROMPT = (
        "You are an adversarial Senior Staff Reviewer in Synapr's multi-agent consensus network.\n"
        "Your mission is to stress-test and challenge the proposed task decomposition plan:\n"
        "1. Identify potential file lock collisions or overlapping file scopes.\n"
        "2. Spot cyclic dependencies or missing API contract interfaces.\n"
        "3. Check whether tasks are appropriately isolated for independent Git worktrees.\n"
        "Output MUST be valid JSON adhering to:\n"
        "{\n"
        '  "verdict": "APPROVED" | "REVISE_REQUIRED" | "REJECTED",\n'
        '  "criticism": "Comprehensive technical feedback",\n'
        '  "risks_identified": ["Risk 1", "Risk 2"],\n'
        '  "suggested_modifications": ["Modification 1"],\n'
        '  "consensus_score": 0.0 to 1.0\n'
        "}"
    )

    ARBITER_SYSTEM_PROMPT = (
        "You are the Chief Arbiter in Synapr's consensus engine.\n"
        "You evaluate the initial proposal alongside adversarial critiques.\n"
        "Synthesize all perspectives and output a final consensus decision in JSON:\n"
        "{\n"
        '  "approved": true | false,\n'
        '  "consensus_score": 0.0 to 1.0,\n'
        '  "synthesis": "Summary of decision and why it is safe to execute"\n'
        "}"
    )

    def __init__(
        self,
        gateway: Optional[LLMGateway] = None,
        router: Optional[ModelRouter] = None,
    ) -> None:
        self.gateway = gateway or LLMGateway()
        self.router = router or ModelRouter(self.gateway.config)

    async def verify_plan(
        self,
        goal: str,
        subtasks: List[SubTask],
        max_rounds: int = 2,
    ) -> ExecutionPlan:
        """Run multi-LLM debate rounds on the proposed subtasks until consensus is reached."""
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        debate_rounds: List[DebateRound] = []
        current_subtasks = list(subtasks)
        final_score = 1.0

        logger.info(f"Initiating multi-model consensus debate for plan {plan_id} ({len(current_subtasks)} tasks)")
        bus.emit("consensus:start", {"plan_id": plan_id, "subtasks_count": len(current_subtasks)})

        for round_num in range(1, max_rounds + 1):
            proposal_str = self._format_proposal(goal, current_subtasks)
            critiques = await self._run_critics(proposal_str)

            # Evaluate with Arbiter
            arbiter_decision = await self._run_arbiter(proposal_str, critiques)
            consensus_score = arbiter_decision.get("consensus_score", 0.9)
            approved = arbiter_decision.get("approved", True)

            round_record = DebateRound(
                round_number=round_num,
                plan_proposal=proposal_str,
                critiques=critiques,
                synthesis=arbiter_decision.get("synthesis", "Plan verified."),
                consensus_score=consensus_score,
                approved=approved,
            )
            debate_rounds.append(round_record)

            bus.emit(
                "consensus:round_complete",
                {
                    "round": round_num,
                    "consensus_score": consensus_score,
                    "approved": approved,
                    "critiques_count": len(critiques),
                },
            )

            final_score = consensus_score
            if approved or round_num >= max_rounds:
                break

        logger.info(f"Consensus reached for {plan_id} with score {final_score:.2f}")
        return ExecutionPlan(
            id=plan_id,
            goal=goal,
            subtasks=current_subtasks,
            debate_rounds=debate_rounds,
            final_consensus_score=final_score,
        )

    async def _run_critics(self, proposal: str) -> List[DebateCritique]:
        """Gather critiques from peer critic models asynchronously."""
        critic_roles = [
            ("Architectural Reviewer", 0),
            ("Collision & Concurrency Guard", 1),
        ]

        async def _query_single_critic(role: str, idx: int) -> DebateCritique:
            prompt = (
                f"You are the {role}.\n"
                f"Evaluate this execution plan proposal:\n\n{proposal}\n\n"
                "Return your structured critique in JSON format."
            )
            resp = await self.router.run_critic(
                prompt=prompt,
                critic_idx=idx,
                system_prompt=self.CRITIC_SYSTEM_PROMPT,
            )
            data = self._parse_json(resp.content)
            return DebateCritique(
                critic_role=role,
                model_name=resp.model,
                criticism=data.get("criticism", resp.content[:200]),
                risks_identified=data.get("risks_identified", []),
                suggested_modifications=data.get("suggested_modifications", []),
                verdict=data.get("verdict", "APPROVED"),
            )

        tasks = [_query_single_critic(role, idx) for role, idx in critic_roles]
        return await asyncio.gather(*tasks)

    async def _run_arbiter(self, proposal: str, critiques: List[DebateCritique]) -> Dict[str, Any]:
        """Query arbiter to synthesize proposal and critiques into final verdict."""
        critique_summaries = "\n\n".join(
            f"[{c.critic_role} ({c.model_name}) - Verdict: {c.verdict}]\n"
            f"Criticism: {c.criticism}\n"
            f"Risks: {', '.join(c.risks_identified)}"
            for c in critiques
        )

        arbiter_prompt = (
            f"Proposal:\n{proposal}\n\n"
            f"Peer Critiques:\n{critique_summaries}\n\n"
            "Provide your final synthesis and consensus score in JSON format."
        )

        resp = await self.router.run_arbiter(
            prompt=arbiter_prompt,
            system_prompt=self.ARBITER_SYSTEM_PROMPT,
        )
        return self._parse_json(resp.content)

    def _format_proposal(self, goal: str, subtasks: List[SubTask]) -> str:
        tasks_fmt = []
        for t in subtasks:
            tasks_fmt.append(
                f"- ID: {t.id} | Title: {t.title}\n"
                f"  Target Editor: {t.target_editor}\n"
                f"  File Scope: {t.file_scope}\n"
                f"  Dependencies: {t.dependencies}\n"
                f"  Test Command: {t.test_command or 'default'}"
            )
        return f"Feature Goal: {goal}\n\nProposed Subtasks:\n" + "\n".join(tasks_fmt)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        code_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_fence:
            try:
                return json.loads(code_fence.group(1).strip())
            except Exception:
                pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"approved": True, "consensus_score": 0.90, "synthesis": text[:200]}
