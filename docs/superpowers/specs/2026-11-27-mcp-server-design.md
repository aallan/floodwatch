# Floodwatch MCP server: design

Status: approved, 27 November 2026.

## Intent

tawriver.watch serves Floodwatch's data to people as a map. This adds a second
front door, for agents: a public MCP server that serves the same data to any
MCP client, so a person can ask their own assistant "is the Taw up at
Umberleigh?" or "is anything spilling into the Mole?" and get Floodwatch's
answer. Same data, different consumers.

The MCP code is to be kept as separate from Floodwatch as is sensible, so it
can be lifted into its own repository later and reused (cornwall-watch is the
likely second user).

## Goals

- A public, read-only MCP endpoint at `https://tawriver.watch/mcp`, open to
  anyone, with no sign-in.
- Tools covering what the site shows: gauges and their latest readings, flood
  and weather warnings, a gauge's history, rain and flow forecasts, storm
  overflows, drought and power cuts.
- Discoverable by the MCP standard (a server card and an AI Catalog) and by the
  `llms.txt` convention.
- An **Agents** tab on the site, between Map and About, telling people how to
  point their agent at it and what it offers.
- A reusable, standard-library MCP transport module with no Floodwatch imports.

## Non-goals (for this version)

- Pictures (charts, map snapshots). They wait until a test shows whether a
  remote connector's tool-result images reach the Claude iPhone app, and until
  there's a way to rasterise on Linux without a heavy dependency.
- MCP resources, prompts, subscriptions (`subscriptions/listen`), tasks,
  sampling, elicitation, SSE responses, sessions.
- Authentication of any kind.
- Publishing to the MCP Registry, or splitting the module into its own
  repository. Both are possible later.

## Anti-goals

It fails, even if it works, if:

- a stranger can make it fetch anything from a third party (Open-Meteo, the
  Environment Agency, anyone);
- agent traffic can slow or stop the website;
- an agent could reasonably take it for an official flood warning service;
- it returns data the site doesn't show, or shows differently.

## Constraints

- Standard library only, as the rest of Floodwatch. Python 3.12 on the
  droplet (`requires-python >= 3.10` in `pyproject.toml`).
- The droplet has one CPU and about 1 GB of memory, shared with the web server,
  the poller and Caddy.
- Caddy v2.11 terminates HTTPS. Core Caddy has no rate limiting without a
  custom build, so rate limiting lives in the MCP process.
- Floodwatch and monitoring-cornwall stay separate repositories and droplets.
- The site's forecast cache (`monitor/cache.py`) is in the web server's
  memory, so another process can't share it except through the web server.

## Approaches considered

1. **Standard library, separate service (chosen).** A small transport module
   and a Floodwatch tool module, run as their own systemd service behind
   Caddy, reading the website's own API on `127.0.0.1:8090`. No dependencies;
   small enough to read line by line; we track MCP revisions ourselves.
2. **The official Python SDK (FastMCP), separate service.** The protocol
   handled and kept current for us, and the same code as the estate's local
   MCP servers. Rejected: it brings a large dependency tree (pydantic,
   starlette, uvicorn and more) onto a public server for the first time, with a
   virtualenv and Dependabot churn, for a server that needs a fraction of it.
3. **Built into `serve.py`.** Simplest to deploy. Rejected: agent traffic would
   share the website's threads.

Separately, spinning the transport out as its own repository now was
considered and deferred: standard-library MCP servers already exist
(zeromcp, py-http-mcp-server), ours is deliberately narrower, and the cost of
a library is following the spec for other people. Keeping the module free of
Floodwatch imports makes the later move cheap.

## Architecture

```
agent ──HTTPS──▶ Caddy ──┬─ /mcp, /mcp/server-card,
                         │  /.well-known/ai-catalog.json ──▶ floodwatch-mcp (127.0.0.1:8091)
                         │                                         │
                         │                                         └─HTTP─▶ serve.py API and data files
                         └─ everything else ──────────────────────▶ serve.py (127.0.0.1:8090)
```

Everything here runs on the droplet. `127.0.0.1` is the droplet's own
loopback address: the website already listens only there, with Caddy
forwarding public HTTPS to it, and the MCP service does the same on port 8091.

The MCP service never opens the database or the network beyond the website on
`127.0.0.1:8090`. Every answer comes from the website's own JSON (the files in
`site/data/` and the `/api/` routes), so it is the site's data by
construction, and the forecasts come out of the web server's existing cache.
Upstream calls stay bounded however busy agents get, because the cache keys are
Floodwatch's own gauge IDs.

### Code layout

Working names; the builder may rename.

