"""Smoke tests: the server imports cleanly, every tool registers, and the
safety behaviour the directory listing promises actually holds.

Runs on any OS — Windows-only behavior is behind function bodies,
so import + registration is fully testable on Linux CI. Tests that need
Windows APIs are skipped elsewhere.

Tool functions are called directly here, so every argument is passed
explicitly: omitted parameters would receive pydantic FieldInfo defaults.
"""

import asyncio
import json
import os
import pathlib
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jarvis-mcp"))

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
    # desktop
    "win_arrange_window", "win_notify",
    # wireless
    "win_wifi_networks", "win_wifi_connect", "win_wifi_disconnect",
    "win_bluetooth_devices", "win_bluetooth_power",
}

on_windows = pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")


def _tools():
    import server

    return asyncio.run(server.mcp.list_tools())


def _manifest() -> dict:
    return json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


# ── registration and metadata ────────────────────────────────────────────────

def test_all_tools_registered():
    names = {t.name for t in _tools()}
    assert names == EXPECTED_TOOLS
    assert len(names) == 52


def test_every_tool_is_annotated():
    """The Anthropic directory requires title/readOnlyHint/destructiveHint on every tool."""
    for t in _tools():
        a = t.annotations
        assert a is not None, t.name
        assert a.title, t.name
        assert a.read_only_hint is not None, t.name
        assert a.destructive_hint is not None, t.name
        assert len(t.name) <= 64, t.name


def test_manifest_lists_every_tool():
    listed = {t["name"] for t in _manifest()["tools"]}
    assert listed == {t.name for t in _tools()}


def test_versions_agree():
    import tomllib

    from mcp_instance import SERVER_VERSION

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert _manifest()["version"] == SERVER_VERSION == pyproject["project"]["version"]


def test_manifest_settings_reach_the_server():
    from utils import settings

    m = _manifest()
    env = m["server"]["mcp_config"]["env"]
    assert env[settings.ALLOW_POWER_ACTIONS] == "${user_config.allow_power_actions}"
    assert env[settings.ALLOW_PERMANENT_DELETE] == "${user_config.allow_permanent_delete}"
    for key in ("allow_power_actions", "allow_permanent_delete"):
        assert m["user_config"][key]["default"] is False


# ── privacy ──────────────────────────────────────────────────────────────────

def test_command_log_is_off_by_default(monkeypatch):
    import importlib
    from utils import shell

    monkeypatch.delenv("JARVIS_COMMAND_LOG", raising=False)
    importlib.reload(shell)
    assert shell.LOG_FILE == ""


def test_old_job_output_is_pruned(monkeypatch, tmp_path):
    from utils import jobs

    monkeypatch.setattr(jobs, "_JOBS_ROOT", str(tmp_path))
    old, fresh = tmp_path / "oldjob", tmp_path / "newjob"
    old.mkdir()
    fresh.mkdir()
    (old / "stdout.log").write_text("secret output")
    two_days_ago = time.time() - 2 * 24 * 3600
    os.utime(old, (two_days_ago, two_days_ago))
    assert jobs.prune_old_jobs() == 1
    assert not old.exists() and fresh.exists()


# ── power and delete settings ────────────────────────────────────────────────

@pytest.fixture
def settings_off(monkeypatch):
    from utils import settings

    monkeypatch.delenv(settings.ALLOW_POWER_ACTIONS, raising=False)
    monkeypatch.delenv(settings.ALLOW_PERMANENT_DELETE, raising=False)


def test_power_actions_blocked_by_default(settings_off):
    from tools import system

    for coro in (
        system.win_shutdown(delay_seconds=600),
        system.win_restart(delay_seconds=600),
        system.win_kill_process(identifier="no-such-process", force=False),
    ):
        assert "turned off" in asyncio.run(coro)


def test_permanent_delete_blocked_by_default(settings_off, tmp_path):
    from tools import files

    f = tmp_path / "keep.txt"
    f.write_text("x")
    out = asyncio.run(files.win_delete_file(path=str(f), recursive=False, permanent=True))
    assert "turned off" in out
    assert f.exists()


def test_permanent_delete_when_enabled(monkeypatch, tmp_path):
    from tools import files
    from utils import settings

    monkeypatch.setenv(settings.ALLOW_PERMANENT_DELETE, "true")
    f = tmp_path / "gone.txt"
    f.write_text("x")
    out = asyncio.run(files.win_delete_file(path=str(f), recursive=False, permanent=True))
    assert out.startswith("Permanently deleted")
    assert not f.exists()


@on_windows
def test_default_delete_uses_recycle_bin(settings_off, tmp_path):
    from tools import files

    f = tmp_path / "recycle_me.txt"
    f.write_text("x")
    out = asyncio.run(files.win_delete_file(path=str(f), recursive=False, permanent=False))
    assert out.startswith("Moved to Recycle Bin"), out
    assert not f.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has a Recycle Bin")
def test_default_delete_never_erases_without_recycle_bin(settings_off, tmp_path):
    from tools import files

    f = tmp_path / "safe.txt"
    f.write_text("x")
    out = asyncio.run(files.win_delete_file(path=str(f), recursive=False, permanent=False))
    assert out.startswith("Not deleted")
    assert f.exists()


# ── no-overwrite move/copy ───────────────────────────────────────────────────

@pytest.mark.parametrize("tool", ["win_move_file", "win_copy_file"])
def test_move_and_copy_never_overwrite(tool, tmp_path):
    from tools import files

    src, dst = tmp_path / "a.txt", tmp_path / "b.txt"
    src.write_text("A")
    dst.write_text("B")
    out = asyncio.run(getattr(files, tool)(source=str(src), destination=str(dst)))
    assert out.startswith("Destination already exists")
    assert dst.read_text() == "B" and src.exists()


# ── parsing ──────────────────────────────────────────────────────────────────

def test_wifi_parser_keeps_strongest_signal_per_network():
    from tools.wireless import _parse_networks, _saved_profiles

    sample = """
SSID 1 : HomeNet
    Authentication          : WPA2-Personal
    BSSID 1                 : aa:bb
         Signal             : 40%
         Band               : 2.4 GHz
    BSSID 2                 : cc:dd
         Signal             : 91%
         Band               : 5 GHz
SSID 2 :
    Authentication          : Open
         Signal             : 12%
"""
    nets = _parse_networks(sample)
    assert [n["ssid"] for n in nets] == ["HomeNet", "(hidden)"]
    assert nets[0]["signal"] == 91 and nets[0]["auth"] == "WPA2-Personal"
    assert _saved_profiles("    All User Profile     : HomeNet\n") == ["HomeNet"]
