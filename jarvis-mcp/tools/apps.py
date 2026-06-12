"""
Application management tools.

win_open_app          : Open any application by name
win_close_app         : Close a running application
win_list_running_apps : List currently running apps
win_switch_to_app     : Bring an app window to the foreground
win_list_installed    : Show available installed programs
"""

import asyncio
import logging
import time

import psutil
from pydantic import Field
from mcp_instance import mcp
from utils.app_finder import find_application, launch_application, list_installed_apps
from utils.procs import protected_pids
from utils.shell import run_command_async

logger = logging.getLogger(__name__)


@mcp.tool(
    name="win_open_app",
    annotations={"title": "Open Application", "readOnlyHint": False, "destructiveHint": False},
)
async def win_open_app(
    app_name: str = Field(..., description="Name of the application to open. E.g. 'chrome', 'discord', 'notepad', 'steam', 'spotify', 'vs code', 'calculator', 'file explorer'"),
) -> str:
    """Find and open any installed application by name. Supports partial names and aliases."""
    def _impl() -> str:
        app_path = find_application(app_name)
        if not app_path:
            return (
                f"Could not find '{app_name}' on this machine. "
                "Try win_list_installed to see what's available."
            )
        success = launch_application(app_path)
        if success:
            return f"Launched '{app_name}' → {app_path}"
        return f"Found '{app_name}' at {app_path} but failed to launch it."

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_close_app",
    annotations={"title": "Close Application", "readOnlyHint": False, "destructiveHint": True},
)
async def win_close_app(
    app_name: str = Field(..., description="Process or app name to close. E.g. 'chrome', 'notepad', 'discord'. Partial matches work."),
) -> str:
    """Close a running application. Tries graceful close first, then force-kills."""
    def _impl() -> str:
        query = app_name.lower().strip()
        protected = protected_pids()
        killed = []
        skipped_self = 0

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info["name"].lower()
                if query in pname or pname.startswith(query.replace(" ", "")):
                    if proc.info["pid"] in protected:
                        skipped_self += 1
                        continue
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed.append(f"{proc.info['name']} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not killed:
            if skipped_self:
                return f"Only matches for '{app_name}' are the Jarvis MCP server itself — not closing it."
            return f"No running process found matching '{app_name}'."
        result = f"Closed {len(killed)} process(es): {', '.join(killed)}"
        if skipped_self:
            result += f"\nSkipped {skipped_self} process(es) belonging to the MCP server itself."
        return result

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_list_running_apps",
    annotations={"title": "List Running Applications", "readOnlyHint": True, "destructiveHint": False},
)
async def win_list_running_apps() -> str:
    """List all currently running processes sorted by memory usage, with PID, CPU%, and RAM."""
    def _impl() -> str:
        # cpu_percent needs two samples per process — the first call always
        # returns 0.0. Prime, wait, then read real values.
        for p in psutil.process_iter():
            try:
                p.cpu_percent()
            except psutil.Error:
                pass
        time.sleep(0.25)

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
            try:
                mem_mb = proc.info["memory_info"].rss / (1024 * 1024)
                processes.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "cpu": proc.info["cpu_percent"],
                    "mem_mb": round(mem_mb, 1),
                    "status": proc.info["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        processes.sort(key=lambda x: x["mem_mb"], reverse=True)
        top = processes[:40]

        lines = [f"{'PID':>7}  {'Name':<35}  {'CPU%':>5}  {'RAM MB':>7}  Status"]
        lines.append("─" * 70)
        for p in top:
            lines.append(f"{p['pid']:>7}  {p['name']:<35}  {p['cpu']:>5.1f}  {p['mem_mb']:>7.1f}  {p['status']}")
        lines.append(f"\n{len(processes)} total processes. Showing top 40 by RAM.")
        return "\n".join(lines)

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_switch_to_app",
    annotations={"title": "Switch to Application", "readOnlyHint": False, "destructiveHint": False},
)
async def win_switch_to_app(
    app_name: str = Field(..., description="App to bring to foreground. E.g. 'chrome', 'notepad', 'discord'"),
) -> str:
    """Bring an application window to the foreground (focus it)."""
    # Single-quote escaping — raw interpolation broke (or executed) on
    # names containing quotes or $(...)
    safe_query = app_name.lower().replace("'", "''")
    ps_script = f"""
$query = '{safe_query}'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {{
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}}
"@
$procs = Get-Process | Where-Object {{
    ($_.MainWindowTitle -ne '') -and (
        $_.ProcessName -like "*$query*" -or
        $_.MainWindowTitle -like "*$query*"
    )
}}
if ($procs) {{
    $p = $procs | Select-Object -First 1
    [Win32]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
    [Win32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
    Write-Output "Switched to: $($p.MainWindowTitle) ($($p.ProcessName))"
}} else {{
    Write-Output "No window found matching '$query'"
}}
"""
    result = await run_command_async(ps_script, shell="powershell")
    return result["stdout"] or result["stderr"] or "No output."


@mcp.tool(
    name="win_list_installed",
    annotations={"title": "List Installed Applications", "readOnlyHint": True, "destructiveHint": False},
)
async def win_list_installed(
    limit: int = Field(default=50, description="Max number of apps to return (default 50)", ge=1, le=200),
) -> str:
    """List applications installed on the machine from Start Menu shortcuts."""
    apps = await asyncio.to_thread(list_installed_apps, limit)
    if not apps:
        return "No applications found in Start Menu."
    return f"Found {len(apps)} apps:\n" + "\n".join(f"  • {a}" for a in apps)
