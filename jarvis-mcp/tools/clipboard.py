"""Clipboard tools."""

import logging
from pydantic import Field
from mcp_instance import mcp
from utils.shell import run_command

logger = logging.getLogger(__name__)


@mcp.tool(
    name="win_get_clipboard",
    annotations={"title": "Get Clipboard Contents", "readOnlyHint": True, "destructiveHint": False},
)
async def win_get_clipboard() -> str:
    """Read and return the current text content of the Windows clipboard."""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return "Clipboard is empty or contains non-text content."
        preview = text[:5000]
        suffix = f"\n\n[... {len(text) - 5000} more chars truncated]" if len(text) > 5000 else ""
        return f"Clipboard ({len(text)} chars):\n\n{preview}{suffix}"
    except ImportError:
        pass
    result = run_command("Get-Clipboard", shell="powershell", timeout=5)
    return f"Clipboard:\n\n{result['stdout']}" if result["success"] and result["stdout"] else "Clipboard is empty."


@mcp.tool(
    name="win_set_clipboard",
    annotations={"title": "Set Clipboard Contents", "readOnlyHint": False, "destructiveHint": False},
)
async def win_set_clipboard(
    text: str = Field(..., description="Text to put on the clipboard."),
) -> str:
    """Write text to the Windows clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        preview = text[:100] + ("..." if len(text) > 100 else "")
        return f"Clipboard set ({len(text)} chars): {preview}"
    except ImportError:
        pass
    escaped = text.replace("'", "''")
    result = run_command(f"Set-Clipboard -Value '{escaped}'", shell="powershell", timeout=5)
    if result["success"]:
        preview = text[:100] + ("..." if len(text) > 100 else "")
        return f"Clipboard set ({len(text)} chars): {preview}"
    return f"Failed: {result['stderr']}"
