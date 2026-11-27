"""Protocol dispatch, each rule pinned to the MCP specification section it comes from.

Sections are named by their path under ``docs/specification/`` in
modelcontextprotocol/modelcontextprotocol: revision ``2026-07-28`` unless
another revision is given.
"""

import base64
import email.message
import json
import unittest

from stdmcp import App, SUPPORTED_VERSIONS, Tool, ToolError, dispatch
from stdmcp.protocol import MODERN

SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"


def _echo(station, days):
    return {"station": station, "days": days, "river": "Afon Taf"}


def _refuse(station, days):
    raise ToolError(f"No gauge called {station}.")


def _crash(station, days):
    raise RuntimeError("database at /secret/path is locked")


def _unserialisable(station, days):
    return {"stations": {station}}


def _huge(station, days):
    return {"data": "x" * 500}


SCHEMA = {
    "type": "object",
    "properties": {
        "station": {"type": "string"},
        "days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
    },
    "required": ["station"],
    "additionalProperties": False,
}


def _tool(name, handler):
    return Tool(name=name, title=name.title(), description=f"The {name} tool.", input_schema=SCHEMA, handler=handler)


APP = App(
    name="example",
    version="1.2.3",
    title="Example Server",
    description="A server for tests.",
    instructions="Ask about rivers.",
    url="https://example.org/mcp",
    tools=(_tool("echo", _echo), _tool("refuse", _refuse), _tool("crash", _crash), _tool("huge", _huge), _tool("Afon Tâf", _echo),
           _tool("odd", _unserialisable)),
    max_result_chars=200,
)


HELLO = {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "c", "version": "1"}}


def legacy(method, params=None, id=1, version="2025-11-25"):
    """A handshake-era request: no ``_meta`` version, the header if given."""
    headers = {} if version is None else {"MCP-Protocol-Version": version}
    message = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        message["params"] = params
    return headers, message


def modern(method, params=None, id=1, name=None, version=MODERN, meta_version=MODERN, extra_headers=None):
    """A stateless request with consistent headers, unless told otherwise."""
    params = dict(params or {})
    params["_meta"] = {
        VERSION_KEY: meta_version,
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    headers = {"MCP-Protocol-Version": version, "Mcp-Method": method}
    if method == "tools/call":
        headers["Mcp-Name"] = params.get("name") if name is None else name
    headers.update(extra_headers or {})
    return headers, {"jsonrpc": "2.0", "id": id, "method": method, "params": params}


class MessageShapeTests(unittest.TestCase):
    # basic/transports/streamable-http.mdx, "Sending Messages": the body MUST be a
    # single JSON-RPC request or notification. Batches are not part of this revision.
    def test_not_an_object_or_a_batch_is_an_invalid_request(self):
        invalid = (
            [{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
            "ping",
            3,
            None,
            {"id": 1},
            {"jsonrpc": "1.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "id": None, "method": "ping"},
        )
        for message in invalid:
            with self.subTest(message=message):
                status, body = dispatch(APP, {}, message)
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], -32600)
                self.assertEqual(body["jsonrpc"], "2.0")

    # basic/transports/streamable-http.mdx, "Sending Messages", item 5: an accepted
    # notification gets 202 with no body.
    def test_notification_is_accepted_without_a_body(self):
        for headers in ({}, {"MCP-Protocol-Version": "2025-11-25"}, {"MCP-Protocol-Version": MODERN}):
            with self.subTest(headers=headers):
                self.assertEqual(dispatch(APP, headers, {"jsonrpc": "2.0", "method": "notifications/initialized"}), (202, None))


class LegacyTests(unittest.TestCase):
    # 2025-11-25/basic/lifecycle.mdx, "Initialization" and "Version Negotiation".
    def test_initialize_negotiates_a_version(self):
        for requested, answered in (("2025-06-18", "2025-06-18"), ("2025-03-26", "2025-03-26"), ("2024-11-05", "2025-11-25")):
            with self.subTest(requested=requested):
                headers, message = legacy("initialize", {**HELLO, "protocolVersion": requested}, version=None)
                status, body = dispatch(APP, headers, message)
                self.assertEqual(status, 200)
                self.assertEqual(body["id"], 1)
                self.assertEqual(
                    body["result"],
                    {
                        "protocolVersion": answered,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "example", "title": "Example Server", "version": "1.2.3"},
                        "instructions": "Ask about rivers.",
                    },
                )

    # 2025-11-25/basic/utilities/ping.mdx: the receiver responds with an empty result.
    def test_ping(self):
        self.assertEqual(dispatch(APP, *legacy("ping", id="p")), (200, {"jsonrpc": "2.0", "id": "p", "result": {}}))

    # 2025-11-25/basic/transports.mdx, "Protocol Version Header": an unsupported
    # version gets 400; the body uses the -32022 shape of basic/versioning.mdx so
    # dual-era clients recognise it.
    def test_unknown_legacy_header_version_is_rejected(self):
        status, body = dispatch(APP, *legacy("tools/list", version="2024-01-01"))
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], -32022)
        self.assertEqual(body["error"]["data"], {"supported": list(SUPPORTED_VERSIONS), "requested": "2024-01-01"})

    # basic/transports/streamable-http.mdx, "Protocol Version Header": a request
    # without the header MAY be treated as 2025-03-26.
    def test_missing_header_is_treated_as_2025_03_26(self):
        status, body = dispatch(APP, *legacy("tools/list", version=None))
        self.assertEqual(status, 200)
        self.assertNotIn("resultType", body["result"])

    # basic/transports/streamable-http.mdx, "Earlier Streamable HTTP Revisions": an
    # Mcp-Session-Id is ignored, and none is minted.
    def test_session_id_is_ignored(self):
        headers, message = legacy("tools/list")
        headers["Mcp-Session-Id"] = "abc"
        status, body = dispatch(APP, headers, message)
        self.assertEqual(status, 200)
        self.assertNotIn("Mcp-Session-Id", json.dumps(body))


