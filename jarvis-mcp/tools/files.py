"""
File system tools.

win_list_directory  : List contents of a folder
win_read_file       : Read a file's text content
win_search_files    : Search for files by name or extension
win_create_folder   : Create a new directory
win_move_file       : Move or rename a file/folder
win_copy_file       : Copy a file
win_delete_file     : Delete a file or folder
win_get_file_info   : Metadata for a file/folder
"""

import asyncio
import fnmatch
import logging
import os
import shutil
import stat as stat_module
from datetime import datetime
from typing import Optional

from pydantic import Field
from mcp_instance import mcp

logger = logging.getLogger(__name__)


def _expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))

def _size_str(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def _ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def _is_hidden(entry: os.DirEntry) -> bool:
    """Windows hides files via the hidden attribute, not a leading dot."""
    if entry.name.startswith("."):
        return True
    try:
        attrs = entry.stat(follow_symlinks=False).st_file_attributes
        return bool(attrs & stat_module.FILE_ATTRIBUTE_HIDDEN)
    except (AttributeError, OSError):
        # st_file_attributes is Windows-only
        return False


@mcp.tool(
    name="win_list_directory",
    annotations={"title": "List Directory Contents", "readOnlyHint": True, "destructiveHint": False},
)
async def win_list_directory(
    path: str = Field(..., description="Directory to list. E.g. 'C:\\\\Users\\\\Eternal\\\\Desktop', '~', '%USERPROFILE%\\\\Downloads'"),
    show_hidden: bool = Field(default=False, description="Include hidden files (default False)"),
    limit: int = Field(default=100, description="Max entries to return (default 100)", ge=1, le=1000),
) -> str:
    """List the contents of a directory with sizes and modification dates."""
    def _impl() -> str:
        p = _expand(path)
        if not os.path.exists(p):
            return f"Path does not exist: {p}"
        if not os.path.isdir(p):
            return f"Not a directory: {p}"

        try:
            items = []
            for entry in os.scandir(p):
                if not show_hidden and _is_hidden(entry):
                    continue
                try:
                    stat = entry.stat()
                    items.append({"name": entry.name, "is_dir": entry.is_dir(), "size": stat.st_size, "modified": stat.st_mtime})
                except (PermissionError, OSError):
                    items.append({"name": entry.name, "is_dir": entry.is_dir(), "size": 0, "modified": 0})

            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            total = len(items)
            shown = items[:limit]

            lines = [f"Directory: {p}  ({total} items)\n"]
            lines.append(f"{'Type':<6}  {'Size':>10}  {'Modified':<20}  Name")
            lines.append("─" * 65)
            for item in shown:
                kind = "DIR" if item["is_dir"] else "FILE"
                size = "—" if item["is_dir"] else _size_str(item["size"])
                mod = _ts(item["modified"]) if item["modified"] else "—"
                lines.append(f"{kind:<6}  {size:>10}  {mod:<20}  {item['name']}")
            if total > limit:
                lines.append(f"\n... and {total - limit} more items.")
            return "\n".join(lines)
        except PermissionError:
            return f"Permission denied: {p}"

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_read_file",
    annotations={"title": "Read File Contents", "readOnlyHint": True, "destructiveHint": False},
)
async def win_read_file(
    path: str = Field(..., description="Path to the file to read."),
    max_chars: int = Field(default=10000, description="Max characters to return (default 10000)", ge=100, le=100000),
    encoding: str = Field(default="utf-8", description="File encoding, usually 'utf-8' or 'cp1252'"),
) -> str:
    """Read and return the text content of a file."""
    def _impl() -> str:
        p = _expand(path)
        if not os.path.exists(p):
            return f"File not found: {p}"
        if os.path.isdir(p):
            return "That's a directory. Use win_list_directory instead."

        size = os.path.getsize(p)
        try:
            with open(p, "r", encoding=encoding, errors="replace") as f:
                content = f.read(max_chars + 1)
            if "\x00" in content:
                return f"Cannot read '{p}' as text — it appears to be a binary file."
            truncated = len(content) > max_chars
            content = content[:max_chars]
            header = f"File: {p}  ({_size_str(size)})\n{'─' * 50}\n"
            footer = f"\n{'─' * 50}\n[Truncated at {max_chars} chars. Full size: {_size_str(size)}]" if truncated else ""
            return header + content + footer
        except PermissionError:
            return f"Permission denied: {p}"
        except Exception as e:
            return f"Error reading file: {e}"

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_search_files",
    annotations={"title": "Search for Files", "readOnlyHint": True, "destructiveHint": False},
)
async def win_search_files(
    query: str = Field(..., description="Filename or wildcard pattern. E.g. '*.py', 'report*', 'config.json'"),
    search_path: str = Field(default="C:\\", description="Root directory to search. Use a specific folder for speed (default 'C:\\')"),
    limit: int = Field(default=30, description="Max results (default 30)", ge=1, le=200),
    file_type: Optional[str] = Field(default=None, description="Extension filter like '.py', '.txt', '.docx'"),
) -> str:
    """Search for files by name or wildcard pattern across a directory tree."""
    def _impl() -> str:
        root_path = _expand(search_path)
        if not os.path.isdir(root_path):
            return f"Search path does not exist: {root_path}"

        SKIP_DIRS = {"$Recycle.Bin", "Windows", "System Volume Information", "Recovery",
                     ".git", "node_modules", "__pycache__", ".cache"}
        query_lower = query.lower()
        # Wildcard queries must match exactly — a substring fallback made
        # '*.py' also match every '.pyc' file.
        has_wildcard = any(c in query_lower for c in "*?[")
        results = []

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                fname_lower = fname.lower()
                if has_wildcard:
                    matched = fnmatch.fnmatch(fname_lower, query_lower)
                else:
                    matched = query_lower in fname_lower
                if matched:
                    if file_type and not fname_lower.endswith(file_type.lower()):
                        continue
                    full_path = os.path.join(root, fname)
                    try:
                        stat = os.stat(full_path)
                        results.append({"path": full_path, "size": stat.st_size, "modified": stat.st_mtime})
                    except (PermissionError, OSError):
                        results.append({"path": full_path, "size": 0, "modified": 0})
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        if not results:
            return f"No files found matching '{query}' in {root_path}"
        lines = [f"Found {len(results)} file(s) matching '{query}':\n"]
        for r in results:
            lines.append(f"  {_size_str(r['size']):>10}  {_ts(r['modified']) if r['modified'] else '—'}  {r['path']}")
        return "\n".join(lines)

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_create_folder",
    annotations={"title": "Create Folder", "readOnlyHint": False, "destructiveHint": False},
)
async def win_create_folder(
    path: str = Field(..., description="Full path of the folder to create (including parent dirs if needed)."),
) -> str:
    """Create a new directory (and any missing parent directories)."""
    p = _expand(path)
    try:
        await asyncio.to_thread(os.makedirs, p, exist_ok=True)
        return f"Created folder: {p}"
    except PermissionError:
        return f"Permission denied: {p}"
    except Exception as e:
        return f"Failed to create folder: {e}"


