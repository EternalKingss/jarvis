"""
Scheduled automations: Windows Task Scheduler tasks that Jarvis owns.

Scope is the whole safety story here:
  * Every task lives in the \\Jarvis\\ Task Scheduler folder. List, run and
    delete only ever address that folder, so the user's own tasks are never
    touched.
  * Tasks run as the signed-in user, only while they are signed in, without
    elevation (RunLevel Limited) and with no stored password.
  * Each automation gets a folder under %USERPROFILE%\\.jarvis\\automations
    holding its script, its settings (meta.json) and a capped output log.

The builders in this module are pure functions so they can be unit tested on
any OS; only create/list/run/delete shell out to PowerShell.
"""

import json
import os
import re
import shutil
import time
from typing import Literal, Optional

from utils.shell import run_command
from utils.winrt import ps_quote, toast_script

TASK_PATH = "\\Jarvis\\"
MAX_AUTOMATIONS = 25
MIN_EVERY_MINUTES = 5
LOG_MAX_BYTES = 200 * 1024

Schedule = Literal["once", "daily", "weekly", "every_minutes", "at_logon"]
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,59}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AutomationError(ValueError):
    """Bad input, with a message meant for the user."""


def root_dir() -> str:
    # Not %LOCALAPPDATA%: Claude Desktop is an MSIX app, and Windows redirects
    # its children's AppData writes into the package's private LocalCache,
    # where the Task Scheduler (running outside the package) cannot see them.
    # The user profile root is not redirected, so both sides agree on this path.
    return os.path.join(os.path.expanduser("~"), ".jarvis", "automations")


def automation_dir(name: str) -> str:
    return os.path.join(root_dir(), name)


def validate_name(name: str) -> str:
    name = name.strip()
    if not _NAME_RE.match(name):
        raise AutomationError(
            "Name must be 1-60 characters: letters, numbers, spaces, '-', '_' or '.', starting with a letter or number.")
    return name


def normalize_days(days: Optional[list[str]]) -> list[str]:
    out = []
    for d in days or []:
        match = next((full for full in DAYS if full.lower().startswith(d.strip().lower()[:3])), None)
        if match is None or len(d.strip()) < 3:
            raise AutomationError(f"Unknown day '{d}'. Use names like Mon, Tuesday, Fri.")
        if match not in out:
            out.append(match)
    return out


def describe_schedule(schedule: Schedule, time_of_day: Optional[str], date: Optional[str],
                      days: list[str], every_minutes: Optional[int]) -> str:
    if schedule == "once":
        return f"once on {date} at {time_of_day}"
    if schedule == "daily":
        return f"every day at {time_of_day}"
    if schedule == "weekly":
        return f"every {', '.join(d[:3] for d in days)} at {time_of_day}"
    if schedule == "every_minutes":
        return f"every {every_minutes} minutes"
    return "when you sign in to Windows"


def trigger_ps(schedule: Schedule, time_of_day: Optional[str], date: Optional[str],
               days: list[str], every_minutes: Optional[int]) -> str:
    """PowerShell expression for the task trigger. Validates the inputs each schedule needs."""
    if schedule in ("once", "daily", "weekly"):
        if not time_of_day or not _TIME_RE.match(time_of_day):
            raise AutomationError("time_of_day is required for this schedule, as 24-hour HH:MM (e.g. '08:30').")
    if schedule == "once":
        if not date or not _DATE_RE.match(date):
            raise AutomationError("date is required for a one-time automation, as YYYY-MM-DD.")
        return f"New-ScheduledTaskTrigger -Once -At ([datetime]::ParseExact({ps_quote(date + ' ' + time_of_day)}, 'yyyy-MM-dd HH:mm', $null))"
    if schedule == "daily":
        return f"New-ScheduledTaskTrigger -Daily -At {ps_quote(time_of_day)}"
    if schedule == "weekly":
        if not days:
            raise AutomationError("days is required for a weekly automation, e.g. ['Mon', 'Thu'].")
        return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {','.join(days)} -At {ps_quote(time_of_day)}"
    if schedule == "every_minutes":
        if not every_minutes or every_minutes < MIN_EVERY_MINUTES or every_minutes > 1440:
            raise AutomationError(f"every_minutes must be between {MIN_EVERY_MINUTES} and 1440.")
        return ("New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) "
                f"-RepetitionInterval (New-TimeSpan -Minutes {every_minutes})")
    if schedule == "at_logon":
        return "New-ScheduledTaskTrigger -AtLogOn -User \"$env:USERDOMAIN\\$env:USERNAME\""
    raise AutomationError(f"Unknown schedule '{schedule}'.")


