"""
Shell executor utility.
Runs commands in cmd or PowerShell, returns structured output.
No artificial blocking — Claude handles confirmation in conversation.
Everything is logged.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from typing import Literal, Optional

logger = logging.getLogger(__name__)

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "command_history.log")


LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _log_command(command: str, shell: str, working_dir: str, exit_code: int) -> None:
    """Append executed command to history log. Rotates at 5 MB."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Rotate if over size limit
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= LOG_MAX_BYTES:
            bak = LOG_FILE + ".bak"
            if os.path.exists(bak):
                os.remove(bak)
            os.rename(LOG_FILE, bak)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{shell}] [{exit_code}] {command}  (cwd: {working_dir})\n")
    except Exception as e:
        logger.warning(f"Failed to write command log: {e}")


def _resolve_working_dir(working_dir: Optional[str]) -> str:
    """Resolve working directory, defaulting to user home."""
    if working_dir:
        expanded = os.path.expandvars(os.path.expanduser(working_dir))
        if os.path.isdir(expanded):
            return expanded
        logger.warning(f"Working dir '{working_dir}' not found, using home dir")
    return os.path.expanduser("~")


def run_command(
    command: str,
    shell: Literal["powershell", "cmd"] = "powershell",
    working_dir: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    """
    Execute a shell command and return structured results.

    Returns a dict with:
        command       — the command that was run
        shell         — shell used
        working_dir   — directory it ran in
        exit_code     — process exit code (0 = success)
        stdout        — standard output (truncated at 8000 chars)
        stderr        — standard error (truncated at 2000 chars)
        execution_ms  — wall-clock time in milliseconds
        success       — True if exit_code == 0
    """
    cwd = _resolve_working_dir(working_dir)
    start = time.monotonic()

    try:
        if shell == "powershell":
            # Run PowerShell with UTF-8 output, bypass execution policy for scripts
            cmd_args = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-OutputFormat", "Text",
                "-Command", command,
            ]
        else:
            # cmd.exe with unicode codepage
            cmd_args = ["cmd.exe", "/c", "chcp 65001 >nul 2>&1 & " + command]

        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Truncate large outputs — return the most useful parts
        if len(stdout) > 8000:
            half = 3500
            stdout = stdout[:half] + f"\n\n... [truncated {len(stdout) - half*2} chars] ...\n\n" + stdout[-half:]
        if len(stderr) > 2000:
            stderr = stderr[:2000] + f"\n... [truncated]"

        _log_command(command, shell, cwd, result.returncode)

        return {
            "command": command,
            "shell": shell,
            "working_dir": cwd,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "execution_ms": elapsed_ms,
            "success": result.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log_command(command, shell, cwd, -1)
        return {
            "command": command,
            "shell": shell,
            "working_dir": cwd,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds.",
            "execution_ms": elapsed_ms,
            "success": False,
        }

    except FileNotFoundError as e:
        return {
            "command": command,
            "shell": shell,
            "working_dir": cwd,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Shell not found: {e}. Is PowerShell installed?",
            "execution_ms": 0,
            "success": False,
        }

    except Exception as e:
        logger.error(f"Unexpected error running command: {e}")
        return {
            "command": command,
            "shell": shell,
            "working_dir": cwd,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Unexpected error: {type(e).__name__}: {e}",
            "execution_ms": 0,
            "success": False,
        }


def format_result(result: dict) -> str:
    """Format a run_command result dict into a readable string for Claude."""
    lines = [
        f"Command : {result['command']}",
        f"Shell   : {result['shell']}",
        f"Cwd     : {result['working_dir']}",
        f"Exit    : {result['exit_code']} ({'success' if result['success'] else 'failed'})",
        f"Time    : {result['execution_ms']}ms",
    ]

    if result["stdout"]:
        lines += ["", "── stdout ──────────────────────────────", result["stdout"]]

    if result["stderr"]:
        lines += ["", "── stderr ──────────────────────────────", result["stderr"]]

    return "\n".join(lines)
