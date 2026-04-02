"""
System control tools.

win_get_system_info     : CPU, RAM, disk, GPU, OS info
win_list_processes      : Running processes
win_kill_process        : Kill a process by name or PID
win_adjust_volume       : Volume up / down / mute / set level
win_take_screenshot     : Capture the screen
win_get_network_info    : IP addresses, Wi-Fi, connections
win_shutdown            : Shutdown the PC
win_restart             : Restart the PC
win_lock                : Lock the workstation
win_cancel_shutdown     : Cancel a pending shutdown
"""

import logging
import os
from datetime import datetime
from typing import Literal, Optional

import psutil
from pydantic import Field
from mcp_instance import mcp
from utils.shell import run_command

logger = logging.getLogger(__name__)
SCREENSHOT_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Jarvis Screenshots")


@mcp.tool(
    name="win_get_system_info",
    annotations={"title": "Get System Information", "readOnlyHint": True, "destructiveHint": False},
)
async def win_get_system_info() -> str:
    """Get comprehensive system info: CPU, RAM, disks, GPU, OS version, uptime, battery."""
    uname = os.popen("ver").read().strip()
    cpu_count = psutil.cpu_count(logical=False)
    cpu_logical = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    cpu_usage = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disk_lines = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk_lines.append(
                f"  {part.device} ({part.fstype})  "
                f"Total: {usage.total/1e9:.1f} GB  "
                f"Used: {usage.used/1e9:.1f} GB ({usage.percent}%)  "
                f"Free: {usage.free/1e9:.1f} GB"
            )
        except PermissionError:
            pass

    gpu_result = run_command("wmic path Win32_VideoController get Name,AdapterRAM,DriverVersion /format:csv", shell="cmd")
    gpu_info = gpu_result["stdout"] if gpu_result["success"] else "Unavailable"

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time

    battery_line = ""
    try:
        bat = psutil.sensors_battery()
        if bat:
            status = "charging" if bat.power_plugged else "on battery"
            battery_line = f"\nBattery    : {bat.percent:.0f}% ({status})"
    except Exception:
        pass

    cpu_name_result = run_command("wmic cpu get Name /value", shell="cmd")
    cpu_name = ""
    for line in cpu_name_result["stdout"].splitlines():
        if line.startswith("Name="):
            cpu_name = line.split("=", 1)[1].strip()
            break

    return f"""── System Information ──────────────────────────────────────────
OS         : {uname}
Uptime     : {str(uptime).split('.')[0]}

── CPU ─────────────────────────────────────────────────────────
Name       : {cpu_name}
Cores      : {cpu_count} physical / {cpu_logical} logical
Frequency  : {cpu_freq.current:.0f} MHz (max {cpu_freq.max:.0f} MHz)
Usage now  : {cpu_usage}%

── Memory ──────────────────────────────────────────────────────
RAM Total  : {mem.total/1e9:.2f} GB
RAM Used   : {mem.used/1e9:.2f} GB ({mem.percent}%)
RAM Free   : {mem.available/1e9:.2f} GB
Swap Total : {swap.total/1e9:.2f} GB  Used: {swap.used/1e9:.2f} GB{battery_line}

── Disks ───────────────────────────────────────────────────────
{chr(10).join(disk_lines) or '  No disks found'}

── GPU ─────────────────────────────────────────────────────────
{gpu_info[:500]}""".strip()


