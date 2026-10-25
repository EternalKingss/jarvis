"""
Desktop tools.

win_arrange_window : Minimize, maximize, restore, snap, center, or move/resize a window
win_notify         : Show a Windows toast notification
"""

import asyncio
import ctypes
import logging
import sys
from typing import Literal, Optional

from pydantic import Field
from mcp_instance import mcp
from utils.shell import run_command_async
from utils.winrt import toast_script

logger = logging.getLogger(__name__)

_SW_MAXIMIZE, _SW_MINIMIZE, _SW_RESTORE = 3, 6, 9
_SWP_NOZORDER, _SWP_NOACTIVATE = 0x0004, 0x0010
_MONITOR_DEFAULTTONEAREST = 2
_DPI_AWARENESS_PER_MONITOR_V2 = -4


def _find_window(title: str) -> tuple[Optional[int], Optional[str], list[str]]:
    """Return (hwnd, title) for the best visible top-level window match, plus all visible titles."""
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


def _work_area(hwnd: int) -> tuple[int, int, int, int]:
    """Usable area (left, top, right, bottom) of the monitor the window is on, excluding the taskbar."""
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    monitor = ctypes.windll.user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
    ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info))
    r = info.rcWork
    return r.left, r.top, r.right, r.bottom


@mcp.tool(
    name="win_arrange_window",
    annotations={"title": "Arrange Window", "readOnlyHint": False, "destructiveHint": False},
)
async def win_arrange_window(
    window_title: str = Field(..., description="Exact or partial title of the window. E.g. 'Notepad', 'Chrome', 'Downloads'."),
    action: Literal["minimize", "maximize", "restore", "snap_left", "snap_right", "center", "move_resize"] = Field(
        ..., description="What to do. snap_left/snap_right fill half the screen; move_resize uses x, y, width, height."),
    x: Optional[int] = Field(default=None, description="move_resize only: left edge in pixels."),
    y: Optional[int] = Field(default=None, description="move_resize only: top edge in pixels."),
    width: Optional[int] = Field(default=None, description="move_resize only: width in pixels.", ge=100),
    height: Optional[int] = Field(default=None, description="move_resize only: height in pixels.", ge=100),
) -> str:
    """Minimize, maximize, restore, snap to the left or right half of the screen, center, or move and resize a window."""
    if sys.platform != "win32":
        return "Window management is only available on Windows."

    def _impl() -> str:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        # Physical pixels, so coordinates match what the user sees on high-DPI screens.
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(_DPI_AWARENESS_PER_MONITOR_V2))

        hwnd, title, visible = _find_window(window_title)
        if hwnd is None:
            sample = ", ".join(f"'{t}'" for t in visible[:15])
            return f"No visible window title contains '{window_title}'. Open windows include: {sample}"

        if action in ("minimize", "maximize", "restore"):
            user32.ShowWindow(hwnd, {"minimize": _SW_MINIMIZE, "maximize": _SW_MAXIMIZE, "restore": _SW_RESTORE}[action])
            return f"{action.capitalize()}d '{title}'."

        left, top, right, bottom = _work_area(hwnd)
        area_w, area_h = right - left, bottom - top
        if action == "snap_left":
            rect = (left, top, area_w // 2, area_h)
        elif action == "snap_right":
            rect = (left + area_w // 2, top, area_w - area_w // 2, area_h)
        else:
            cur = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(cur))
            cur_w, cur_h = cur.right - cur.left, cur.bottom - cur.top
            if action == "center":
                w, h = min(cur_w, area_w), min(cur_h, area_h)
                rect = (left + (area_w - w) // 2, top + (area_h - h) // 2, w, h)
            else:
                if all(v is None for v in (x, y, width, height)):
                    return "move_resize needs at least one of x, y, width or height."
                rect = (cur.left if x is None else x, cur.top if y is None else y,
                        cur_w if width is None else width, cur_h if height is None else height)

        user32.ShowWindow(hwnd, _SW_RESTORE)  # a maximized window ignores SetWindowPos
        if not user32.SetWindowPos(hwnd, None, *rect, _SWP_NOZORDER | _SWP_NOACTIVATE):
            return f"Could not move '{title}' (error {ctypes.GetLastError()}). Windows running as administrator can't be moved by a normal process."
        return f"Moved '{title}' to x={rect[0]}, y={rect[1]}, {rect[2]}x{rect[3]}."

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_notify",
    annotations={"title": "Show Notification", "readOnlyHint": False, "destructiveHint": False},
)
async def win_notify(
    title: str = Field(..., description="Notification heading. Keep it short.", max_length=100),
    message: str = Field(..., description="Notification body text.", max_length=500),
) -> str:
    """Show a Windows desktop notification (toast) to the user, for a reminder or when something finishes."""
    result = await run_command_async(toast_script(title, message), shell="powershell", timeout=15)
    if result["success"] and "shown" in result["stdout"]:
        return f"Notification shown: {title}"
    return (
        f"Could not show the notification: {result['stderr'] or 'no error text'}. "
        "Check that notifications are on in Settings > System > Notifications."
    )
