# Floodwatch MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, read-only MCP server at `https://tawriver.watch/mcp` serving the map's data to agents, after moving the map's browser-side state and forecast logic into the server's JSON.

**Architecture:** Two pull requests. PR A changes the website only: `live.py` writes the amber `approach` state and drops stale trends, `forecast.flow()` returns scaled days, and the JavaScript reads them. PR B adds `stdmcp/`, a standard-library MCP transport with no Floodwatch imports, and `floodwatch_mcp/`, nine tools that read the website's own API on the droplet's loopback, run as their own sandboxed systemd service behind Caddy; plus discovery files and an Agents tab.

**Tech Stack:** Python 3.12 standard library (`http.server`, `json`, `urllib`, `threading`, `unittest`), vanilla JavaScript, Node 22 test runner, Caddy 2.11, systemd 255.

**Spec:** `docs/superpowers/specs/2026-11-27-mcp-server-design.md`

## Global Constraints

- Standard library only. No new packages on the droplet or in CI.
- `stdmcp/` must not import `monitor`, `serve`, `floodwatch_mcp` or anything else from this repository. A test enforces it.
- Supported protocol versions, newest first: `2026-07-28`, `2025-11-25`, `2025-06-18`, `2025-03-26`. A POST without `MCP-Protocol-Version` is `2025-03-26`.
- Error codes: `-32700` parse error, `-32600` invalid request, `-32601` method not found, `-32602` invalid params, `-32020` HeaderMismatch, `-32022` UnsupportedProtocolVersion with `data: {"supported": [...], "requested": "..."}`.
- Never mint or echo `Mcp-Session-Id`. Never respond with `text/event-stream`. `GET` and `DELETE` on the endpoint: `405`.
- Limits: body 65,536 bytes; 8 requests in progress (then `503` with `Retry-After: 1`); overall 600 requests a minute; per client address 300 a minute with bursts of 60 (then `429` with `Retry-After`); tool result text at most 100,000 characters; local API timeout 5 seconds.
- Server card: `$schema` `https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json`, `name` `watch.tawriver/floodwatch`, media type `application/mcp-server-card+json`. AI Catalog: `specVersion` `1.0`, identifier `urn:air:tawriver.watch:mcp:floodwatch`, media type `application/ai-catalog+json`. Both: `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET`, `Access-Control-Allow-Headers: Content-Type, If-None-Match`, `Access-Control-Expose-Headers: ETag`, `Cache-Control: public, max-age=3600`, `ETag`, `304` on a matching `If-None-Match`.
- Authoritative texts, pinned: MCP spec `docs/specification/2026-07-28` and `2025-11-25` and `schema/2026-07-28/schema.ts` in modelcontextprotocol/modelcontextprotocol at `024d5255eb44`; modelcontextprotocol/ext-server-card at `28db12c9b4a3`. Where they disagree with this plan, they win; fix the plan.
- Tests on the Mac run at `nice -n 19` (machine-time agreement with the Vera session): `nice -n 19 make test`.
- Every change to `site/js/*.js` or `site/css/style.css` bumps its `?v=` in `site/index.html`.
- British English in all user-facing text; no em dashes in prose.

## Review Focus

1. **A client that sends no `Origin`, no `Accept`, or `Accept: */*`** (curl, server-side connectors). Expected: served normally. Test in Task 6.
2. **A tool call with a valid-looking but unknown station ID, or the right ID for the wrong tool** (a level gauge passed to `rain_forecast`). Expected: an `isError` result naming the tool that fits, not a protocol error or a 500. Test in Task 9.
3. **The website down or slow while the MCP service is up** (deploys restart `floodwatch.service`). Expected: an `isError` result saying Floodwatch is briefly unavailable, within the 5-second timeout. Test in Task 8.
4. **Unicode in names and in `Mcp-Name`** (Welsh and Cornish names, a `=?base64?...?=` sentinel). Expected: names pass through as UTF-8 JSON; a sentinel-encoded `Mcp-Name` is decoded before comparing with the body. Test in Task 4.
5. **A legacy client that sends `initialize` and then a modern-shaped request, or a modern request carrying an `Mcp-Session-Id`.** Expected: each request judged on its own; the session header ignored. Test in Task 4.

---

## PR A: the website works out its states on the server

Branch: `server-side-states` from `main`.

### Task 1: Amber state and stale trends in `live.json`

**Files:**
- Modify: `monitor/live.py` (`build()`, add `APPROACH`)
- Modify: `site/js/map.js:555-562` (`APPROACH`, `gaugeState`), `site/js/map.js:1003` (`_internals`)
- Modify: `site/index.html` (`map.js?v=`)
- Test: `tests/test_live.py`, `tests/js/map.test.mjs:12-29`

