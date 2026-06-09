# Jarvis

A Windows OS Control MCP Server for Claude Desktop. Gives Claude full control over your
Windows machine — terminal, apps, files, system, browser, media, clipboard, and screen —
via 32 tools over the Model Context Protocol.

## Tools

- **Terminal**: run any cmd/PowerShell command or script
  - `win_run_command`, `win_run_script`
- **Apps**: open, close, list, switch applications
  - `win_open_app`, `win_close_app`, `win_list_running_apps`, `win_switch_to_app`, `win_list_installed`
- **System**: info, processes, volume, screenshot, shutdown/restart/lock
  - `win_get_system_info`, `win_list_processes`, `win_kill_process`, `win_adjust_volume`,
    `win_take_screenshot`, `win_get_network_info`, `win_shutdown`, `win_restart`,
    `win_cancel_shutdown`, `win_lock`
- **Files**: list, read, search, create, move, copy, delete
  - `win_list_directory`, `win_read_file`, `win_search_files`, `win_create_folder`,
    `win_move_file`, `win_copy_file`, `win_delete_file`, `win_get_file_info`
- **Browser**: open URLs, web search
  - `win_open_url`, `win_search_web`
- **Media**: play/pause/next/prev/stop
  - `win_media_control`
- **Clipboard**: get/set clipboard text
  - `win_get_clipboard`, `win_set_clipboard`
- **Screen**: OCR screen text, active window info
  - `win_read_screen_text`, `win_get_active_window`

## Setup

1. Install dependencies:
   ```
   pip install -r jarvis-mcp/requirements.txt
   ```
2. (Optional, for OCR) Install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and ensure it's on your `PATH`.
3. Add the server to your Claude Desktop config (see `jarvis-mcp/claude_desktop_config.json`
   for the `mcpServers` block to copy in).
4. Restart Claude Desktop. Claude now has direct control over your Windows machine.

## Transport

stdio — Claude Desktop spawns `jarvis-mcp/server.py` as a subprocess.
