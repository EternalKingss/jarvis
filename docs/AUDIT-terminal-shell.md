# Jarvis MCP Audit — Terminal & Shell Reliability

Audit of the whole server with focus on why terminal/shell tool calls
(`win_run_command`, `win_run_script`) misbehave when running commands and
scripts. Findings are ordered by how much day-to-day pain each one causes.

Every shell-based tool in the server (`terminal.py`, plus `apps.py`,
`system.py`, `clipboard.py`, `media.py`, `screen.py` which all shell out)
funnels through `utils/shell.py:run_command`, so fixes there pay off across
all 32 tools.

---

## P0 — Correctness bugs in the shell executor

### 1. Child processes inherit the MCP protocol's stdin

`utils/shell.py:113` — `subprocess.Popen` sets `stdout` and `stderr` but not
`stdin`. The server runs over **stdio transport** (Claude Desktop pipes
JSON-RPC through the server's stdin), and spawned shells inherit that handle.

Consequences:

- Any command that reads stdin (`pip` prompting y/n, `git` asking for
  credentials, `choco`, `python` without a script, `pause` in a batch file)
  either **steals MCP protocol bytes** — corrupting the session — or blocks
  until the timeout kills it. This is a classic "the MCP randomly dies /
  hangs when I run scripts" root cause.

**Fix:** pass `stdin=subprocess.DEVNULL`. Interactive prompts then fail fast
with a readable error instead of hanging or eating the protocol stream.

### 2. Quoting/escaping breaks commands passed via `-Command`

`utils/shell.py:102-111` — the command string is spliced into
`powershell.exe -Command <prefix + command>` as a Popen list. On Windows
that goes through `list2cmdline` (MSVCRT quoting rules), and PowerShell then
**re-parses its command line with its own rules**. Commands containing double
quotes, `$`, backticks, `%`, or nested quoting frequently arrive mangled —
they work in a real terminal but fail through the tool. The cmd.exe path
(`cmd /c "chcp 65001 >nul 2>&1 & …"`) has the same problem with cmd's own
quote-stripping rules.

**Fix:** for PowerShell, use `-EncodedCommand` with the UTF-16LE base64
encoding of `prefix + command`:

```python
encoded = base64.b64encode((_PS_UTF8_PREFIX + command).encode("utf-16-le")).decode()
cmd_args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
```

This eliminates the entire quoting class of failures — the command arrives
byte-for-byte intact regardless of content. For cmd.exe, pass a single
string (not a list) so `list2cmdline` doesn't add a second layer of quoting.
This also makes the UTF-8 `chcp`/`[Console]::OutputEncoding` shims more
reliable since they can't be broken by the user command's quoting.

### 3. `&&` and `||` don't exist in Windows PowerShell 5.1

The default shell is `powershell.exe` (5.1). LLM-generated commands are full
of `cd x && python y.py` — in PS 5.1 that fails with *"The token '&&' is not
a valid statement separator"*. This is almost certainly a top source of
"it has a lot of issues running stuff": the exact command that works
everywhere else fails here.

**Fixes (compose all three):**

- Detect `pwsh.exe` (PowerShell 7+) at startup and prefer it when present —
  PS7 supports `&&`/`||` and has far better Unicode defaults.
- Say it in the tool description (`tools/terminal.py:23-24`): "PowerShell
  5.1: use `;` not `&&`" — descriptions are the one place you get to teach
  the model calling the tool.
- Optionally pre-scan the command for ` && `/` || ` when running under 5.1
  and return a targeted error message ("use `;` or shell='cmd'") instead of
  the cryptic parser error.

### 4. Silent working-directory fallback runs commands in the wrong place

`utils/shell.py:48-55` — if `working_dir` doesn't exist, the command
silently runs in `%USERPROFILE%`. Claude passes a slightly-wrong path, the
script runs in the home directory, and the resulting errors ("file not
found", files created in the wrong place, git commands against the wrong
repo) look like *the script* is broken. The warning goes to the server's
stderr log, which the model never sees.

**Fix:** return an error result (`success: False`, clear message "working
directory does not exist: …") instead of falling back. Wrong-but-loud beats
wrong-and-quiet for an agent that can self-correct.

### 5. False `success: True` — PowerShell exit codes don't propagate

`powershell -Command "some.exe args"` exits 0 unless the *last* statement
was a native command or the script called `exit`. A failing tool in the
middle of a pipeline, or a cmdlet writing errors, still yields
`exit_code: 0` → `success: True`, and the model happily moves on believing
the step worked.

**Fix:** append exit-code propagation to the command:

```powershell
<command>; if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE } elseif (-not $?) { exit 1 }
```

(Trivially composable with the `-EncodedCommand` change in #2.)

### 6. Console window flash on every command

`subprocess.Popen` without `creationflags=subprocess.CREATE_NO_WINDOW`
under a GUI parent (Claude Desktop) can flash a console window for every
one of the dozens of shell-outs the server does — including background ones
like `win_get_system_info`'s two PowerShell calls.

**Fix:** add `creationflags=subprocess.CREATE_NO_WINDOW` in `run_command`.

---

## P1 — Capability gaps that make whole workflows impossible

### 7. No persistent shell session — state evaporates between calls

Every call spawns a fresh `powershell.exe`. So:

- `cd` doesn't stick; activating a venv doesn't stick; `$env:` vars don't
  stick. Claude activates a venv in call 1, runs `pip install` in call 2,
  and it lands in the global interpreter.
- PowerShell startup (plus `Add-Type` in several tools) costs 0.5–2s per
  call, so multi-step work is slow.

**Fix (biggest single improvement to "using terminals to do stuff"):** add a
session-based shell — keep one PowerShell process alive, write commands to
its stdin, delimit output with a sentinel (e.g.
`echo "<<<JARVIS_DONE:$LASTEXITCODE>>>"`), read until the sentinel.
Suggested tools: `win_shell_exec(session_id=…)` +
`win_shell_close(session_id)`, or a `session` parameter on
`win_run_command`. State (cwd, env, venv) then persists across calls,
exactly like a human's terminal.

### 8. No background/long-running execution

Timeout is capped at 300s (`terminal.py:26`) / 600s (`terminal.py:46`), and
the process tree is killed at timeout. That means:

- Long builds/installs die mid-flight (possibly leaving half-installed
  state).
- **Starting a dev server is impossible** — it gets killed at the timeout,
  every time. There's no detach option and no way to check on a process
  later other than `win_list_processes`.

**Fix:** either a `detach: bool` flag (launch with
`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, redirect output to a temp
file, return the PID + log path immediately) or proper job tools:
`win_start_job` / `win_get_job_output` / `win_stop_job`. Pairs naturally
with the session work in #7.

### 9. `win_run_script` should run a real script file, not a `& { }` block

`tools/terminal.py:54` wraps the script in `& { … }` and shoves it through
`-Command`. That breaks scripts with a top-level `param(...)` block, gives
no `$PSScriptRoot`, and inherits every quoting problem from #2.

**Fix:** write the script to a temp `.ps1` and run
`powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <tmp>`;
delete the file afterwards. Real script semantics, real exit codes, zero
escaping issues. (Note: `shell.py:101`'s comment claims execution policy is
bypassed, but no `-ExecutionPolicy` flag is actually passed — with `-File`
it starts to matter.)

### 10. Truncated output is gone forever

`shell.py:145-149` truncates stdout at 8 000 chars (4 000 on timeout — an
inconsistency worth unifying) and stderr at 2 000. Build logs and stack
traces routinely exceed that, and there is no way to retrieve the rest, so
the model re-runs commands trying to see the part that was cut off.

**Fix:** when output exceeds the cap, spill the full output to a temp file
and include the path in the result ("full output: C:\...\jarvis_out_x.log —
use win_read_file"). Also raise the stderr cap (that's where the stack
trace lives) and consider a `max_output` parameter.

### 11. Timeouts and errors are indistinguishable from real exit codes

Timeout, shell-not-found, and unexpected exceptions all report
`exit_code: -1` (`shell.py:133,169,182`) — a value a real process can also
exit with. **Fix:** add a `timed_out: bool` field and a distinct `error`
field to the result dict, and surface them in `format_result`.

---

## P2 — Smaller terminal/shell issues

12. **Default timeout of 30s is too low** for the most common agent commands
    (`pip install`, `npm install`, `git clone`). The model often forgets to
    raise it and the command is killed mid-install. Suggest default 60–120s,
    and align the two tools' caps (300 vs 600 today).
13. **Command history log** (`shell.py:19`): `command_history.log` lives
    inside the package dir but isn't in `.gitignore` — one `git add .` on
    the user's machine commits their full command history (which can
    contain tokens/passwords typed into commands). Add it to `.gitignore`,
    and consider logging to `%LOCALAPPDATA%\Jarvis` instead.
14. **`_log_command` isn't thread-safe** — tools run via `asyncio.to_thread`,
    so concurrent calls can interleave writes or race the rotation
    (`shell.py:37-41`). A `threading.Lock` around it is enough.
15. **Process-tree kill race** (`shell.py:58-74`): children are snapshotted
    and then killed parent-last; a child spawned between snapshot and kill
    escapes. Kill the parent first (stops new spawns), then the children —or
    use `taskkill /T /F` as the fallback.
16. **No env-var injection** — callers can't pass environment variables to a
    command; an `env: dict` parameter on `win_run_command` is cheap and
    composes with #7.
17. **`win_get_system_info` is slow**: `cpu_percent(interval=1)` plus two
    sequential PowerShell spawns ≈ 3–5s per call. Run the two CIM queries in
    one PowerShell invocation and drop the interval to 0.2s.
18. **Tool descriptions could prevent misuse**: `win_run_command`'s
    description should state the things the model keeps tripping on — no
    session persistence between calls (until #7 lands), `;` not `&&` on
    PS 5.1, output truncation limits, and "commands must be non-interactive".

---

## Non-terminal observations (brief)

- `tools/apps.py:65` — `win_close_app` matching (`query in pname`) is loose:
  closing "edge" also kills `MicrosoftEdgeUpdate.exe`; closing "code" would
  match anything containing it. Require whole-word/prefix match on the
  process stem, and report what matched before it's dead.
- `tools/apps.py` / `utils/app_finder.py:138` — when an alias isn't found in
  PATH, the bare exe name is returned and `launch_application` reports
  success if `Popen` didn't throw; `os.startfile` fallbacks can also "succeed"
  while nothing visible happens. Verify the process actually appeared
  (psutil) before claiming "Launched".
- `utils/app_finder.py:104` — `_search_program_files` does a recursive
  `glob` over all of `%PROGRAMFILES%`; on a big disk this takes tens of
  seconds inside a tool call. Cap the walk depth or cache results.
- `tools/files.py:145` — `win_search_files` defaults to `search_path="C:\\"`,
  a full-disk walk with no time budget. Add a wall-clock cutoff (e.g. 10s,
  return partial results + "narrow the search path").
- `tools/system.py:236-239` — volume control via `SendKeys` is focus- and
  timing-fragile and can't set an absolute level; consider `pycaw` (COM,
  deterministic, supports get/set percent).
- `tests/test_smoke.py` only asserts registration. The shell layer is the
  highest-risk code and is testable cross-platform by faking the shell
  binary (or on Windows CI via `runs-on: windows-latest` — GitHub provides
  it): quoting round-trips, timeout kill, working-dir validation, exit-code
  propagation. A `windows-latest` CI job running real `win_run_command`
  cases would catch every P0 above.

---

## Suggested order of work

| Step | Items | Why first |
|------|-------|-----------|
| 1 | #1, #2, #4, #5, #6 (one PR in `shell.py`) | Small diffs, kill the biggest "commands randomly fail/hang/lie" classes |
| 2 | #3 (pwsh detection + description fixes) | Directly targets the most common LLM-written command failure |
| 3 | #9, #10, #11, #12 | Script semantics + observability of failures |
| 4 | #7, #8 (sessions + background jobs) | The big capability unlock; build on a now-solid executor |
| 5 | P2 leftovers + Windows CI tests | Lock it in so it stays fixed |
