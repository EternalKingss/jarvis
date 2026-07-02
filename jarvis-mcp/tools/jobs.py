"""
Background job tools — run long commands without a timeout.

win_start_job   : Launch a command in the background, get a job_id immediately
win_job_output  : Poll a job for new output + status (live tail)
win_stop_job    : Kill a running job and its process tree
win_list_jobs   : List every job started this session

Use these instead of win_run_command whenever a command may run longer than the
timeout — installs, builds, dev servers, watchers. Start the job, then poll it
with win_job_output to watch output stream in and to check whether it finished.
"""

import logging
from typing import Literal, Optional

from pydantic import Field
from mcp_instance import mcp
from utils.jobs import (
    format_job,
    format_job_list,
    job_output_async,
    list_jobs_async,
    start_job_async,
    stop_job_async,
)

logger = logging.getLogger(__name__)


@mcp.tool(
    name="win_start_job",
    annotations={"title": "Start Background Job", "readOnlyHint": False, "destructiveHint": True},
)
async def win_start_job(
    command: str = Field(..., description="Command to run in the background. E.g. 'pip install -r requirements.txt', 'npm run dev', 'python train.py'."),
    shell: Literal["powershell", "cmd"] = Field(default="powershell", description="Shell to use: 'powershell' (default) or 'cmd'"),
    working_dir: Optional[str] = Field(default=None, description="Directory to run in. E.g. 'C:\\\\Users\\\\Eternal\\\\project'. Defaults to user home. Errors if it does not exist."),
) -> str:
    """
    Launch a command as a background job and return a job_id immediately.

    Unlike win_run_command there is NO timeout — the process keeps running after
    this returns. Use for anything long-running: installs, builds, dev servers,
    watchers. Poll progress and completion with win_job_output(job_id); stop it
    with win_stop_job(job_id).
    """
    result = await start_job_async(command=command, shell=shell, working_dir=working_dir)
    return format_job(result)


@mcp.tool(
    name="win_job_output",
    annotations={"title": "Get Background Job Output", "readOnlyHint": True, "destructiveHint": False},
)
async def win_job_output(
    job_id: str = Field(..., description="The job_id returned by win_start_job."),
    from_start: bool = Field(default=False, description="If true, return all output from the beginning instead of only new output since the last poll."),
) -> str:
    """
    Poll a background job: returns new output since your last call plus live
    status (running / exited + exit code). Call repeatedly to tail a job as it
    runs, and to confirm whether it actually finished and with what exit code.
    Pass from_start=true to re-read the entire output.
    """
    result = await job_output_async(job_id=job_id, from_start=from_start)
    return format_job(result)


@mcp.tool(
    name="win_stop_job",
    annotations={"title": "Stop Background Job", "readOnlyHint": False, "destructiveHint": True},
)
async def win_stop_job(
    job_id: str = Field(..., description="The job_id returned by win_start_job."),
) -> str:
    """Kill a running background job and its entire process tree."""
    result = await stop_job_async(job_id=job_id)
    return format_job(result)


@mcp.tool(
    name="win_list_jobs",
    annotations={"title": "List Background Jobs", "readOnlyHint": True, "destructiveHint": False},
)
async def win_list_jobs() -> str:
    """List every background job started this session with its current status."""
    result = await list_jobs_async()
    return format_job_list(result)
