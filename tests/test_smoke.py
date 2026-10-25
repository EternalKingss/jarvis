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
    "win_list_directory", "win_read_file", "win_write_file", "win_search_files",
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
    # ui automation
    "win_uia_inspect", "win_uia_click", "win_uia_type_into", "win_uia_read",
    "win_uia_select", "win_uia_focus", "win_uia_menu", "win_uia_list_windows",
}


def test_all_tools_registered():
    import server

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
    assert len(tools) == 45


def test_every_tool_is_annotated():
    """The Anthropic directory requires title/readOnlyHint/destructiveHint on every tool."""
    import server

    for t in asyncio.run(server.mcp.list_tools()):
        a = t.annotations
        assert a is not None, t.name
        assert a.title, t.name
        assert a.readOnlyHint is not None, t.name
        assert a.destructiveHint is not None, t.name
        assert len(t.name) <= 64, t.name


def test_manifest_lists_every_tool():
    import json
    import server

    root = pathlib.Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    listed = {t["name"] for t in manifest["tools"]}
    registered = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert listed == registered


def test_command_log_is_off_by_default(monkeypatch):
    import importlib
    from utils import shell

    monkeypatch.delenv("JARVIS_COMMAND_LOG", raising=False)
    importlib.reload(shell)
    assert shell.LOG_FILE == ""
