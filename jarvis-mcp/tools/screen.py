"""Screen tools."""

import asyncio
import logging
import os
from mcp_instance import mcp
from utils.shell import run_command_async

logger = logging.getLogger(__name__)


@mcp.tool(
    name="win_read_screen_text",
    annotations={"title": "Read Screen Text (OCR)", "readOnlyHint": True, "destructiveHint": False},
)
async def win_read_screen_text() -> str:
    """Capture the current screen and extract all visible text using OCR (Tesseract)."""
    def _impl() -> str:
        try:
            from PIL import ImageGrab
            import pytesseract

            for tp in [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            ]:
                if os.path.exists(tp):
                    pytesseract.pytesseract.tesseract_cmd = tp
                    break

            img = ImageGrab.grab()
            text = pytesseract.image_to_string(img).strip()
            if not text:
                return "Screen captured but no text detected."
            return f"Screen text ({len(text)} chars):\n\n{text[:8000]}" + (
                f"\n\n[Truncated — {len(text) - 8000} more chars]" if len(text) > 8000 else ""
            )
        except ImportError as e:
            return (
                f"Missing dependency: {e}\n"
                "Install: pip install Pillow pytesseract\n"
                "Then install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
            )
        except Exception as e:
            return f"OCR failed: {e}"

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
