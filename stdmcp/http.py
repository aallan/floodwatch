"""Streamable HTTP for ``dispatch``: one JSON response per POST, never a stream or a session.

Also serves the server card and the AI Catalog, and applies the limits: request
body size, requests in progress, and per-client and overall rate limits. Every
request gets exactly one log line on stderr.
"""

import hashlib
import json
import logging
import math
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from stdmcp.discovery import CARD_TYPE, CATALOG_TYPE, ai_catalog, card_url, server_card
from stdmcp.protocol import App, dispatch
from stdmcp.ratelimit import Limiter

log = logging.getLogger("stdmcp")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
SERVER_ERROR = -32000

MCP_CORS = {
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept, MCP-Protocol-Version, Mcp-Method, Mcp-Name",
    "Access-Control-Max-Age": "600",
}
# docs/discovery.md, "CORS Requirements" and "Caching".
DOCUMENT_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET",
    "Access-Control-Allow-Headers": "Content-Type, If-None-Match",
    "Access-Control-Expose-Headers": "ETag",
    "Cache-Control": "public, max-age=3600",
}


@dataclass(frozen=True)
class Limits:
    max_body: int = 65_536
    max_in_flight: int = 8
    per_client: tuple = (300, 60)
    overall: tuple = (600, 120)


def any_https_origin(origin: str) -> bool:
    """The default origin policy: any ``https`` origin; anything else, ``null`` included, is refused."""
    return origin.startswith("https://")


class _Refuse(Exception):
    def __init__(self, status: int, message: str, code: int = INVALID_REQUEST, headers: dict | None = None):
        super().__init__(message)
        self.status, self.message, self.code, self.headers = status, message, code, headers or {}


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not JSON")


def _document(body: dict, media_type: str) -> tuple[bytes, str, str]:
    data = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    return data, media_type, '"' + hashlib.sha256(data).hexdigest()[:32] + '"'


def _path(target: str) -> str | None:
    """The path of a request target, or ``None`` if it cannot be parsed."""
    try:
        return urlsplit(target).path
    except ValueError:
        return None


def _etag_matches(header: str, etag: str) -> bool:
    """Weak comparison, as ``If-None-Match`` uses (RFC 9110, 13.1.2)."""
    tags = [tag.strip() for tag in header.split(",")]
    return "*" in tags or etag in (tag.removeprefix("W/") for tag in tags)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, app: App, catalog_identifier: str, limits: Limits, origin_ok, trust_forwarded: bool):
        self.app, self.limits, self.origin_ok, self.trust_forwarded = app, limits, origin_ok, trust_forwarded
        self.limiter = Limiter(limits.per_client, limits.overall)
        self.slots = threading.BoundedSemaphore(limits.max_in_flight)
        self.endpoint = urlsplit(app.url).path
        self.documents = {
            urlsplit(card_url(app)).path: _document(server_card(app), CARD_TYPE),
            "/.well-known/ai-catalog.json": _document(ai_catalog(app, catalog_identifier), CATALOG_TYPE),
        }
        # A subclass per server, so each can set its own timeout.
        super().__init__(address, type("Handler", (Handler,), {}))


