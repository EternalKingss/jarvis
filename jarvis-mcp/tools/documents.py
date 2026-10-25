"""
File power-up tools.

win_search_in_files : Find text inside files (like grep), with line numbers
win_zip             : Compress files/folders into a .zip
win_unzip           : Extract a .zip into a folder
win_open_file       : Open a document, image or folder in its default app
win_read_document   : Read the text of a PDF or Word (.docx) file
"""

import asyncio
import fnmatch
import logging
import os
import re
import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

from pydantic import Field
from mcp_instance import mcp

logger = logging.getLogger(__name__)

_SKIP_DIRS = {"$Recycle.Bin", "Windows", "System Volume Information", "Recovery",
              ".git", "node_modules", "__pycache__", ".venv", ".cache"}
_MAX_SEARCH_FILE_BYTES = 5 * 1024 * 1024
_MAX_DOC_CHARS = 100_000

# Opening these would run a program, not view a file. win_open_file refuses
# them; running things stays with the terminal tools, which are marked destructive.
_EXECUTABLE_EXTS = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".msi", ".msp", ".scr", ".pif", ".cpl", ".hta", ".jar", ".lnk", ".url", ".reg", ".appref-ms", ".application",
}


def _expand(path: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


@mcp.tool(
    name="win_search_in_files",
    annotations={"title": "Search Inside Files", "readOnlyHint": True, "destructiveHint": False},
)
async def win_search_in_files(
    text: str = Field(..., description="Text to look for inside files (or a regular expression if regex=True)."),
    folder: str = Field(..., description="Folder to search, including subfolders. E.g. '~\\\\Documents'."),
    file_pattern: str = Field(default="*", description="Only files whose name matches, e.g. '*.txt', '*.py' (default all)."),
    regex: bool = Field(default=False, description="Treat text as a regular expression (default False)."),
    case_sensitive: bool = Field(default=False, description="Match case exactly (default False)."),
    max_results: int = Field(default=50, description="Max matching lines to return (default 50).", ge=1, le=500),
) -> str:
    """Search for text inside files in a folder and return matching lines with file paths and line numbers. Skips binary files and files over 5 MB."""
    def _impl() -> str:
        root = _expand(folder)
        if not os.path.isdir(root):
            return f"Folder not found: {root}"
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(text if regex else re.escape(text), flags)
        except re.error as e:
            return f"Invalid regular expression: {e}"

        hits, files_scanned = [], 0
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for name in files:
                if not fnmatch.fnmatch(name.lower(), file_pattern.lower()):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(path) > _MAX_SEARCH_FILE_BYTES:
                        continue
                    with open(path, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                if b"\x00" in data[:4096]:
                    continue  # binary
                files_scanned += 1
                for n, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                    if pattern.search(line):
                        snippet = line.strip()
                        hits.append(f"{path}:{n}: {snippet[:200]}{'...' if len(snippet) > 200 else ''}")
                        if len(hits) >= max_results:
                            return f"First {max_results} matches (stopped early):\n" + "\n".join(hits)
        if not hits:
            return f"No matches for '{text}' in {files_scanned} files under {root}."
        return f"{len(hits)} matches in {files_scanned} files searched:\n" + "\n".join(hits)

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_zip",
    annotations={"title": "Create Zip", "readOnlyHint": False, "destructiveHint": False},
)
async def win_zip(
    sources: list[str] = Field(..., description="Files and/or folders to put in the zip.", min_length=1),
    destination: str = Field(..., description="Path of the .zip to create. Fails if it already exists."),
) -> str:
    """Compress files and folders into a new .zip file. Never overwrites an existing file."""
    def _impl() -> str:
        dest = _expand(destination)
        if not dest.lower().endswith(".zip"):
            dest += ".zip"
        if os.path.exists(dest):
            return f"Destination already exists: {dest}. Pick another name or delete it first."
        paths = [_expand(s) for s in sources]
        missing = [p for p in paths if not os.path.exists(p)]
        if missing:
            return f"Not found: {', '.join(missing)}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        count = 0
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                if os.path.isfile(p):
                    z.write(p, os.path.basename(p))
                    count += 1
                    continue
                base = os.path.dirname(p.rstrip("\\/"))
                for dirpath, _dirs, files in os.walk(p):
                    for name in files:
                        full = os.path.join(dirpath, name)
                        if os.path.abspath(full) == dest:
                            continue
                        z.write(full, os.path.relpath(full, base))
                        count += 1
        return f"Created {dest}  ({count} files, {os.path.getsize(dest):,} bytes)"

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_unzip",
    annotations={"title": "Extract Zip", "readOnlyHint": False, "destructiveHint": False},
)
async def win_unzip(
    zip_path: str = Field(..., description="The .zip file to extract."),
    destination: Optional[str] = Field(default=None, description="Folder to extract into. Defaults to a new folder next to the zip, named after it."),
) -> str:
    """Extract a .zip file into a folder. Stops without extracting anything if any file would be overwritten."""
    def _impl() -> str:
        src = _expand(zip_path)
        if not os.path.isfile(src):
            return f"Zip not found: {src}"
        dest = _expand(destination) if destination else os.path.splitext(src)[0]
        try:
            z = zipfile.ZipFile(src)
        except zipfile.BadZipFile:
            return f"Not a valid zip file: {src}"
        with z:
            members = z.infolist()
            root = os.path.realpath(dest)
            conflicts = []
            for m in members:
                target = os.path.realpath(os.path.join(dest, m.filename))
                # Zip-slip guard: entries like '..\\..\\x' must stay inside dest.
                if os.path.commonpath([root, target]) != root:
                    return f"Refusing to extract: '{m.filename}' would land outside {dest}."
                if not m.is_dir() and os.path.exists(target):
                    conflicts.append(m.filename)
            if conflicts:
                shown = ", ".join(conflicts[:10]) + (" ..." if len(conflicts) > 10 else "")
                return f"Nothing extracted: {len(conflicts)} file(s) already exist in {dest}: {shown}. Pick an empty destination."
            z.extractall(dest)
        files = sum(1 for m in members if not m.is_dir())
        return f"Extracted {files} files into {dest}"

    return await asyncio.to_thread(_impl)


