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
import re
import subprocess
import tempfile
import time
from typing import Literal, Optional
from xml.etree import ElementTree as ET

import psutil

logger = logging.getLogger(__name__)

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "command_history.log")

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

_CLIXML_MARKER = "#< CLIXML"
_XML_ESCAPE_RE = re.compile(r"_x([0-9A-Fa-f]{4})_")


def _decode_ps_escapes(text: str) -> str:
    """Decode CLIXML _xHHHH_ character escapes (e.g. _x000D_ -> CR)."""
    return _XML_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def clean_clixml(text: str) -> str:
    """Turn PowerShell's CLIXML-serialized error stream back into plain text.

    When powershell.exe's stderr is redirected, it serializes error records as
    CLIXML (``#< CLIXML`` followed by an ``<Objs>`` document) instead of plain
    text, so callers see markup garbage instead of the message. We extract the
    text of the top-level ``<S>`` string records (which hold the error text) and
    decode the ``_xHHHH_`` escapes. Anything printed before the marker is kept
    as-is. If parsing fails, the original text is returned rather than dropped.
    """
    if not text or _CLIXML_MARKER not in text:
        return text

    prefix, _, blob = text.partition(_CLIXML_MARKER)
    blob = blob.lstrip("\r\n ")
    try:
        root = ET.fromstring(blob)
    except ET.ParseError:
        return text

    parts = []
    for el in list(root):
        # Namespaced tags arrive as '{...}S'; compare on the local name.
        if el.tag.split("}")[-1] == "S" and el.text:
            parts.append(_decode_ps_escapes(el.text))

    # A blob that parsed cleanly but held no <S> string records is progress or
    # other metadata, not output. Returning the original text here was why
    # progress-only CLIXML came through as raw markup.
    cleaned = (prefix + "".join(parts)).strip()
    if not parts:
        return prefix.strip()
    return cleaned or text

# CREATE_NO_WINDOW keeps a console from flashing on every shell-out under GUI
# hosts (Claude Desktop). It only exists on Windows; getattr keeps the module
# importable on other platforms (CI, dev), where the flag is a harmless 0.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _build_ps_script(command: str) -> str:
    """Build the PowerShell script that wraps the user command.

    Three things this handles:

    * UTF-8 output — Windows PowerShell 5.1 defaults to the OEM codepage for
      pipes.  We set OutputEncoding to UTF-8 first.
    * Exit-code propagation — we capture $LASTEXITCODE and exit with it so the
      caller sees a real nonzero exit when a native command fails.
    * PATH for non-interactive sessions — MCP sessions don't inherit the user's
      interactive PATH, so node/pnpm/npm may not be found.  We prepend common
      install locations and strip Windows AppX stubs (e.g. WindowsApps\\node.exe)
      which silently exit 0 with no stdout when run without a Store session.

    NOTE: This script is written to a temp .ps1 file and run with
    ``powershell.exe -File``.  Using file I/O (not -EncodedCommand + stdout PIPE)
    is critical on Windows — when PowerShell's stdout is a pipe, native-command
    output silently disappears.  Writing to a file and reading it back captures
    everything reliably.
    """
    return (
        "try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}\n"
        # Progress records are serialized into the redirected error stream as
        # CLIXML. They carry no information a caller wants and they buried every
        # real message in markup.
        "$ProgressPreference = 'SilentlyContinue'\n"
        "$global:LASTEXITCODE = 0\n"
        "# --- PATH fix for non-interactive MCP sessions ---\n"
        "# Strip Windows AppX stubs (e.g. WindowsApps\\node.exe) that silently\n"
        "# exit 0 with no stdout/stderr when run outside an interactive Store session.\n"
        "$env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notmatch 'WindowsApps' }) -join ';'\n"
        "# Prepend common Node.js / package-manager locations.\n"
        "foreach ($_p in @(\n"
        "    \"$env:ProgramFiles\\nodejs\",\n"
        "    \"$env:LOCALAPPDATA\\Programs\\nodejs\",\n"
        "    \"$env:LOCALAPPDATA\\Volta\\bin\",\n"
        "    \"$env:LOCALAPPDATA\\nvm\",\n"
        "    \"$env:APPDATA\\npm\",\n"
        "    \"$env:LOCALAPPDATA\\nvs\\default\")) {\n"
        "    if ((Test-Path $_p) -and ($env:PATH -split ';') -notcontains $_p) {\n"
        "        $env:PATH = $_p + ';' + $env:PATH\n"
        "    }\n"
        "}\n"
        "# --- end PATH fix ---\n"
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


def build_shell_args(command: str, shell: str) -> list[str]:
    """Build the argv for launching a command in the chosen shell.

    Used by the background-job runner (utils/jobs.py), which redirects the
    child's stdout/stderr to real files rather than pipes.

    run_command() deliberately does NOT use this: it writes the script to a temp
    .ps1 and launches it through cmd.exe with an OS-level > redirect, because
    handles passed by subprocess.Popen do not reliably propagate native-EXE
    output through PowerShell's pipeline. Keep the two paths separate.
    """
    if shell == "powershell":
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-OutputFormat", "Text",
            "-EncodedCommand", _encode_ps(_build_ps_script(command)),
        ]
    return ["cmd.exe", "/c", "chcp 65001 >nul 2>&1 & " + command]


