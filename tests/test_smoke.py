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
    # automations
    "win_automation_create", "win_automation_list", "win_automation_run_now",
    "win_automation_history", "win_automation_delete",
    # windows settings
    "win_brightness", "win_theme", "win_volume_level", "win_audio_output", "win_power_plan",
    # file power-ups
    "win_search_in_files", "win_zip", "win_unzip", "win_open_file", "win_read_document",
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
    assert len(names) == 67


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
    assert env[settings.ALLOW_AUTOMATIONS] == "${user_config.allow_automations}"
    for key in ("allow_power_actions", "allow_permanent_delete", "allow_automations"):
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
    monkeypatch.delenv(settings.ALLOW_AUTOMATIONS, raising=False)


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


# ── scheduled automations ────────────────────────────────────────────────────

def test_automations_blocked_by_default(settings_off):
    from tools import automations

    out = asyncio.run(automations.win_automation_create(
        name="x", command="echo hi", schedule="daily", time_of_day="09:00", date=None,
        days=None, every_minutes=None, shell="powershell", notify=False))
    assert "turned off" in out
    assert "turned off" in asyncio.run(automations.win_automation_run_now(name="x"))


def test_automation_storage_avoids_redirected_appdata():
    """Claude Desktop (MSIX) redirects AppData writes, which Task Scheduler can't see."""
    from utils import automations as auto

    assert "appdata" not in auto.root_dir().lower()
    assert auto.root_dir().startswith(os.path.expanduser("~"))


def test_automation_input_validation():
    from utils import automations as auto

    assert auto.validate_name("  Clean Downloads ") == "Clean Downloads"
    for bad in ("", "../escape", "a" * 61, "semi;colon"):
        with pytest.raises(auto.AutomationError):
            auto.validate_name(bad)
    assert auto.normalize_days(["mon", "Friday", "MON"]) == ["Monday", "Friday"]
    with pytest.raises(auto.AutomationError):
        auto.normalize_days(["Funday"])
    with pytest.raises(auto.AutomationError):
        auto.trigger_ps("daily", "9am", None, [], None)
    with pytest.raises(auto.AutomationError):
        auto.trigger_ps("once", "09:00", None, [], None)
    with pytest.raises(auto.AutomationError):
        auto.trigger_ps("every_minutes", None, None, [], 1)
    assert "-Weekly -DaysOfWeek Monday,Friday" in auto.trigger_ps("weekly", "08:30", None, ["Monday", "Friday"], None)


def test_automation_tasks_are_scoped_and_unelevated():
    from utils import automations as auto

    ps = auto.register_ps("Demo", "C:/x/Demo", "New-ScheduledTaskTrigger -AtLogOn", "Created by Windows Jarvis")
    assert f"-TaskPath '{auto.TASK_PATH}'" in ps
    assert "-RunLevel Limited" in ps and "-LogonType Interactive" in ps
    script = auto.runner_script("Demo", "Get-Date", "powershell", False, "C:/x/Demo")
    assert "output.log" in script and "Get-Date" in script


# ── file power-ups ───────────────────────────────────────────────────────────

def test_search_in_files_skips_binaries(tmp_path):
    from tools import documents

    (tmp_path / "a.txt").write_text("one\nfind me\n")
    (tmp_path / "b.bin").write_bytes(b"\x00find me\x00")
    out = asyncio.run(documents.win_search_in_files(
        text="FIND ME", folder=str(tmp_path), file_pattern="*", regex=False, case_sensitive=False, max_results=10))
    assert "a.txt:2: find me" in out and "b.bin" not in out


def test_zip_and_unzip_never_overwrite(tmp_path):
    from tools import documents

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "f.txt").write_text("data")
    zip_path = tmp_path / "out.zip"
    assert asyncio.run(documents.win_zip(sources=[str(tmp_path / "src")], destination=str(zip_path))).startswith("Created")
    assert "already exists" in asyncio.run(documents.win_zip(sources=[str(tmp_path / "src")], destination=str(zip_path)))
    dest = tmp_path / "unpacked"
    assert asyncio.run(documents.win_unzip(zip_path=str(zip_path), destination=str(dest))).startswith("Extracted 1")
    assert (dest / "src" / "f.txt").read_text() == "data"
    assert asyncio.run(documents.win_unzip(zip_path=str(zip_path), destination=str(dest))).startswith("Nothing extracted")


def test_unzip_blocks_path_traversal(tmp_path):
    import zipfile

    from tools import documents

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../escape.txt", "x")
    out = asyncio.run(documents.win_unzip(zip_path=str(evil), destination=str(tmp_path / "out")))
    assert out.startswith("Refusing")
    assert not (tmp_path / "escape.txt").exists()


def test_read_docx(tmp_path):
    import zipfile

    from tools import documents

    doc = tmp_path / "d.docx"
    with zipfile.ZipFile(doc, "w") as z:
        z.writestr("word/document.xml",
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   "<w:body><w:p><w:r><w:t>Hello Word</w:t></w:r></w:p></w:body></w:document>")
    assert "Hello Word" in asyncio.run(documents.win_read_document(path=str(doc), max_chars=1000))


def test_open_file_refuses_programs(tmp_path):
    from tools import documents

    for name in ("run.exe", "script.ps1", "go.bat", "link.lnk"):
        f = tmp_path / name
        f.write_text("x")
        assert "was not opened" in asyncio.run(documents.win_open_file(path=str(f)))


# ── screenshots ──────────────────────────────────────────────────────────────

@on_windows
def test_capture_reports_missing_window():
    from utils.capture import CaptureError, capture

    with pytest.raises(CaptureError, match="No visible window"):
        capture(window_title="zz-no-such-window-zz")
