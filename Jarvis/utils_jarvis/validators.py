"""Input validation utilities."""

import re


def sanitize_text(text: str) -> str:
    """Simple sanitation for user provided text."""
    if not isinstance(text, str):
        return ""
    # Remove dangerous shell characters
    cleaned = re.sub(r"[;&|]", "", text)
    return cleaned.strip()
