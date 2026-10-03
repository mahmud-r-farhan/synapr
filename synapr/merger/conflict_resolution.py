"""LLM-assisted cleanup and validation of conflicted file contents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from synapr.core.logger import logger

if TYPE_CHECKING:
    from synapr.gateway.router import ModelRouter


class ConflictResolutionMixin:
    router: ModelRouter
    RESOLVER_SYSTEM_PROMPT: str

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