class ModernSelectionTests(unittest.TestCase):
    # basic/transports/streamable-http.mdx, "Protocol Version Header": the header
    # MUST match _meta, else 400 HeaderMismatch.
    def test_header_and_meta_version_disagree(self):
        for headers, message in (
            modern("tools/list", version="2025-11-25"),
            modern("tools/list", meta_version="2025-11-25"),
            legacy("tools/list", version=MODERN),
        ):
            with self.subTest(headers=headers):
                status, body = dispatch(APP, headers, message)
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], -32020)

    # basic/transports/streamable-http.mdx, "Standard Request Headers" and
    # "Server Validation": Mcp-Method and Mcp-Name must be present and match.
    def test_mcp_method_and_name_must_match_the_body(self):
        mismatched_method = modern("tools/list", extra_headers={"Mcp-Method": "tools/call"})
        missing_method = modern("tools/list")
        del missing_method[0]["Mcp-Method"]
        mismatched_name = modern("tools/call", {"name": "echo", "arguments": {"station": "1"}}, name="refuse")
        missing_name = modern("tools/call", {"name": "echo", "arguments": {"station": "1"}})
        del missing_name[0]["Mcp-Name"]
        for headers, message in (mismatched_method, missing_method, mismatched_name, missing_name):
            with self.subTest(headers=headers):
                status, body = dispatch(APP, headers, message)
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], -32020)

    # basic/versioning.mdx, "Protocol Version Negotiation": UnsupportedProtocolVersionError.
    def test_unsupported_modern_version(self):
        status, body = dispatch(APP, *modern("tools/list", version="1900-01-01", meta_version="1900-01-01"))
        self.assertEqual(status, 400)
        self.assertEqual(
            body,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32022,
                    "message": "Unsupported protocol version",
                    "data": {"supported": list(SUPPORTED_VERSIONS), "requested": "1900-01-01"},
                },
            },
        )

    # basic/transports/streamable-http.mdx, "Case Sensitivity": header names are
    # case-insensitive; http.server hands over an email.message.Message.
    def test_headers_from_http_server_are_case_insensitive(self):
        headers, message = modern("tools/list")
        parsed = email.message.Message()
        for key, value in headers.items():
            parsed[key.upper()] = value
        status, body = dispatch(APP, parsed, message)
        self.assertEqual(status, 200)
        lowered = {key.lower(): value for key, value in headers.items()}
        self.assertEqual(dispatch(APP, lowered, message)[0], 200)