- `stdmcp/` — the reusable package. No imports from `monitor`, `serve` or
  anything Floodwatch.
  - `server.py` — HTTP handler and JSON-RPC dispatch, version negotiation,
    header checks, limits, CORS, error mapping.
  - `tools.py` — a tool registry: name, title, description, input schema,
    annotations, handler. Validates arguments against the small JSON Schema
    subset the tools use (types, required, enum, minimum, maximum, pattern).
  - `ratelimit.py` — token buckets keyed by client address.
  - `discovery.py` — builds the server card and the AI Catalog from the
    server's own name, version, description and URL, so they can't drift from
    what `server/discover` says.
  - Its own tests, in a folder it can take with it.
- `floodwatch_mcp.py` (or `agents/`) — the Floodwatch side: the instructions
  text, the tool functions, each an ordinary function that fetches from the
  local API and reshapes it, and `main()`.

## First step: the website works out its states on the server

Some of what the map shows is worked out in the browser, not in the data the
MCP server reads. Before the MCP work, that logic moves into the server's JSON,
so the map and the agents read the same values (decided after the builder
check):

- **Amber gauges.** `gaugeState` in `site/js/map.js` turns a river level at or
  above 70% of the top of its typical range (`APPROACH = 0.7`) amber, as
  `approach`, unless it's already `high` or `stale`. `monitor/live.py` takes
  over that rule and writes `approach` as the gauge's `state` in `live.json`;
  `gaugeState` then reads the state as given (its rain branch, `raining` and
  `dry`, is already the server's).
- **Stale trends.** The map hides a stale gauge's trend arrow. `live.py` stops
  writing a `trend` for a stale gauge.
- **The flow forecast.** `/api/forecast/flow/<id>` returns the model's days and
  an `anchor.ratio`; `scaleForecast` in `site/js/stations.js` applies the ratio
  (the falling flow scaled, any rise from rain added at the model's size). The
  scaling moves into `monitor/forecast.py`, and the API returns the scaled days
  alongside the model's own, which the chart still draws faintly. The chart's
  caption text stays in the browser.

The existing JavaScript tests for `gaugeState` and the forecast scaling move to
Python tests of the same cases, so the behaviour is pinned before and after.
This is a website change of its own, with its own pull request, released before
the MCP server.

## Protocol

The server supports both eras of MCP, because current clients still speak the
handshake versions:

| Version | How |
|---|---|
| `2026-07-28` (modern) | Stateless. Every request carries `_meta` with `io.modelcontextprotocol/protocolVersion`; `server/discover` implemented (it's a MUST); `MCP-Protocol-Version`, `Mcp-Method` and `Mcp-Name` headers checked against the body, `400` with `HeaderMismatch` (-32020) on disagreement; `UnsupportedProtocolVersion` (-32022) listing supported versions; `resultType: "complete"` on every result; `ttlMs` and `cacheScope: "public"` on `server/discover` and `tools/list`. |
| `2025-11-25`, `2025-06-18`, `2025-03-26` (legacy) | `initialize` answered with the negotiated version, capabilities `{tools: {}}`, server info and instructions; `notifications/initialized` gets `202`. No `Mcp-Session-Id` is ever issued (sessions are optional in these versions), so the server stays stateless. A request without `MCP-Protocol-Version` is treated as `2025-03-26`, as the spec allows. |

Common to both:

- Methods: `tools/list` and `tools/call`; plus `server/discover` (modern) or
  `initialize` and `ping` (legacy). Anything else is `-32601`, with HTTP `404`
  under the modern rules.
- POST only, `Content-Type: application/json`, one JSON-RPC message per body
  (legacy batches rejected). Responses are always `application/json`, never
  SSE; the spec lets the server choose. `GET` and `DELETE` on `/mcp` get `405`.
- `tools/list` in a fixed order.
- Tool errors (bad station ID, no forecast for that gauge, site unavailable)
  come back as tool results with `isError: true` and a sentence an agent can
  act on; protocol errors (bad JSON, unknown method, bad arguments) as JSON-RPC
  errors.

Note that the spec moved under us in July (the stateless revision). The test
suite should pin each rule above to the spec section it comes from, so the next
revision is a diff against tests rather than a reread.

### Authoritative documents

Build against these, pinned to the commits read for this design. Where they
and this design disagree, the published text wins and the design is corrected.

- MCP specification, revisions `2026-07-28` and `2025-11-25`:
  `docs/specification/` in
  [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol)
  at `024d5255eb44`, chiefly `basic/transports/streamable-http.mdx`,
  `basic/versioning.mdx`, `server/discover.mdx`, `server/tools.mdx`,
  `changelog.mdx` and `schema`.
- Server card and discovery: SEP-2127 (Final) in the same repository, and
  [modelcontextprotocol/ext-server-card](https://github.com/modelcontextprotocol/ext-server-card)
  at `28db12c9b4a3`: `schema.ts`, `schema.json`, `docs/discovery.md` and the
  valid and invalid examples, which the discovery tests should run against.
- AI Catalog: [Agent-Card/ai-catalog](https://github.com/Agent-Card/ai-catalog)
  at `08692c41e676`. This one is not an MCP document and its status should be
  checked at build time; the catalog is one small static file, so a change
  costs little.

## Tools

All read-only (`readOnlyHint: true`, `openWorldHint: false`). Each returns the
data as `structuredContent` and the same JSON as a text block, for clients that
only read text. Times are ISO 8601 with the UK offset; units are named in the
field (`level_m`, `rain_mm`, `flow_m3s`). Every result carries `generated`
(when Floodwatch last refreshed that data) and an `attribution` line for its
sources and licences.

| Tool | Arguments | Answers | Source |
|---|---|---|---|
| `list_stations` | none | Every gauge: ID, name, kind (river level, tidal, rain), river, location, unit, typical range, whether it has a flow forecast | `live.json`, `forecast.FLOW_OUTLETS` via the API |
| `conditions` | optional `station_id`, optional `kind` | Latest reading at each gauge: value, time, trend, state (as the map shows it, `approach` included), and whether it's stale; plus counts (how many high, near the top, rising, stale) | `live.json` |
| `flood_warnings` | none | Environment Agency flood warnings and alerts in force, and Met Office weather warnings for the area | `warnings.json`, `weather.json` |
| `station_history` | `station_id`, `days` (1 to 30, default 7) | Readings over that period, with the typical range and record high | `/api/stations/<id>/readings` |
| `rain_forecast` | `station_id` (a rain gauge) | Rain over the next 48 hours | `/api/forecast/rain/<id>` |
| `flow_forecast` | `station_id` (a gauge with a forecast) | River flow for the days ahead, scaled to the measured flow as the chart shows it, with normal and high flow for comparison | `/api/forecast/flow/<id>` |
| `storm_overflows` | optional `state` (`spilling`, `recent`, `quiet`), optional `overflow_id` | Overflows and their state, or one overflow's detail and spill history | `overflows.json`, `/api/overflows/<id>` |
| `drought` | none | The latest Environment Agency drought report and stage for the area | `drought.json` |
| `power_cuts` | none | Live power cuts in the area | `powercuts.json` |

This splits the earlier `background` tool into `list_stations`, `drought` and
`power_cuts` (my call): an agent needs station IDs before it can ask for
history, and one-job tools are easier for a model to choose between.

### Instructions

The server's `instructions` (returned by `server/discover` and `initialize`)
say: what Floodwatch is and covers (the Taw catchment in North Devon); that it
is not an official warning service and that the Environment Agency's flood
warnings, which it relays, are the authority; units and time zone; that
readings arrive every 15 minutes or so and `stale` means a gauge has stopped
reporting; and the attribution owed for each source. Station, river and
overflow names come from third parties and appear only as data fields, never in
the instructions.

## Safety and limits

All in the reusable module unless noted, with Floodwatch's values:

- **Sandbox (Floodwatch).** Its own systemd unit, `floodwatch-mcp.service`,
  bound to `127.0.0.1:8091`, running as an unprivileged user with the existing
  hardening plus: no writable paths at all; `IPAddressDeny=any` and
  `IPAddressAllow=localhost`, so it cannot reach the internet even if
  compromised; `MemoryMax=96M`; `CPUQuota=30%`; `TasksMax=32`.
- **Bounded work.** At most 8 requests in progress; beyond that `503` with
  `Retry-After`. Upstream (local API) calls time out at 5 seconds.
- **Rate limits.** The main protection is the overall limit, 600 requests a
  minute, and the cap on requests in progress. Per client address the limit is
  deliberately loose, 300 a minute with bursts of 60, because hosted clients
  (a claude.ai custom connector, and so the Claude phone app) call from their
  provider's servers, so many people share one address; it only stops a single
  runaway caller from taking the whole overall budget. Over either, `429` with
  `Retry-After`. The client address is the one Caddy puts in
  `X-Forwarded-For`, trusted only because the service listens on localhost
  alone. (My call, after the builder check.)
- **Input limits.** Body at most 64 KB (also enforced in Caddy with
  `request_body max_size`); arguments validated against each tool's schema;
  station and overflow IDs match the site's existing pattern
  (`[A-Za-z0-9_-]{1,24}`) before any URL is built; unknown arguments rejected.
- **Output limits.** A tool result over 100,000 characters is an error in
  tests; `station_history` thins to hourly readings beyond 7 days so 30 days
  stays under it.
- **Origin.** The spec requires checking `Origin` against DNS rebinding, which
  is a risk for servers on a private network. This one is public, read-only and
  holds nothing a website couldn't fetch already, so the Floodwatch
  configuration accepts any `https` origin, rejects anything else present
  (including `null`) with `403`, and accepts requests with no `Origin`. CORS
  allows any origin, with no credentials. (My call; the module takes an origin
  policy as a parameter.)
- **Logging.** One line per request to the journal: time, client address,
  method, tool, status, duration. No request bodies.

## Discovery

| URL | Served by | Content |
|---|---|---|
| `/mcp/server-card` | MCP service | Server card: `$schema` v1, `name` `watch.tawriver/floodwatch`, `title`, `description`, `version` (the git describe the site shows), `websiteUrl`, `repository`, `remotes: [{type: "streamable-http", url: "https://tawriver.watch/mcp", supportedProtocolVersions: [...]}]`. Media type `application/mcp-server-card+json`; CORS headers, `Cache-Control: public, max-age=3600`, `ETag` and `304` as the discovery document asks. |
| `/.well-known/ai-catalog.json` | MCP service | One entry, identifier `urn:air:tawriver.watch:mcp:floodwatch`, type `application/mcp-server-card+json`, `url` the card. Media type `application/ai-catalog+json`; same CORS and caching. Served by the MCP service so both documents come from one place. |
| `/llms.txt` | `serve.py` (static) | What Floodwatch is, the data and its licences, the MCP endpoint and how to connect, and the JSON files and API routes for agents that read the web instead. |
| `<link rel="alternate" type="text/markdown" href="/llms.txt">` | `index.html` | Points page-reading agents at `llms.txt`. |
| `/robots.txt` | `serve.py` (static) | Allows everything, names the sitemap if one is added. |

Left out, with reasons: HTTP `Link` headers (considered and rejected by the
server card's authors), `/.well-known/ai-plugin.json` (OpenAI's retired format),
and unregistered `rel` values.

## The Agents tab

A third route, `#/agents`, between Map and About in the header, built like the
About view (static HTML in `index.html`, styled with the existing classes).
It holds:

1. One paragraph: Floodwatch has an MCP server, so an AI assistant can read the
   same data as this map. Read-only, free, no sign-in.
2. The endpoint, `https://tawriver.watch/mcp`, with a copy button.
3. How to connect, short and specific: Claude (custom connector), Claude Code
   (`claude mcp add --transport http floodwatch https://tawriver.watch/mcp`),
   and a generic JSON snippet for other clients. The builder verifies each
   client's current wording and menu path at build time.
4. The tools, one line each, from the table above.
5. Fair use: the rate limits, that it's not an official warning service, and
   the data licences, linking to About's source table.
6. Links to the server card, the AI Catalog and `llms.txt`.

A test checks that the tool names on the tab match the registry, so the page
can't drift from the server.

## Deployment

- `deploy/floodwatch-mcp.service` with the hardening above.
- `deploy/Caddyfile`: `handle /mcp*` and `handle /.well-known/ai-catalog.json`
  to `127.0.0.1:8091`, with `request_body { max_size 64KB }`; everything else
  as now.
- `make mcp` runs the MCP service locally against `make serve`.
- README section, CHANGELOG entry, About text mentioning the Agents tab.

## Testing

- Transport tests in `stdmcp/`, each named for the spec rule it checks:
  modern and legacy flows, version negotiation and the unsupported-version
  error, header mismatches, notifications, `405` for GET and DELETE, Origin
  policy, body limit, rate limiter, concurrency cap, CORS.
- Tool tests against a fake local API (fixture JSON), including bad IDs, a
  site that's down, and the output size cap.
- Discovery tests: card and catalog fields, media types, ETag and `304`.
- Before deploying: a live check with Claude Code (`claude mcp add`) against
  `make serve` and `make mcp` on the Mac, and with the MCP Inspector if it
  speaks the modern version.
- After deploying: connect from claude.ai as a custom connector, then from the
  Claude iPhone app. Separately, the picture test that decides the next
  version: does an image in a remote tool result show on the phone?
- Tests on the Mac run at `nice -n 19`, following the machine-time agreement
  with the Vera session.

## Left to the builder

- Module and file names, and how the Floodwatch side is structured.
- Exact JSON shapes of each tool's result, within the conventions above.
- Whether tools declare an `outputSchema`.
- The Agents tab's wording and layout, in the site's existing style.