@mcp.tool(
    name="win_open_file",
    annotations={"title": "Open File", "readOnlyHint": False, "destructiveHint": False},
)
async def win_open_file(
    path: str = Field(..., description="Document, image, video or folder to open, e.g. '~\\\\Desktop\\\\report.pdf'."),
) -> str:
    """Open a document, image, video or folder in its default app, as if the user double-clicked it. Programs and scripts are refused; use the terminal tools to run those."""
    p = _expand(path)
    if not os.path.exists(p):
        return f"Not found: {p}"
    ext = os.path.splitext(p)[1].lower()
    if os.path.isfile(p) and ext in _EXECUTABLE_EXTS:
        return f"'{os.path.basename(p)}' is a program or script ({ext}), so it was not opened. Run programs with win_run_command or win_open_app instead."
    try:
        await asyncio.to_thread(os.startfile, p)
    except OSError as e:
        return f"Couldn't open it: {e}. Windows may have no app set for '{ext}' files."
    return f"Opened {p}"


def _docx_text(path: str) -> str:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paragraphs = []
    for para in root.iter(f"{ns}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{ns}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{ns}tab":
                parts.append("\t")
            elif node.tag in (f"{ns}br", f"{ns}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def _pdf_text(path: str, max_chars: int) -> tuple[str, int, int]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("this PDF is password-protected")
    pages, chars, read = [], 0, 0
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        pages.append(f"── Page {i} ──\n{text.strip()}")
        chars += len(text)
        read = i
        if chars >= max_chars:
            break
    return "\n\n".join(pages), read, len(reader.pages)


@mcp.tool(
    name="win_read_document",
    annotations={"title": "Read PDF or Word Document", "readOnlyHint": True, "destructiveHint": False},
)
async def win_read_document(
    path: str = Field(..., description="Path to a .pdf or .docx file."),
    max_chars: int = Field(default=20000, description="Max characters to return (default 20000).", ge=500, le=_MAX_DOC_CHARS),
) -> str:
    """Read the text of a PDF or Word (.docx) document. Scanned PDFs with no text layer come back empty; open them and use win_read_screen_text instead."""
    def _impl() -> str:
        p = _expand(path)
        if not os.path.isfile(p):
            return f"File not found: {p}"
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext == ".docx":
                text, note = _docx_text(p), ""
            elif ext == ".pdf":
                text, read, total = _pdf_text(p, max_chars)
                note = f" (pages 1-{read} of {total})" if read < total else f" ({total} pages)"
            elif ext == ".doc":
                return "Old .doc files aren't supported. Open it in Word and save as .docx, or use win_open_file."
            else:
                return f"'{ext}' isn't a PDF or .docx. For plain text files use win_read_file."
        except Exception as e:
            return f"Couldn't read {os.path.basename(p)}: {e}"
        text = text.strip()
        if not text:
            return f"No text found in {os.path.basename(p)}. If it's a scanned document, open it and use win_read_screen_text."
        cut = f"\n\n[Truncated at {max_chars} characters]" if len(text) > max_chars else ""
        return f"{os.path.basename(p)}{note}:\n\n{text[:max_chars]}{cut}"

    return await asyncio.to_thread(_impl)
