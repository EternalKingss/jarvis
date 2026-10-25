"""
Microsoft UI Automation tools for windows_jarvis.
Uses pywinauto (UIA backend) to read and control any Windows app's UI elements.
This lets Jarvis interact with buttons, inputs, menus, dialogs — anything visible.
"""

import io
import re
import contextlib
from pydantic import Field
from typing import Optional
from mcp_instance import mcp


def _get_desktop():
    try:
        from pywinauto import Desktop
    except ImportError as e:
        raise RuntimeError(
            "UI Automation needs the pywinauto package (Windows only). "
            "Reinstall the extension, or run: pip install pywinauto"
        ) from e
    return Desktop(backend="uia")


def _partial(title: str) -> str:
    """Case-insensitive 'contains' regex for a literal title."""
    return f"(?i).*{re.escape(title)}.*"


def _find_window(title: str):
    """Find a window by exact title, else the first partial match.

    pywinauto specs are lazy and never raise on construction, so an exact
    lookup has to be checked with exists() before falling back.
    """
    desktop = _get_desktop()
    exact = desktop.window(title=title)
    if exact.exists(timeout=0):
        return exact
    partial = desktop.window(title_re=_partial(title), found_index=0)
    if not partial.exists(timeout=5):
        raise LookupError(
            f"no open window title contains '{title}'. "
            "Run win_uia_list_windows to see the exact titles."
        )
    return partial


def _find_control(win, title: str, control_type: Optional[str] = None):
    """Find a control inside a window by exact title, else the first partial match."""
    kwargs = {"control_type": control_type} if control_type else {}
    if not title:
        return win.child_window(found_index=0, **kwargs)
    exact = win.child_window(title=title, **kwargs)
    if exact.exists(timeout=0):
        return exact
    return win.child_window(title_re=_partial(title), found_index=0, **kwargs)


