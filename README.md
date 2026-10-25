# Windows Jarvis

Control your Windows PC from Claude. Jarvis is a local MCP server that gives
Claude Desktop 45 tools for the terminal, apps, files, system, screen, clipboard,
media and Microsoft UI Automation on Windows 10 and 11.

Everything runs on your own computer. Jarvis has no accounts, no telemetry and
no remote server. See [PRIVACY.md](PRIVACY.md).

## Install

1. Download `windows-jarvis-<version>.mcpb` from the
   [latest release](https://github.com/EternalKingss/jarvis/releases).
2. Double-click it, or drag it onto the Claude Desktop window, or install it
   from **Settings > Extensions**.
3. Click **Install**. Claude Desktop sets up Python and the dependencies for you.

Requirements:

- Windows 10 or 11
- Claude Desktop with extension support
- Optional, for `win_read_screen_text` only: the free
  [Tesseract OCR engine](https://github.com/UB-Mannheim/tesseract/wiki), installed
  to its default `Program Files\Tesseract-OCR` folder or on your `PATH`

## Example prompts

- "What's using the most RAM right now, and how much free disk space do I have?"
- "Find every PDF in my Downloads folder from this month and move them into Documents\Invoices."
- "Open Notepad, type a shopping list of eggs, milk and bread, then save it to my Desktop as list.txt."
- "Run `winget upgrade` in the background and tell me when it finishes and what was updated."
- "Take a screenshot and tell me what error the open dialog is showing."

## Tools

Every tool carries MCP safety annotations (`readOnlyHint`, `destructiveHint`,
`title`). Destructive tools can change or delete things, so expect Claude to
check with you before using them.

| Area | Read-only | Changes things | Destructive |
|------|-----------|----------------|-------------|
| Terminal | | | `win_run_command`, `win_run_script` |
| Jobs | `win_job_output`, `win_list_jobs` | | `win_start_job`, `win_stop_job` |
| Apps | `win_list_running_apps`, `win_list_installed` | `win_open_app`, `win_switch_to_app` | `win_close_app` |
| System | `win_get_system_info`, `win_list_processes`, `win_get_network_info` | `win_adjust_volume`, `win_take_screenshot`, `win_cancel_shutdown`, `win_lock` | `win_kill_process`, `win_shutdown`, `win_restart` |
| Files | `win_list_directory`, `win_read_file`, `win_search_files`, `win_get_file_info` | `win_create_folder`, `win_move_file`, `win_copy_file` | `win_write_file`, `win_delete_file` |
| Browser | | `win_open_url`, `win_search_web` | |
| Media | | `win_media_control` | |
| Clipboard | `win_get_clipboard` | `win_set_clipboard` | |
| Screen | `win_read_screen_text`, `win_get_active_window` | | |
| UI Automation | `win_uia_inspect`, `win_uia_read`, `win_uia_list_windows` | `win_uia_focus` | `win_uia_click`, `win_uia_type_into`, `win_uia_select`, `win_uia_menu` |

Notes:

- `win_delete_file` deletes permanently. It does not use the Recycle Bin.
- `win_move_file` and `win_copy_file` never overwrite. If the target exists
  they stop and say so.
- `win_run_command` and friends run with your own Windows permissions. Jarvis
  never elevates on its own; anything that needs administrator rights shows the
  normal Windows UAC prompt.

## How it works

Claude Desktop starts `jarvis-mcp/server.py` with `uv` and talks to it over
stdio. Each tool runs a PowerShell or CMD command, a Python call (psutil,
Pillow, pywinauto) or a Windows API, and returns plain text to Claude.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Extension shows "Server disconnected" | Open **Settings > Extensions > Windows Jarvis** and check the log. Reinstalling the `.mcpb` rebuilds its Python environment. |
| `win_read_screen_text` says Tesseract is missing | Install Tesseract from the link above, then restart Claude Desktop. |
| A UI Automation tool can't find a window | Run `win_uia_list_windows` and use part of a title it shows. Some apps running as administrator are hidden from non-admin processes. |
| A command works in your terminal but not in Jarvis | Jarvis runs non-interactively. Commands that prompt for input will hang; use `win_start_job` and `win_stop_job` for long or interactive ones. |
| You want a local record of commands | Set the `JARVIS_COMMAND_LOG` environment variable to a file path. It is off by default. |

## Support

Report bugs and security issues at
<https://github.com/EternalKingss/jarvis/issues>.

## Development

```
uv sync --group dev
uv run pytest tests -q
uv run jarvis-mcp/server.py
```

Without uv: `pip install -r jarvis-mcp/requirements.txt`, then point an
`mcpServers` entry at `jarvis-mcp/server.py` (see
`jarvis-mcp/claude_desktop_config.json`).

### Building the extension

```
npx @anthropic-ai/mcpb validate manifest.json
npx @anthropic-ai/mcpb pack . windows-jarvis-1.0.0.mcpb
```

`.mcpbignore` keeps tests, git data and local environments out of the bundle.
When you add or rename a tool, update `tools` in `manifest.json`; the test
suite fails until it matches the server.
