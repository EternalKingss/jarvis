"""
Wi-Fi and Bluetooth tools.

win_wifi_networks    : Saved Wi-Fi profiles and nearby networks with signal strength
win_wifi_connect     : Connect to a saved Wi-Fi network
win_wifi_disconnect  : Disconnect from the current Wi-Fi network
win_bluetooth_devices: Paired Bluetooth devices and whether they are connected
win_bluetooth_power  : Turn the Bluetooth radio on or off
"""

import logging
import re
from typing import Literal

from pydantic import Field
from mcp_instance import mcp
from utils.shell import run_command_async
from utils.winrt import AWAIT_PRELUDE, ps_quote

logger = logging.getLogger(__name__)

_LOCATION_HINT = (
    "Windows only lists nearby Wi-Fi networks when location access is on: "
    "Settings > Privacy & security > Location > 'Let desktop apps access your location'."
)


def _saved_profiles(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"All User Profile\s*:\s*(.+)", text)]


def _parse_networks(text: str) -> list[dict]:
    """Parse `netsh wlan show networks mode=bssid` (English output) into one entry per SSID."""
    networks, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"SSID \d+\s*:\s*(.*)", line)
        if m:
            cur = {"ssid": m.group(1).strip() or "(hidden)", "auth": "", "signal": 0, "band": ""}
            networks.append(cur)
        elif cur is not None:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if key == "Authentication":
                cur["auth"] = value
            elif key == "Signal":
                signal = int(value.rstrip("%") or 0)
                if signal > cur["signal"]:
                    cur["signal"] = signal
            elif key == "Band" and not cur["band"]:
                cur["band"] = value
    return networks


@mcp.tool(
    name="win_wifi_networks",
    annotations={"title": "List Wi-Fi Networks", "readOnlyHint": True, "destructiveHint": False},
)
async def win_wifi_networks(
    limit: int = Field(default=15, description="Max nearby networks to list, strongest first (default 15)", ge=1, le=60),
) -> str:
    """List saved Wi-Fi networks (ones you can connect to) and nearby networks with signal strength."""
    profiles = await run_command_async("netsh wlan show profiles", shell="cmd", timeout=15)
    nearby = await run_command_async("netsh wlan show networks mode=bssid", shell="cmd", timeout=15)
    if "no wireless interface" in (profiles["stdout"] + profiles["stderr"]).lower():
        return "This PC has no Wi-Fi adapter (or it is disabled)."

    saved = _saved_profiles(profiles["stdout"])
    lines = ["── Saved networks (can connect) ────────────"]
    lines += [f"  {name}" for name in saved] or ["  (none)"]

    lines.append("\n── Nearby networks ─────────────────────────")
    out = nearby["stdout"] + nearby["stderr"]
    networks = _parse_networks(nearby["stdout"])
    if networks:
        networks.sort(key=lambda n: n["signal"], reverse=True)
        for n in networks[:limit]:
            mark = "  (saved)" if n["ssid"] in saved else ""
            lines.append(f"  {n['signal']:>3}%  {n['band'] or '?':<8} {n['auth']:<16} {n['ssid']}{mark}")
        if len(networks) > limit:
            lines.append(f"  ... and {len(networks) - limit} weaker networks.")
    elif "location" in out.lower():
        lines.append(f"  {_LOCATION_HINT}")
    else:
        lines.append(out.strip()[:2000] or "  (none found)")
    return "\n".join(lines)


@mcp.tool(
    name="win_wifi_connect",
    annotations={"title": "Connect to Wi-Fi", "readOnlyHint": False, "destructiveHint": False},
)
async def win_wifi_connect(
    name: str = Field(..., description="Name of a saved Wi-Fi network (see win_wifi_networks). New networks must be joined once from Windows settings first."),
) -> str:
    """Connect to a saved Wi-Fi network. Switching networks briefly interrupts the internet connection."""
    profiles = await run_command_async("netsh wlan show profiles", shell="cmd", timeout=15)
    saved = _saved_profiles(profiles["stdout"])
    match = next((p for p in saved if p.lower() == name.lower()), None)
    if match is None:
        return (
            f"'{name}' is not a saved network. Saved: {', '.join(saved) or 'none'}. "
            "Join a new network once from the Windows Wi-Fi menu so its password is stored, then try again."
        )
    result = await run_command_async(f"& netsh wlan connect ('name=' + {ps_quote(match)})", shell="powershell", timeout=20)
    text = (result["stdout"] or result["stderr"]).strip()
    return f"{text or 'Connection request sent'} ({match})."


