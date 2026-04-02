"""Shared FastMCP instance — imported by every tools module."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("windows_mcp")
