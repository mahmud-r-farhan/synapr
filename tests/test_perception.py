"""Unit tests for optical perception and OCR context extractor."""

import asyncio

from synapr.perception.screen import (
    OCRContextEngine,
    OpticalPerceptionEngine,
    WindowInspector,
)


def test_ocr_pattern_parsing() -> None:
    """Test extracting compiler errors, warnings, and test results from logs."""
    ocr = OCRContextEngine()

    sample_log = (
        "Compiling backend v0.1.0\n"
        "warning: unused variable `temp`\n"
        "FAILED tests/test_api.py::test_auth - AssertionError: 401 != 200\n"
        "SyntaxError: invalid syntax on line 42\n"
    )

    parsed = ocr.parse_text(sample_log)
    assert len(parsed["errors"]) >= 2
    assert len(parsed["warnings"]) >= 1
    assert parsed["completion_detected"] is False

    success_log = "Ran 12 tests in 0.4s. 100% passed."
    parsed_success = ocr.parse_text(success_log)
    assert parsed_success["completion_detected"] is True


def test_window_inspector() -> None:
    """Test window inspector runs without raising exceptions."""
    inspector = WindowInspector()
    windows = inspector.find_ide_windows()
    assert isinstance(windows, list)


def test_optical_engine() -> None:
    """Test full optical perception cycle."""
    async def _test() -> None:
        engine = OpticalPerceptionEngine()
        res = await engine.inspect_task_window("task-non-existent-99")
        assert res.task_id == "task-non-existent-99"
        assert res.window_found is False

    asyncio.run(_test())