@mcp.tool(
    name="win_wifi_disconnect",
    annotations={"title": "Disconnect Wi-Fi", "readOnlyHint": False, "destructiveHint": True},
)
async def win_wifi_disconnect() -> str:
    """Disconnect from the current Wi-Fi network. If Wi-Fi is the only connection, this also cuts Claude off until you reconnect."""
    result = await run_command_async("netsh wlan disconnect", shell="cmd", timeout=15)
    return (result["stdout"] or result["stderr"]).strip() or "Disconnect request sent."


_BT_DEVICES_SCRIPT = r"""
$devices = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -like 'BTHENUM\DEV_*' -or $_.InstanceId -like 'BTHLE\DEV_*' }
foreach ($d in $devices) {
    $c = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName '{83DA6326-97A6-4088-9453-A1923F573B29} 15' -ErrorAction SilentlyContinue).Data
    $state = if ($c -eq $true) { 'connected' } else { 'not connected' }
    Write-Output ("{0}|{1}" -f $d.FriendlyName, $state)
}
"""


@mcp.tool(
    name="win_bluetooth_devices",
    annotations={"title": "List Bluetooth Devices", "readOnlyHint": True, "destructiveHint": False},
)
async def win_bluetooth_devices() -> str:
    """List paired Bluetooth devices and whether each one is connected right now."""
    result = await run_command_async(_BT_DEVICES_SCRIPT, shell="powershell", timeout=30)
    rows = sorted({line for line in result["stdout"].splitlines() if "|" in line})
    if not rows:
        return "No paired Bluetooth devices found (or this PC has no Bluetooth adapter)."
    lines = ["Paired Bluetooth devices:"]
    for row in rows[:50]:
        name, _, state = row.partition("|")
        lines.append(f"  {state:<14} {name}")
    return "\n".join(lines)


def _bt_power_script(state: str) -> str:
    return AWAIT_PRELUDE + (
        "[Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime] | Out-Null\n"
        "$access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])\n"
        "if ($access -ne 'Allowed') { Write-Error \"ACCESS:$access\"; exit 4 }\n"
        "$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])\n"
        "$bt = $radios | Where-Object { $_.Kind -eq 'Bluetooth' } | Select-Object -First 1\n"
        "if ($null -eq $bt) { Write-Error 'NO_BLUETOOTH'; exit 5 }\n"
        f"$status = Await ($bt.SetStateAsync('{state}')) ([Windows.Devices.Radios.RadioAccessStatus])\n"
        "Write-Output \"$status|$($bt.State)\"\n"
    )


@mcp.tool(
    name="win_bluetooth_power",
    annotations={"title": "Turn Bluetooth On/Off", "readOnlyHint": False, "destructiveHint": True},
)
async def win_bluetooth_power(
    state: Literal["on", "off"] = Field(..., description="'on' or 'off'."),
) -> str:
    """Turn the Bluetooth radio on or off. Turning it off disconnects Bluetooth keyboards, mice and headphones."""
    result = await run_command_async(_bt_power_script("On" if state == "on" else "Off"), shell="powershell", timeout=30)
    err = result["stderr"]
    if "NO_BLUETOOTH" in err:
        return "This PC has no Bluetooth radio (or it is disabled in Device Manager)."
    if "ACCESS:" in err:
        return "Windows denied access to the Bluetooth radio. Check Settings > Privacy & security > Radios."
    if not result["success"]:
        return f"Could not change Bluetooth: {err or 'no error text'}"
    status, _, now = result["stdout"].strip().partition("|")
    return f"Bluetooth is now {now.lower() or state}." if status == "Allowed" else f"Bluetooth change refused: {status}"
