"""Screen tools."""

import asyncio
import logging
import os
import tempfile
import uuid
from mcp_instance import mcp
from utils import winrt
from utils.shell import run_command, run_command_async

logger = logging.getLogger(__name__)

_MAX_OCR_CHARS = 8000


@mcp.tool(
    name="win_read_screen_text",
    annotations={"title": "Read Screen Text (OCR)", "readOnlyHint": True, "destructiveHint": False},
)
async def win_read_screen_text() -> str:
    """Capture the current screen and extract all visible text using the built-in Windows OCR engine."""
    def _impl() -> str:
        try:
            from PIL import ImageGrab
        except ImportError:
            return "Pillow is missing. Reinstall the extension, or run: pip install Pillow"

        path = os.path.join(tempfile.gettempdir(), f"jarvis_ocr_{uuid.uuid4().hex[:8]}.png")
        try:
            ImageGrab.grab().save(path)
            result = run_command(winrt.ocr_script(path), shell="powershell", timeout=60)
        except Exception as e:
            return f"OCR failed: {type(e).__name__}: {e}"
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        if "NO_OCR_LANGUAGE" in result["stderr"]:
            return (
                "Windows OCR has no language pack installed. Add one in Settings > Time & language > "
                "Language & region > (your language) > Language options > Optical character recognition."
            )
        if not result["success"]:
            return f"OCR failed: {result['stderr'] or 'no error text'}"

        text = result["stdout"].strip()
        if not text:
            return "Screen captured but no text detected."
        suffix = f"\n\n[Truncated, {len(text) - _MAX_OCR_CHARS} more chars]" if len(text) > _MAX_OCR_CHARS else ""
        return f"Screen text ({len(text)} chars):\n\n{text[:_MAX_OCR_CHARS]}{suffix}"

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_get_active_window",
    annotations={"title": "Get Active Window Info", "readOnlyHint": True, "destructiveHint": False},
)
async def win_get_active_window() -> str:
    """Get the title and process name of the currently focused window."""
    # $procId, NOT $pid — $PID is a read-only automatic variable in
    # PowerShell, so assigning to it fails and the lookup silently
    # resolves to the PowerShell helper process instead.
    ps_script = """
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinAPI {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
$hwnd = [WinAPI]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[WinAPI]::GetWindowText($hwnd, $sb, 256) | Out-Null
$title = $sb.ToString()
$procId = [uint32]0
[WinAPI]::GetWindowThreadProcessId($hwnd, [ref]$procId) | Out-Null
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
Write-Output "Title  : $title"
Write-Output "Process: $($proc.ProcessName)"
Write-Output "PID    : $procId"
"""
    result = await run_command_async(ps_script, shell="powershell", timeout=10)
    return result["stdout"] or result["stderr"] or "Could not get active window info."