# ── Inspect ───────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_inspect",
    annotations={"title": "Inspect Window UI Tree", "readOnlyHint": True, "destructiveHint": False},
    description=(
        "Inspect the UI element tree of any open window. "
        "Returns all controls (buttons, inputs, menus, etc.) inside the window — "
        "use this to discover what's clickable before interacting."
    ),
)
def win_uia_inspect(
    window_title: str = Field(
        ...,
        description="Partial or full title of the window to inspect (e.g. 'Notepad', 'Chrome', 'Settings').",
    ),
    max_depth: int = Field(
        default=4,
        description="How deep to recurse into the UI tree (1-8). Higher = more detail but slower.",
        ge=1,
        le=8,
    ),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists", timeout=5)

        # Capture print_control_identifiers output
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            win.print_control_identifiers(depth=max_depth)
        output = buf.getvalue()

        # Trim if very long
        if len(output) > 6000:
            output = output[:6000] + "\n\n[...truncated — use smaller max_depth or a more specific window]"

        return f"UI tree for '{window_title}':\n\n{output}"
    except Exception as e:
        return f"❌ Could not inspect window '{window_title}': {e}"


# ── Click ─────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_click",
    annotations={"title": "Click UI Element", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Click any UI element (button, link, tab, menu item) inside a Windows app by its name. "
        "Works even if the window isn't in focus. "
        "Use win_uia_inspect first to find the exact control name."
    ),
)
def win_uia_click(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(..., description="Exact or partial title of the control to click."),
    control_type: str = Field(
        default="",
        description="Optional control type to narrow search: 'Button', 'MenuItem', 'TabItem', 'ListItem', 'Hyperlink', etc.",
    ),
    double_click: bool = Field(default=False, description="If True, double-click instead of single click."),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists visible", timeout=5)
        ctrl = _find_control(win, control_title, control_type or None)
        ctrl.wait("exists enabled", timeout=5)
        if double_click:
            ctrl.double_click_input()
        else:
            ctrl.click_input()
        return f"✅ Clicked '{control_title}' in '{window_title}'"
    except Exception as e:
        return f"❌ Click failed: {e}"


# ── Type ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_type_into",
    annotations={"title": "Type Into UI Field", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Type text into a specific input field, text box, or search bar inside any Windows app. "
        "Use win_uia_inspect to find the control name first."
    ),
)
def win_uia_type_into(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(..., description="Title/name of the input field to type into."),
    text: str = Field(..., description="Text to type."),
    clear_first: bool = Field(default=True, description="If True, clears existing text before typing."),
    press_enter: bool = Field(default=False, description="If True, presses Enter after typing."),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists visible", timeout=5)
        ctrl = _find_control(win, control_title, "Edit")
        ctrl.wait("exists enabled", timeout=5)
        ctrl.click_input()
        if clear_first:
            ctrl.type_keys("^a{DELETE}", with_spaces=True)
        ctrl.type_keys(text, with_spaces=True)
        if press_enter:
            ctrl.type_keys("{ENTER}")
        return f"✅ Typed into '{control_title}' in '{window_title}'"
    except Exception as e:
        return f"❌ Type failed: {e}"


# ── Read ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_read",
    annotations={"title": "Read UI Element Text", "readOnlyHint": True, "destructiveHint": False},
    description=(
        "Read the text or value from a UI element inside any Windows app. "
        "Works for labels, input fields, status bars, list items, etc."
    ),
)
def win_uia_read(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(
        default="",
        description="Title of the specific control to read. Leave blank to read all visible text in the window.",
    ),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists", timeout=5)

        if not control_title:
            # Read all text from the window
            texts = []
            for ctrl in win.descendants():
                try:
                    t = ctrl.window_text()
                    if t and t.strip():
                        texts.append(t.strip())
                except Exception:
                    pass
            seen = list(dict.fromkeys(texts))  # deduplicate preserving order
            return f"Text in '{window_title}':\n\n" + "\n".join(seen[:100])

        ctrl = _find_control(win, control_title)
        ctrl.wait("exists", timeout=5)
        value = ctrl.window_text() or ctrl.get_value() if hasattr(ctrl, "get_value") else ctrl.window_text()
        return f"Value of '{control_title}': {value}"
    except Exception as e:
        return f"❌ Read failed: {e}"


# ── Select ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_select",
    annotations={"title": "Select UI List Item", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Select an item from a dropdown, list box, combo box, or tab control inside any Windows app."
    ),
)
def win_uia_select(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(..., description="Title/name of the dropdown, list, or tab control."),
    item: str = Field(..., description="The item to select (by its visible text)."),
    control_type: str = Field(
        default="",
        description="Control type: 'ComboBox', 'ListBox', 'TabControl', 'List', etc.",
    ),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists visible", timeout=5)
        ctrl = _find_control(win, control_title, control_type or None)
        ctrl.wait("exists enabled", timeout=5)
        ctrl.select(item)
        return f"✅ Selected '{item}' in '{control_title}'"
    except Exception as e:
        return f"❌ Select failed: {e}"


# ── Focus / Bring to front ────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_focus",
    annotations={"title": "Focus Window", "readOnlyHint": False, "destructiveHint": False},
    description="Bring a window to the front and give it focus.",
)
def win_uia_focus(
    window_title: str = Field(..., description="Partial or full title of the window to focus."),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists", timeout=5)
        win.set_focus()
        win.bring_to_front() if hasattr(win, "bring_to_front") else None
        return f"✅ Focused window: '{window_title}'"
    except Exception as e:
        return f"❌ Focus failed: {e}"


# ── Menu navigation ───────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_menu",
    annotations={"title": "Navigate App Menu", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Click through an app's menu bar. "
        "Provide the menu path as arrow-separated items, e.g. 'File->Save As' or 'Edit->Find->Find Next'."
    ),
)
def win_uia_menu(
    window_title: str = Field(..., description="Partial or full title of the window."),
    menu_path: str = Field(
        ...,
        description="Menu path separated by '->'. Example: 'File->Save As', 'View->Zoom->100%'.",
    ),
) -> str:
    try:
        win = _find_window(window_title)
        win.wait("exists visible", timeout=5)
        win.set_focus()
        items = [item.strip() for item in menu_path.split("->")]
        win.menu_select("->".join(items))
        return f"✅ Navigated menu: {menu_path}"
    except Exception as e:
        return f"❌ Menu navigation failed: {e}"


# ── Get window list ───────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_list_windows",
    annotations={"title": "List UI Automation Windows", "readOnlyHint": True, "destructiveHint": False},
    description="List all open windows that UI Automation can see, with their titles.",
)
def win_uia_list_windows() -> str:
    try:
        desktop = _get_desktop()
        windows = desktop.windows()
        results = []
        for w in windows:
            try:
                title = w.window_text()
                if title and title.strip():
                    results.append(title.strip())
            except Exception:
                pass
        seen = list(dict.fromkeys(results))
        if not seen:
            return "No windows found."
        return f"Open windows ({len(seen)}):\n\n" + "\n".join(f"• {t}" for t in seen)
    except Exception as e:
        return f"❌ Could not list windows: {e}"
