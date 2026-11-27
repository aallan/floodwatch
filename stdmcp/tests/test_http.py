"""The HTTP transport, against real servers on port 0."""

import http.client
import json
import socket
import threading
import time
import unittest
from unittest import mock

import stdmcp.http
from stdmcp import App, Limits, Tool, ToolError, any_https_origin, make_server

SCHEMA = {
    "type": "object",
    "properties": {"station": {"type": "string"}},
    "required": ["station"],
    "additionalProperties": False,
}


class Gate:
    """A tool handler that blocks until the test opens the gate."""

    def __init__(self):
        self.open = threading.Event()
        self.entered = threading.Semaphore(0)

    def __call__(self, station):
        self.entered.release()
        if not self.open.wait(5):
            raise ToolError("gate never opened")
        return {"station": station}


def _app(gate=None):
    tools = [Tool("echo", "Echo", "Echoes.", SCHEMA, lambda station: {"station": station})]
    if gate is not None:
        tools.append(Tool("wait", "Wait", "Waits.", SCHEMA, gate))
    return App(
        name="org.example/test", version="1.0.0", title="Test", description="A test server.", instructions="Ask.",
        url="https://example.org/mcp", tools=tuple(tools), website_url="https://example.org",
        repository_url="https://github.com/example/test",
    )


def _call(name="echo", station="Pontypridd", id=1):
    return {"jsonrpc": "2.0", "id": id, "method": "tools/call", "params": {"name": name, "arguments": {"station": station}}}


JSON = {"Content-Type": "application/json"}


