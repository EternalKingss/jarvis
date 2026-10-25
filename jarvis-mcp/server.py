#!/usr/bin/env python3
"""
windows_mcp — Jarvis Windows OS Control MCP Server
====================================================
Gives Claude full control over the Windows machine via 67 tools across:
  - Terminal   : run any cmd/PowerShell command or script
  - Jobs       : start/poll/stop long-running background commands
  - Apps       : open, close, list, switch applications
  - System     : info, processes, volume, screenshot, shutdown/restart/lock
  - Desktop    : arrange windows, show notifications, scheduled automations
  - Settings   : brightness, light/dark mode, volume per app, audio output, power plan
  - Wireless   : Wi-Fi networks, Bluetooth devices and radio
  - Files      : list, read, search, create, move, copy, delete; search inside, zip, open, read PDF/Word
  - Browser    : open URLs, web search
  - Media      : play/pause/next/prev/stop
  - Clipboard  : get/set clipboard text
  - Screen     : OCR screen text (built-in Windows OCR), active window info
  - UI Automation : inspect, click, type into, read and select controls in any app

Transport: stdio (runs as subprocess of Claude Desktop)
"""

import logging
import sys

# ── Shared MCPServer instance must be imported first ──────────────────────────
from mcp_instance import mcp  # noqa: F401

import os
import socket


def _backfill_env() -> None:
    """Claude Desktop launches MCP servers with an incomplete Windows env.
    Repair the well-known vars so child shells behave like normal sessions."""
    os.environ.setdefault("COMPUTERNAME", socket.gethostname().upper())
    os.environ.setdefault("USERDOMAIN", os.environ.get("COMPUTERNAME", socket.gethostname().upper()))
    os.environ.setdefault("LOGONSERVER", "\\\\" + os.environ["COMPUTERNAME"])


_backfill_env()


# ── Register all tools by importing each module ─────────────────────────────
# Imports trigger the @mcp.tool() decorators in each file.
import tools.terminal   # noqa: F401  win_run_command, win_run_script
import tools.apps       # noqa: F401  win_open_app, win_close_app, win_list_running_apps, win_switch_to_app, win_list_installed
import tools.system     # noqa: F401  win_get_system_info, win_list_processes, win_kill_process, win_adjust_volume,
                        #             win_take_screenshot, win_get_network_info, win_shutdown, win_restart, win_lock, win_cancel_shutdown
import tools.files      # noqa: F401  win_list_directory, win_read_file, win_search_files, win_create_folder,
                        #             win_move_file, win_copy_file, win_delete_file, win_get_file_info
import tools.browser    # noqa: F401  win_open_url, win_search_web
import tools.media      # noqa: F401  win_media_control
import tools.clipboard  # noqa: F401  win_get_clipboard, win_set_clipboard
import tools.screen     # noqa: F401  win_read_screen_text, win_get_active_window
import tools.jobs       # noqa: F401  win_start_job, win_job_output, win_stop_job, win_list_jobs
import tools.uia        # noqa: F401  win_uia_inspect, win_uia_click, win_uia_type_into, win_uia_read,
                        #             win_uia_select, win_uia_focus, win_uia_menu, win_uia_list_windows
import tools.desktop    # noqa: F401  win_arrange_window, win_notify
import tools.wireless   # noqa: F401  win_wifi_networks, win_wifi_connect, win_wifi_disconnect,
                        #             win_bluetooth_devices, win_bluetooth_power
import tools.automations  # noqa: F401  win_automation_create, win_automation_list, win_automation_run_now,
                          #             win_automation_history, win_automation_delete
import tools.winsettings  # noqa: F401  win_brightness, win_theme, win_volume_level, win_audio_output, win_power_plan
import tools.documents    # noqa: F401  win_search_in_files, win_zip, win_unzip, win_open_file, win_read_document


if __name__ == "__main__":
    # stdio transport — Claude Desktop spawns this as a subprocess
    # Log to stderr only (stdout is reserved for MCP protocol messages)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    mcp.run()
