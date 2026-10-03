"""Deterministic offline completion behavior."""

from __future__ import annotations

import asyncio
import json

from synapr.gateway.models import GatewayResponse


class GatewayMockMixin:
    async def _complete_mock(
        self, prompt: str, system_prompt: str | None, model: str
    ) -> GatewayResponse:
        """Deterministic, rich offline mock responses for local offline air-gap workflows and tests."""
        await asyncio.sleep(0.05)  # Simulate non-blocking async dispatch
        lower_prompt = prompt.lower()
        lower_sys = (system_prompt or "").lower()

        # 1. Goal Decomposition & Subtask Planning
        if "decompose" in lower_prompt or "subtask" in lower_prompt or "planner" in lower_sys or "architect" in lower_sys or "goal:" in lower_prompt:
            mock_plan = {
                "subtasks": [
                    {
                        "id": "task-api-01",
                        "title": "Backend API Service Implementation",
                        "description": "Develop core REST API endpoints and data validation models.",
                        "target_editor": "vscode",
                        "file_scope": ["src/api/*", "tests/test_api.py"],
                        "dependencies": [],
                        "instructions": "Implement FastAPI router endpoints with Pydantic validation.",
                        "test_command": "pytest tests/test_api.py -v",
                    },
                    {
                        "id": "task-ui-02",
                        "title": "Frontend Interface & Client Integration",
                        "description": "Construct reactive client dashboard and visual state bindings.",
                        "target_editor": "cursor",
                        "file_scope": ["src/ui/*", "static/*"],
                        "dependencies": ["task-api-01"],
                        "instructions": "Build responsive UI views connecting to the API endpoints.",
                        "test_command": "npm test || echo 'UI tests passed'",
                    },
                ]
            }
            return GatewayResponse(
                content=json.dumps(mock_plan, indent=2),
                model=model,
                provider="mock",
                tokens_used=180,
            )

        # 2. Debate / Architectural Critique
        elif "critic" in lower_prompt or "debate" in lower_prompt or "critique" in lower_sys:
            mock_critique = {
                "verdict": "APPROVED",
                "criticism": "The proposed task breakdown establishes clean architectural decoupling. Worktree scopes are non-overlapping.",
                "risks_identified": [
                    "Ensure API interface schemas are frozen before UI integration completes.",
                    "Verify CORS policies for local dev environment.",
                ],
                "suggested_modifications": [
                    "Add automated schema export step in task-api-01.",
                ],
                "consensus_score": 0.95,
            }
            return GatewayResponse(
                content=json.dumps(mock_critique, indent=2),
                model=model,
                provider="mock",
                tokens_used=140,
            )

        # 3. Consensus Synthesis / Arbiter
        elif "synthesis" in lower_prompt or "arbiter" in lower_prompt or "consensus" in lower_sys:
            mock_synthesis = {
                "consensus_score": 0.96,
                "approved": True,
                "summary": "Subtasks verified. Risk mitigations accepted. Ready for worktree isolation.",
            }
            return GatewayResponse(
                content=json.dumps(mock_synthesis, indent=2),
                model=model,
                provider="mock",
                tokens_used=95,
            )

        # 4. Self-Healing Merge Conflict Resolution
        elif "conflict" in lower_prompt or "merge" in lower_prompt or "resolver" in lower_sys:
            # Clean conflict-free output
            resolved_text = (
                "# Self-healed integration code\n"
                "def get_status():\n"
                "    return {'status': 'healthy', 'version': '1.0.0'}\n"
            )
            return GatewayResponse(
                content=resolved_text,
                model=model,
                provider="mock",
                tokens_used=110,
            )

        # Generic default response
        return GatewayResponse(
            content=f"[Synapr Mock Agent] Processed successfully for model {model}.",
            model=model,
            provider="mock",
            tokens_used=42,
        )
