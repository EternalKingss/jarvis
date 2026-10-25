"""
Scheduled automation tools (Windows Task Scheduler, \\Jarvis\\ folder only).

win_automation_create  : Schedule a command (once, daily, weekly, every N minutes, at sign-in)
win_automation_list    : Every Jarvis automation with its command, schedule and last result
win_automation_run_now : Run an automation immediately
win_automation_history : Recent output of an automation
win_automation_delete  : Remove an automation

Creating and running need the "Allow scheduled automations" setting. Listing,
reading history and deleting always work, so the user can clean up anytime.
These run on the PC without Claude; they are not Claude's own scheduled tasks.
"""

import asyncio
import logging
from typing import Literal, Optional

from pydantic import Field
from mcp_instance import mcp
from utils import automations as auto
from utils import settings

logger = logging.getLogger(__name__)


def _known(name: str) -> Optional[dict]:
    return next((t for t in auto.list_tasks() if t["name"].lower() == name.strip().lower()), None)


@mcp.tool(
    name="win_automation_create",
    annotations={"title": "Create Scheduled Automation", "readOnlyHint": False, "destructiveHint": True},
)
async def win_automation_create(
    name: str = Field(..., description="Short unique name, e.g. 'Clean Downloads'. Letters, numbers, spaces, - _ ."),
    command: str = Field(..., description="What to run. PowerShell code by default (or a cmd line if shell='cmd'). It runs unattended, so it must not prompt for input."),
    schedule: Literal["once", "daily", "weekly", "every_minutes", "at_logon"] = Field(
        ..., description="When to run. 'every_minutes' also suits watch-style checks (e.g. move new PDFs out of Downloads)."),
    time_of_day: Optional[str] = Field(default=None, description="24-hour HH:MM. Needed for once, daily and weekly."),
    date: Optional[str] = Field(default=None, description="YYYY-MM-DD. Needed for once."),
    days: Optional[list[str]] = Field(default=None, description="Weekly only: days to run, e.g. ['Mon', 'Thu']."),
    every_minutes: Optional[int] = Field(default=None, description="every_minutes only: interval, 5 to 1440."),
    shell: Literal["powershell", "cmd"] = Field(default="powershell", description="'powershell' (default) or 'cmd'."),
    notify: bool = Field(default=False, description="Show a Windows notification each time it finishes (default False)."),
) -> str:
    """Schedule a command to run on this PC later or repeatedly, even when Claude is closed (Windows Task Scheduler). Requires the 'scheduled automations' extension setting. Always show the user the exact command and schedule and get their OK first."""
    if not settings.enabled(settings.ALLOW_AUTOMATIONS):
        return settings.disabled_message(settings.ALLOW_AUTOMATIONS)
    try:
        when = await asyncio.to_thread(
            auto.create, name, command, shell, schedule, time_of_day, date, days, every_minutes, notify)
    except auto.AutomationError as e:
        return f"Not created: {e}"
    return (f"Automation '{name.strip()}' created. It runs {when} as you, without admin rights, while you're signed in.\n"
            "Check it with win_automation_history, or remove it with win_automation_delete.")


@mcp.tool(
    name="win_automation_list",
    annotations={"title": "List Scheduled Automations", "readOnlyHint": True, "destructiveHint": False},
)
async def win_automation_list() -> str:
    """List every automation Jarvis has scheduled, with its exact command, schedule, next run and last result."""
    rows = await asyncio.to_thread(auto.list_tasks)
    if not rows:
        return "No Jarvis automations are scheduled."
    lines = [f"Jarvis automations ({len(rows)}/{auto.MAX_AUTOMATIONS}):"]
    for r in rows:
        meta = r["meta"]
        lines.append(f"\n• {r['name']}  [{r['state']}]")
        lines.append(f"    Runs   : {meta.get('schedule', '(unknown)')}")
        lines.append(f"    Command: ({meta.get('shell', '?')}) {meta.get('command', '(script missing)')}")
        lines.append(f"    Next   : {r['next'] or '-'}   Last: {r['last'] or 'never'}"
                     + (f" ({auto.result_text(r['result'])})" if r["last"] else ""))
    return "\n".join(lines)


@mcp.tool(
    name="win_automation_run_now",
    annotations={"title": "Run Automation Now", "readOnlyHint": False, "destructiveHint": True},
)
async def win_automation_run_now(
    name: str = Field(..., description="Name of an existing Jarvis automation (see win_automation_list)."),
) -> str:
    """Run one of Jarvis's scheduled automations right away. Requires the 'scheduled automations' extension setting."""
    if not settings.enabled(settings.ALLOW_AUTOMATIONS):
        return settings.disabled_message(settings.ALLOW_AUTOMATIONS)
    task = await asyncio.to_thread(_known, name)
    if task is None:
        return f"No Jarvis automation named '{name}'. Use win_automation_list to see them."
    r = await asyncio.to_thread(auto.run_now, task["name"])
    if "started" in r["stdout"]:
        return f"Started '{task['name']}'. Its output appears in win_automation_history once it finishes."
    return f"Could not start it: {r['stderr'] or 'no error text'}"


@mcp.tool(
    name="win_automation_history",
    annotations={"title": "Automation History", "readOnlyHint": True, "destructiveHint": False},
)
async def win_automation_history(
    name: str = Field(..., description="Name of a Jarvis automation."),
    max_chars: int = Field(default=4000, description="How much recent output to show (default 4000).", ge=200, le=20000),
) -> str:
    """Show when an automation last ran, its result, and its most recent output."""
    task = await asyncio.to_thread(_known, name)
    if task is None:
        return f"No Jarvis automation named '{name}'. Use win_automation_list to see them."
    log = await asyncio.to_thread(auto.read_log, task["name"], max_chars)
    head = (f"'{task['name']}': last run {task['last'] or 'never'}"
            + (f" ({auto.result_text(task['result'])})" if task["last"] else "")
            + f", next {task['next'] or '-'}.")
    return head + ("\n\nRecent output:\n" + log if log.strip() else "\n\nNo output recorded yet.")


@mcp.tool(
    name="win_automation_delete",
    annotations={"title": "Delete Automation", "readOnlyHint": False, "destructiveHint": True},
)
async def win_automation_delete(
    name: str = Field(..., description="Name of the Jarvis automation to remove."),
) -> str:
    """Remove a Jarvis automation so it never runs again, along with its saved script and output. Only Jarvis's own automations can be deleted."""
    task = await asyncio.to_thread(_known, name)
    if task is None:
        return f"No Jarvis automation named '{name}'. Use win_automation_list to see them."
    r = await asyncio.to_thread(auto.delete, task["name"])
    if "deleted" in r["stdout"]:
        return f"Deleted automation '{task['name']}'."
    return f"Could not delete it: {r['stderr'] or 'no error text'}"
