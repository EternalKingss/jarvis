"""
Background job runner.

run_command runs a command to completion under a timeout — fine for quick
commands, useless for installs, builds, and dev servers that either run for
minutes or never exit. This module launches commands as detached background
jobs with no timeout, streams their output to files, and lets callers poll for
incremental output and status.

Design notes:
  * Output goes to per-job files (stdout.log / stderr.log). Nothing is held in
    pipe buffers, so there is no risk of the child blocking on a full pipe, and
    output is never lost — it can be re-read from the start at any time.
  * Polling is incremental: each read advances a byte offset per stream, so a
    caller "tails" the job by calling win_job_output repeatedly.
  * Jobs live in a module-level registry for the lifetime of the MCP server
    process, so they persist across tool calls.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
import uuid
from typing import Literal, Optional

from utils.shell import (
    _CREATE_NO_WINDOW,
    _kill_process_tree,
    _resolve_working_dir,
    build_shell_args,
    clean_clixml,
)

logger = logging.getLogger(__name__)

_JOBS_ROOT = os.path.join(tempfile.gettempdir(), "jarvis_jobs")
_MAX_OUTPUT_CHARS = 8000

_jobs: dict[str, "Job"] = {}


class Job:
    """A single background command and its captured output."""

    def __init__(self, job_id: str, command: str, shell: str, cwd: str):
        self.id = job_id
        self.command = command
        self.shell = shell
        self.cwd = cwd
        self.started_at = time.time()
        self.ended_at: Optional[float] = None
        self.exit_code: Optional[int] = None
        self.killed = False

        self.dir = os.path.join(_JOBS_ROOT, job_id)
        self.stdout_path = os.path.join(self.dir, "stdout.log")
        self.stderr_path = os.path.join(self.dir, "stderr.log")

        self.proc: Optional[subprocess.Popen] = None
        # Byte offsets already returned to the caller, per stream.
        self._offsets = {"stdout": 0, "stderr": 0}

    def poll(self) -> Optional[int]:
        """Refresh and return the exit code (None while still running)."""
        if self.exit_code is None and self.proc is not None:
            rc = self.proc.poll()
            if rc is not None:
                self.exit_code = rc
                self.ended_at = time.time()
        return self.exit_code

    @property
    def status(self) -> str:
        if self.poll() is None:
            return "running"
        if self.killed:
            return "stopped"
        return "exited"

    @property
    def running(self) -> bool:
        return self.status == "running"

    def _elapsed(self) -> float:
        end = self.ended_at if self.ended_at is not None else time.time()
        return round(end - self.started_at, 1)

    def read_new(self, stream: str, from_start: bool) -> str:
        """Return output for a stream, advancing the incremental read offset."""
        path = self.stdout_path if stream == "stdout" else self.stderr_path
        offset = 0 if from_start else self._offsets[stream]
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                raw = f.read()
                self._offsets[stream] = f.tell()
        except FileNotFoundError:
            return ""
        text = raw.decode("utf-8", errors="replace")
        if stream == "stderr":
            text = clean_clixml(text)
        return text

    def summary(self) -> dict:
        return {
            "job_id": self.id,
            "command": self.command,
            "shell": self.shell,
            "working_dir": self.cwd,
            "status": self.status,
            "running": self.running,
            "exit_code": self.exit_code,
            "elapsed_seconds": self._elapsed(),
        }


def _cap(text: str) -> str:
    """Keep the most recent output when a chunk is very large (live tail)."""
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    kept = text[-_MAX_OUTPUT_CHARS:]
    return f"... [truncated {len(text) - _MAX_OUTPUT_CHARS} earlier chars] ...\n{kept}"


def start_job(
    command: str,
    shell: Literal["powershell", "cmd"] = "powershell",
    working_dir: Optional[str] = None,
) -> dict:
    """Launch a command as a background job. Returns immediately with a job_id."""
    try:
        cwd = _resolve_working_dir(working_dir)
    except NotADirectoryError as e:
        return {"success": False, "error": str(e)}

    job_id = uuid.uuid4().hex[:8]
    job = Job(job_id, command, shell, cwd)
    os.makedirs(job.dir, exist_ok=True)

    try:
        out_f = open(job.stdout_path, "wb")
        err_f = open(job.stderr_path, "wb")
        try:
            job.proc = subprocess.Popen(
                build_shell_args(command, shell),
                stdin=subprocess.DEVNULL,
                stdout=out_f,
                stderr=err_f,
                cwd=cwd,
                creationflags=_CREATE_NO_WINDOW,
            )
        finally:
            # The child inherited its own handles; close the parent copies so
            # EOF is observed correctly when the child exits.
            out_f.close()
            err_f.close()
    except FileNotFoundError as e:
        return {"success": False, "error": f"Shell not found: {e}. Is PowerShell installed?"}
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Failed to start job: {e}")
        return {"success": False, "error": f"{type(e).__name__}: {e}"}

    _jobs[job_id] = job
    result = job.summary()
    result["success"] = True
    result["pid"] = job.proc.pid
    return result


def job_output(job_id: str, from_start: bool = False) -> dict:
    """Return output since the last read (or from the start) plus live status."""
    job = _jobs.get(job_id)
    if job is None:
        return {"success": False, "error": f"No such job: {job_id}"}

    job.poll()
    stdout = _cap(job.read_new("stdout", from_start))
    stderr = _cap(job.read_new("stderr", from_start))

    result = job.summary()
    result["success"] = True
    result["stdout"] = stdout
    result["stderr"] = stderr
    return result


def stop_job(job_id: str) -> dict:
    """Kill a running job and its process tree."""
    job = _jobs.get(job_id)
    if job is None:
        return {"success": False, "error": f"No such job: {job_id}"}

    if job.poll() is None:
        _kill_process_tree(job.proc.pid)
        job.killed = True
        try:
            job.proc.wait(timeout=5)
        except Exception:
            pass
        # The exit code after an external kill is unreliable — psutil may reap
        # the process before Popen does, making poll() report a false 0 — so
        # record it as a kill (-1) instead of trusting the returncode.
        job.exit_code = -1
        job.ended_at = time.time()

    result = job.summary()
    result["success"] = True
    return result


def list_jobs() -> dict:
    """Return a summary of every job started this server session."""
    return {"success": True, "jobs": [job.summary() for job in _jobs.values()]}


# ── async wrappers ──────────────────────────────────────────────────────────
# Tool handlers run on the server event loop; keep file/subprocess work off it.

async def start_job_async(command, shell="powershell", working_dir=None) -> dict:
    return await asyncio.to_thread(start_job, command, shell, working_dir)


async def job_output_async(job_id, from_start=False) -> dict:
    return await asyncio.to_thread(job_output, job_id, from_start)


async def stop_job_async(job_id) -> dict:
    return await asyncio.to_thread(stop_job, job_id)


async def list_jobs_async() -> dict:
    return await asyncio.to_thread(list_jobs)


def format_job(result: dict) -> str:
    """Format a job result dict into readable text for Claude."""
    if not result.get("success"):
        return f"Error: {result.get('error', 'unknown error')}"

    lines = [
        f"Job     : {result['job_id']}",
        f"Command : {result['command']}",
        f"Cwd     : {result['working_dir']}",
        f"Status  : {result['status']}"
        + (f" (exit {result['exit_code']})" if result.get("exit_code") is not None else ""),
        f"Elapsed : {result['elapsed_seconds']}s",
    ]
    if "pid" in result:
        lines.append(f"PID     : {result['pid']}")

    if "stdout" in result or "stderr" in result:
        if result.get("stdout"):
            lines += ["", "── stdout (new) ────────────────────────", result["stdout"]]
        if result.get("stderr"):
            lines += ["", "── stderr (new) ────────────────────────", result["stderr"]]
        if not result.get("stdout") and not result.get("stderr"):
            lines += ["", "(no new output since last read)"]

    return "\n".join(lines)


def format_job_list(result: dict) -> str:
    """Format list_jobs output for Claude."""
    jobs = result.get("jobs", [])
    if not jobs:
        return "No background jobs this session."
    lines = ["Background jobs:"]
    for j in jobs:
        exit_part = f" exit={j['exit_code']}" if j.get("exit_code") is not None else ""
        lines.append(
            f"  [{j['job_id']}] {j['status']}{exit_part}  {j['elapsed_seconds']}s  :: {j['command']}"
        )
    return "\n".join(lines)