class ServerTest(unittest.TestCase):
    limits = Limits()
    trust_forwarded = True

    def setUp(self):
        self.gate = Gate()
        self.addCleanup(self.gate.open.set)
        patcher = mock.patch.object(stdmcp.http.Handler, "log_message", autospec=True)
        self.log = patcher.start()
        self.addCleanup(patcher.stop)
        self.httpd = make_server(_app(self.gate), "127.0.0.1", 0, catalog_identifier="urn:air:example.org:mcp:test",
                                 limits=self.limits, trust_forwarded=self.trust_forwarded)
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.port = self.httpd.server_address[1]

    def request(self, method, path, body=None, headers=None):
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            con.request(method, path, body=body, headers=headers or {})
            r = con.getresponse()
            return r.status, r, r.read()
        finally:
            con.close()

    def post(self, message, headers=JSON, path="/mcp"):
        return self.request("POST", path, message, headers)

    def raw(self, data):
        """Send bytes on a bare socket and return everything the server sends back."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as s:
            s.sendall(data)
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := s.recv(65536):
                chunks.append(chunk)
        return b"".join(chunks)


class Post(ServerTest):
    def test_tool_call_answers_json(self):
        status, r, body = self.post(_call())
        self.assertEqual(status, 200)
        self.assertEqual(r.getheader("Content-Type"), "application/json")
        self.assertEqual(json.loads(body)["result"]["structuredContent"], {"station": "Pontypridd"})

    def test_curl_style_requests_are_served(self):
        # Review Focus 1: no Origin, Accept: */*.
        status, r, body = self.post(_call(), {"Content-Type": "application/json", "Accept": "*/*"})
        self.assertEqual(status, 200)
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))
        self.assertFalse(json.loads(body)["result"]["isError"])

    def test_no_accept_header_is_served(self):
        # Review Focus 1: http.client sends no Accept unless asked.
        status, _, body = self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(status, 200)
        self.assertEqual([t["name"] for t in json.loads(body)["result"]["tools"]], ["echo", "wait"])

    def test_unicode_passes_through_as_utf8(self):
        status, _, body = self.post(_call(station="Pont-y-tŷ-pridd"))
        self.assertEqual(status, 200)
        self.assertIn("Pont-y-tŷ-pridd".encode(), body)

    def test_content_type_parameters_are_allowed(self):
        self.assertEqual(self.post(_call(), {"Content-Type": "application/json; charset=utf-8"})[0], 200)

    def test_wrong_content_type_is_415(self):
        for headers in ({"Content-Type": "text/plain"}, {"Content-Type": "application/jsonx"}, {}):
            with self.subTest(headers=headers):
                self.assertEqual(self.post(_call(), headers)[0], 415)

    def test_notification_is_202_without_body(self):
        status, _, body = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(status, 202)
        self.assertEqual(body, b"")

    def test_unparseable_json_is_parse_error(self):
        for body in (b"{not json", b"\xff\xfe\x00", b"[" * 50_000, b'{"id": NaN}', b"9" * 5000):
            with self.subTest(body=body[:10]):
                status, r, answer = self.post(body)
                self.assertEqual(status, 400)
                self.assertEqual(r.getheader("Content-Type"), "application/json")
                message = json.loads(answer)
                self.assertIsNone(message["id"])
                self.assertEqual(message["error"]["code"], -32700)

    def test_batch_is_rejected_by_dispatch(self):
        status, _, body = self.post([_call()])
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], -32600)

    def test_body_over_the_limit_is_413_without_reading_it(self):
        # The length alone decides: the server answers without waiting for a body.
        answer = self.raw(b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 65537\r\n\r\n")
        self.assertTrue(answer.startswith(b"HTTP/1.0 413 "), answer[:40])

    def test_body_at_the_limit_is_read(self):
        message = _call()
        body = json.dumps(message).encode()
        body += b" " * (65_536 - len(body))
        self.assertEqual(self.post(body)[0], 200)

    def test_missing_or_bad_length_is_refused(self):
        start = b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
        cases = {
            b"\r\n": b"413",
            b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n": b"413",
            b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n": b"413",
            b"Content-Length: -1\r\n\r\n": b"400",
            b"Content-Length: 1e3\r\n\r\n": b"400",
            b"Content-Length: 2\r\nContent-Length: 3\r\n\r\n{}": b"400",
        }
        for rest, status in cases.items():
            with self.subTest(rest=rest):
                answer = self.raw(start + rest)
                self.assertEqual(answer.split(b" ")[1], status, answer[:60])

    def test_short_body_is_400(self):
        answer = self.raw(b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{}")
        self.assertEqual(answer.split(b" ")[1], b"400")

    def test_slow_body_is_cut_off(self):
        self.httpd.RequestHandlerClass.timeout = 0.3
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as s:
            s.sendall(b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{")
            started = time.monotonic()
            # Dribble bytes slower than the whole-body deadline allows.
            for _ in range(4):
                time.sleep(0.1)
                try:
                    s.sendall(b" ")
                except OSError:
                    break
            try:
                answer = s.recv(1024)
            except OSError:  # the server may reset a connection it stopped reading
                answer = b""
        self.assertLess(time.monotonic() - started, 2)
        self.assertIn(answer.split(b" ")[1:2], ([b"408"], []))
        self.assertEqual(self.post(_call())[0], 200)


class Methods(ServerTest):
    def test_get_and_delete_are_405(self):
        for method in ("GET", "DELETE", "PUT"):
            with self.subTest(method=method):
                status, r, _ = self.request(method, "/mcp")
                self.assertEqual(status, 405)
                self.assertEqual(r.getheader("Allow"), "POST, OPTIONS")

    def test_never_an_event_stream_or_session(self):
        status, r, _ = self.request("GET", "/mcp", headers={"Accept": "text/event-stream"})
        self.assertEqual(status, 405)
        status, r, _ = self.post(_call(), {**JSON, "Mcp-Session-Id": "abc"})
        self.assertEqual(status, 200)
        self.assertIsNone(r.getheader("Mcp-Session-Id"))

    def test_unknown_paths_are_404(self):
        for method, path in (("GET", "/"), ("POST", "/mcpx"), ("GET", "/mcp/server-card/x")):
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path, b"{}" if method == "POST" else None, JSON)[0], 404)
        self.assertTrue(self.raw(b"GET http://[::1/mcp HTTP/1.1\r\nHost: x\r\n\r\n").startswith(b"HTTP/1.0 404 "))

    def test_query_string_is_ignored(self):
        self.assertEqual(self.post(_call(), path="/mcp?x=1")[0], 200)

    def test_no_server_version(self):
        _, r, _ = self.post(_call())
        self.assertEqual(r.getheader("Server"), "stdmcp")


class Origins(ServerTest):
    def test_https_origin_is_allowed_with_cors(self):
        status, r, _ = self.post(_call(), {**JSON, "Origin": "https://claude.ai"})
        self.assertEqual(status, 200)
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")

    def test_other_origins_are_403(self):
        for origin in ("http://evil.example", "null", "file://", ""):
            with self.subTest(origin=origin):
                status, r, _ = self.post(_call(), {**JSON, "Origin": origin})
                self.assertEqual(status, 403)

    def test_preflight(self):
        status, r, body = self.request("OPTIONS", "/mcp", headers={"Origin": "https://claude.ai", "Access-Control-Request-Method": "POST"})
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")
        self.assertEqual(r.getheader("Access-Control-Allow-Methods"), "POST, OPTIONS")
        self.assertEqual(r.getheader("Access-Control-Allow-Headers"), "Content-Type, Accept, MCP-Protocol-Version, Mcp-Method, Mcp-Name")
        self.assertEqual(r.getheader("Access-Control-Max-Age"), "600")

    def test_preflight_from_a_refused_origin_is_403(self):
        self.assertEqual(self.request("OPTIONS", "/mcp", headers={"Origin": "null"})[0], 403)

    def test_any_https_origin(self):
        self.assertTrue(any_https_origin("https://tawriver.watch"))
        for origin in ("http://tawriver.watch", "null", "", "chrome-extension://abc"):
            self.assertFalse(any_https_origin(origin))


class Logging(ServerTest):
    def lines(self):
        return [(call.args[0].address_string(), call.args[1] % call.args[2:]) for call in self.log.call_args_list]

    def test_one_line_per_request_with_client_method_tool_and_status(self):
        self.post(_call(), {**JSON, "X-Forwarded-For": "198.51.100.1, 203.0.113.9 "})
        self.request("GET", "/nowhere")
        (client, first), (_, second) = self.lines()
        self.assertEqual(client, "203.0.113.9")
        self.assertRegex(first, r"^POST /mcp tools/call echo 200 \d+ms$")
        self.assertRegex(second, r"^GET /nowhere - - 404 \d+ms$")

    def test_no_bodies_or_header_values_in_the_log(self):
        self.post(_call(station="secret-station"), {**JSON, "Origin": "https://secret.example"})
        self.post(b"{secret", JSON)
        text = " ".join(line for _, line in self.lines())
        self.assertNotIn("secret", text)
        self.assertIn(" - - 400 ", text)


class Concurrency(ServerTest):
    limits = Limits(max_in_flight=2)

    def test_more_than_max_in_flight_is_503(self):
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.post(_call("wait"))[0])) for _ in range(2)]
        for t in threads:
            t.start()
        for _ in threads:
            self.assertTrue(self.gate.entered.acquire(timeout=5))
        status, r, _ = self.post(_call())
        self.assertEqual(status, 503)
        self.assertEqual(r.getheader("Retry-After"), "1")
        self.gate.open.set()
        for t in threads:
            t.join(5)
        self.assertEqual(results, [200, 200])
        self.assertEqual(self.post(_call())[0], 200)

    def test_slots_are_released_on_every_path(self):
        bad = [
            ("POST", "/mcp", b"{", JSON), ("POST", "/mcp", b"{}", {"Content-Type": "text/plain"}),
            ("POST", "/mcp", b"{}", {**JSON, "Origin": "null"}), ("GET", "/mcp", None, {}), ("GET", "/x", None, {}),
            ("OPTIONS", "/mcp", None, {}), ("GET", "/mcp/server-card", None, {}),
        ]
        for _ in range(3):
            for method, path, body, headers in bad:
                self.request(method, path, body, headers)
        self.raw(b"POST /mcp HTTP/1.1\r\nContent-Type: application/json\r\nContent-Length: 10\r\n\r\n{")
        with mock.patch.object(stdmcp.http, "dispatch", side_effect=RuntimeError("boom")), \
                mock.patch.object(stdmcp.http.log, "exception") as logged:
            status, _, body = self.post(_call())
        self.assertEqual(status, 500)
        logged.assert_called_once()
        self.assertNotIn(b"boom", body)
        self.assertEqual(self.post(_call())[0], 200)
        self.assertEqual(self.post(_call())[0], 200)


class RateLimits(ServerTest):
    limits = Limits(per_client=(60, 2), overall=(600, 100))

    def test_client_is_the_last_forwarded_address(self):
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "198.51.100.1, 203.0.113.9 "})[0], 200)
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "203.0.113.9"})[0], 200)
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "10.0.0.1,203.0.113.9"})[0], 429)
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "203.0.113.9, 10.0.0.1"})[0], 200)

    def test_per_client_limit_is_429_with_whole_seconds(self):
        headers = {**JSON, "X-Forwarded-For": "203.0.113.9"}
        self.assertEqual(self.post(_call(), headers)[0], 200)
        self.assertEqual(self.request("GET", "/.well-known/ai-catalog.json", headers=headers)[0], 200)
        status, r, _ = self.post(_call(), headers)
        self.assertEqual(status, 429)
        self.assertRegex(r.getheader("Retry-After"), r"^[1-9]\d*$")
        # Another client is unaffected.
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "198.51.100.1"})[0], 200)

    def test_retry_after_rounds_up(self):
        self.httpd.limiter = mock.Mock(check=mock.Mock(return_value=0.0001))
        self.assertEqual(self.post(_call())[1].getheader("Retry-After"), "1")
        self.httpd.limiter = mock.Mock(check=mock.Mock(return_value=2.1))
        self.assertEqual(self.post(_call())[1].getheader("Retry-After"), "3")


class Untrusted(ServerTest):
    limits = Limits(per_client=(60, 1), overall=(600, 100))
    trust_forwarded = False

    def test_forwarded_header_ignored_when_not_trusted(self):
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "203.0.113.1"})[0], 200)
        self.assertEqual(self.post(_call(), {**JSON, "X-Forwarded-For": "203.0.113.2"})[0], 429)


class Documents(ServerTest):
    def test_server_card(self):
        status, r, body = self.request("GET", "/mcp/server-card", headers={"Accept": "application/mcp-server-card+json"})
        self.assertEqual(status, 200)
        self.assertEqual(r.getheader("Content-Type"), "application/mcp-server-card+json")
        card = json.loads(body)
        self.assertEqual(card["name"], "org.example/test")
        self.assertEqual(card["remotes"][0]["url"], "https://example.org/mcp")

    def test_catalog(self):
        status, r, body = self.request("GET", "/.well-known/ai-catalog.json")
        self.assertEqual(status, 200)
        self.assertEqual(r.getheader("Content-Type"), "application/ai-catalog+json")
        entry = json.loads(body)["entries"][0]
        self.assertEqual(entry["identifier"], "urn:air:example.org:mcp:test")
        self.assertEqual(entry["url"], "https://example.org/mcp/server-card")

    def test_cors_and_caching_headers(self):
        for path in ("/mcp/server-card", "/.well-known/ai-catalog.json"):
            with self.subTest(path=path):
                _, r, _ = self.request("GET", path, headers={"Origin": "null"})
                self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")
                self.assertEqual(r.getheader("Access-Control-Allow-Methods"), "GET")
                self.assertEqual(r.getheader("Access-Control-Allow-Headers"), "Content-Type, If-None-Match")
                self.assertEqual(r.getheader("Access-Control-Expose-Headers"), "ETag")
                self.assertEqual(r.getheader("Cache-Control"), "public, max-age=3600")
                self.assertRegex(r.getheader("ETag"), r'^"[0-9a-f]+"$')

    def test_etag_and_304(self):
        _, r, body = self.request("GET", "/mcp/server-card")
        etag = r.getheader("ETag")
        for value in (etag, f'"other", {etag}', f"W/{etag}", "*"):
            with self.subTest(value=value):
                status, r2, again = self.request("GET", "/mcp/server-card", headers={"If-None-Match": value})
                self.assertEqual(status, 304)
                self.assertEqual(again, b"")
                self.assertEqual(r2.getheader("ETag"), etag)
                self.assertEqual(r2.getheader("Access-Control-Allow-Origin"), "*")
        status, _, again = self.request("GET", "/mcp/server-card", headers={"If-None-Match": '"other"'})
        self.assertEqual((status, again), (200, body))
        _, other, _ = self.request("GET", "/.well-known/ai-catalog.json")
        self.assertNotEqual(other.getheader("ETag"), etag)

    def test_document_preflight_and_methods(self):
        status, r, _ = self.request("OPTIONS", "/mcp/server-card", headers={"Origin": "https://x.example"})
        self.assertEqual(status, 204)
        self.assertEqual(r.getheader("Access-Control-Allow-Headers"), "Content-Type, If-None-Match")
        status, r, _ = self.request("POST", "/.well-known/ai-catalog.json", b"{}", JSON)
        self.assertEqual(status, 405)
        self.assertEqual(r.getheader("Allow"), "GET, OPTIONS")


if __name__ == "__main__":
    unittest.main()
