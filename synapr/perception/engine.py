"""Coordination of window selection, capture, and telemetry parsing."""

from __future__ import annotations

from synapr.config import PerceptionConfig
from synapr.perception.capture import ScreenCapturer
from synapr.perception.models import PerceptionResult
from synapr.perception.ocr import OCRContextEngine
from synapr.perception.windows import WindowInspector


class OpticalPerceptionEngine:
    """Coordinates screen inspection, window tracking, and error parsing."""

    def __init__(self, config: PerceptionConfig | None = None) -> None:
        self.config = config or PerceptionConfig()
        self.inspector = WindowInspector()
        self.capturer = ScreenCapturer(self.config.screenshot_dir)
        self.ocr = OCRContextEngine()

    async def inspect_task_window(self, task_id: str, editor_hint: str | None = None) -> PerceptionResult:
        """Inspect the open IDE window corresponding to a task."""
        keywords = [task_id, editor_hint or "code", "synapr"]
        windows = self.inspector.find_ide_windows(keywords)

        if not windows:
            return PerceptionResult(
                task_id=task_id,
                window_found=False,
                extracted_text="No active IDE window matched task criteria.",
            )

        target_window = windows[0]
        shot_path = None
        if self.config.capture_screenshots:
            shot_path = self.capturer.capture_window(target_window, task_id)

        # Parse window title for common compile/status signals
        parsed = self.ocr.parse_text(target_window.title)

        return PerceptionResult(
            task_id=task_id,
            window_found=True,
            window_title=target_window.title,
            detected_errors=parsed["errors"],
            detected_warnings=parsed["warnings"],
            completion_detected=parsed["completion_detected"],
            extracted_text=f"Window Title: {target_window.title}",
            screenshot_path=shot_path,
        )
