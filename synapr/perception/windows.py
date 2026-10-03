"""Native and fallback discovery for visible IDE windows."""

from __future__ import annotations

import ctypes
import platform
from typing import Any

from synapr.perception.models import WindowInfo


class WindowInspector:
    """Discovers and inspects top-level GUI windows for running IDEs."""

    def __init__(self) -> None:
        self.is_windows = platform.system() == "Windows"

    def find_ide_windows(self, keywords: list[str] | None = None) -> list[WindowInfo]:
        """Find open windows matching target keywords (e.g. 'Code', 'Cursor', task id)."""
        targets = [k.lower() for k in (keywords or ["code", "cursor", "studio", "windsurf", "synapr"])]
        found: list[WindowInfo] = []

        if self.is_windows:
            found.extend(self._find_windows_win32(targets))
        else:
            # Unix / macOS fallback via wmctrl or ps
            found.extend(self._find_windows_generic(targets))

        return found

    def _find_windows_win32(self, targets: list[str]) -> list[WindowInfo]:
        """Enumerate top-level Windows GUI windows using User32 ctypes."""
        results: list[WindowInfo] = []
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]  # Windows-only API

        WNDENUMPROC = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]  # Windows-only API
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
        )

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

    def _find_windows_generic(self, targets: list[str]) -> list[WindowInfo]:
        """Generic fallback for non-Windows platforms."""
        return []