@mcp.tool(
    name="win_list_processes",
    annotations={"title": "List Running Processes", "readOnlyHint": True, "destructiveHint": False},
)
async def win_list_processes(
    sort_by: Literal["cpu", "memory", "name", "pid"] = Field(default="memory", description="Sort order: 'cpu', 'memory' (default), 'name', or 'pid'"),
    limit: int = Field(default=30, description="Number of processes to show (default 30)", ge=1, le=200),
    filter_name: Optional[str] = Field(default=None, description="Only show processes whose name contains this string"),
) -> str:
    """List running processes with CPU, memory usage, PID, and status."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status", "username"]):
        try:
            mem_mb = p.info["memory_info"].rss / (1024 * 1024)
            name = p.info["name"]
            if filter_name and filter_name.lower() not in name.lower():
                continue
            procs.append({
                "pid": p.info["pid"], "name": name,
                "cpu": p.info["cpu_percent"], "mem_mb": round(mem_mb, 1),
                "status": p.info["status"],
                "user": (p.info.get("username") or "").split("\\")[-1],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    sort_key = {"cpu": lambda x: x["cpu"], "memory": lambda x: x["mem_mb"],
                "name": lambda x: x["name"].lower(), "pid": lambda x: x["pid"]}.get(sort_by, lambda x: x["mem_mb"])
    procs.sort(key=sort_key, reverse=(sort_by in ("cpu", "memory")))
    procs = procs[:limit]

    lines = [f"{'PID':>7}  {'Name':<35}  {'CPU%':>5}  {'RAM MB':>7}  {'User':<15}  Status"]
    lines.append("─" * 85)
    for p in procs:
        lines.append(f"{p['pid']:>7}  {p['name']:<35}  {p['cpu']:>5.1f}  {p['mem_mb']:>7.1f}  {p['user']:<15}  {p['status']}")
    lines.append(f"\nShowing {len(procs)} processes (sorted by {sort_by}).")
    return "\n".join(lines)


@mcp.tool(
    name="win_kill_process",
    annotations={"title": "Kill Process", "readOnlyHint": False, "destructiveHint": True},
)
async def win_kill_process(
    identifier: str = Field(..., description="Process name (partial match OK) or numeric PID. E.g. 'chrome', 'notepad', '1234'"),
    force: bool = Field(default=False, description="If True, force-kill immediately. If False (default), try graceful termination first."),
) -> str:
    """Terminate a process by name or PID."""
    killed = []
    errors = []

    try:
        pid = int(identifier)
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.kill() if force else proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
            killed.append(f"{name} (PID {pid})")
        except psutil.NoSuchProcess:
            return f"No process with PID {pid}."
        except psutil.AccessDenied:
            return f"Access denied killing PID {pid}. Try running as administrator."
    except ValueError:
        query = identifier.lower()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if query in proc.info["name"].lower():
                    proc.kill() if force else proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed.append(f"{proc.info['name']} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                errors.append(str(e))

    if not killed:
        return f"No process found matching '{identifier}'."
    result = f"Killed {len(killed)} process(es): {', '.join(killed)}"
    if errors:
        result += f"\n{len(errors)} process(es) skipped (access denied)."
    return result


@mcp.tool(
    name="win_adjust_volume",
    annotations={"title": "Adjust System Volume", "readOnlyHint": False, "destructiveHint": False},
)
async def win_adjust_volume(
    action: Literal["up", "down", "mute", "unmute"] = Field(..., description="Volume action: 'up', 'down', 'mute', or 'unmute'"),
) -> str:
    """Control system volume: raise, lower, mute, or unmute."""
    scripts = {
        "mute":   "$shell = New-Object -comObject WScript.Shell; $shell.SendKeys([char]173); Write-Output 'Muted'",
        "unmute": "$shell = New-Object -comObject WScript.Shell; $shell.SendKeys([char]173); Write-Output 'Unmuted (toggled)'",
        "up":     "$shell = New-Object -comObject WScript.Shell; 1..5 | ForEach-Object { $shell.SendKeys([char]175) }; Write-Output 'Volume increased'",
        "down":   "$shell = New-Object -comObject WScript.Shell; 1..5 | ForEach-Object { $shell.SendKeys([char]174) }; Write-Output 'Volume decreased'",
    }
    result = run_command(scripts[action], shell="powershell")
    return result["stdout"] or result["stderr"] or f"Volume {action} sent."


@mcp.tool(
    name="win_take_screenshot",
    annotations={"title": "Take Screenshot", "readOnlyHint": False, "destructiveHint": False},
)
async def win_take_screenshot(
    save_path: Optional[str] = Field(default=None, description="Where to save the PNG. Defaults to ~/Pictures/Jarvis Screenshots/screenshot_TIMESTAMP.png"),
) -> str:
    """Capture the current screen and save it as a PNG file."""
    try:
        from PIL import ImageGrab
        if save_path:
            out_path = os.path.expandvars(os.path.expanduser(save_path))
        else:
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(SCREENSHOT_DIR, f"screenshot_{ts}.png")
        img = ImageGrab.grab()
        img.save(out_path)
        return f"Screenshot saved: {out_path}  ({img.width}x{img.height})"
    except ImportError:
        return "Error: Pillow not installed. Run: pip install Pillow"
    except Exception as e:
        return f"Screenshot failed: {e}"


@mcp.tool(
    name="win_get_network_info",
    annotations={"title": "Get Network Information", "readOnlyHint": True, "destructiveHint": False},
)
async def win_get_network_info() -> str:
    """Get network configuration: IP addresses, Wi-Fi SSID/signal, and active connections."""
    lines = ["── Network Interfaces ──────────────────────────────────────────"]
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    for iface, addr_list in addrs.items():
        stat = stats.get(iface)
        is_up = stat.isup if stat else False
        speed = f"{stat.speed} Mbps" if stat and stat.speed else "unknown"
        lines.append(f"\n{iface} ({'UP' if is_up else 'DOWN'}, {speed})")
        for addr in addr_list:
            if addr.family.name in ("AF_INET", "AF_INET6"):
                lines.append(f"  {addr.family.name}: {addr.address}")

    wifi_result = run_command("netsh wlan show interfaces", shell="cmd")
    if wifi_result["success"] and wifi_result["stdout"]:
        lines.append("\n── Wi-Fi ───────────────────────────────────────────────────────")
        for line in wifi_result["stdout"].splitlines():
            line = line.strip()
            if any(k in line for k in ("SSID", "Signal", "State", "Radio type", "Authentication")):
                lines.append(f"  {line}")

    conns = psutil.net_connections()
    established = sum(1 for c in conns if c.status == "ESTABLISHED")
    lines.append(f"\n── Connections ─────────────────────────────────────────────────")
    lines.append(f"  Established: {established}  Total: {len(conns)}")
    return "\n".join(lines)


@mcp.tool(
    name="win_shutdown",
    annotations={"title": "Shutdown Computer", "readOnlyHint": False, "destructiveHint": True},
)
async def win_shutdown(
    delay_seconds: int = Field(default=0, description="Seconds before shutdown (0 = immediate)", ge=0, le=3600),
) -> str:
    """Shut down the computer. Always confirm with the user before calling this."""
    result = run_command(f"shutdown /s /t {delay_seconds}", shell="cmd")
    if result["success"] or result["exit_code"] == 0:
        return f"Shutdown in {delay_seconds}s. Use win_cancel_shutdown to abort." if delay_seconds > 0 else "Shutting down now."
    return f"Shutdown failed: {result['stderr']}"


@mcp.tool(
    name="win_restart",
    annotations={"title": "Restart Computer", "readOnlyHint": False, "destructiveHint": True},
)
async def win_restart(
    delay_seconds: int = Field(default=0, description="Seconds before restart (0 = immediate)", ge=0, le=3600),
) -> str:
    """Restart the computer. Always confirm with the user before calling this."""
    result = run_command(f"shutdown /r /t {delay_seconds}", shell="cmd")
    if result["success"] or result["exit_code"] == 0:
        return f"Restart in {delay_seconds}s. Use win_cancel_shutdown to abort." if delay_seconds > 0 else "Restarting now."
    return f"Restart failed: {result['stderr']}"


@mcp.tool(
    name="win_cancel_shutdown",
    annotations={"title": "Cancel Shutdown/Restart", "readOnlyHint": False, "destructiveHint": False},
)
async def win_cancel_shutdown() -> str:
    """Cancel a pending scheduled shutdown or restart."""
    result = run_command("shutdown /a", shell="cmd")
    return "Shutdown/restart cancelled." if result["success"] else f"Cancel failed (maybe nothing was pending): {result['stderr']}"


@mcp.tool(
    name="win_lock",
    annotations={"title": "Lock Workstation", "readOnlyHint": False, "destructiveHint": False},
)
async def win_lock() -> str:
    """Lock the Windows workstation (shows login screen)."""
    result = run_command("rundll32.exe user32.dll,LockWorkStation", shell="cmd")
    return "Workstation locked." if result["success"] else f"Lock failed: {result['stderr']}"
