"""
Intelligent application finder for Windows.
Searches Start Menu, Program Files, AppData, registry, and PATH
to locate installed applications by fuzzy name matching.
"""

import fnmatch
import glob
import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Common app aliases — map what people say to actual executable names
ALIASES: dict[str, list[str]] = {
    "browser":        ["chrome", "firefox", "msedge", "opera", "brave"],
    "chrome":         ["chrome"],
    "firefox":        ["firefox"],
    "edge":           ["msedge"],
    "discord":        ["discord"],
    "steam":          ["steam"],
    "spotify":        ["spotify"],
    "vscode":         ["code"],
    "vs code":        ["code"],
    "visual studio code": ["code"],
    "notepad":        ["notepad"],
    "notepad++":      ["notepad++"],
    "word":           ["winword"],
    "excel":          ["excel"],
    "powerpoint":     ["powerpnt"],
    "outlook":        ["outlook"],
    "teams":          ["teams"],
    "slack":          ["slack"],
    "zoom":           ["zoom"],
    "obs":            ["obs64", "obs"],
    "vlc":            ["vlc"],
    "file explorer":  ["explorer"],
    "explorer":       ["explorer"],
    "task manager":   ["taskmgr"],
    "calculator":     ["calc"],
    "paint":          ["mspaint"],
    "cmd":            ["cmd"],
    "terminal":       ["wt", "cmd"],
    "windows terminal": ["wt"],
    "powershell":     ["powershell"],
    "control panel":  ["control"],
    "settings":       ["ms-settings:"],
    "photos":         ["microsoft.photos"],
    "snipping tool":  ["snippingtool", "snip"],
}

# Well-known search directories
SEARCH_DIRS = [
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMFILES%"),
    os.path.expandvars(r"%PROGRAMFILES(X86)%"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps"),
]


def _normalize(name: str) -> str:
    return name.lower().strip()


def _find_in_path(exe_name: str) -> Optional[str]:
    """Check if exe exists anywhere in system PATH."""
    try:
        result = subprocess.run(
            ["where", exe_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            first_match = result.stdout.strip().splitlines()[0]
            return first_match
    except Exception:
        pass
    return None


def _search_start_menu(query: str) -> list[str]:
    """Search Start Menu .lnk shortcuts for matching apps."""
    matches = []
    q = _normalize(query)
    for search_dir in SEARCH_DIRS[:2]:  # Only Start Menu dirs
        if not os.path.isdir(search_dir):
            continue
        for root, _, files in os.walk(search_dir):
            for fname in files:
                if fname.lower().endswith(".lnk") and q in fname.lower():
                    matches.append(os.path.join(root, fname))
    return matches


def _search_program_files(query: str) -> list[str]:
    """Search Program Files for matching .exe files."""
    matches = []
    q = _normalize(query)
    for search_dir in SEARCH_DIRS[2:]:
        if not os.path.isdir(search_dir):
            continue
        pattern = os.path.join(search_dir, "**", f"*{q}*.exe")
        try:
            found = glob.glob(pattern, recursive=True)
            matches.extend(found[:5])  # cap per dir
        except Exception:
            pass
    return matches


def find_application(app_request: str) -> Optional[str]:
    """
    Find an application path or launch command from a user request string.
    Returns the best match as a string suitable for subprocess.Popen / os.startfile,
    or None if nothing found.
    """
    query = _normalize(app_request)

    # 1. Check aliases first — fastest path
    for alias, exe_names in ALIASES.items():
        if query == alias or query in alias or alias in query:
            for exe in exe_names:
                path = _find_in_path(exe)
                if path:
                    logger.info(f"Found '{app_request}' via alias → {path}")
                    return path
            # If not in PATH, return the bare exe name anyway (Windows will search)
            return exe_names[0]

    # 2. Try exact exe name in PATH
    path = _find_in_path(query)
    if path:
        return path

    # 3. Try with .exe suffix
    path = _find_in_path(query + ".exe")
    if path:
        return path

    # 4. Search Start Menu shortcuts
    shortcuts = _search_start_menu(query)
    if shortcuts:
        logger.info(f"Found '{app_request}' via Start Menu: {shortcuts[0]}")
        return shortcuts[0]

    # 5. Search Program Files
    exes = _search_program_files(query)
    if exes:
        # Prefer exact basename match
        for exe in exes:
            if _normalize(os.path.basename(exe)).startswith(query):
                logger.info(f"Found '{app_request}' via Program Files: {exe}")
                return exe
        logger.info(f"Found '{app_request}' via Program Files (fuzzy): {exes[0]}")
        return exes[0]

    logger.warning(f"Could not find application: '{app_request}'")
    return None


def launch_application(app_path: str) -> bool:
    """
    Launch an application by path, shortcut, or bare name.
    Returns True if the launch command succeeded (process started),
    False on error.
    """
    try:
        # ms-settings: URIs and similar protocol handlers
        if ":" in app_path and not os.path.exists(app_path):
            os.startfile(app_path)
            return True

        # .lnk shortcuts
        if app_path.lower().endswith(".lnk"):
            os.startfile(app_path)
            return True

        # Full path or bare exe name
        subprocess.Popen(
            [app_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        return True

    except FileNotFoundError:
        # Last resort: let Windows shell resolve it
        try:
            os.startfile(app_path)
            return True
        except Exception as e:
            logger.error(f"Failed to launch '{app_path}': {e}")
            return False

    except Exception as e:
        logger.error(f"Failed to launch '{app_path}': {e}")
        return False


def list_installed_apps(limit: int = 50) -> list[str]:
    """
    Return a list of app names from the Start Menu (best effort).
    """
    apps = []
    for search_dir in SEARCH_DIRS[:2]:
        if not os.path.isdir(search_dir):
            continue
        for root, _, files in os.walk(search_dir):
            for fname in files:
                if fname.lower().endswith(".lnk"):
                    name = fname[:-4]  # strip .lnk
                    if name not in apps:
                        apps.append(name)
                if len(apps) >= limit:
                    return sorted(apps)
    return sorted(apps)