def _log_command(command: str, shell: str, working_dir: str, exit_code: int) -> None:
    """Append executed command to history log. Rotates at 5 MB."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
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
    not exist.  Silently falling back to the home dir made scripts run in the
    wrong place, and the resulting errors looked like the script's fault.
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

    Implementation note — PowerShell path:
        When PowerShell's stdout is connected to a PIPE (as with subprocess.PIPE),
        native-command (EXE) output silently vanishes on Windows.  PowerShell
        cmdlet output (Write-Output, etc.) still works, but node, git, pnpm, etc.
        produce nothing.

        Fix: write the PS script to a temp .ps1 file, redirect stdout/stderr to
        temp files via open() file handles (not PIPE), then read the files back.
        File handles propagate native-command output correctly.
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

    # ── PowerShell path ──────────────────────────────────────────────────────
    if shell == "powershell":
        script_path = out_path = err_path = None
        try:
            # Write the PS script to a temp file (UTF-8 with BOM so PS 5.x
            # reads it as UTF-8 regardless of the system code page).
            tmp_dir = tempfile.gettempdir()
            script_path = os.path.join(tmp_dir, f"jarvis_{os.getpid()}_{int(time.monotonic()*1000)}.ps1")
            out_path    = script_path + ".out"
            err_path    = script_path + ".err"

            with open(script_path, "w", encoding="utf-8-sig") as sf:
                sf.write(_build_ps_script(command))

            # Launch PowerShell via cmd.exe so cmd's OS-level > redirect sets up
            # PS stdout/stderr as file handles.  This sidesteps the issue where
            # Python's subprocess.Popen-passed file handles don't propagate native
            # EXE stdout through PowerShell's internal pipeline correctly.
            # Pass as a flat STRING (not a list) so Python's list2cmdline() is
            # never called.  list2cmdline wraps the third element in outer quotes
            # and escapes inner " as \" — but cmd.exe doesn't understand \"
            # escaping, so the command-line arrives garbled and cmd exits 1
            # immediately.  Passing a string lets CreateProcess receive it as-is:
            # cmd.exe sees the > and 2> as redirections, not literal text.
            cmd_str = (
                f'cmd.exe /c '
                f'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass'
                f' -File "{script_path}" > "{out_path}" 2> "{err_path}"'
            )

            timed_out = False
            proc = subprocess.Popen(
                cmd_str,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,   # cmd.exe's own stdout (unused)
                stderr=subprocess.PIPE,   # cmd.exe's own stderr (unused)
                cwd=cwd,
                creationflags=_CREATE_NO_WINDOW,
            )

            try:
                # communicate() drains the PIPE handles so cmd.exe doesn't
                # deadlock, then waits for process exit.
                proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc.pid)
                proc.communicate()
                timed_out = True

            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Read output from the files cmd.exe redirected PS output into.
            raw_stdout = ""
            raw_stderr = ""
            if os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    raw_stdout = f.read().decode("utf-8", errors="replace")
            if os.path.exists(err_path):
                with open(err_path, "rb") as f:
                    raw_stderr = f.read().decode("utf-8", errors="replace")

            if timed_out:
                _log_command(command, shell, cwd, -1)
                return {
                    "command": command,
                    "shell": shell,
                    "working_dir": cwd,
                    "exit_code": -1,
                    "stdout": raw_stdout.strip()[:4000],
                    "stderr": f"Command timed out after {timeout} seconds. Process tree killed.",
                    "execution_ms": elapsed_ms,
                    "success": False,
                }

            exit_code = proc.returncode

        except FileNotFoundError as e:
            return {
                "command": command,
                "shell": shell,
                "working_dir": cwd,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Shell not found: {e}. Is PowerShell installed?",
                "execution_ms": int((time.monotonic() - start) * 1000),
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
                "execution_ms": int((time.monotonic() - start) * 1000),
                "success": False,
            }
        finally:
            for p in (script_path, out_path, err_path):
                if p:
                    try:
                        os.unlink(p)
                    except Exception:
                        pass

    # ── cmd.exe path ─────────────────────────────────────────────────────────
    else:
        try:
            cmd_str = "cmd.exe /c chcp 65001 >nul 2>&1 & " + command

            proc = subprocess.Popen(
                cmd_str,
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
            exit_code = proc.returncode

        except FileNotFoundError as e:
            return {
                "command": command,
                "shell": shell,
                "working_dir": cwd,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Shell not found: {e}. Is cmd.exe installed?",
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

    # ── shared post-processing ────────────────────────────────────────────────
    elapsed_ms = int((time.monotonic() - start) * 1000)
    stdout = raw_stdout.strip()
    stderr = clean_clixml(raw_stderr).strip()

    # Truncate large outputs — return the most useful parts
    if len(stdout) > 8000:
        half = 3500
        stdout = stdout[:half] + f"\n\n... [truncated {len(stdout) - half*2} chars] ...\n\n" + stdout[-half:]
    if len(stderr) > 2000:
        stderr = stderr[:2000] + "\n... [truncated]"

    _log_command(command, shell, cwd, exit_code)

    return {
        "command": command,
        "shell": shell,
        "working_dir": cwd,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "execution_ms": elapsed_ms,
        "success": exit_code == 0,
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
