"""
User settings from the extension's install screen.

Claude Desktop passes each manifest `user_config` value to the server as an
environment variable (see manifest.json -> server.mcp_config.env). Anything
not set counts as off, so a bare `python server.py` run is the safe default.
"""

import os

ALLOW_POWER_ACTIONS = "JARVIS_ALLOW_POWER_ACTIONS"
ALLOW_PERMANENT_DELETE = "JARVIS_ALLOW_PERMANENT_DELETE"
ALLOW_AUTOMATIONS = "JARVIS_ALLOW_AUTOMATIONS"

_SETTING_TITLES = {
    ALLOW_POWER_ACTIONS: "Allow shutdown, restart and killing processes",
    ALLOW_PERMANENT_DELETE: "Allow permanent delete (skip the Recycle Bin)",
    ALLOW_AUTOMATIONS: "Allow scheduled automations",
}


def enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def disabled_message(name: str) -> str:
    """What a tool returns when the user has not switched its setting on."""
    return (
        f"This action is turned off. To allow it, open Claude Desktop > Settings > "
        f"Extensions > Windows Jarvis and enable '{_SETTING_TITLES[name]}'."
    )