@mcp.tool(
    name="win_move_file",
    annotations={"title": "Move or Rename File", "readOnlyHint": False, "destructiveHint": False},
)
async def win_move_file(
    source: str = Field(..., description="Current path of the file or folder to move/rename."),
    destination: str = Field(..., description="Target path or folder. If a directory, file is moved into it."),
) -> str:
    """Move a file or folder to a new location, or rename it."""
    src, dst = _expand(source), _expand(destination)
    if not os.path.exists(src):
        return f"Source not found: {src}"
    try:
        await asyncio.to_thread(shutil.move, src, dst)
        return f"Moved: {src}  →  {dst}"
    except Exception as e:
        return f"Move failed: {e}"


@mcp.tool(
    name="win_copy_file",
    annotations={"title": "Copy File", "readOnlyHint": False, "destructiveHint": False},
)
async def win_copy_file(
    source: str = Field(..., description="File to copy."),
    destination: str = Field(..., description="Target path or folder."),
) -> str:
    """Copy a file to a new location."""
    src, dst = _expand(source), _expand(destination)
    if not os.path.exists(src):
        return f"Source not found: {src}"
    if os.path.isdir(src):
        return "Use win_run_command with 'robocopy' to copy whole directories."
    try:
        result = await asyncio.to_thread(shutil.copy2, src, dst)
        return f"Copied: {src}  →  {result}"
    except Exception as e:
        return f"Copy failed: {e}"


@mcp.tool(
    name="win_delete_file",
    annotations={"title": "Delete File or Folder", "readOnlyHint": False, "destructiveHint": True},
)
async def win_delete_file(
    path: str = Field(..., description="Path to delete. THIS IS PERMANENT — not sent to Recycle Bin."),
    recursive: bool = Field(default=False, description="Delete non-empty directories and all contents (default False)."),
) -> str:
    """Delete a file or folder permanently. Always confirm with the user first."""
    p = _expand(path)
    if not os.path.exists(p):
        return f"Path not found: {p}"
    try:
        if os.path.isfile(p):
            await asyncio.to_thread(os.remove, p)
            return f"Deleted file: {p}"
        elif os.path.isdir(p):
            if recursive:
                await asyncio.to_thread(shutil.rmtree, p)
                return f"Deleted directory and all contents: {p}"
            else:
                await asyncio.to_thread(os.rmdir, p)
                return f"Deleted empty directory: {p}"
    except OSError as e:
        if "not empty" in str(e).lower():
            return "Directory is not empty. Set recursive=True to delete it and all contents."
        return f"Delete failed: {e}"
    except Exception as e:
        return f"Delete failed: {e}"


@mcp.tool(
    name="win_get_file_info",
    annotations={"title": "Get File Info", "readOnlyHint": True, "destructiveHint": False},
)
async def win_get_file_info(
    path: str = Field(..., description="File or folder path to inspect."),
) -> str:
    """Get metadata for a file or directory: size, created/modified dates, type."""
    def _impl() -> str:
        p = _expand(path)
        if not os.path.exists(p):
            return f"Path not found: {p}"
        try:
            stat = os.stat(p)
            kind = "Directory" if os.path.isdir(p) else "File"
            lines = [
                f"Path     : {p}", f"Type     : {kind}",
                f"Size     : {_size_str(stat.st_size)} ({stat.st_size:,} bytes)",
                f"Created  : {_ts(stat.st_ctime)}", f"Modified : {_ts(stat.st_mtime)}",
                f"Accessed : {_ts(stat.st_atime)}",
            ]
            if kind == "Directory":
                try:
                    count = sum(len(files) for _, _, files in os.walk(p))
                    lines.append(f"Files    : {count} (recursive)")
                except Exception:
                    pass
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    return await asyncio.to_thread(_impl)
