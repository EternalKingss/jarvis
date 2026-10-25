# Windows Jarvis Privacy Policy

Last updated: 2026-10-24

Windows Jarvis is a local MCP server. It runs on your own computer as a
subprocess of Claude Desktop and talks to Claude only over standard input and
output. This policy explains what it touches and what it keeps.

## What Jarvis collects

Nothing. Jarvis has no accounts, no telemetry, no analytics and no remote
server. It never sends your files, commands, screen contents or any other data
to the developer or to any third party.

## What Jarvis reads

When Claude calls a tool, Jarvis reads what that tool needs from your machine,
for example a file you asked about, the clipboard, the text on screen, the list
of running processes, or the UI of an open window. The result is returned to
Claude as part of your conversation. How Anthropic handles conversation data is
covered by [Anthropic's Privacy Policy](https://www.anthropic.com/legal/privacy).

## What Jarvis stores on your computer

- **Screenshots** from `win_take_screenshot` are saved to
  `Pictures\Jarvis Screenshots` (or the path you choose).
- **Background job output** from `win_start_job` is written to
  `%TEMP%\jarvis_jobs` so it can be read back while the job runs. These files
  stay until you or Windows clear the temp folder.
- **Temporary scripts** used to run PowerShell commands are deleted as soon as
  the command finishes.
- **Command history is off.** Jarvis does not record the commands it runs. If
  you set the `JARVIS_COMMAND_LOG` environment variable to a file path, it will
  append each command to that file, on your machine only.

## Network access

The Jarvis server makes no network requests of its own.

- `win_open_url` and `win_search_web` open a page in your default browser.
  The website or search engine you visit handles that request under its own
  privacy policy.
- Commands that you ask Claude to run with `win_run_command`, `win_run_script`
  or `win_start_job` can do anything a PowerShell or CMD command can, including
  using the network. They run with your own Windows permissions.

## Contact

Questions or privacy concerns: open an issue at
<https://github.com/EternalKingss/jarvis/issues>.
