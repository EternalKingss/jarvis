"""Smoke test: the server imports cleanly and every tool registers.

Runs on any OS — Windows-only behavior is behind function bodies,
so import + registration is fully testable on Linux CI.
"""

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "jarvis-mcp"))

EXPECTED_TOOLS = {
    # terminal
    "win_run_command", "win_run_script",
    # jobs
    "win_start_job", "win_job_output", "win_stop_job", "win_list_jobs",
    # apps
    "win_open_app", "win_close_app", "win_list_running_apps",
    "win_switch_to_app", "win_list_installed",
    # system
    "win_get_system_info", "win_list_processes", "win_kill_process",
    "win_adjust_volume", "win_take_screenshot", "win_get_network_info",
    "win_shutdown", "win_restart", "win_cancel_shutdown", "win_lock",
    # files
    "win_list_directory", "win_read_file", "win_search_files",
    "win_create_folder", "win_move_file", "win_copy_file",
    "win_delete_file", "win_get_file_info",
    # browser
    "win_open_url", "win_search_web",
    # media
    "win_media_control",
    # clipboard
    "win_get_clipboard", "win_set_clipboard",
    # screen
    "win_read_screen_text", "win_get_active_window",
}


def test_all_tools_registered():
    import server

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
    assert len(tools) == 36
