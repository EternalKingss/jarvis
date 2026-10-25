"""
Windows settings tools.

win_brightness    : Read or set display brightness (laptop screens and DDC/CI monitors)
win_theme         : Read or switch light/dark mode
win_volume_level  : Read or set exact volume / mute, for the whole PC or one app
win_audio_output  : List playback devices or switch the default one
win_power_plan    : List power plans or switch the active one
"""

import asyncio
import logging
import re
from typing import Literal, Optional

from pydantic import Field
from mcp_instance import mcp
from utils import brightness
from utils.com import run_com
from utils.shell import run_command_async

logger = logging.getLogger(__name__)

_PERSONALIZE = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


@mcp.tool(
    name="win_brightness",
    annotations={"title": "Display Brightness", "readOnlyHint": False, "destructiveHint": False},
)
async def win_brightness(
    level: Optional[int] = Field(default=None, description="New brightness 0-100 for every display that supports it. Leave out to just read it.", ge=0, le=100),
) -> str:
    """Read or set screen brightness. Works on laptop screens and on external monitors with DDC/CI enabled."""
    if level is None:
        found = await asyncio.to_thread(brightness.get)
        if not found:
            return "No display reported its brightness. External monitors need DDC/CI turned on in the monitor's own menu."
        return "Brightness:\n" + "\n".join(f"  {name}: {value}%" for name, value in found)
    changed = await asyncio.to_thread(brightness.set_all, level)
    if not changed:
        return "Couldn't change brightness on any display. External monitors need DDC/CI turned on in the monitor's own menu."
    return f"Set brightness to {level}% on: {', '.join(changed)}."


@mcp.tool(
    name="win_theme",
    annotations={"title": "Light/Dark Mode", "readOnlyHint": False, "destructiveHint": False},
)
async def win_theme(
    mode: Literal["status", "light", "dark"] = Field(default="status", description="'light', 'dark', or 'status' to just read the current mode."),
) -> str:
    """Read or switch Windows between light and dark mode (apps and the taskbar)."""
    if mode == "status":
        r = await run_command_async(
            f"$p = Get-ItemProperty '{_PERSONALIZE}'; \"$($p.AppsUseLightTheme)|$($p.SystemUsesLightTheme)\"", shell="powershell")
        apps, system = (r["stdout"].strip().split("|") + ["", ""])[:2]
        word = {"1": "light", "0": "dark"}
        return f"Apps: {word.get(apps, 'light')} mode. Taskbar and Start: {word.get(system, 'dark')} mode."
    value = 1 if mode == "light" else 0
    # WM_SETTINGCHANGE "ImmersiveColorSet" tells running apps to repaint now.
    script = (
        f"Set-ItemProperty '{_PERSONALIZE}' -Name AppsUseLightTheme -Value {value} -Type DWord\n"
        f"Set-ItemProperty '{_PERSONALIZE}' -Name SystemUsesLightTheme -Value {value} -Type DWord\n"
        "Add-Type -Namespace J -Name W -MemberDefinition '[DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] "
        "public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, UIntPtr w, string l, uint f, uint t, out UIntPtr r);'\n"
        "$r = [UIntPtr]::Zero; [J.W]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'ImmersiveColorSet', 2, 3000, [ref]$r) | Out-Null\n"
        "'ok'\n"
    )
    r = await run_command_async(script, shell="powershell")
    return f"Switched to {mode} mode." if "ok" in r["stdout"] else f"Couldn't change the theme: {r['stderr']}"


def _session_name(session) -> str:
    try:
        if session.Process:
            return session.Process.name()
    except Exception:
        pass
    return "System sounds"


