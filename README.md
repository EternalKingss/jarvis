# Windows Jarvis

Control your Windows PC from Claude. Jarvis is a local MCP server that gives
Claude Desktop 52 tools for the terminal, apps and windows, files, system,
screen, clipboard, media, Wi-Fi and Bluetooth, notifications and Microsoft UI
Automation on Windows 10 and 11.

Everything runs on your own computer. Jarvis has no accounts, no telemetry and
no remote server. See [PRIVACY.md](PRIVACY.md).

## Install

1. Download `windows-jarvis-<version>.mcpb` from the
   [latest release](https://github.com/EternalKingss/jarvis/releases).
2. Double-click it, or drag it onto the Claude Desktop window, or install it
   from **Settings > Extensions**.
3. Click **Install**. Claude Desktop sets up Python and the dependencies for you.

Requirements: Windows 10 or 11, and Claude Desktop with extension support.
Nothing else to install: screen OCR uses the engine built into Windows.

## Settings

Open **Settings > Extensions > Windows Jarvis** to change these. Both are off
by default.

| Setting | What it allows |
|---------|----------------|
| Allow shutdown, restart and killing processes | `win_shutdown`, `win_restart`, `win_kill_process` |
| Allow permanent delete (skip the Recycle Bin) | `win_delete_file` with `permanent=True` |

While a setting is off, the tool replies that the action is turned off and
where to enable it.

## Example prompts

- "What's using the most RAM right now, and how much free disk space do I have?"
- "Find every PDF in my Downloads folder from this month and move them into Documents\Invoices."
- "Open Notepad, type a shopping list of eggs, milk and bread, then save it to my Desktop as list.txt."
- "Run `winget upgrade` in the background and notify me when it's done."
- "Take a screenshot and tell me what error the open dialog is showing."
- "Put Chrome on the left half of the screen and VS Code on the right."
- "Which Wi-Fi networks are nearby, and switch me to the strongest saved one."

## Tools

Every tool carries MCP safety annotations (`readOnlyHint`, `destructiveHint`,
`title`). Destructive tools can change or delete things, so expect Claude to
check with you before using them.

| Area | Read-only | Changes things | Destructive |
|------|-----------|----------------|-------------|
| Terminal | | | `win_run_command`, `win_run_script` |
| Jobs | `win_job_output`, `win_list_jobs` | | `win_start_job`, `win_stop_job` |
| Apps | `win_list_running_apps`, `win_list_installed` | `win_open_app`, `win_switch_to_app` | `win_close_app` |
| Desktop | | `win_arrange_window`, `win_notify` | |
| System | `win_get_system_info`, `win_list_processes`, `win_get_network_info` | `win_adjust_volume`, `win_take_screenshot`, `win_cancel_shutdown`, `win_lock` | `win_kill_process`\*, `win_shutdown`\*, `win_restart`\* |
| Files | `win_list_directory`, `win_read_file`, `win_search_files`, `win_get_file_info` | `win_create_folder`, `win_move_file`, `win_copy_file` | `win_write_file`, `win_delete_file` |
| Browser | | `win_open_url`, `win_search_web` | |
| Media | | `win_media_control` | |
| Clipboard | `win_get_clipboard` | `win_set_clipboard` | |
| Screen | `win_read_screen_text`, `win_get_active_window` | | |
| Wireless | `win_wifi_networks`, `win_bluetooth_devices` | `win_wifi_connect` | `win_wifi_disconnect`, `win_bluetooth_power` |
| UI Automation | `win_uia_inspect`, `win_uia_read`, `win_uia_list_windows` | `win_uia_focus` | `win_uia_click`, `win_uia_type_into`, `win_uia_select`, `win_uia_menu` |

\* Off until enabled in [Settings](#settings).

Notes:

- `win_delete_file` moves things to the Recycle Bin, so they can be restored.
  Paths with no Recycle Bin (network shares, most USB sticks) are refused
  unless permanent delete is enabled.
- `win_move_file` and `win_copy_file` never overwrite. If the target exists
  they stop and say so.
- `win_take_screenshot` saves a PNG and also shows Claude a downscaled copy,
  so it can see what is on screen.
- `win_wifi_connect` works with saved networks. Join a new network once from
  the Windows Wi-Fi menu so its password is stored.
- `win_wifi_disconnect` and `win_bluetooth_power` can cut your connection to
  Claude or your Bluetooth keyboard and mouse.
- `win_run_command` and friends run with your own Windows permissions. Jarvis
  never elevates on its own; anything that needs administrator rights shows the
  normal Windows UAC prompt.

## How it works

Claude Desktop starts `jarvis-mcp/server.py` with `uv` and talks to it over
stdio. Each tool runs a PowerShell or CMD command, a Python call (psutil,
Pillow, pywinauto) or a Windows API, and returns text (and, for screenshots,
an image) to Claude.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Extension shows "Server disconnected" | Open **Settings > Extensions > Windows Jarvis** and check the log. Reinstalling the `.mcpb` rebuilds its Python environment. |
| A tool says the action is turned off | Enable the matching option in [Settings](#settings). |
| `win_read_screen_text` says no OCR language is installed | Settings > Time & language > Language & region > your language > Language options > add Optical character recognition. |
| `win_wifi_networks` shows no nearby networks | Turn on Settings > Privacy & security > Location > "Let desktop apps access your location". Windows requires it for Wi-Fi scans. |
| Notifications don't appear | Check Settings > System > Notifications, and that Focus / Do not disturb is off. They show under "Windows PowerShell". |
| A UI Automation tool can't find a window | Run `win_uia_list_windows` and use part of a title it shows. Some apps running as administrator are hidden from non-admin processes. |
| A command works in your terminal but not in Jarvis | Jarvis runs non-interactively. Commands that prompt for input will hang; use `win_start_job` and `win_stop_job` for long or interactive ones. |
| You want a local record of commands | Set the `JARVIS_COMMAND_LOG` environment variable to a file path. It is off by default. |

## Support

Report bugs and security issues at
<https://github.com/EternalKingss/jarvis/issues>.

## License

[MIT](LICENSE)

## Development

```
uv sync --group dev
uv run pytest tests -q
uv run jarvis-mcp/server.py
```

Settings are read from environment variables, so for a local run set
`JARVIS_ALLOW_POWER_ACTIONS=true` or `JARVIS_ALLOW_PERMANENT_DELETE=true` to
switch them on.

Without uv: `pip install -r jarvis-mcp/requirements.txt`, then point an
`mcpServers` entry at `jarvis-mcp/server.py` (see
`jarvis-mcp/claude_desktop_config.json`).

### Releasing

1. Bump the version in `manifest.json`, `pyproject.toml` and
   `jarvis-mcp/mcp_instance.py` (a test checks they match).
2. Merge to `main`, then tag it: `git tag v1.2.0 && git push origin v1.2.0`.
3. The Release workflow validates the manifest, builds
   `windows-jarvis-<version>.mcpb` and attaches it to the GitHub release.

To build locally instead:

```
npx @anthropic-ai/mcpb validate manifest.json
npx @anthropic-ai/mcpb pack . windows-jarvis-<version>.mcpb
```

`.mcpbignore` keeps tests, git data and local environments out of the bundle.
When you add or rename a tool, update `tools` in `manifest.json`; the test
suite fails until it matches the server.
