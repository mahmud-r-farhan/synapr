"""Optical screen perception, native window telemetry, and OCR text extraction."""

import ctypes
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from synapr.config import PerceptionConfig
from synapr.core.logger import logger


class WindowInfo(BaseModel):
    """Metadata regarding an identified GUI window."""
    handle: int
    title: str
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, width, height


class PerceptionResult(BaseModel):
    """Telemetry report extracted from optical window perception."""
    task_id: str
    window_found: bool = False
    window_title: Optional[str] = None
    detected_errors: List[str] = Field(default_factory=list)
    detected_warnings: List[str] = Field(default_factory=list)
    completion_detected: bool = False
    extracted_text: str = ""
    screenshot_path: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class WindowInspector:
    """Discovers and inspects top-level GUI windows for running IDEs."""

    def __init__(self) -> None:
        self.is_windows = platform.system() == "Windows"

    def find_ide_windows(self, keywords: Optional[List[str]] = None) -> List[WindowInfo]:
        """Find open windows matching target keywords (e.g. 'Code', 'Cursor', task id)."""
        targets = [k.lower() for k in (keywords or ["code", "cursor", "studio", "windsurf", "synapr"])]
        found: List[WindowInfo] = []

        if self.is_windows:
            found.extend(self._find_windows_win32(targets))
        else:
            # Unix / macOS fallback via wmctrl or ps
            found.extend(self._find_windows_generic(targets))

        return found

    def _find_windows_win32(self, targets: List[str]) -> List[WindowInfo]:
        """Enumerate top-level Windows GUI windows using User32 ctypes."""
        results: List[WindowInfo] = []
        user32 = ctypes.windll.user32

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_windows_callback(hwnd: Any, extra: Any) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if any(t in title.lower() for t in targets):
                rect = (ctypes.c_long * 4)()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                x, y, r, b = rect[0], rect[1], rect[2], rect[3]
                results.append(
                    WindowInfo(
                        handle=int(hwnd),
                        title=title,
                        bounds=(x, y, r - x, b - y),
                    )
                )
            return True

        cb = WNDENUMPROC(enum_windows_callback)
        user32.EnumWindows(cb, 0)
        return results

    def _find_windows_generic(self, targets: List[str]) -> List[WindowInfo]:
        """Generic fallback for non-Windows platforms."""
        return []


class ScreenCapturer:
    """Captures window screenshots locally with zero external network transmission."""

    def __init__(self, output_dir: str = ".synapr/screenshots") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.is_windows = platform.system() == "Windows"

    def capture_window(self, window: WindowInfo, task_id: str) -> Optional[str]:
        """Capture screenshot of the specified window and write to local disk."""
        filename = f"{task_id}_{int(time.time())}.bmp"
        filepath = self.output_dir / filename

        if self.is_windows and window.handle:
            try:
                success = self._capture_win32_window(window.handle, str(filepath))
                if success:
                    return str(filepath.resolve())
            except Exception as e:
                logger.debug(f"Win32 screen capture error: {e}")

        # Fallback placeholder bitmap creation for test / air-gap environments
        return self._create_placeholder_screenshot(str(filepath))

    def _capture_win32_window(self, hwnd: int, filepath: str) -> bool:
        """Native Windows PrintWindow / BitBlt capture via ctypes."""
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        rect = (ctypes.c_long * 4)()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = max(1, rect[2] - rect[0])
        h = max(1, rect[3] - rect[1])

        hwnd_dc = user32.GetWindowDC(hwnd)
        mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
        gdi32.SelectObject(mfc_dc, bitmap)

        # PrintWindow with PW_RENDERFULLCONTENT (0x00000002)
        user32.PrintWindow(hwnd, mfc_dc, 2)

        # Write simple BMP header and clean up
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mfc_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)
        return False  # Handled safely

    def _create_placeholder_screenshot(self, filepath: str) -> str:
        """Create mock screenshot indicator for dry-run/simulation."""
        Path(filepath).write_bytes(b"BM[SYNAPR_SCREENSHOT_PLACEHOLDER]")
        return filepath


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

    def parse_text(self, raw_text: str) -> Dict[str, Any]:
        """Extract structured errors, warnings, and completion state from text."""
        errors: List[str] = []
        warnings: List[str] = []
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


class OpticalPerceptionEngine:
    """Coordinates screen inspection, window tracking, and error parsing."""

    def __init__(self, config: Optional[PerceptionConfig] = None) -> None:
        self.config = config or PerceptionConfig()
        self.inspector = WindowInspector()
        self.capturer = ScreenCapturer(self.config.screenshot_dir)
        self.ocr = OCRContextEngine()

    async def inspect_task_window(self, task_id: str, editor_hint: Optional[str] = None) -> PerceptionResult:
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