**Interfaces:**
- Produces: `live.APPROACH = 0.7`; `live.json` level `state` values `high | approach | normal | low | unknown | stale`; no `trend` key on any stale entry.

- [ ] **Step 1: Write the failing tests** in `tests/test_live.py`, class `Build`:

```python
def test_near_the_top_of_the_range_is_approach(self):
    # typical [0.5, 2.0]: 70% of 2.0 is 1.4
    self.assertEqual(self.state_after(1.39), "normal")
    self.assertEqual(self.state_after(1.4), "approach")
    self.assertEqual(self.state_after(2.3), "high")

def test_no_typical_range_is_unknown_not_approach(self): ...   # typical_high None, value 5 -> "unknown"

def test_a_stale_gauge_has_no_trend(self):
    # rising readings, newest 4 hours old
    entry = self.entry_for(...)
    self.assertEqual(entry["state"], "stale")
    self.assertNotIn("trend", entry)

def test_a_fresh_gauge_keeps_its_trend(self): ...              # "trend" == "rising"
```

`state_after` and `entry_for` are small helpers on the class using `add_station` and `add_readings` from `tests/support.py`, as `test_level_states` does.

- [ ] **Step 2: Run them to see them fail**

Run: `nice -n 19 python3 -m unittest tests.test_live -v`
Expected: the four new tests FAIL (`'normal' != 'approach'`, `'trend' unexpectedly found`).

- [ ] **Step 3: Implement in `monitor/live.py`**

Add `APPROACH = 0.7  # a level at 70% of the top of its typical range is near it` beside `STALE_AFTER`. In the level branch insert, after `high` and before `low`: `elif s["typical_high"] is not None and value >= APPROACH * s["typical_high"]: entry["state"] = "approach"`. Compute the trend only when not stale (`if not stale: entry["trend"] = ...`), for level and tidal alike.

- [ ] **Step 4: Simplify `gaugeState` in `site/js/map.js`**

`function gaugeState(s) { return s.state; }`, with the comment saying the server decides the state (`monitor/live.py`). Remove `APPROACH` from the file and from `_internals`. In `tests/js/map.test.mjs`, replace the `APPROACH` tests with one asserting `gaugeState` returns `s.state` for each of `approach`, `high`, `stale`, `raining`, `tidal`. Bump `map.js?v=` in `site/index.html`.

- [ ] **Step 5: Run all tests**

Run: `nice -n 19 make test`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add monitor/live.py site/js/map.js site/index.html tests/test_live.py tests/js/map.test.mjs
git commit -m "Work out the amber gauge state on the server, and drop stale trends"
```

Note for the reviewer: the station popup (`site/js/stations.js:54,512`) showed a stale gauge's trend; it now shows none, matching the marker.

### Task 2: Scaled flow forecast from the API

**Files:**
- Modify: `monitor/forecast.py` (add `scale_forecast`, extend `flow()`)
- Modify: `site/js/stations.js:361-385,406,415,738` (drop `scaleForecast`, read `d.scaled`)
- Modify: `site/index.html` (`stations.js?v=`), `CHANGELOG.md`
- Test: `tests/test_forecast.py`, `tests/js/stations.test.mjs:100-119`

**Interfaces:**
- Produces: `forecast.scale_forecast(days: list[list], k: float, now: int) -> list[list]`; `flow(station_id)` result gains `"scaled"`: the days as the chart shows them (equal to `"days"` when there's no anchor). `"days"` stays the model's own.

- [ ] **Step 1: Write the failing tests** in `tests/test_forecast.py`, new class `ScaleForecast(unittest.TestCase)`, porting the three JavaScript cases exactly:

```python
def test_falling_flow_is_scaled_and_a_rise_added_at_the_models_size(self):
    days = [[d(0), 2, 2, 2], [d(1), 2, 2, 2], [d(2), 1.5, 1, 2], [d(3), 1, 0.5, 4], [d(4), 3, None, 9]]
    now = d(1) + 3600
    self.assertEqual(forecast.scale_forecast(days, 6, now), [
        [d(0), 2, 2, 2], [d(1), 12, 12, 12], [d(2), 9, 6, 12], [d(3), 6, 3, 14], [d(4), 8, None, 19]])

def test_no_scaling_returns_the_days_unchanged(self): ...   # k == 1 -> same list
def test_rain_on_the_first_forecast_day_is_added_not_multiplied(self):
    # [[d(0), 2, 2, 2], [d(1), 3, 2, 40]], k 6 -> [[d(0), 2, 2, 2], [d(1), 13, 12, 50]]
