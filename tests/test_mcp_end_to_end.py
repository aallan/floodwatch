"""The MCP server end to end: floodwatch_mcp's entry point in front of serve.py's own server."""

import http.client
import json
import shutil
import tempfile
import threading
import unittest
from functools import partial
from pathlib import Path
from unittest import mock

import serve
import stdmcp
import stdmcp.http
from floodwatch_mcp import __main__ as entry
from tests.support import DBTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mcp"
MODERN = "2026-07-28"
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"


class EndToEnd(DBTestCase):
    def setUp(self):
        super().setUp()
        for handler in (serve.Handler, stdmcp.http.Handler):
            patcher = mock.patch.object(handler, "log_message")
            patcher.start()
            self.addCleanup(patcher.stop)
        # serve.py serves a temporary copy of the site's JSON, never site/data.
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / "data").mkdir()
        shutil.copy(FIXTURES / "live.json", root / "data" / "live.json")
        self.site = serve.Server(("127.0.0.1", 0), partial(serve.Handler, directory=str(root)))
        self.start(self.site)
        app = entry.make_app(f"http://127.0.0.1:{self.site.server_address[1]}", "http://localhost/mcp")
        self.mcp = stdmcp.make_server(app, "127.0.0.1", 0, catalog_identifier=entry.CATALOG_IDENTIFIER, trust_forwarded=True)
        self.start(self.mcp)
        self.stations = json.loads((FIXTURES / "live.json").read_text())["stations"]

    def start(self, server):
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def request(self, method, path, body=None, headers=None):
        con = http.client.HTTPConnection("127.0.0.1", self.mcp.server_address[1], timeout=10)
        try:
            data = None if body is None else json.dumps(body).encode()
            con.request(method, path, data, {"Content-Type": "application/json", **(headers or {})})
            r = con.getresponse()
            return r.status, json.loads(r.read())
        finally:
            con.close()

    def rpc(self, n, method, params=None, headers=None):
        body = {"jsonrpc": "2.0", "id": n, "method": method}
        if params is not None:
            body["params"] = params
        status, answer = self.request("POST", "/mcp", body, headers)
        self.assertEqual(status, 200, answer)
        self.assertNotIn("error", answer)
        return answer["result"]

    def test_legacy_session(self):
        init = self.rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "test", "version": "0"}})
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        self.assertEqual(init["serverInfo"]["name"], "watch.tawriver/floodwatch")
        self.assertEqual(init["serverInfo"]["title"], "Floodwatch")
        self.assertFalse(init["serverInfo"]["version"].startswith("v"))
        headers = {"MCP-Protocol-Version": "2025-06-18"}
        names = [t["name"] for t in self.rpc(2, "tools/list", headers=headers)["tools"]]
        self.assertIn("conditions", names)
        self.assertEqual(len(names), 9)
        result = self.rpc(3, "tools/call", {"name": "conditions", "arguments": {}}, headers)
        self.assertFalse(result["isError"], result)
        self.assertEqual(len(result["structuredContent"]["stations"]), len(self.stations))

    def test_modern_session(self):
        def headers(method, name=None):
            h = {"MCP-Protocol-Version": MODERN, "Mcp-Method": method}
            if name:
                h["Mcp-Name"] = name
            return h
        meta = {VERSION_KEY: MODERN}
        found = self.rpc(1, "server/discover", {"_meta": meta}, headers("server/discover"))
        self.assertIn(MODERN, found["supportedVersions"])
        self.assertEqual(found["_meta"]["io.modelcontextprotocol/serverInfo"]["websiteUrl"], "https://tawriver.watch")
        result = self.rpc(2, "tools/call", {"name": "list_stations", "arguments": {}, "_meta": meta},
                          headers("tools/call", "list_stations"))
        self.assertFalse(result["isError"], result)
        self.assertEqual([s["id"] for s in result["structuredContent"]["stations"]], [s["id"] for s in self.stations])

    def test_discovery_documents(self):
        status, card = self.request("GET", "/mcp/server-card")
        self.assertEqual(status, 200)
        self.assertEqual(card["repository"]["url"], "https://github.com/aallan/floodwatch")
        status, catalog = self.request("GET", "/.well-known/ai-catalog.json")
        self.assertEqual(status, 200)
        self.assertEqual(catalog["entries"][0]["identifier"], "urn:air:tawriver.watch:mcp:floodwatch")


class EntryPoint(unittest.TestCase):
    def test_version_drops_the_leading_v(self):
        with mock.patch.object(serve, "git_version", return_value="v2.0.0-12-gd904ef7c"):
            self.assertEqual(entry.version(), "2.0.0-12-gd904ef7c")
        with mock.patch.object(serve, "git_version", return_value=None):
            self.assertEqual(entry.version(), "unknown")

    def test_defaults_bind_loopback_and_trust_caddy(self):
        with mock.patch.object(entry, "serve") as run:
            entry.main([])
        app, host, port = run.call_args.args
        self.assertEqual((host, port), ("127.0.0.1", 8091))
        self.assertEqual(app.url, "https://tawriver.watch/mcp")
        self.assertEqual(run.call_args.kwargs["catalog_identifier"], "urn:air:tawriver.watch:mcp:floodwatch")
        self.assertIs(run.call_args.kwargs["trust_forwarded"], True)

    def test_options(self):
        with mock.patch.object(entry, "serve") as run:
            entry.main(["--port", "9001", "--site", "http://127.0.0.1:9000", "--url", "http://localhost:9001/mcp"])
        app, host, port = run.call_args.args
        self.assertEqual((host, port, app.url), ("127.0.0.1", 9001, "http://localhost:9001/mcp"))


if __name__ == "__main__":
    unittest.main()
