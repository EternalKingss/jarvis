"""
Microsoft UI Automation tools for windows_jarvis.
Uses pywinauto (UIA backend) to read and control any Windows app's UI elements.
This lets Jarvis interact with buttons, inputs, menus, dialogs — anything visible.

pywinauto talks to UI Automation over COM, so every UIA call runs on the
shared COM thread (utils.com.run_com).
"""

import contextlib
import io
import re
from typing import Optional

from pydantic import Field
from mcp_instance import mcp
from utils.com import run_com

_MAX_OUTPUT_CHARS = 6000


def _cap(text: str, hint: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + f"\n\n[...truncated, {len(text) - _MAX_OUTPUT_CHARS} more chars — {hint}]"


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
async def win_uia_inspect(
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
    def _impl() -> str:
        try:
            win = _find_window(window_title)
            win.wait("exists", timeout=5)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                win.print_control_identifiers(depth=max_depth)
            output = _cap(buf.getvalue(), "use a smaller max_depth or a more specific window")
            return f"UI tree for '{window_title}':\n\n{output}"
        except Exception as e:
            return f"❌ Could not inspect window '{window_title}': {e}"

    return await run_com(_impl)


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
async def win_uia_click(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(..., description="Exact or partial title of the control to click."),
    control_type: str = Field(
        default="",
        description="Optional control type to narrow search: 'Button', 'MenuItem', 'TabItem', 'ListItem', 'Hyperlink', etc.",
    ),
    double_click: bool = Field(default=False, description="If True, double-click instead of single click."),
) -> str:
    def _impl() -> str:
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

    return await run_com(_impl)


# ── Type ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_type_into",
    annotations={"title": "Type Into UI Field", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Type text into a specific input field, text box, or search bar inside any Windows app. "
        "Use win_uia_inspect to find the control name first."
    ),
)
async def win_uia_type_into(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(..., description="Title/name of the input field to type into."),
    text: str = Field(..., description="Text to type."),
    clear_first: bool = Field(default=True, description="If True, clears existing text before typing."),
    press_enter: bool = Field(default=False, description="If True, presses Enter after typing."),
) -> str:
    def _impl() -> str:
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

    return await run_com(_impl)


# ── Read ──────────────────────────────────────────────────────────────────────

def _control_value(ctrl) -> str:
    """Best text for a control: its value (edits, combos) if it has one, else its label."""
    try:
        wrapper = ctrl.wrapper_object()
    except Exception:
        wrapper = ctrl
    for getter in ("get_value", "window_text"):
        fn = getattr(wrapper, getter, None)
        if fn is None:
            continue
        try:
            value = fn()
        except Exception:
            continue
        if value:
            return str(value)
    return ""


@mcp.tool(
    name="win_uia_read",
    annotations={"title": "Read UI Element Text", "readOnlyHint": True, "destructiveHint": False},
    description=(
        "Read the text or value from a UI element inside any Windows app. "
        "Works for labels, input fields, status bars, list items, etc."
    ),
)
async def win_uia_read(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(
        default="",
        description="Title of the specific control to read. Leave blank to read all visible text in the window.",
    ),
) -> str:
    def _impl() -> str:
        try:
            win = _find_window(window_title)
            win.wait("exists", timeout=5)

            if not control_title:
                texts = []
                for ctrl in win.descendants():
                    try:
                        t = ctrl.window_text()
                        if t and t.strip():
                            texts.append(t.strip())
                    except Exception:
                        pass
                seen = list(dict.fromkeys(texts))  # deduplicate preserving order
                body = _cap("\n".join(seen), "name a control_title to read just one element")
                return f"Text in '{window_title}':\n\n{body}"

            ctrl = _find_control(win, control_title)
            ctrl.wait("exists", timeout=5)
            value = _control_value(ctrl)
            return f"Value of '{control_title}': {value}" if value else f"'{control_title}' has no text or value."
        except Exception as e:
            return f"❌ Read failed: {e}"

    return await run_com(_impl)


# ── Select ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_select",
    annotations={"title": "Select UI List Item", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Select an item from a dropdown, list box, combo box, or tab control inside any Windows app."
    ),
)
async def win_uia_select(
    window_title: str = Field(..., description="Partial or full title of the window."),
    control_title: str = Field(..., description="Title/name of the dropdown, list, or tab control."),
    item: str = Field(..., description="The item to select (by its visible text)."),
    control_type: str = Field(
        default="",
        description="Control type: 'ComboBox', 'ListBox', 'TabControl', 'List', etc.",
    ),
) -> str:
    def _impl() -> str:
        try:
            win = _find_window(window_title)
            win.wait("exists visible", timeout=5)
            ctrl = _find_control(win, control_title, control_type or None)
            ctrl.wait("exists enabled", timeout=5)
            ctrl.select(item)
            return f"✅ Selected '{item}' in '{control_title}'"
        except Exception as e:
            return f"❌ Select failed: {e}"

    return await run_com(_impl)


# ── Focus / Bring to front ────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_focus",
    annotations={"title": "Focus Window", "readOnlyHint": False, "destructiveHint": False},
    description="Bring a window to the front and give it focus.",
)
async def win_uia_focus(
    window_title: str = Field(..., description="Partial or full title of the window to focus."),
) -> str:
    def _impl() -> str:
        try:
            win = _find_window(window_title)
            win.wait("exists", timeout=5)
            win.set_focus()
            return f"✅ Focused window: '{window_title}'"
        except Exception as e:
            return f"❌ Focus failed: {e}"

    return await run_com(_impl)


# ── Menu navigation ───────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_menu",
    annotations={"title": "Navigate App Menu", "readOnlyHint": False, "destructiveHint": True},
    description=(
        "Click through an app's menu bar. "
        "Provide the menu path as arrow-separated items, e.g. 'File->Save As' or 'Edit->Find->Find Next'."
    ),
)
async def win_uia_menu(
    window_title: str = Field(..., description="Partial or full title of the window."),
    menu_path: str = Field(
        ...,
        description="Menu path separated by '->'. Example: 'File->Save As', 'View->Zoom->100%'.",
    ),
) -> str:
    def _impl() -> str:
        try:
            win = _find_window(window_title)
            win.wait("exists visible", timeout=5)
            win.set_focus()
            items = [item.strip() for item in menu_path.split("->")]
            win.menu_select("->".join(items))
            return f"✅ Navigated menu: {menu_path}"
        except Exception as e:
            return f"❌ Menu navigation failed: {e}"

    return await run_com(_impl)


# ── Get window list ───────────────────────────────────────────────────────────

@mcp.tool(
    name="win_uia_list_windows",
    annotations={"title": "List UI Automation Windows", "readOnlyHint": True, "destructiveHint": False},
    description="List all open windows that UI Automation can see, with their titles.",
)
async def win_uia_list_windows() -> str:
    def _impl() -> str:
        try:
            results = []
            for w in _get_desktop().windows():
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

    return await run_com(_impl)
