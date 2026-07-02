"""
Shell executor utility.
Runs commands in cmd or PowerShell, returns structured output.
No artificial blocking — Claude handles confirmation in conversation.
Everything is logged.
"""

import asyncio
import base64
import logging
import os
import subprocess
import time
from typing import Literal, Optional

import psutil

logger = logging.getLogger(__name__)

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "command_history.log")


LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

# CREATE_NO_WINDOW keeps a console from flashing on every shell-out under GUI
# hosts (Claude Desktop). It only exists on Windows; getattr keeps the module
# importable on other platforms (CI, dev), where the flag is a harmless 0.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _build_ps_script(command: str) -> str:
    """Wrap a user command into a self-contained PowerShell script.

    Two problems this solves:

    * UTF-8 output — Windows PowerShell 5.1 writes the OEM codepage to pipes by
      default, mangling non-ASCII output when we decode it as UTF-8. The
      try/catch guards hosts without an attached console, where setting it
      throws.
    * Exit-code propagation — with ``-Command`` the host exits 0 even when a
      native command inside returned nonzero or a cmdlet threw, so failures were
      reported as ``success: True``. We reset ``$LASTEXITCODE``, run the command
      in a try/catch (terminating errors -> exit 1), then exit with the last
      native exit code.

    The result is handed to PowerShell via ``-EncodedCommand`` (base64 of the
    UTF-16LE bytes), which sidesteps the nested-quoting breakage that
    ``-Command`` suffers with quotes, ``$`` and backticks.
    """
    return (
        "try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}\n"
        "$global:LASTEXITCODE = 0\n"
        "try {\n"
        f"{command}\n"
        "}\n"
        "catch {\n"
        "  Write-Error $_\n"
        "  exit 1\n"
        "}\n"
        "if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }\n"
        "exit 0\n"
    )


def _encode_ps(script: str) -> str:
    """Encode a PowerShell script for -EncodedCommand (base64 UTF-16LE)."""
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


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
    """Resolve working directory, defaulting to user home.

    Raises NotADirectoryError when an explicit working_dir was given but does
    not exist. Silently falling back to the home dir here made scripts run in
    the wrong place, and the resulting errors looked like the script's fault.
    """
    if working_dir:
        expanded = os.path.expandvars(os.path.expanduser(working_dir))
        if os.path.isdir(expanded):
            return expanded
        raise NotADirectoryError(
            f"working_dir does not exist: '{working_dir}' (resolved to '{expanded}')"
        )
    return os.path.expanduser("~")


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all of its descendants.

    Killing only the shell on timeout leaves grandchildren (the actual
    command) running orphaned on Windows.
    """
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = parent.children(recursive=True) + [parent]
    for p in procs:
        try:
            p.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(procs, timeout=3)


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
    try:
        cwd = _resolve_working_dir(working_dir)
    except NotADirectoryError as e:
        return {
            "command": command,
            "shell": shell,
            "working_dir": working_dir,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "execution_ms": 0,
            "success": False,
        }

    start = time.monotonic()

    try:
        if shell == "powershell":
            # Run PowerShell with UTF-8 output and correct exit-code propagation.
            # -EncodedCommand (base64 UTF-16LE) avoids nested-quoting breakage.
            cmd_args = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-OutputFormat", "Text",
                "-EncodedCommand", _encode_ps(_build_ps_script(command)),
            ]
        else:
            # cmd.exe with unicode codepage
            cmd_args = ["cmd.exe", "/c", "chcp 65001 >nul 2>&1 & " + command]

        proc = subprocess.Popen(
            cmd_args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            creationflags=_CREATE_NO_WINDOW,
        )
        try:
            raw_stdout, raw_stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc.pid)
            raw_stdout, raw_stderr = proc.communicate()
            elapsed_ms = int((time.monotonic() - start) * 1000)
            _log_command(command, shell, cwd, -1)
            return {
                "command": command,
                "shell": shell,
                "working_dir": cwd,
                "exit_code": -1,
                "stdout": (raw_stdout or "").strip()[:4000],
                "stderr": f"Command timed out after {timeout} seconds. Process tree killed.",
                "execution_ms": elapsed_ms,
                "success": False,
            }

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = raw_stdout.strip()
        stderr = raw_stderr.strip()

        # Truncate large outputs — return the most useful parts
        if len(stdout) > 8000:
            half = 3500
            stdout = stdout[:half] + f"\n\n... [truncated {len(stdout) - half*2} chars] ...\n\n" + stdout[-half:]
        if len(stderr) > 2000:
            stderr = stderr[:2000] + "\n... [truncated]"

        _log_command(command, shell, cwd, proc.returncode)

        return {
            "command": command,
            "shell": shell,
            "working_dir": cwd,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "execution_ms": elapsed_ms,
            "success": proc.returncode == 0,
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


async def run_command_async(
    command: str,
    shell: Literal["powershell", "cmd"] = "powershell",
    working_dir: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    """run_command off the event loop.

    Tool handlers run on the server's event loop; a blocking subprocess call
    there stalls the whole MCP connection (heartbeats included) for the
    duration of the command.
    """
    return await asyncio.to_thread(
        run_command, command=command, shell=shell, working_dir=working_dir, timeout=timeout
    )


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
