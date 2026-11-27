"""stdmcp: a standard-library-only, read-only MCP server toolkit."""

from stdmcp.protocol import SUPPORTED_VERSIONS, App, dispatch
from stdmcp.tools import Tool, ToolError

__all__ = ["App", "SUPPORTED_VERSIONS", "Tool", "ToolError", "dispatch"]