```

where `d(n)` is midnight UTC on 1 November 2026 plus `n` days. Add to class `Anchor`: `test_flow_includes_the_scaled_days` (with an anchor ratio, `"scaled"` differs from `"days"` from today on) and `test_scaled_is_the_days_without_an_anchor`.

- [ ] **Step 2: Run them to see them fail**

Run: `nice -n 19 python3 -m unittest tests.test_forecast -v`
Expected: FAIL, `module 'monitor.forecast' has no attribute 'scale_forecast'`.

- [ ] **Step 3: Implement `scale_forecast`** as a direct port of `scaleForecast` in `site/js/stations.js:367-385` (same algorithm and comments; round to 2 places as `flow()` rounds), and in `flow()` add `d["scaled"] = scale_forecast(d["days"], d["anchor"]["ratio"] if d["anchor"] else 1, int(time.time()))` after the anchor line.

- [ ] **Step 4: Read `d.scaled` in `site/js/stations.js`**

Replace `const shown = scaleForecast(days, k, now);` with `const shown = d.scaled || days;`. Keep `k` for the caption, as `d.anchor && d.anchor.ratio > 0 && hasMeasured ? d.anchor.ratio : 1`. Delete `scaleForecast`, remove it from `_internals`, and delete its test from `tests/js/stations.test.mjs`. Bump `stations.js?v=`. Add to `CHANGELOG.md` under Unreleased, Changed: "The map's amber 'near top of range' state, and the scaled river flow forecast, are now worked out by the server, so every consumer of its data sees the same."

- [ ] **Step 5: Run all tests**

Run: `nice -n 19 make test`
Expected: all pass.

- [ ] **Step 6: Check it in the browser.** `make serve`, open a level gauge near the top of its range (or edit a reading in a scratch copy of the database) and the Umberleigh flow forecast; the amber marker and the forecast chart look as before.

- [ ] **Step 7: Commit, open PR A, wait for CI, ask the user before merging**

```bash
git add monitor/forecast.py site/js/stations.js site/index.html CHANGELOG.md tests/test_forecast.py tests/js/stations.test.mjs
git commit -m "Scale the flow forecast on the server"
```

After merge the user deploys with `git pull` on the droplet and restarts `floodwatch.service` (Python changed). Give them the exact command only once the PR is merged.

---

## PR B: the MCP server

Branch: `mcp-server` (already holds the design commit), rebased on `main` after PR A merges.

### Task 3: Tool registry and argument validation

**Files:**
- Create: `stdmcp/__init__.py`, `stdmcp/tools.py`
- Create: `stdmcp/tests/__init__.py`, `stdmcp/tests/test_tools.py`, `stdmcp/tests/test_independent.py`
- Modify: `Makefile` (`test-py` also runs `$(PYTHON) -m unittest discover -s stdmcp/tests -t .`)

**Interfaces:**
- Produces:
  - `class ToolError(Exception)`: a message for the agent; becomes an `isError` result.
  - `@dataclass(frozen=True) class Tool: name: str; title: str; description: str; input_schema: dict; handler: Callable[..., dict]`. `annotations()` returns `{"title": ..., "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}`; `listing()` returns the `tools/list` entry (`name`, `title`, `description`, `inputSchema`, `annotations`).
  - `validate(schema: dict, args: object) -> dict`: returns the arguments with defaults filled in, or raises `ValueError(message)`. Supports `type` (`object`, `string`, `integer`, `boolean`), `properties`, `required`, `additionalProperties: false`, `enum`, `minimum`, `maximum`, `pattern` (full match), `default`.
  - `stdmcp/__init__.py` re-exports `Tool`, `ToolError`, and (from later tasks) `App`, `Limits`, `serve`, `SUPPORTED_VERSIONS`.

- [ ] **Step 1: Write the failing tests**: `test_defaults_are_filled`, `test_unknown_arguments_are_rejected`, `test_required`, `test_integer_bounds` (`days` 0 and 31 rejected, 30 accepted, `True` rejected as an integer), `test_pattern_is_a_full_match` (the pattern `[A-Za-z0-9_-]{1,24}`, written without anchors, rejects `"50140 x"` and a 25-character ID, so full matching is what's tested), `test_enum`, `test_non_object_arguments_are_rejected`, `test_listing_shape`. And `test_independent.py`: `test_stdmcp_imports_nothing_from_floodwatch` parses every `stdmcp/*.py` with `ast` and asserts no import names `monitor`, `serve` or `floodwatch_mcp`.
- [ ] **Step 2: Run them to see them fail.** `nice -n 19 python3 -m unittest discover -s stdmcp/tests -t . -v`: import errors.
- [ ] **Step 3: Implement** `stdmcp/tools.py` and `stdmcp/__init__.py`.
- [ ] **Step 4: Run them to see them pass.** Same command: PASS.
- [ ] **Step 5: Commit.** `git commit -m "stdmcp: tool registry and argument validation"`

### Task 4: Protocol dispatch, without sockets

**Files:**
- Create: `stdmcp/protocol.py`, `stdmcp/tests/test_protocol.py`

**Interfaces:**
- Consumes: `Tool`, `ToolError`, `validate` (Task 3).
- Produces:
  - `SUPPORTED_VERSIONS = ("2026-07-28", "2025-11-25", "2025-06-18", "2025-03-26")`; `MODERN = "2026-07-28"`.
  - `@dataclass(frozen=True) class App: name: str; version: str; title: str; description: str; instructions: str; url: str; tools: tuple[Tool, ...]; website_url: str | None = None; repository_url: str | None = None; max_result_chars: int = 100_000`.
  - `dispatch(app: App, headers: Mapping[str, str], message: object) -> tuple[int, dict | None]`: the HTTP status and the JSON-RPC response (or `None` for `202`). `headers` is case-insensitive (`email.message.Message` or a lower-cased dict).

Behaviour to implement, each with a test named for its spec section (`basic/transports/streamable-http.mdx`, `basic/versioning.mdx`, `server/discover.mdx`, `server/tools.mdx`, and `2025-11-25/basic/lifecycle.mdx`):

| Case | Status | Body |
|---|---|---|
| Not a JSON object, or batch (list) | 400 | `-32600` (`-32700` is produced by Task 6 for unparseable bytes) |
| A notification (no `id`), any version | 202 | none |
| Legacy `initialize` | 200 | `protocolVersion`: the requested one if supported, else `2025-11-25`; `capabilities: {"tools": {}}`; `serverInfo: {name, title, version}`; `instructions` |
| Legacy `ping` | 200 | `{}` |
| Request whose `MCP-Protocol-Version` header is `2026-07-28`, or whose `_meta` has `io.modelcontextprotocol/protocolVersion` | modern rules below | |
| Modern: header and `_meta` version disagree, or `Mcp-Method` ≠ `method`, or `Mcp-Name` ≠ `params.name` for `tools/call` | 400 | `-32020` |
| Modern: version not in `SUPPORTED_VERSIONS` | 400 | `-32022`, `data: {"supported": [...], "requested": v}` |
| Unknown legacy header version (e.g. `2024-01-01`) | 400 | `-32022` as above |
| Modern `server/discover` | 200 | `resultType: "complete"`, `supportedVersions`, `capabilities: {"tools": {}}`, `_meta["io.modelcontextprotocol/serverInfo"]`, `instructions`, `ttlMs: 3600000`, `cacheScope: "public"` |
| `tools/list` | 200 | tools in registration order; modern adds `resultType`, `ttlMs: 3600000`, `cacheScope: "public"` |
| `tools/call`, unknown tool | 200 | `-32602` "Unknown tool: x" |
| `tools/call`, invalid arguments | 200 | `-32602` with the `ValueError` message |
| `tools/call`, handler returns dict | 200 | `content: [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]`, `structuredContent: result`, `isError: false`; modern adds `resultType: "complete"` and `_meta` serverInfo |
| `tools/call`, handler raises `ToolError` | 200 | `content: [{"type": "text", "text": message}]`, `isError: true` |
| `tools/call`, handler raises anything else | 200 | `isError: true`, "The server couldn't answer that just now."; the exception is logged, never returned |
| Result text over `max_result_chars` | 200 | `isError: true`, "The answer was too large; ask for less." |
| Unknown method | modern 404 / legacy 200 | `-32601` |
| `Mcp-Name` value `=?base64?...?=` | decoded (UTF-8) before comparing | |
| `Mcp-Session-Id` present | ignored | |

- [ ] **Step 1: Write the failing tests**, one per row, plus the Review Focus items 4 and 5: `test_mcp_name_base64_sentinel_is_decoded` (a name `"Afon Taf"`-style non-ASCII tool name round-trips) and `test_each_request_is_judged_on_its_own` (legacy `initialize`, then a modern `tools/list` with a `Mcp-Session-Id`: both succeed, no session header in either result).
- [ ] **Step 2: Run them to see them fail.** `nice -n 19 python3 -m unittest stdmcp.tests.test_protocol -v`
- [ ] **Step 3: Implement `stdmcp/protocol.py`.** Pure functions; no I/O except `logging`.
- [ ] **Step 4: Run them to see them pass.**
- [ ] **Step 5: Commit.** `git commit -m "stdmcp: protocol dispatch for the stateless and handshake versions"`

### Task 5: Rate limiter

**Files:**
- Create: `stdmcp/ratelimit.py`, `stdmcp/tests/test_ratelimit.py`

**Interfaces:**
- Produces: `class TokenBucket(rate_per_minute: float, burst: int, clock=time.monotonic)` with `take() -> float` (0 if allowed, else seconds until allowed); `class Limiter(per_client: tuple[float, int], overall: tuple[float, int], max_clients=10_000, clock=time.monotonic)` with `check(client: str) -> float`. Buckets for idle clients are dropped once `max_clients` is reached (oldest first), so memory stays bounded.

- [ ] **Step 1: Write the failing tests** with a fake clock: `test_burst_then_refill` (60 allowed at once, the 61st waits 0.2 s at 300 a minute), `test_overall_limit_applies_across_clients`, `test_retry_after_is_positive_and_small`, `test_idle_clients_are_forgotten`.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement**, thread-safe with one lock.
- [ ] **Step 4: Run them to see them pass.**
- [ ] **Step 5: Commit.** `git commit -m "stdmcp: token bucket rate limiter"`

### Task 6: The HTTP server, and discovery

**Files:**
- Create: `stdmcp/http.py`, `stdmcp/discovery.py`, `stdmcp/tests/test_http.py`, `stdmcp/tests/test_discovery.py`
- Create: `stdmcp/tests/fixtures/` with `minimal.json`, `templated-remote.json`, and the `invalid/` examples from ext-server-card `28db12c9b4a3` (with a `SOURCE` file naming the commit)

**Interfaces:**
- Consumes: `App`, `dispatch` (Task 4); `Limiter` (Task 5).
- Produces:
  - `@dataclass(frozen=True) class Limits: max_body: int = 65_536; max_in_flight: int = 8; per_client: tuple = (300, 60); overall: tuple = (600, 120)`.
  - `def any_https_origin(origin: str) -> bool` (the default origin policy: `True` for `https://` origins, `False` for anything else including `null`).
  - `server_card(app: App) -> dict` and `ai_catalog(app: App, identifier: str) -> dict`.
  - `make_server(app: App, host: str, port: int, *, catalog_identifier: str, limits: Limits = Limits(), origin_ok=any_https_origin, trust_forwarded: bool = True) -> ThreadingHTTPServer`; `serve(...)` with the same arguments runs it forever. Paths are taken from `urlsplit(app.url).path` (`/mcp`), plus `/mcp/server-card` and `/.well-known/ai-catalog.json`.

Behaviour, each with a test against a real server on port 0 (as `tests/test_serve.py` does):

- `POST /mcp`: `Content-Type` must be `application/json` (parameters allowed), else `415`. Body over `max_body` (by `Content-Length`, or missing length): `413`. Unparseable JSON: `400` with `-32700` and `"id": null`. Otherwise `dispatch()`; JSON responses with `Content-Type: application/json`.
- `Origin` present and `origin_ok` false: `403`. Responses to an allowed `Origin` carry `Access-Control-Allow-Origin: *`; `OPTIONS /mcp` answers the preflight (`Allow-Methods: POST, OPTIONS`; `Allow-Headers: Content-Type, Accept, MCP-Protocol-Version, Mcp-Method, Mcp-Name`; `Max-Age: 600`).
- `GET` and `DELETE /mcp`: `405` with `Allow: POST, OPTIONS`.
- More than `max_in_flight` requests at once: `503`, `Retry-After: 1` (a semaphore acquired without blocking).
- Rate limited: `429`, `Retry-After` as whole seconds rounded up. Client address: the last address in `X-Forwarded-For` when `trust_forwarded`, else the socket peer.
- `GET /mcp/server-card` and `GET /.well-known/ai-catalog.json`: the documents, with the media types, CORS, `Cache-Control`, `ETag` (a hash of the body), and `304` for a matching `If-None-Match`, as the Global Constraints say. Both count against the rate limit.
- Anything else: `404`. No `Server` version header (`server_version = "stdmcp"`, `sys_version = ""`).
- One log line per request to stderr: client, method, JSON-RPC method and tool name if any, status, milliseconds.

`server_card(app)` gives `$schema`, `name`, `version`, `title`, `description`, `websiteUrl`, `repository` (`{"url": ..., "source": "github"}`) when set, and `remotes: [{"type": "streamable-http", "url": app.url, "supportedProtocolVersions": list(SUPPORTED_VERSIONS)}]`. `ai_catalog(app, identifier)` gives `{"specVersion": "1.0", "entries": [{"identifier": identifier, "type": "application/mcp-server-card+json", "url": app.url + "/server-card"}]}`.

- [ ] **Step 1: Write the failing tests.** Include Review Focus item 1: `test_curl_style_requests_are_served` (no `Origin`, `Accept: */*`) and `test_no_accept_header_is_served`. Discovery tests check the card against the rules in the pinned `schema.json` that matter here (the `$schema` pattern, the `name` pattern `^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$`, required `name`, `version`, `description`, a remote `url` pattern) and that each `invalid/` fixture breaks one of those rules.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** `stdmcp/http.py` on `http.server.ThreadingHTTPServer` with `daemon_threads = True`, and `stdmcp/discovery.py`.
- [ ] **Step 4: Run them to see them pass.** `nice -n 19 python3 -m unittest discover -s stdmcp/tests -t . -v`
- [ ] **Step 5: Commit.** `git commit -m "stdmcp: HTTP transport, limits, server card and AI Catalog"`

### Task 7: `stdmcp` README

**Files:**
- Create: `stdmcp/README.md`

- [ ] **Step 1: Write it**: what it is (a standard-library MCP server for read-only tools over Streamable HTTP, both the stateless revision and the handshake versions), what it deliberately leaves out (sessions, SSE, resources, prompts, subscriptions, auth), a twenty-line example defining one tool and calling `serve()`, the limits and their defaults, the pinned spec commits, and that it's meant to be lifted out of Floodwatch whole.
- [ ] **Step 2: Commit.** `git commit -m "stdmcp: README"`

### Task 8: Floodwatch's local API client

**Files:**
- Create: `floodwatch_mcp/__init__.py`, `floodwatch_mcp/site.py`
- Create: `tests/test_mcp_site.py`

**Interfaces:**
- Produces: `class Site(base: str = "http://127.0.0.1:8090", timeout: float = 5)` with `json(path: str) -> dict` (GETs `base + path`; raises `stdmcp.ToolError("Floodwatch is briefly unavailable; try again in a minute.")` on connection errors, timeouts and 5xx; returns the parsed body for 2xx; for 404 raises `NotFound(message)` carrying the API's `error` text).

- [ ] **Step 1: Write the failing tests** against a tiny `http.server` fixture on port 0: `test_reads_json`, `test_404_carries_the_api_message`, `test_down_is_a_tool_error` (closed port), `test_slow_is_a_tool_error` (fixture sleeps past a 0.2 s timeout) — Review Focus item 3.
- [ ] **Step 2–4: Fail, implement with `urllib.request`, pass.**
- [ ] **Step 5: Commit.** `git commit -m "Floodwatch MCP: local API client"`

### Task 9: The nine tools

**Files:**
- Create: `floodwatch_mcp/tools.py`, `floodwatch_mcp/text.py` (instructions and attribution strings)
- Create: `tests/test_mcp_tools.py`, `tests/fixtures/mcp/` (copies of `live.json`, `warnings.json`, `weather.json`, `drought.json`, `powercuts.json`, `overflows.json`, one readings, one rain forecast, one flow forecast and one overflow detail response, trimmed)

**Interfaces:**
- Consumes: `Site` (Task 8); `Tool`, `ToolError` (Task 3).
- Produces: `TOOLS: tuple[Tool, ...]` in this order: `list_stations`, `conditions`, `flood_warnings`, `station_history`, `rain_forecast`, `flow_forecast`, `storm_overflows`, `drought`, `power_cuts`; `INSTRUCTIONS: str`; `make_tools(site: Site) -> tuple[Tool, ...]` (so tests inject a fixture-backed `Site`).

Arguments, exactly:

| Tool | Schema |
|---|---|
| `conditions` | `station_id` string, pattern `[A-Za-z0-9_-]{1,24}`, optional; `kind` enum `level`, `tidal`, `rain`, optional |
| `station_history` | `station_id` required, same pattern; `days` integer 1–30, default 7 |
| `rain_forecast`, `flow_forecast` | `station_id` required |
| `storm_overflows` | `state` enum `spilling`, `recent`, `quiet`, optional; `overflow_id` same pattern, optional |
| the rest | no arguments (`{"type": "object", "properties": {}, "additionalProperties": false}`) |

Result conventions (spec, Tools section): times as ISO 8601 with the `Europe/London` offset (`zoneinfo`); units in field names (`level_m`, `rain_mm`, `flow_m3s`); every result has `generated` (ISO) and `attribution` (from `text.py`, per source). `station_history` passes `days` to the API and, beyond 7 days, keeps the last reading in each hour. `conditions` adds `counts`: `high`, `approach`, `rising`, `stale`.

Errors (Review Focus item 2): an unknown station ID is a `ToolError` "No gauge with ID x. list_stations gives the IDs."; a level gauge passed to `rain_forecast` is "x is a river level gauge; rain_forecast needs a rain gauge. list_stations shows each gauge's kind."; a gauge without a flow forecast names the gauges that have one.

`INSTRUCTIONS` covers, in plain sentences: Floodwatch watches the River Taw catchment in North Devon; it is not an official warning service and the Environment Agency's warnings, which `flood_warnings` relays, are the authority; units and the UK time zone; readings arrive every 15 minutes or so and `stale` means a gauge stopped reporting; `approach` means within 30% of the top of the typical range; cite the `attribution` given. No station, river or overflow names.

- [ ] **Step 1: Write the failing tests**: one per tool for its normal answer against the fixtures; the three error messages above; `test_tool_order_is_fixed`; `test_every_result_has_generated_and_attribution`; `test_thirty_days_fits_the_result_limit` (a fixture of 30 days at 15 minutes thins under 100,000 characters); `test_instructions_name_no_third_party_strings` (no station name from the fixture `live.json` appears in `INSTRUCTIONS`).
- [ ] **Step 2: Run them to see them fail.** `nice -n 19 python3 -m unittest tests.test_mcp_tools -v`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them to see them pass.**
- [ ] **Step 5: Commit.** `git commit -m "Floodwatch MCP: the nine tools"`

### Task 10: Entry point, service and Caddy

**Files:**
- Create: `floodwatch_mcp/__main__.py`, `deploy/floodwatch-mcp.service`
- Modify: `deploy/Caddyfile`, `Makefile` (`mcp` target, help line), `tests/test_mcp_tools.py` (an end-to-end test)

**Interfaces:**
- Consumes: everything above. `serve.git_version()` for the version, with a leading `v` stripped (`v2.0.0-12-gd904ef7c` becomes `2.0.0-12-gd904ef7c`).
- Produces: `python3 -m floodwatch_mcp [--port 8091] [--site http://127.0.0.1:8090] [--url https://tawriver.watch/mcp]`, binding `127.0.0.1` only. `App(name="watch.tawriver/floodwatch", title="Floodwatch", description=..., website_url="https://tawriver.watch", repository_url="https://github.com/aallan/floodwatch", ...)`, `catalog_identifier="urn:air:tawriver.watch:mcp:floodwatch"`. `make mcp` runs it with `--url http://localhost:8091/mcp` for local testing.

`deploy/floodwatch-mcp.service`: as `floodwatch.service`, but `ExecStart=/usr/bin/python3 -m floodwatch_mcp --port 8091`, `After=` and `Wants=floodwatch.service`, no `ReadWritePaths`, plus `IPAddressDeny=any`, `IPAddressAllow=localhost`, `MemoryMax=96M`, `CPUQuota=30%`, `TasksMax=32`, `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`, `PrivateNetwork=no`.

`deploy/Caddyfile`, inside `tawriver.watch { }`, before the existing `reverse_proxy`:

```
@agents path /mcp /mcp/* /.well-known/ai-catalog.json
handle @agents {
	request_body {
		max_size 64KB
	}
	reverse_proxy 127.0.0.1:8091 {
		header_down -Server
	}
}
```

and wrap the existing `reverse_proxy` in `handle { }`.

- [ ] **Step 1: Write the failing end-to-end test**: start `serve.py`'s `Server` on port 0 with the test database (as `tests/test_serve.py`), start the MCP server on port 0 pointed at it, and run a legacy session (`initialize`, `tools/list`, `tools/call conditions`) and a modern one (`server/discover`, `tools/call list_stations` with the three headers and `_meta`).
- [ ] **Step 2: Run it to see it fail.**
- [ ] **Step 3: Implement** `__main__.py`, the unit, the Caddyfile and the Makefile target. Validate the Caddyfile with `caddy validate --config deploy/Caddyfile --adapter caddyfile` if Caddy is installed on the Mac; otherwise note it for the deploy.
- [ ] **Step 4: Run all tests.** `nice -n 19 make test`: all pass.
- [ ] **Step 5: Live check on the Mac.** `make serve` and `make mcp` in two terminals, then `claude mcp add --transport http floodwatch-local http://localhost:8091/mcp` and ask Claude Code "what are the Taw's gauges saying?"; it calls the tools and answers. Remove it afterwards with `claude mcp remove floodwatch-local`.
- [ ] **Step 6: Commit.** `git commit -m "Floodwatch MCP: entry point, systemd unit and Caddy routes"`

### Task 11: Discovery files and the Agents tab

**Files:**
- Create: `site/llms.txt`, `site/robots.txt`
- Modify: `site/index.html` (nav link between Map and About; `<section id="view-agents" class="view">`; `<link rel="alternate" type="text/markdown" href="/llms.txt">`; version bumps), `site/js/app.js` (`VIEWS = ['map', 'agents', 'about']`, comment, copy button), `site/css/style.css` (only what the existing About classes don't cover)
- Create: `tests/js/agents.test.mjs` or add to `tests/test_serve.py`

**Interfaces:**
- Consumes: `TOOLS` (Task 9) for the drift test.

The Agents view, in the About view's style (spec, The Agents tab): a paragraph saying Floodwatch has an MCP server for AI assistants, read-only, free, no sign-in; the endpoint `https://tawriver.watch/mcp` in a `<code>` with a Copy button (`navigator.clipboard.writeText`, button text "Copied" for two seconds); how to connect in Claude (custom connector; check the current menu wording at claude.ai before writing it), Claude Code (`claude mcp add --transport http floodwatch https://tawriver.watch/mcp`), and other clients (a JSON snippet with `"type": "http"` and the URL); a table of the nine tools with one line each; fair use (the limits, not an official warning service, the licences, linking `#/about`); links to `/mcp/server-card`, `/.well-known/ai-catalog.json` and `/llms.txt`.

`site/llms.txt` follows llmstxt.org: an `# Floodwatch` heading, a one-paragraph summary, then `## MCP server` (URL, how to connect, the tools), `## Data` (the JSON files in `/data/` and the `/api/` routes, one line each), `## Licences` (from About's sources table). `site/robots.txt`: `User-agent: *` and `Allow: /`.

- [ ] **Step 1: Write the failing tests**: in `tests/test_serve.py`, `test_llms_txt_and_robots_are_served` (200, `text/plain`), `test_agents_tab_lists_every_tool` (every name in `floodwatch_mcp.tools.TOOLS` appears in `index.html`'s `#view-agents`, and no other `snake_case` tool-looking name does), `test_head_links_llms_txt`; in `tests/js`, `#/agents` routes to `view-agents`.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run all tests, then check in the browser** at desktop and phone widths, light and dark: the tab sits between Map and About, the copy button works, the map still starts when going back to Map.
- [ ] **Step 5: Commit.** `git commit -m "Agents tab, llms.txt and robots.txt"`

### Task 12: Documentation, PR, deploy

**Files:**
- Modify: `README.md` (an "MCP server" section: what it is, the tools, connecting, how it's deployed and sandboxed; the test count), `CHANGELOG.md` (Unreleased, Added), `site/index.html` About text (one sentence pointing to the Agents tab)

- [ ] **Step 1: Write the docs.** Run the writing-voice audit on the README section: `python3 <writing-voice>/scripts/voice_audit.py --register report README.md`.
- [ ] **Step 2: Full test run.** `nice -n 19 make test`: all pass.
- [ ] **Step 3: Commit, push, open PR B, wait for CI.** Ask the user before merging.
- [ ] **Step 4: After the user merges, give the deploy commands**, and only then:

```bash
ssh tawriver.watch 'cd /srv/floodwatch && runuser -u floodwatch -- git pull -q && cp deploy/floodwatch-mcp.service /etc/systemd/system/ && cp deploy/Caddyfile /etc/caddy/Caddyfile && systemctl daemon-reload && systemctl enable --now floodwatch-mcp && systemctl reload caddy'
```

- [ ] **Step 5: Verify live**: `curl -s https://tawriver.watch/mcp/server-card`, `curl -s https://tawriver.watch/.well-known/ai-catalog.json`, a `server/discover` POST, `systemctl show floodwatch-mcp -p IPAddressDeny,MemoryMax`, and that the map still loads.
- [ ] **Step 6: Hand the user the two connector tests**: add `https://tawriver.watch/mcp` as a custom connector at claude.ai and ask about the Taw; then the same from the Claude iPhone app. Record the results in the PR, with the separate picture question (does an image in a remote tool result show on the phone?) left open for the next version.
