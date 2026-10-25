"""
Finding top-level windows and their on-screen bounds (Win32, via ctypes).

Callers that use pixel coordinates should call use_physical_pixels() first on
the same thread, so positions match what the user sees on high-DPI screens.
"""

import ctypes
import sys
from typing import Optional

_DPI_AWARENESS_PER_MONITOR_V2 = -4
_DWMWA_EXTENDED_FRAME_BOUNDS = 9


def use_physical_pixels() -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(_DPI_AWARENESS_PER_MONITOR_V2))


def find_window(title: str) -> tuple[Optional[int], Optional[str], list[str]]:
    """Return (hwnd, title) for the best visible top-level window match, plus all visible titles.

    An exact (case-insensitive) title wins over a partial match. When nothing
    matches, hwnd and title are None and the list holds the visible titles.
    """
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_collect, 0)
    query = title.lower()
    for match in (lambda t: t.lower() == query, lambda t: query in t.lower()):
        for hwnd, t in found:
            if match(t):
                return hwnd, t, []
    return None, None, [t for _, t in found]


def not_found_message(title: str, visible: list[str]) -> str:
    sample = ", ".join(f"'{t}'" for t in visible[:15])
    return f"No visible window title contains '{title}'. Open windows include: {sample}"


def window_bounds(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the visible window frame, without the drop shadow."""
    from ctypes import wintypes
    rect = wintypes.RECT()
    hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        hwnd, _DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect))
    if hr != 0:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def is_minimized(hwnd: int) -> bool:
    return bool(ctypes.windll.user32.IsIconic(hwnd))