class DiscoverTests(unittest.TestCase):
    # server/discover.mdx, "Response".
    def test_server_discover(self):
        status, body = dispatch(APP, *modern("server/discover"))
        self.assertEqual(status, 200)
        result = body["result"]
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["supportedVersions"], list(SUPPORTED_VERSIONS))
        self.assertEqual(result["capabilities"], {"tools": {}})
        self.assertEqual(result["_meta"][SERVER_INFO_KEY]["name"], "example")
        self.assertEqual(result["_meta"][SERVER_INFO_KEY]["version"], "1.2.3")
        self.assertEqual(result["instructions"], "Ask about rivers.")
        self.assertEqual(result["ttlMs"], 3600000)
        self.assertEqual(result["cacheScope"], "public")


class ToolsListTests(unittest.TestCase):
    # server/tools.mdx, "Listing Tools"; schema.ts CacheableResult for the modern extras.
    def test_tools_list(self):
        names = ["echo", "refuse", "crash", "huge", "Afon Tâf", "odd"]
        status, body = dispatch(APP, *legacy("tools/list"))
        self.assertEqual(status, 200)
        self.assertEqual([t["name"] for t in body["result"]["tools"]], names)
        self.assertEqual(body["result"]["tools"][0], APP.tools[0].listing())
        self.assertEqual(set(body["result"]), {"tools"})

        status, body = dispatch(APP, *modern("tools/list"))
        self.assertEqual(status, 200)
        result = body["result"]
        self.assertEqual([t["name"] for t in result["tools"]], names)
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["ttlMs"], 3600000)
        self.assertEqual(result["cacheScope"], "public")


class ToolsCallTests(unittest.TestCase):
    # server/tools.mdx, "Error Handling": an unknown tool is a protocol error.
    def test_unknown_tool(self):
        params = {"name": "x", "arguments": {}}
        for headers, message in (legacy("tools/call", params), modern("tools/call", params)):
            with self.subTest(headers=headers):
                status, body = dispatch(APP, headers, message)
                self.assertEqual(status, 200)
                self.assertEqual(body["error"], {"code": -32602, "message": "Unknown tool: x"})

    # server/tools.mdx, "Error Handling" (and 2025-11-25/changelog.mdx, SEP-1303):
    # input validation errors are tool execution errors, so the model can correct
    # itself. Arguments that are not an object fail the CallToolRequest schema and
    # stay a protocol error.
    def test_invalid_arguments(self):
        status, body = dispatch(APP, *legacy("tools/call", {"name": "echo", "arguments": {"station": "1", "days": 99}}))
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], {"content": [{"type": "text", "text": "days must be at most 30"}], "isError": True})

        status, body = dispatch(APP, *legacy("tools/call", {"name": "echo", "arguments": ["1"]}))
        self.assertEqual(status, 200)
        self.assertEqual(body["error"]["code"], -32602)

    # server/tools.mdx, "Calling Tools", "Text Content" and "Structured Content".
    def test_handler_result(self):
        expected = {"station": "1", "days": 7, "river": "Afon Taf"}
        status, body = dispatch(APP, *legacy("tools/call", {"name": "echo", "arguments": {"station": "1"}}))
        self.assertEqual(status, 200)
        self.assertEqual(
            body["result"],
            {
                "content": [{"type": "text", "text": json.dumps(expected, ensure_ascii=False)}],
                "structuredContent": expected,
                "isError": False,
            },
        )

        status, body = dispatch(APP, *modern("tools/call", {"name": "echo", "arguments": {"station": "1"}}))
        result = body["result"]
        self.assertEqual(result["structuredContent"], expected)
        self.assertIs(result["isError"], False)
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["_meta"][SERVER_INFO_KEY]["name"], "example")

    # server/tools.mdx, "Error Handling": tool execution errors are results with isError.
    def test_handler_raises_tool_error(self):
        status, body = dispatch(APP, *legacy("tools/call", {"name": "refuse", "arguments": {"station": "Z"}}))
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], {"content": [{"type": "text", "text": "No gauge called Z."}], "isError": True})

    # server/tools.mdx, "Security Considerations": servers must not leak internals.
    def test_handler_crash_is_logged_not_returned(self):
        with self.assertLogs("stdmcp", "ERROR") as logs:
            status, body = dispatch(APP, *modern("tools/call", {"name": "crash", "arguments": {"station": "1"}}))
        self.assertEqual(status, 200)
        self.assertIs(body["result"]["isError"], True)
        self.assertEqual(body["result"]["content"], [{"type": "text", "text": "The server couldn't answer that just now."}])
        self.assertNotIn("secret", json.dumps(body))
        self.assertIn("database at /secret/path is locked", "\n".join(logs.output))

    # server/tools.mdx, "Error Handling": a result that cannot be sent is a server
    # error, reported like any other crash rather than escaping dispatch.
    def test_unserialisable_result_is_logged_not_raised(self):
        with self.assertLogs("stdmcp", "ERROR"):
            status, body = dispatch(APP, *legacy("tools/call", {"name": "odd", "arguments": {"station": "1"}}))
        self.assertEqual(status, 200)
        crashed = "The server couldn't answer that just now."
        self.assertEqual(body["result"], {"content": [{"type": "text", "text": crashed}], "isError": True})

    # server/tools.mdx, "Security Considerations": servers should limit what they return.
    def test_result_over_the_limit(self):
        status, body = dispatch(APP, *legacy("tools/call", {"name": "huge", "arguments": {"station": "1"}}))
        self.assertEqual(status, 200)
        too_large = "The answer was too large; ask for less."
        self.assertEqual(body["result"], {"content": [{"type": "text", "text": too_large}], "isError": True})


