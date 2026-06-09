#!/usr/bin/env python3
"""
windows_mcp — Jarvis Windows OS Control MCP Server
====================================================
Gives Claude full control over the Windows machine via 32 tools across:
  - Terminal   : run any cmd/PowerShell command or script
  - Apps       : open, close, list, switch applications
  - System     : info, processes, volume, screenshot, shutdown/restart/lock
  - Files      : list, read, search, create, move, copy, delete
  - Browser    : open URLs, web search
  - Media      : play/pause/next/prev/stop
  - Clipboard  : get/set clipboard text
  - Screen     : OCR screen text, active window info

Transport: stdio (runs as subprocess of Claude Desktop)
"""

import logging
import sys

# ── Shared FastMCP instance must be imported first ──────────────────────────
from mcp_instance import mcp  # noqa: F401

# ── Register all tools by importing each module ─────────────────────────────
# Imports trigger the @mcp.tool() decorators in each file.
import tools.terminal   # win_run_command, win_run_script
import tools.apps       # win_open_app, win_close_app, win_list_running_apps, win_switch_to_app, win_list_installed
import tools.system     # win_get_system_info, win_list_processes, win_kill_process, win_adjust_volume,
                        # win_take_screenshot, win_get_network_info, win_shutdown, win_restart, win_lock, win_cancel_shutdown
import tools.files      # win_list_directory, win_read_file, win_search_files, win_create_folder,
                        # win_move_file, win_copy_file, win_delete_file, win_get_file_info
import tools.browser    # win_open_url, win_search_web
import tools.media      # win_media_control
import tools.clipboard  # win_get_clipboard, win_set_clipboard
import tools.screen     # win_read_screen_text, win_get_active_window


if __name__ == "__main__":
    # stdio transport — Claude Desktop spawns this as a subprocess
    # Log to stderr only (stdout is reserved for MCP protocol messages)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    mcp.run()
