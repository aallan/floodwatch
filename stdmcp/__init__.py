"""stdmcp: a standard-library-only, read-only MCP server toolkit."""

from stdmcp.discovery import ai_catalog, server_card
from stdmcp.http import Limits, any_https_origin, make_server, serve
from stdmcp.protocol import SUPPORTED_VERSIONS, App, dispatch
from stdmcp.tools import Tool, ToolError

__all__ = ["App", "Limits", "SUPPORTED_VERSIONS", "Tool", "ToolError", "ai_catalog", "any_https_origin", "dispatch", "make_server",
           "serve", "server_card"]