@mcp.tool(
    name="win_volume_level",
    annotations={"title": "Set Volume Level", "readOnlyHint": False, "destructiveHint": False},
)
async def win_volume_level(
    level: Optional[int] = Field(default=None, description="Exact volume 0-100. Leave out (with mute unset) to just read the levels.", ge=0, le=100),
    app: Optional[str] = Field(default=None, description="Only this app, by process name, e.g. 'spotify' or 'chrome'. Leave out for the whole PC."),
    mute: Optional[bool] = Field(default=None, description="True to mute, False to unmute."),
) -> str:
    """Read or set the exact volume, or mute/unmute, for the whole PC or for one app (like the Windows volume mixer)."""
    def _impl() -> str:
        from pycaw.pycaw import AudioUtilities

        if app is None:
            speakers = AudioUtilities.GetSpeakers()
            ep = speakers.EndpointVolume
            if level is not None:
                speakers.volume_percent = level
            if mute is not None:
                ep.SetMute(int(mute), None)
            state = "muted" if ep.GetMute() else f"{round(speakers.volume_percent)}%"
            return f"{speakers.FriendlyName}: {state}"

        query = app.lower().removesuffix(".exe")
        sessions = [s for s in AudioUtilities.GetAllSessions() if query in _session_name(s).lower()]
        if not sessions:
            playing = sorted({_session_name(s) for s in AudioUtilities.GetAllSessions()})
            return f"No app named '{app}' is using audio right now. Apps with audio: {', '.join(playing) or 'none'}."
        for s in sessions:
            vol = s.SimpleAudioVolume
            if level is not None:
                vol.SetMasterVolume(level / 100, None)
            if mute is not None:
                vol.SetMute(int(mute), None)
        vol = sessions[0].SimpleAudioVolume
        state = "muted" if vol.GetMute() else f"{round(vol.GetMasterVolume() * 100)}%"
        return f"{_session_name(sessions[0])}: {state}"

    try:
        return await run_com(_impl)
    except Exception as e:
        return f"Volume change failed: {type(e).__name__}: {e}"


@mcp.tool(
    name="win_audio_output",
    annotations={"title": "Audio Output Device", "readOnlyHint": False, "destructiveHint": False},
)
async def win_audio_output(
    device: Optional[str] = Field(default=None, description="Switch the default playback device to this one (exact or partial name). Leave out to list devices."),
) -> str:
    """List playback devices (speakers, headphones, monitors) or switch which one Windows plays sound through."""
    def _impl() -> str:
        from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
        from pycaw.pycaw import AudioUtilities

        devices = AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
        default_id = AudioUtilities.GetSpeakers().id
        if device is None:
            lines = ["Playback devices:"]
            lines += [f"  {'* ' if d.id == default_id else '  '}{d.FriendlyName}" for d in devices]
            return "\n".join(lines) + "\n(* = current default)"
        q = device.lower()
        match = (next((d for d in devices if d.FriendlyName.lower() == q), None)
                 or next((d for d in devices if q in d.FriendlyName.lower()), None))
        if match is None:
            return f"No playback device matches '{device}'. Devices: {', '.join(d.FriendlyName for d in devices)}."
        AudioUtilities.SetDefaultDevice(match.id, [ERole.eConsole, ERole.eMultimedia, ERole.eCommunications])
        return f"Sound now plays through {match.FriendlyName}."

    try:
        return await run_com(_impl)
    except Exception as e:
        return f"Audio device change failed: {type(e).__name__}: {e}"


_PLAN_RE = re.compile(r"GUID:\s*([0-9a-fA-F-]{36})\s+\((.+?)\)\s*(\*)?")


@mcp.tool(
    name="win_power_plan",
    annotations={"title": "Power Plan", "readOnlyHint": False, "destructiveHint": False},
)
async def win_power_plan(
    plan: Optional[str] = Field(default=None, description="Switch to this plan (exact or partial name, e.g. 'balanced', 'high performance'). Leave out to list plans."),
) -> str:
    """List Windows power plans or switch the active one, such as Balanced, High performance or Power saver."""
    r = await run_command_async("powercfg /list", shell="cmd", timeout=15)
    plans = [(m.group(1), m.group(2), bool(m.group(3))) for m in _PLAN_RE.finditer(r["stdout"])]
    if not plans:
        return f"Couldn't read power plans: {r['stderr'] or r['stdout'][:300]}"
    if plan is None:
        return "Power plans:\n" + "\n".join(f"  {'* ' if active else '  '}{name}" for _, name, active in plans) + "\n(* = active)"
    q = plan.lower()
    match = next((p for p in plans if p[1].lower() == q), None) or next((p for p in plans if q in p[1].lower()), None)
    if match is None:
        return f"No power plan matches '{plan}'. Plans: {', '.join(p[1] for p in plans)}."
    r = await run_command_async(f"powercfg /setactive {match[0]}", shell="cmd", timeout=15)
    return f"Power plan is now {match[1]}." if r["success"] else f"Couldn't switch: {r['stderr']}"
