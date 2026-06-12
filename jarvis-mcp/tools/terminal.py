"""
Terminal tools — full command-line access to Windows.

win_run_command : Run any cmd / PowerShell command, get full output back
win_run_script  : Run a multi-line PowerShell script block
"""

import logging
from typing import Literal, Optional

from pydantic import Field
from mcp_instance import mcp
from utils.shell import run_command_async, format_result

logger = logging.getLogger(__name__)


@mcp.tool(
    name="win_run_command",
    annotations={"title": "Run Terminal Command", "readOnlyHint": False, "destructiveHint": True},
)
async def win_run_command(
    command: str = Field(..., description="Any cmd or PowerShell command. E.g. 'dir C:\\Users\\Eternal\\Desktop', 'git status', 'python script.py', 'ipconfig /all', 'Get-Process | Sort CPU -Desc | Select -First 10'"),
    shell: Literal["powershell", "cmd"] = Field(default="powershell", description="Shell to use: 'powershell' (default) or 'cmd'"),
    working_dir: Optional[str] = Field(default=None, description="Directory to run in. E.g. 'C:\\\\Users\\\\Eternal\\\\Desktop\\\\project' or '~'. Defaults to user home."),
    timeout: int = Field(default=30, description="Max seconds to wait (default 30, max 300)", ge=1, le=300),
) -> str:
    """
    Execute any command in Windows PowerShell or CMD and return the full output.

    Use for: running scripts, git commands, pip/npm installs, system queries,
    PowerShell cmdlets, file operations — anything you'd type in a terminal.
    Returns full stdout, stderr, exit code, and timing.
    """
    result = await run_command_async(command=command, shell=shell, working_dir=working_dir, timeout=timeout)
    return format_result(result)


@mcp.tool(
    name="win_run_script",
    annotations={"title": "Run PowerShell Script", "readOnlyHint": False, "destructiveHint": True},
)
async def win_run_script(
    script: str = Field(..., description="Multi-line PowerShell script to execute as a single block. Write it as you would in a .ps1 file."),
    working_dir: Optional[str] = Field(default=None, description="Directory to run the script in. Defaults to user home."),
    timeout: int = Field(default=60, description="Max seconds to wait (default 60)", ge=1, le=600),
) -> str:
    """
    Execute a multi-line PowerShell script block and return the full output.

    Use when you need loops, conditionals, or multi-line logic.
    The entire script runs as a single unit.
    """
    wrapped = f"& {{\n{script}\n}}"
    result = await run_command_async(command=wrapped, shell="powershell", working_dir=working_dir, timeout=timeout)
    return format_result(result)
