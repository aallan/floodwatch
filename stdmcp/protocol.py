"""JSON-RPC dispatch for MCP, both the stateless and the handshake versions.

``dispatch`` is a pure function of the server description, the request headers
and one parsed JSON-RPC message. It returns the HTTP status and the response
body. Reading the request, Origin checks, CORS and limits belong to the HTTP
layer.

A request whose ``MCP-Protocol-Version`` header is the modern version, or whose
``_meta`` names a protocol version, follows the stateless rules of revision
2026-07-28. Anything else follows the handshake revisions (2025-03-26 to
2025-11-25), without ever issuing a session.
"""

import base64
import binascii
import json
import logging
from dataclasses import dataclass
from typing import Mapping

from stdmcp.tools import Tool, ToolError, validate

MODERN = "2026-07-28"
SUPPORTED_VERSIONS = ("2026-07-28", "2025-11-25", "2025-06-18", "2025-03-26")
_HANDSHAKE_VERSIONS = SUPPORTED_VERSIONS[1:]
_NEGOTIATED_FALLBACK = "2025-11-25"
# The spec lets a server treat a request without the header as this version.
_HEADERLESS_VERSION = "2025-03-26"

_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
_SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
_CACHE = {"ttlMs": 3_600_000, "cacheScope": "public"}

INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022

_CRASHED = "The server couldn't answer that just now."
_TOO_LARGE = "The answer was too large; ask for less."

log = logging.getLogger("stdmcp")


@dataclass(frozen=True)
class App:
    name: str
    version: str
    title: str
    description: str
    instructions: str
    url: str
    tools: tuple[Tool, ...]
    website_url: str | None = None
    repository_url: str | None = None
    max_result_chars: int = 100_000

    def server_info(self) -> dict:
        """The ``Implementation`` object of the 2026-07-28 schema."""
        info = {"name": self.name, "title": self.title, "version": self.version, "description": self.description}
        if self.website_url:
            info["websiteUrl"] = self.website_url
        return info


class _Reject(Exception):
    """A JSON-RPC error, with the HTTP status to send it under."""

    def __init__(self, status: int, code: int, message: str, data: object = None):
        super().__init__(message)
        self.status, self.code, self.message, self.data = status, code, message, data