class UnknownMethodTests(unittest.TestCase):
    # basic/transports/streamable-http.mdx, "Protocol Version Header": 404 with
    # -32601 under the modern rules; legacy keeps plain JSON-RPC over 200.
    def test_unknown_method(self):
        status, body = dispatch(APP, *modern("resources/list"))
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], -32601)

        status, body = dispatch(APP, *legacy("resources/list"))
        self.assertEqual(status, 200)
        self.assertEqual(body["error"]["code"], -32601)

        # initialize belongs to the handshake versions only.
        status, body = dispatch(APP, *modern("initialize"))
        self.assertEqual(status, 404)


class ReviewFocusTests(unittest.TestCase):
    # basic/transports/streamable-http.mdx, "Value Encoding": servers MUST decode an
    # encoded Mcp-Name before comparing it with the body.
    def test_mcp_name_base64_sentinel_is_decoded(self):
        params = {"name": "Afon Tâf", "arguments": {"station": "1"}}
        encoded = "=?base64?" + base64.b64encode("Afon Tâf".encode("utf-8")).decode("ascii") + "?="
        status, body = dispatch(APP, *modern("tools/call", params, name=encoded))
        self.assertEqual(status, 200)
        self.assertIs(body["result"]["isError"], False)

        wrong = "=?base64?" + base64.b64encode(b"echo").decode("ascii") + "?="
        status, body = dispatch(APP, *modern("tools/call", params, name=wrong))
        self.assertEqual((status, body["error"]["code"]), (400, -32020))

        status, body = dispatch(APP, *modern("tools/call", params, name="=?base64?not base64!?="))
        self.assertEqual((status, body["error"]["code"]), (400, -32020))

        # http.server decodes header bytes as Latin-1, so a sentinel can hold non-ASCII.
        status, body = dispatch(APP, *modern("tools/call", params, name="=?base64?é?="))
        self.assertEqual((status, body["error"]["code"]), (400, -32020))

    # basic/versioning.mdx, "Backward Compatibility": a dual-era server may serve both
    # eras on one endpoint; no session is kept between requests.
    def test_each_request_is_judged_on_its_own(self):
        headers, message = legacy("initialize", HELLO, version=None)
        first = dispatch(APP, headers, message)
        second = dispatch(APP, *modern("tools/list", extra_headers={"Mcp-Session-Id": "abc"}))
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertIn("protocolVersion", first[1]["result"])
        self.assertEqual(second[1]["result"]["resultType"], "complete")
        for _, body in (first, second):
            self.assertNotIn("session", json.dumps(body).lower())


if __name__ == "__main__":
    unittest.main()
