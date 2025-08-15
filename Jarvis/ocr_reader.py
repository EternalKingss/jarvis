"""OCR Screen Reader utilities for Jarvis."""

import logging
import os
from typing import Optional, Tuple

from PIL import ImageGrab, Image
import pytesseract

# Set Tesseract path for Windows
if os.name == 'nt':  # Windows
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        logging.info(f"Tesseract path set to: {tesseract_path}")
    else:
        logging.warning(f"Tesseract not found at {tesseract_path}")


def capture_screen(region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Image.Image]:
    """Capture a screenshot of the given region.

    Args:
        region: Optional bounding box as (left, top, right, bottom).

    Returns:
        Captured :class:`PIL.Image.Image` or ``None`` on failure.
    """
    try:
        return ImageGrab.grab(bbox=region)
    except Exception as exc:  # pragma: no cover - environment specific
        logging.error("Failed to capture screen: %s", exc)
        return None


def extract_text(image: Optional[Image.Image]) -> str:
    """Extract text from a PIL image using Tesseract.

    Args:
        image: Image to process.

    Returns:
        Extracted text or empty string if extraction fails.
    """
    if image is None:
        return ""
    try:
        return pytesseract.image_to_string(image)
    except Exception as exc:  # pragma: no cover - external dependency
        logging.error("Failed to extract text: %s", exc)
        return ""


def read_text_from_screen(region: Optional[Tuple[int, int, int, int]] = None, focus_main_content: bool = False) -> str:
    """Convenience wrapper to capture the screen and extract text.
    
    Args:
        region: Optional bounding box as (left, top, right, bottom)
        focus_main_content: If True, tries to focus on main content area
    """
    if focus_main_content:
        # Try to focus on the main content area (center portion of screen)
        # This helps avoid reading system messages, toolbars, etc.
        import tkinter as tk
        root = tk.Tk()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.destroy()
        
        # Focus on center-left 70% of screen width, but capture more of the height
        # Skip left/right 15%, but only skip top 5% to get more content
        margin_x = int(screen_width * 0.15)  # Skip sides (toolbars, etc.)
        margin_y_top = int(screen_height * 0.05)  # Small top margin
        margin_y_bottom = int(screen_height * 0.15)  # Larger bottom margin (system messages)
        
        region = (margin_x, margin_y_top, screen_width - margin_x, screen_height - margin_y_bottom)
        
    image = capture_screen(region)
    return extract_text(image)
