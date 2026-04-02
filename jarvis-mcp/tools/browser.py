"""Browser / web tools."""

import logging
import webbrowser
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field
from mcp_instance import mcp

logger = logging.getLogger(__name__)

SEARCH_ENGINES = {
    "google":     "https://www.google.com/search?q={}",
    "bing":       "https://www.bing.com/search?q={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
    "youtube":    "https://www.youtube.com/results?search_query={}",
    "github":     "https://github.com/search?q={}",
}


@mcp.tool(
    name="win_open_url",
    annotations={"title": "Open URL in Browser", "readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
)
async def win_open_url(
    url: str = Field(..., description="URL to open. E.g. 'https://github.com', 'youtube.com'. Protocol added automatically if missing."),
) -> str:
    """Open a URL in the user's default web browser."""
    if not url.startswith(("http://", "https://", "file://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"Opened: {url}"
    except Exception as e:
        return f"Failed to open URL: {e}"


@mcp.tool(
    name="win_search_web",
    annotations={"title": "Search the Web", "readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
)
async def win_search_web(
    query: str = Field(..., description="Search query"),
    engine: Literal["google", "bing", "duckduckgo", "youtube", "github"] = Field(default="google", description="Search engine to use (default: google)"),
) -> str:
    """Open a web search in the default browser."""
    url = SEARCH_ENGINES[engine].format(quote_plus(query))
    try:
        webbrowser.open(url)
        return f"Searching {engine} for '{query}'\n{url}"
    except Exception as e:
        return f"Failed: {e}"