def _error(request_id: object, code: int, message: str, data: object = None) -> dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _unsupported(requested: object) -> _Reject:
    data = {"supported": list(SUPPORTED_VERSIONS), "requested": requested}
    return _Reject(400, UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version", data)


def _mismatch(message: str) -> _Reject:
    return _Reject(400, HEADER_MISMATCH, f"Header mismatch: {message}")


def _decode_header(value: str) -> str:
    """Undo the Base64 sentinel encoding of ``Mcp-Name``, if it is used."""
    if value.startswith("=?base64?") and value.endswith("?=") and len(value) >= len("=?base64??="):
        try:
            return base64.b64decode(value[len("=?base64?"):-len("?=")], validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raise _mismatch("Mcp-Name is not valid Base64 UTF-8") from None
    return value


def _check_modern_headers(headers: dict, method: str, params: dict, meta_version: object) -> None:
    """Raise unless the headers mirror the body and name a supported version."""
    header_version = headers.get("mcp-protocol-version")
    if header_version is None:
        raise _mismatch("MCP-Protocol-Version header is missing")
    if header_version != meta_version:
        raise _mismatch(f"MCP-Protocol-Version header value {header_version!r} does not match body value {meta_version!r}")
    if header_version not in SUPPORTED_VERSIONS:
        raise _unsupported(header_version)
    if headers.get("mcp-method") != method:
        raise _mismatch(f"Mcp-Method header value {headers.get('mcp-method')!r} does not match body value {method!r}")
    if method == "tools/call":
        name = headers.get("mcp-name")
        if name is None:
            raise _mismatch("Mcp-Name header is missing")
        if _decode_header(name) != params.get("name"):
            raise _mismatch(f"Mcp-Name header value {name!r} does not match body value {params.get('name')!r}")


def _text_result(text: str, is_error: bool) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _call_tool(app: App, params: dict) -> dict:
    name = params.get("name")
    if not isinstance(name, str):
        raise _Reject(200, INVALID_PARAMS, "Invalid params: name must be a string")
    tool = next((t for t in app.tools if t.name == name), None)
    if tool is None:
        raise _Reject(200, INVALID_PARAMS, f"Unknown tool: {name}")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise _Reject(200, INVALID_PARAMS, "Invalid params: arguments must be an object")
    # Input validation errors are tool execution errors, so the model can
    # correct itself (server/tools.mdx, "Error Handling").
    try:
        arguments = validate(tool.input_schema, arguments)
    except ValueError as e:
        return _text_result(str(e), True)
    try:
        result = tool.handler(**arguments)
    except ToolError as e:
        return _text_result(str(e), True)
    except Exception:
        log.exception("tool %s failed", name)
        return _text_result(_CRASHED, True)
    text = json.dumps(result, ensure_ascii=False)
    if len(text) > app.max_result_chars:
        return _text_result(_TOO_LARGE, True)
    return {"content": [{"type": "text", "text": text}], "structuredContent": result, "isError": False}


def _modern(app: App, method: str, params: dict) -> dict:
    if method == "server/discover":
        result = {"supportedVersions": list(SUPPORTED_VERSIONS), "capabilities": {"tools": {}}, "instructions": app.instructions, **_CACHE}
    elif method == "tools/list":
        result = {"tools": [t.listing() for t in app.tools], **_CACHE}
    elif method == "tools/call":
        result = _call_tool(app, params)
    else:
        raise _Reject(404, METHOD_NOT_FOUND, f"Method not found: {method}")
    # Every result carries resultType, and SHOULD name the server (schema.ts, Result).
    return {"resultType": "complete", **result, "_meta": {_SERVER_INFO_KEY: app.server_info()}}


def _legacy(app: App, headers: dict, method: str, params: dict) -> dict:
    if method == "initialize":
        requested = params.get("protocolVersion")
        return {
            "protocolVersion": requested if requested in _HANDSHAKE_VERSIONS else _NEGOTIATED_FALLBACK,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": app.name, "title": app.title, "version": app.version},
            "instructions": app.instructions,
        }
    version = headers.get("mcp-protocol-version", _HEADERLESS_VERSION)
    if version not in SUPPORTED_VERSIONS:
        raise _unsupported(version)
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [t.listing() for t in app.tools]}
    if method == "tools/call":
        return _call_tool(app, params)
    raise _Reject(200, METHOD_NOT_FOUND, f"Method not found: {method}")


def dispatch(app: App, headers: Mapping[str, str], message: object) -> tuple[int, dict | None]:
    """Answer one parsed JSON-RPC message: ``(HTTP status, response body or None)``."""
    if not isinstance(message, dict):
        return 400, _error(None, INVALID_REQUEST, "Invalid request: expected a single JSON-RPC object")
    request_id = message.get("id")
    # MCP request IDs are strings or integers, never null (bool is an int subclass).
    valid_id = isinstance(request_id, (str, int)) and not isinstance(request_id, bool)
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return 400, _error(request_id if valid_id else None, INVALID_REQUEST, "Invalid request: not a JSON-RPC 2.0 request")
    if "id" not in message:
        return 202, None
    if not valid_id:
        return 400, _error(None, INVALID_REQUEST, "Invalid request: id must be a string or an integer")
    params = message.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return 400, _error(request_id, INVALID_REQUEST, "Invalid request: params must be an object")

    # email.message.Message (from http.server) and dicts both yield items().
    lowered = {key.lower(): value for key, value in headers.items()}
    meta = params.get("_meta")
    meta_version = meta.get(_VERSION_KEY) if isinstance(meta, dict) else None
    try:
        if lowered.get("mcp-protocol-version") == MODERN or meta_version is not None:
            _check_modern_headers(lowered, method, params, meta_version)
            result = _modern(app, method, params)
        else:
            result = _legacy(app, lowered, method, params)
    except _Reject as e:
        return e.status, _error(request_id, e.code, e.message, e.data)
    return 200, {"jsonrpc": "2.0", "id": request_id, "result": result}