def runner_script(name: str, command: str, shell: Literal["powershell", "cmd"], notify: bool, folder: str) -> str:
    """The run.ps1 the task executes: runs the command, appends output to a capped log, optionally notifies."""
    log = os.path.join(folder, "output.log")
    if shell == "cmd":
        body = f"$out = & cmd.exe /d /c {ps_quote(os.path.join(folder, 'command.cmd'))} 2>&1 | Out-String\n$code = $LASTEXITCODE"
    else:
        body = (
            "$global:LASTEXITCODE = 0\n"
            f"$out = & {{\n{command}\n}} *>&1 | Out-String\n"
            "$code = if ($LASTEXITCODE) { $LASTEXITCODE } else { 0 }"
        )
    notify_block = ""
    if notify:
        ok = toast_script(f"Jarvis automation '{name}' finished", "Ran successfully.")
        bad = toast_script(f"Jarvis automation '{name}' failed", "Ask Claude to check its history.")
        notify_block = f"if ($code -eq 0) {{\n{ok}}} else {{\n{bad}}}\n"
    return (
        f"# Windows Jarvis automation: {name}\n"
        "# Created by Jarvis. Delete it with win_automation_delete (or Task Scheduler > Jarvis).\n"
        "$ProgressPreference = 'SilentlyContinue'\n"
        f"$log = {ps_quote(log)}\n"
        "$started = Get-Date\n"
        "try {\n" + body + "\n} catch {\n$out = $_ | Out-String\n$code = 1\n}\n"
        "$entry = \"[$($started.ToString('yyyy-MM-dd HH:mm:ss'))] exit $code`r`n$($out.Trim())`r`n\"\n"
        "Add-Content -Path $log -Value $entry -Encoding UTF8\n"
        f"if ((Get-Item $log).Length -gt {LOG_MAX_BYTES}) {{\n"
        f"  $bytes = [IO.File]::ReadAllBytes($log); $keep = {LOG_MAX_BYTES // 2}\n"
        "  [IO.File]::WriteAllBytes($log, $bytes[($bytes.Length - $keep)..($bytes.Length - 1)])\n"
        "}\n"
        + notify_block +
        "exit $code\n"
    )


def register_ps(name: str, folder: str, trigger: str, description: str) -> str:
    script = os.path.join(folder, "run.ps1")
    args = f"-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File \"{script}\""
    return (
        f"$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument {ps_quote(args)}\n"
        f"$trigger = {trigger}\n"
        "$principal = New-ScheduledTaskPrincipal -UserId \"$env:USERDOMAIN\\$env:USERNAME\" -LogonType Interactive -RunLevel Limited\n"
        "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)\n"
        f"Register-ScheduledTask -TaskPath {ps_quote(TASK_PATH)} -TaskName {ps_quote(name)} -Action $action "
        f"-Trigger $trigger -Principal $principal -Settings $settings -Description {ps_quote(description)} -ErrorAction Stop | Out-Null\n"
        "Write-Output 'registered'\n"
    )


