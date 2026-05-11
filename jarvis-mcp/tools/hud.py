"""
HUD control tools — Claude can push UI events to the Unity HUD.

win_send_hud_message      : Display text/notification in the Unity HUD
win_trigger_hud_animation : Trigger a named animation on the arc reactor ring
win_get_voice_status      : Return current voice engine state and HUD connection status
"""

import logging
import time
from typing import Literal

from pydantic import Field
from mcp_instance import mcp

logger = logging.getLogger(__name__)


def _pipe():
    from bridge.pipe_server import pipe_server
    return pipe_server


def _voice():
    from bridge.voice import voice_engine
    return voice_engine


@mcp.tool(
    name="win_send_hud_message",
    annotations={"title": "Send HUD Message", "readOnlyHint": False, "destructiveHint": False},
)
async def win_send_hud_message(
    message: str = Field(..., description="Text to display in the Jarvis Unity HUD overlay."),
    message_type: Literal["info", "warning", "alert", "success"] = Field(
        default="info",
        description="Visual style: 'info' (blue), 'warning' (amber), 'alert' (red), 'success' (green)",
    ),
    duration_ms: int = Field(
        default=5000,
        description="How long to show the message in milliseconds (default 5000).",
        ge=500,
        le=30000,
    ),
) -> str:
    """Send a text notification to the Jarvis Unity HUD overlay."""
    pipe = _pipe()
    if not pipe.is_connected:
        return "HUD is not connected (Unity app not running)."
    pipe.send({
        "type":         "hud_message",
        "message":      message,
        "message_type": message_type,
        "duration_ms":  duration_ms,
        "timestamp":    time.time(),
    })
    preview = message[:60] + ("..." if len(message) > 60 else "")
    return f"HUD message sent [{message_type}]: '{preview}'"


@mcp.tool(
    name="win_trigger_hud_animation",
    annotations={"title": "Trigger HUD Animation", "readOnlyHint": False, "destructiveHint": False},
)
async def win_trigger_hud_animation(
    animation: Literal["pulse", "alert_flash", "boot_sequence", "scan"] = Field(
        ...,
        description=(
            "Animation to trigger: "
            "'pulse' — single energy burst on the arc reactor ring, "
            "'alert_flash' — red warning flash, "
            "'boot_sequence' — replay the cinematic boot sequence, "
            "'scan' — sweeping scan line effect"
        ),
    ),
    intensity: float = Field(
        default=1.0,
        description="Animation intensity multiplier 0.1–3.0 (default 1.0).",
        ge=0.1,
        le=3.0,
    ),
) -> str:
    """Trigger a visual animation on the Jarvis Unity HUD arc reactor ring."""
    pipe = _pipe()
    if not pipe.is_connected:
        return "HUD is not connected (Unity app not running)."
    pipe.send({
        "type":      "hud_animation",
        "animation": animation,
        "intensity": intensity,
        "timestamp": time.time(),
    })
    return f"Animation triggered: {animation} (intensity {intensity:.1f})"


@mcp.tool(
    name="win_get_voice_status",
    annotations={"title": "Get Voice Mode Status", "readOnlyHint": True, "destructiveHint": False},
)
async def win_get_voice_status() -> str:
    """Return the current voice detection state and HUD connection status."""
    pipe = _pipe()
    try:
        voice = _voice()
        state = voice.get_state()
        muted = voice.is_muted
        return (
            f"Voice state  : {state.name}\n"
            f"Muted        : {muted}\n"
            f"HUD connected: {pipe.is_connected}"
        )
    except Exception as e:
        return (
            f"Voice engine not available: {e}\n"
            f"HUD connected: {pipe.is_connected}"
        )
