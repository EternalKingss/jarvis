"""
Screen capture shared by win_take_screenshot and win_read_screen_text.

capture() grabs the primary screen, every monitor, one window, or a region,
and returns a PIL image plus a short description of what was captured.
"""

from typing import Optional

from utils.windows import find_window, is_minimized, not_found_message, use_physical_pixels, window_bounds


class CaptureError(Exception):
    """Raised with a message meant for the user (window not found, bad region...)."""


def capture(
    window_title: Optional[str] = None,
    region: Optional[tuple[int, int, int, int]] = None,
    all_monitors: bool = False,
):
    """Return (image, description). region is (left, top, width, height) in screen pixels."""
    from PIL import ImageGrab

    use_physical_pixels()
    if window_title:
        hwnd, title, visible = find_window(window_title)
        if hwnd is None:
            raise CaptureError(not_found_message(window_title, visible))
        if is_minimized(hwnd):
            raise CaptureError(f"'{title}' is minimized. Restore it first (win_arrange_window action='restore').")
        left, top, right, bottom = window_bounds(hwnd)
        # Crop the window's rectangle from the whole desktop: what the user
        # sees. A window covered by another shows whatever is on top of it.
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        return img, f"window '{title}' at x={left}, y={top}"
    if region:
        left, top, width, height = region
        if width <= 0 or height <= 0:
            raise CaptureError("Region width and height must be positive.")
        img = ImageGrab.grab(bbox=(left, top, left + width, top + height), all_screens=True)
        return img, f"region x={left}, y={top}, {width}x{height}"
    if all_monitors:
        return ImageGrab.grab(all_screens=True), "all monitors"
    return ImageGrab.grab(), "primary screen"