_LIST_PS = (
    f"$tasks = @(Get-ScheduledTask -TaskPath {ps_quote(TASK_PATH)} -ErrorAction SilentlyContinue)\n"
    "$rows = foreach ($t in $tasks) {\n"
    "  $i = $t | Get-ScheduledTaskInfo\n"
    "  [pscustomobject]@{ name = $t.TaskName; state = [string]$t.State;\n"
    "    next = if ($i.NextRunTime) { $i.NextRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' };\n"
    "    last = if ($i.LastRunTime -and $i.LastRunTime.Year -gt 2000) { $i.LastRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' };\n"
    "    result = $i.LastTaskResult }\n"
    "}\n"
    "ConvertTo-Json -InputObject @($rows) -Compress\n"
)


def list_tasks() -> list[dict]:
    r = run_command(_LIST_PS, shell="powershell", timeout=30)
    try:
        rows = json.loads(r["stdout"] or "[]")
    except json.JSONDecodeError:
        rows = []
    for row in rows:
        row["meta"] = read_meta(row["name"])
    return rows


def read_meta(name: str) -> dict:
    try:
        with open(os.path.join(automation_dir(name), "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def create(name: str, command: str, shell: Literal["powershell", "cmd"], schedule: Schedule,
           time_of_day: Optional[str], date: Optional[str], days: Optional[list[str]],
           every_minutes: Optional[int], notify: bool) -> str:
    name = validate_name(name)
    if not command.strip():
        raise AutomationError("command is empty.")
    day_list = normalize_days(days)
    trigger = trigger_ps(schedule, time_of_day, date, day_list, every_minutes)
    when = describe_schedule(schedule, time_of_day, date, day_list, every_minutes)

    existing = list_tasks()
    if any(t["name"].lower() == name.lower() for t in existing):
        raise AutomationError(f"An automation named '{name}' already exists. Delete it first or pick another name.")
    if len(existing) >= MAX_AUTOMATIONS:
        raise AutomationError(f"Jarvis keeps at most {MAX_AUTOMATIONS} automations. Delete one first.")

    folder = automation_dir(name)
    os.makedirs(folder, exist_ok=True)
    if shell == "cmd":
        with open(os.path.join(folder, "command.cmd"), "w", encoding="utf-8") as f:
            f.write("@echo off\r\nchcp 65001 >nul\r\n" + command + "\r\n")
    with open(os.path.join(folder, "run.ps1"), "w", encoding="utf-8-sig") as f:
        f.write(runner_script(name, command, shell, notify, folder))
    meta = {"name": name, "command": command, "shell": shell, "schedule": when,
            "notify": notify, "created": time.strftime("%Y-%m-%d %H:%M")}
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    preview = command if len(command) <= 200 else command[:197] + "..."
    r = run_command(register_ps(name, folder, trigger, f"Created by Windows Jarvis. Runs: {preview}"),
                    shell="powershell", timeout=30)
    if "registered" not in r["stdout"]:
        shutil.rmtree(folder, ignore_errors=True)
        raise AutomationError(f"Task Scheduler refused it: {r['stderr'] or 'no error text'}")
    return when


def run_now(name: str) -> dict:
    return run_command(
        f"Start-ScheduledTask -TaskPath {ps_quote(TASK_PATH)} -TaskName {ps_quote(name)} -ErrorAction Stop; Write-Output 'started'",
        shell="powershell", timeout=30)


def delete(name: str) -> dict:
    r = run_command(
        f"Unregister-ScheduledTask -TaskPath {ps_quote(TASK_PATH)} -TaskName {ps_quote(name)} -Confirm:$false -ErrorAction Stop; Write-Output 'deleted'",
        shell="powershell", timeout=30)
    if "deleted" in r["stdout"]:
        shutil.rmtree(automation_dir(name), ignore_errors=True)
    return r


def read_log(name: str, max_chars: int) -> str:
    try:
        with open(os.path.join(automation_dir(name), "output.log"), encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    except OSError:
        return ""
    return text[-max_chars:]


def result_text(code) -> str:
    """Task Scheduler's LastTaskResult as words."""
    known = {0: "success", 267009: "running now", 267011: "has not run yet", 267014: "stopped (took over an hour)",
             2147750687: "already running"}
    if code is None:
        return ""
    return known.get(int(code), f"exit code {code}")
