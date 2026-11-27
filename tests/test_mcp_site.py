"""floodwatch_mcp.site: the client for the website's own JSON."""

import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import stdmcp
from floodwatch_mcp.site import NotFound, Site


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, headers=()):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/data/ok.json":
            self.reply(200, json.dumps({"a": 1}).encode())
        elif self.path == "/api/missing":
            self.reply(404, json.dumps({"error": "no such station"}).encode())
        elif self.path == "/api/plain404":
            self.reply(404, b"not json")
        elif self.path == "/api/boom":
            self.reply(502, json.dumps({"error": "forecast unavailable"}).encode())
        elif self.path == "/api/slow":
            time.sleep(1)
            self.reply(200, b"{}")
        elif self.path == "/api/redirect":
            self.reply(302, b"", [("Location", "/data/ok.json")])
        elif self.path == "/api/garbage":
            self.reply(200, b"<html>")
        elif self.path == "/api/list":
            self.reply(200, b"[1]")
        elif self.path == "/api/huge":
            self.reply(200, b"{" + b" " * (6 * 1024 * 1024) + b"}")
        else:
            self.reply(404, json.dumps({"error": "not found"}).encode())


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.site = Site("http://127.0.0.1:%d" % self.httpd.server_address[1], timeout=0.2)

    def test_reads_json(self):
        self.assertEqual(self.site.json("/data/ok.json"), {"a": 1})

    def test_404_carries_the_api_message(self):
        with self.assertRaises(NotFound) as cm:
            self.site.json("/api/missing")
        self.assertEqual(str(cm.exception), "no such station")
        self.assertIsInstance(cm.exception, stdmcp.ToolError)

    def test_404_without_json_body(self):
        with self.assertRaises(NotFound):
            self.site.json("/api/plain404")

    def test_down_is_a_tool_error(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            Site("http://127.0.0.1:%d" % port, timeout=0.2).json("/data/ok.json")

    def test_slow_is_a_tool_error(self):
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            self.site.json("/api/slow")

    def test_5xx_is_unavailable(self):
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            self.site.json("/api/boom")

    def test_redirect_is_unavailable(self):
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            self.site.json("/api/redirect")

    def test_bad_body_is_unavailable(self):
        for path in ("/api/garbage", "/api/list"):
            with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
                self.site.json(path)

    def test_oversized_body_is_unavailable(self):
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            Site(self.site.base, timeout=5).json("/api/huge")

    def raw_server(self, response):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)

        def serve_once():
            conn, _ = srv.accept()
            with conn:
                conn.recv(4096)
                conn.sendall(response)

        threading.Thread(target=serve_once, daemon=True).start()
        return Site("http://127.0.0.1:%d" % srv.getsockname()[1], timeout=1)

    def test_truncated_chunked_body_is_unavailable(self):
        head = b"HTTP/1.1 %s\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
        for status in (b"200 OK", b"404 Not Found"):
            site = self.raw_server(head % status + b"20\r\n{\"error\": ")
            with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable|not found"):
                site.json("/api/x")

    def test_garbage_status_line_is_unavailable(self):
        with self.assertRaisesRegex(stdmcp.ToolError, "briefly unavailable"):
            self.raw_server(b"garbage\r\n\r\n").json("/api/x")

    def test_path_must_be_absolute(self):
        with self.assertRaises(AssertionError):
            self.site.json("http://example.com/")
        with self.assertRaises(AssertionError):
            self.site.json("data/ok.json")


if __name__ == "__main__":
    unittest.main()
