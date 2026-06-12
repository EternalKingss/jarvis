"""Process helpers shared by the app and system tools."""

import os

import psutil


def protected_pids() -> set[int]:
    """PIDs that kill/close tools must never touch: this server and its
    ancestors (the Python process and the Claude Desktop process that
    spawned it). A substring match like 'python' or 'claude' would
    otherwise terminate the MCP server mid-session.
    """
    pids = {os.getpid()}
    try:
        for parent in psutil.Process().parents():
            pids.add(parent.pid)
    except psutil.Error:
        pass
    return pids