class Handler(BaseHTTPRequestHandler):
    server: Server
    server_version = "stdmcp"
    sys_version = ""
    # Seconds a client gets for each read, and for the whole body.
    timeout = 10

    def version_string(self) -> str:
        return self.server_version

    def address_string(self) -> str:
        return getattr(self, "client", None) or self.client_address[0]

    def log_request(self, code="-", size="-") -> None:
        # Requests that reach _handle log their own line; the rest (malformed
        # request lines and the like) keep the standard one.
        if not getattr(self, "client", None):
            super().log_request(code, size)

    def do_POST(self):
        self._handle()

    do_GET = do_HEAD = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_POST

    def _handle(self) -> None:
        started = time.monotonic()
        self.client = self._client_address()
        self.target = _path(self.path)
        self.rpc = self.tool = None
        self.status = 0
        acquired = self.server.slots.acquire(blocking=False)
        try:
            if not acquired:
                raise _Refuse(503, "Too many requests in progress", SERVER_ERROR, {"Retry-After": "1"})
            delay = self.server.limiter.check(self.client)
            if delay > 0:
                raise _Refuse(429, "Rate limited", SERVER_ERROR, {"Retry-After": str(max(1, math.ceil(delay)))})
            self._route()
        except _Refuse as e:
            self._send_error(e)
        except TimeoutError:
            self._send_error(_Refuse(408, "Request body too slow"))
        except OSError:
            # The client went away; there is no one to answer.
            self.close_connection = True
        except Exception:
            log.exception("request failed")
            self._send_error(_Refuse(500, "Internal error", SERVER_ERROR))
        finally:
            if acquired:
                self.server.slots.release()
            elapsed = round((time.monotonic() - started) * 1000)
            path = "?" if self.target is None else self.target[:100]
            self.log_message("%s %s %s %s %s %dms", self.command, path, self.rpc or "-", self.tool or "-", self.status, elapsed)

    def _client_address(self) -> str:
        if self.server.trust_forwarded:
            forwarded = self.headers.get_all("X-Forwarded-For") or []
            if forwarded:
                last = forwarded[-1].rsplit(",", 1)[-1].strip()
                if last:
                    return last[:64]
        return self.client_address[0]

    def _route(self) -> None:
        if self.target == self.server.endpoint:
            self._endpoint()
        elif self.target in self.server.documents:
            self._document(*self.server.documents[self.target])
        else:
            raise _Refuse(404, "Not found")

    def _endpoint(self) -> None:
        origin = self.headers.get("Origin")
        cors = {}
        if origin is not None:
            if not self.server.origin_ok(origin):
                raise _Refuse(403, "Origin not allowed")
            cors = {"Access-Control-Allow-Origin": "*"}
        if self.command == "OPTIONS":
            return self._send(204, {"Access-Control-Allow-Origin": "*", **MCP_CORS})
        if self.command != "POST":
            raise _Refuse(405, "Method not allowed", headers={"Allow": "POST, OPTIONS", **cors})
        body = self._read_body()
        if self.headers.get_content_type() != "application/json":
            raise _Refuse(415, "Content-Type must be application/json", headers=cors)
        try:
            message = json.loads(body, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            raise _Refuse(400, "Parse error", PARSE_ERROR, cors) from None
        if isinstance(message, dict):
            self.rpc = str(message.get("method"))[:64] if isinstance(message.get("method"), str) else None
            params = message.get("params")
            if self.rpc == "tools/call" and isinstance(params, dict) and isinstance(params.get("name"), str):
                self.tool = params["name"][:64]
        status, answer = dispatch(self.server.app, self.headers, message)
        if answer is None:
            return self._send(202, cors)
        self._send(status, cors, json.dumps(answer, ensure_ascii=False).encode("utf-8"), "application/json")

    def _read_body(self) -> bytes:
        """The request body, read only once its declared length is known to be within the limit."""
        limit = self.server.limits.max_body
        lengths = self.headers.get_all("Content-Length") or []
        if "Transfer-Encoding" in self.headers or not lengths:
            raise _Refuse(413, f"A Content-Length of at most {limit} bytes is required")
        value = lengths[0].strip()
        if len(set(lengths)) > 1 or not (value.isascii() and value.isdigit() and len(value) <= 18):
            raise _Refuse(400, "Invalid Content-Length")
        length = int(value)
        if length > limit:
            raise _Refuse(413, f"Request body is larger than {limit} bytes")
        deadline = time.monotonic() + self.timeout
        chunks, remaining = [], length
        while remaining:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError
            self.connection.settimeout(left)
            chunk = self.rfile.read1(remaining)
            if not chunk:
                raise _Refuse(400, "Request body is shorter than its Content-Length")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _document(self, data: bytes, media_type: str, etag: str) -> None:
        if self.command == "OPTIONS":
            return self._send(204, DOCUMENT_HEADERS)
        if self.command != "GET":
            raise _Refuse(405, "Method not allowed", headers={"Allow": "GET, OPTIONS"})
        headers = {**DOCUMENT_HEADERS, "ETag": etag}
        if _etag_matches(self.headers.get("If-None-Match", ""), etag):
            return self._send(304, headers)
        self._send(200, headers, data, media_type)

    def _send_error(self, error: _Refuse) -> None:
        body = {"jsonrpc": "2.0", "id": None, "error": {"code": error.code, "message": error.message}}
        try:
            # Reading the body may have left a short per-read timeout behind.
            self.connection.settimeout(self.timeout)
            self._send(error.status, error.headers, json.dumps(body).encode("utf-8"), "application/json")
        except OSError:
            self.close_connection = True

    def _send(self, status: int, headers: dict, body: bytes = b"", media_type: str | None = None) -> None:
        self.status = status
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        if media_type:
            self.send_header("Content-Type", media_type)
        if status not in (204, 304):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)


def make_server(app: App, host: str, port: int, *, catalog_identifier: str, limits: Limits = Limits(),
                origin_ok=any_https_origin, trust_forwarded: bool = True) -> ThreadingHTTPServer:
    """A server for ``app``, not yet running. ``trust_forwarded`` is safe only behind a proxy on localhost."""
    return Server((host, port), app, catalog_identifier, limits, origin_ok, trust_forwarded)


def serve(app: App, host: str, port: int, **options) -> None:
    """Run ``make_server(app, host, port, **options)`` until interrupted."""
    server = make_server(app, host, port, **options)
    sys.stderr.write(f"stdmcp: {app.name} on http://{host}:{server.server_address[1]}{server.endpoint}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
