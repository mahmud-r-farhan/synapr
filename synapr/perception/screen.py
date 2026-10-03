"""Backward-compatible facade for perception model and engine components."""

from synapr.perception.capture import ScreenCapturer
from synapr.perception.engine import OpticalPerceptionEngine
from synapr.perception.models import PerceptionResult, WindowInfo
from synapr.perception.ocr import OCRContextEngine
from synapr.perception.windows import WindowInspector

__all__ = [
    "OCRContextEngine",
    "OpticalPerceptionEngine",
    "PerceptionResult",
    "ScreenCapturer",
    "WindowInfo",
    "WindowInspector",
]
