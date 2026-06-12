"""Media control tools."""

import logging
from typing import Literal

from pydantic import Field
from mcp_instance import mcp
from utils.shell import run_command_async

logger = logging.getLogger(__name__)

MEDIA_KEYS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}


@mcp.tool(
    name="win_media_control",
    annotations={"title": "Control Media Playback", "readOnlyHint": False, "destructiveHint": False},
)
async def win_media_control(
    action: Literal["play_pause", "next", "previous", "stop"] = Field(..., description="Media action: 'play_pause', 'next', 'previous', or 'stop'. Works with Spotify, YouTube, VLC, etc."),
) -> str:
    """Send a system media key command. Works with any app that responds to media keys."""
    vk = MEDIA_KEYS[action]
    ps_script = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class MediaKey {{
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public static void Send(byte vk) {{
        keybd_event(vk, 0, 0, UIntPtr.Zero);
        keybd_event(vk, 0, 2, UIntPtr.Zero);
    }}
}}
"@
[MediaKey]::Send({vk})
Write-Output "Media: {action}"
"""
    result = await run_command_async(ps_script, shell="powershell", timeout=10)
    return result["stdout"] or f"Media key sent: {action}"
