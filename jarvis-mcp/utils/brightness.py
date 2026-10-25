"""
Display brightness.

Laptop and tablet screens expose brightness through WMI
(WmiMonitorBrightness). External monitors don't; they speak DDC/CI, which
Windows exposes through dxva2's monitor configuration API. get/set try WMI
first and fall back to DDC/CI, so both kinds of display work. Some monitors
have DDC/CI switched off in their own on-screen menu.
"""

import ctypes
import sys

from utils.shell import run_command

_WMI_GET = "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1).CurrentBrightness"


def _wmi_set(level: int) -> str:
    return (f"Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop | "
            f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={level}}} -ErrorAction Stop | Out-Null; 'ok'")


def _physical_monitors():
    """Yield (handle, description) for every physical monitor; caller must not keep handles."""
    from ctypes import wintypes

    class PHYSICAL_MONITOR(ctypes.Structure):
        _fields_ = [("handle", wintypes.HANDLE), ("description", wintypes.WCHAR * 128)]

    user32, dxva2 = ctypes.windll.user32, ctypes.windll.dxva2
    hmons = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)(
        lambda h, _dc, _r, _l: hmons.append(h) or True)
    user32.EnumDisplayMonitors(None, None, proc, 0)

    for hmon in hmons:
        count = wintypes.DWORD()
        if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)) or not count.value:
            continue
        arr = (PHYSICAL_MONITOR * count.value)()
        if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr):
            continue
        try:
            for m in arr:
                yield m.handle, m.description
        finally:
            dxva2.DestroyPhysicalMonitors(count.value, arr)


def get() -> list[tuple[str, int]]:
    """[(display name, brightness 0-100)] for every display that reports it."""
    out = []
    r = run_command(_WMI_GET, shell="powershell", timeout=15)
    if r["success"] and r["stdout"].strip().isdigit():
        out.append(("Built-in display", int(r["stdout"].strip())))
    if sys.platform == "win32":
        from ctypes import wintypes
        for handle, desc in _physical_monitors():
            lo, cur, hi = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            if ctypes.windll.dxva2.GetMonitorBrightness(handle, ctypes.byref(lo), ctypes.byref(cur), ctypes.byref(hi)):
                span = max(hi.value - lo.value, 1)
                out.append((desc or "Monitor", round((cur.value - lo.value) * 100 / span)))
    return out


def set_all(level: int) -> list[str]:
    """Set every display that supports it to level (0-100). Returns the names that changed."""
    changed = []
    r = run_command(_wmi_set(level), shell="powershell", timeout=15)
    if r["success"] and "ok" in r["stdout"]:
        changed.append("Built-in display")
    if sys.platform == "win32":
        from ctypes import wintypes
        for handle, desc in _physical_monitors():
            lo, cur, hi = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            if not ctypes.windll.dxva2.GetMonitorBrightness(handle, ctypes.byref(lo), ctypes.byref(cur), ctypes.byref(hi)):
                continue
            value = lo.value + round((hi.value - lo.value) * level / 100)
            if ctypes.windll.dxva2.SetMonitorBrightness(handle, value):
                changed.append(desc or "Monitor")
    return changed
