"""Shared MCPServer instance — imported by every tools module."""

from mcp.server.mcpserver import MCPServer

SERVER_VERSION = "1.1.0"

mcp = MCPServer("windows_mcp", version=SERVER_VERSION)
