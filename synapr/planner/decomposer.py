"""Task Decomposer that breaks high-level goals into decoupled subtasks."""

import json
import re
from typing import Any

from synapr.core.logger import logger
from synapr.core.models import SubTask
from synapr.discovery.registry import EditorRegistry
from synapr.gateway.client import LLMGateway


class TaskDecomposer:
    """Decomposes complex feature goals into decoupled, parallelizable subtasks."""

    SYSTEM_PROMPT = (
        "You are the Principal Lead Architect of Synapr, an autonomous local development orchestrator.\n"
        "Your role is to take a high-level project goal or plan and break it down into decoupled, "
        "independent sub-tasks that can be executed in parallel isolated Git worktrees.\n"
        "Each task MUST have a clear file_scope to eliminate workspace collisions.\n"
        "Output MUST be valid JSON adhering to the following schema:\n"
        "{\n"
        '  "subtasks": [\n'
        "    {\n"
        '      "id": "task-slug-01",\n'
        '      "title": "Title of the task",\n'
        '      "description": "Short description of objectives",\n'
        '      "target_editor": "vscode" | "cursor" | "android_studio" | "windsurf" | "custom",\n'
        '      "file_scope": ["src/module_a/*", "tests/test_a.py"],\n'
        '      "dependencies": [],\n'
        '      "instructions": "Specific guidance for the coding agent/IDE",\n'
        '      "test_command": "pytest tests/test_a.py -v"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Ensure tasks are strictly decoupled with no overlapping write scopes."
    )

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        registry: EditorRegistry | None = None,
    ) -> None:
        self.gateway = gateway or LLMGateway()
        self.registry = registry or EditorRegistry()

    async def decompose(self, goal: str, context: str | None = None) -> list[SubTask]:
        """Decompose goal into decoupled subtasks."""
        user_prompt = f"Goal: {goal}\n"
        if context:
            user_prompt += f"Context:\n{context}\n"
        user_prompt += "Generate the decoupled task execution plan in JSON format."

        logger.info(f"Decomposing goal: {goal}")
        response = await self.gateway.complete(
            prompt=user_prompt,
            system_prompt=self.SYSTEM_PROMPT,
        )

        subtasks_data = self._extract_json(response.content)
        subtasks: list[SubTask] = []

        for item in subtasks_data.get("subtasks", []):
            # Resolve appropriate editor if target is not available or default
            raw_editor = item.get("target_editor", "vscode")
            resolved_editor = self.registry.resolve_best_editor(
                requested=raw_editor,
                task_tags=[item.get("title", ""), item.get("id", "")],
                file_scopes=item.get("file_scope", []),
            )

            task = SubTask(
                id=item.get("id", f"task-{len(subtasks)+1}"),
                title=item.get("title", "Untitled Subtask"),
                description=item.get("description", ""),
                target_editor=resolved_editor.id,
                file_scope=item.get("file_scope", []),
                dependencies=item.get("dependencies", []),
                instructions=item.get("instructions", ""),
                test_command=item.get("test_command"),
            )
            subtasks.append(task)

        logger.info(f"Decomposed into {len(subtasks)} decoupled subtasks")
        return subtasks

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Robust JSON extraction from LLM response (handling markdown code fences)."""
        # Try raw JSON first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting ```json ... ``` block
        code_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_fence:
            try:
                return json.loads(code_fence.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding outermost { ... }
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse JSON from decomposer. Using fallback single task.")
        return {
            "subtasks": [
                {
                    "id": "task-core-01",
                    "title": "Core Implementation",
                    "description": text[:200],
                    "target_editor": "vscode",
                    "file_scope": ["*"],
                    "dependencies": [],
                    "instructions": text,
                    "test_command": "pytest",
                }
            ]
        }
