"""Regex-based build and terminal status extraction."""

from __future__ import annotations

import re
from typing import Any


class OCRContextEngine:
    """Parses compilation errors, build logs, and test signals from OCR or terminal output."""

    # Regex patterns for build/terminal states
    ERROR_PATTERNS = [
        re.compile(r"(?:error|fatal|exception|failed|panic):\s*(.+)", re.IGNORECASE),
        re.compile(r"SyntaxError:\s*(.+)", re.IGNORECASE),
        re.compile(r"TypeError:\s*(.+)", re.IGNORECASE),
        re.compile(r"NameError:\s*(.+)", re.IGNORECASE),
        re.compile(r"ImportError:\s*(.+)", re.IGNORECASE),
        re.compile(r"error\[E\d+\]:\s*(.+)", re.IGNORECASE),  # Rust
        re.compile(r"FAILED\s+tests/[^\s]+", re.IGNORECASE),  # pytest
    ]

    WARNING_PATTERNS = [
        re.compile(r"(?:warning|warn):\s*(.+)", re.IGNORECASE),
        re.compile(r"DeprecationWarning:\s*(.+)", re.IGNORECASE),
    ]

    SUCCESS_PATTERNS = [
        re.compile(r"(?:passed|success|build\s+successful|tests\s+passed)", re.IGNORECASE),
        re.compile(r"\b100%\s+passed\b", re.IGNORECASE),
    ]

    def parse_text(self, raw_text: str) -> dict[str, Any]:
        """Extract structured errors, warnings, and completion state from text."""
        errors: list[str] = []
        warnings: list[str] = []
        is_success = False

        for line in raw_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            for p in self.ERROR_PATTERNS:
                m = p.search(line_str)
                if m:
                    errors.append(line_str)
                    break

            for p in self.WARNING_PATTERNS:
                m = p.search(line_str)
                if m:
                    warnings.append(line_str)
                    break

            for p in self.SUCCESS_PATTERNS:
                if p.search(line_str):
                    is_success = True

        return {
            "errors": errors[:10],
            "warnings": warnings[:10],
            "completion_detected": is_success and len(errors) == 0,
        }
