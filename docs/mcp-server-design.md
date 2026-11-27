# The MCP server's design

Floodwatch's MCP server went live with version 2.1.0, on 27 November 2026. This is the record of how it is built and why: what it had to do, what it must never do, the approaches weighed, and the choices behind its protocol handling, tools, limits, and discovery. The README says how to use it; this says how it came to be the way it is.

## What it is for

tawriver.watch shows Floodwatch's data to people as a map. The MCP server is a second front door, for AI assistants. It serves the same data to any MCP client. A person can ask their own assistant "is the Taw up at Umberleigh?" or "is anything spilling into the Mole?" and get Floodwatch's answer. The data is the same; only the reader differs.

It had to be:

- public and read-only, at `https://tawriver.watch/mcp`, open to anyone, with no sign-in;
- complete, with tools for everything the site shows: the gauges and their latest readings, flood and weather warnings, a gauge's history, rain and flow forecasts, storm overflows, drought, and power cuts;
- discoverable by the MCP standard's server card and AI Catalog and by the `llms.txt` convention;
- explained to people, on an Agents tab between Map and About;
- built on a standard-library MCP package that imports nothing from Floodwatch. Another project can copy it whole.

Left out of this version: pictures such as charts and map snapshots, which wait until it is clear whether a remote connector's images reach Claude's phone app and until there is a way to draw them on Linux without a heavy dependency; MCP resources, prompts, subscriptions, tasks, sampling, elicitation, server-sent event streams, and sessions; authentication of any kind; and publishing to the MCP Registry.

## What it must never do

It would fail, even while working, if:

- a stranger could make it fetch anything from a third party (Open-Meteo, the Environment Agency, anyone);
- agent traffic could slow or stop the website;
- an agent could reasonably take it for an official flood warning service;
- it returned data the site does not show, or showed it differently.

## Constraints

- Standard library only, as the rest of Floodwatch. The server runs Python 3.12; `pyproject.toml` asks for 3.10 or later.
- The droplet has one CPU and about 1 GB of memory, shared with the web server, the poller, and Caddy.
- Caddy terminates HTTPS. Core Caddy has no rate limiting without a custom build. Rate limiting lives in the MCP process.
- The forecast cache (`monitor/cache.py`) is in the web server's memory. Another process can share it only by asking the web server.

## Approaches weighed

1. **Standard library, as a separate service (chosen).** A small transport package and a Floodwatch tool package, run as their own systemd service behind Caddy, reading the website's own API on `127.0.0.1:8090`. No dependencies, and small enough to read line by line; the cost is following MCP's revisions ourselves.
2. **The official Python SDK (FastMCP), as a separate service.** The protocol would be handled and kept current for us. Rejected because it brings a large dependency tree of pydantic, starlette, uvicorn, and more onto a public server for the first time, with a virtual environment and a stream of dependency updates, for a server that needs a fraction of it.
3. **Built into `serve.py`.** The simplest to deploy. Rejected because agent traffic would share the website's threads.

Publishing the transport as its own repository straight away was weighed and postponed. Standard-library MCP servers already exist, such as zeromcp and py-http-mcp-server, and this one is narrower than they are. A library's real cost is following the specification for other people, so the package stays inside Floodwatch for now. A test keeps it free of Floodwatch imports, which makes the later move cheap.

## How it fits together

Everything runs on the droplet. `127.0.0.1` is the droplet's own loopback address. The website listens only there. Caddy forwards public HTTPS to it. The MCP service does the same on port 8091.

```
agent ──HTTPS──▶ Caddy ──┬─ /mcp, /mcp/server-card,
                         │  /.well-known/ai-catalog.json ──▶ floodwatch-mcp (127.0.0.1:8091)
                         │                                         │
                         │                                         └─HTTP─▶ the site's JSON and API
                         └─ everything else ──────────────────────▶ serve.py (127.0.0.1:8090)
```

The MCP service never opens the database. It reaches nothing on the network but the website. Every answer comes from the website's own JSON: the files in `site/data/` and the `/api/` routes. That makes it the site's data by construction. The forecasts come out of the web server's existing cache. Calls to third parties stay bounded however busy agents get because the cache is keyed by Floodwatch's own gauge IDs.

The code is in two packages:

- `stdmcp/`, the reusable part, with its own tests and [README](../stdmcp/README.md): `tools.py` holds the tool registry and argument checks against the small part of JSON Schema the tools use; `protocol.py` does JSON-RPC dispatch and version negotiation; `ratelimit.py` keeps token buckets by client address; `http.py` is the HTTP server, with its limits and Origin and CORS handling; and `discovery.py` builds the server card and AI Catalog from the server's own name, version, and address. They cannot disagree with what the server says about itself.
- `floodwatch_mcp/`, Floodwatch's side: `site.py` reads the website's JSON; `tools.py` holds the nine tools, each an ordinary function; `text.py` holds the instructions and attributions; and `__main__.py` starts the service.

## The site works out its own states

Some of what the map showed was worked out in the browser. An agent reading the server's JSON would have seen something different. Before the MCP server, that work moved into the server in its own pull request. The map and agents now read the same values:

- **Amber gauges.** A river level is `approach` when it is at or above 70% of the top of its typical range and is not already high or stale. `monitor/live.py` writes that state into `live.json`. The map reads it as given.
- **Stale trends.** The map hid a stale gauge's trend arrow. `live.py` now writes no trend for a stale gauge.
- **The flow forecast.** The chart used to scale the model's forecast to the measured flow itself. `monitor/forecast.py` now does the scaling. The API returns the scaled days beside the model's own days. The chart still draws those faintly.

The JavaScript tests for both moved to Python with the same cases. The behaviour was pinned before and after.

## Protocol

MCP changed in July 2026: revision `2026-07-28` dropped the opening handshake and made every request stand alone. Clients in use still speak the handshake versions. The server speaks both and keeps no state between requests in either.

| Version | How it is handled |
|---|---|
| `2026-07-28` | Every request carries its protocol version in `_meta`. `server/discover` is answered. The `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` headers are checked against the body, and a mismatch gets `400` with `HeaderMismatch` (-32020). An unknown version gets `UnsupportedProtocolVersion` (-32022), listing those supported. Every result carries `resultType: "complete"`, and `server/discover` and `tools/list` carry `ttlMs` and `cacheScope: "public"`. |
| `2025-11-25`, `2025-06-18`, `2025-03-26` | `initialize` is answered with the agreed version, the tools capability, the server's name and version, and its instructions, and `notifications/initialized` gets `202`. No `Mcp-Session-Id` is ever issued (sessions are optional in these versions). A request without `MCP-Protocol-Version` is treated as `2025-03-26`, as the specification allows. |

For both:

- The methods are `tools/list` and `tools/call`, with `server/discover` under the new revision and `initialize` and `ping` under the older revisions. Anything else is `-32601`, with HTTP `404` under the new rules.
- Requests are POSTs of `application/json`, one JSON-RPC message each; the older revisions' batches are refused. Answers are always plain JSON, never an event stream. The specification leaves that choice to the server. `GET` and `DELETE` on `/mcp` get `405`.
- `tools/list` always gives the tools in the same order.
- Bad JSON, an unknown method, an unknown tool, and malformed parameters are JSON-RPC errors. Arguments that fail their tool's schema come back as tool results with `isError: true` and a sentence an agent can act on, as the specification's error handling section and SEP-1303 direct. So do failures inside a tool, such as an unknown gauge, a gauge with no forecast, or the website briefly unavailable.

Each test names the specification rule it checks. The next revision can be compared against the tests rather than reread from scratch.

### The specifications followed

These were read for the design, at the commits named. Where the published text and the design disagreed, the published text won and the design was corrected.

- The MCP specification, revisions `2026-07-28` and `2025-11-25`, in [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) at `024d5255eb44`: chiefly the Streamable HTTP transport, versioning, `server/discover`, tools, the changelog, and the schema.
- Server cards and discovery: SEP-2127 (final) in the same repository and [modelcontextprotocol/ext-server-card](https://github.com/modelcontextprotocol/ext-server-card) at `28db12c9b4a3`. The discovery tests run against its valid and invalid example cards.
- The [AI Catalog](https://github.com/Agent-Card/ai-catalog), at `08692c41e676`. It is not an MCP document, and it may change. Following a change costs little because the AI Catalog is one small file.

## Tools

All nine only read and say so (`readOnlyHint: true`, `openWorldHint: false`). Each returns its data as `structuredContent` and as the same JSON in a text block, for clients that only read text. Times are ISO 8601 with the UK offset. Units are in field names (`level_m`, `rain_mm`, `flow_m3s`). Every result says when Floodwatch last refreshed the data (`generated`) and carries an attribution for its sources and licences.

| Tool | Arguments | Answers | From |
|---|---|---|---|
| `list_stations` | none | Every gauge: ID, name, kind (river level, tidal, or rain), river, location, unit, typical range, and whether it has a flow forecast | `live.json` and the API |
| `conditions` | optional `station_id` and `kind` | The latest reading at each gauge: value, time, trend, and state as the map shows it, judged again when asked, so a gauge goes stale even if the poller has stopped; counts of those high, near the top, rising, and stale; the newest reading's time (`latest_reading`); and whether it is over an hour old (`delayed`) | `live.json` |
| `flood_warnings` | none | Environment Agency flood warnings and alerts in force, and Met Office weather warnings for the area that have not ended, with only Met Office links, as the site shows them | `warnings.json`, `weather.json` |
| `station_history` | `station_id`; `days`, 1 to 30, default 7 | Readings over that period, with the typical range and record high; beyond 7 days, one an hour: the hour's highest level, or its total rain | the readings API |
| `rain_forecast` | `station_id`, a rain gauge | Rain over the next 48 hours | the rain forecast API |
| `flow_forecast` | `station_id`, a gauge with a forecast | River flow for the days ahead, scaled to the measured flow as the chart shows it, with normal and high flow for comparison | the flow forecast API |
| `storm_overflows` | optional `state` (`spilling`, `recent`, `quiet`, or `offline`) and `overflow_id` | Overflows and their state, or one overflow's detail and spill history | `overflows.json` and the overflows API |
| `drought` | none | The latest Environment Agency drought report and stage for the area | `drought.json` |
| `power_cuts` | none | Live power cuts in the area | `powercuts.json` |

The tools are narrow because a model chooses between narrow tools more reliably than between broad tools. An agent needs gauge IDs from `list_stations` before it can ask for a history.

The server's instructions, sent with `server/discover` and `initialize`, say what Floodwatch covers; that it is not an official warning service and that the Environment Agency's warnings are the authority; the units and time zone; what each state means; to compare `generated` and `latest_reading` with the time; and the attribution each source is owed. Gauge, river, and overflow names come from third parties. They appear only as data, never in the instructions.

## Safety and limits

The limits are in `stdmcp`, with Floodwatch's values:

- **The sandbox.** The service runs as its own systemd unit, `floodwatch-mcp.service`, on `127.0.0.1:8091`, as an unprivileged user, with the web server's hardening and more: no writable paths at all; `IPAddressDeny=any` with `IPAddressAllow=localhost`, so it can reach nothing off the machine even if subverted; and `MemoryMax=96M`, `CPUQuota=30%`, and `TasksMax=32`.
- **Bounded work.** Every connection runs in its own thread, so at most 24 are open at once; a connection beyond that is closed before a thread starts, and slow clients cannot use up the task limit. Caddy reads each request's whole body before passing it to the service, so a slow upload holds no thread. At most 8 requests are worked on at once; beyond that the answer is `503` with `Retry-After`. Calls to the website time out after 5 seconds.
- **Rate limits.** The main protection is the overall limit of 600 requests a minute, with the cap on requests in progress. The limit for each client address, 300 a minute in bursts of 60, is loose because many people share one address: hosted clients, including a claude.ai connector, call from their provider's servers. The limit only stops one runaway caller taking the whole budget. Either limit answers `429` with `Retry-After`. The client's address is the one Caddy puts in `X-Forwarded-For`, trusted only from a loopback peer and only when it is a valid address; `stdmcp` trusts the header only when its `trust_forwarded` setting is on, and Floodwatch turns it on.
- **Input limits.** Request bodies are at most 64 KiB, in Caddy and in the service. Arguments are checked against each tool's schema, unknown arguments are refused, and gauge and overflow IDs must match the site's own pattern (`[A-Za-z0-9_-]{1,24}`) before any address is built from them.
- **Output limits.** A result over 100,000 characters is an error; `station_history` thins to hourly readings beyond 7 days, so 30 days fits.
- **Origin.** The specification asks servers to check `Origin`, against a browser attack on servers on a private network. This server is public, read-only, and holds nothing a web page could not fetch already. Floodwatch accepts any `https` origin and requests with none. It refuses anything else (`null` included) with `403`. CORS allows any origin, with no credentials. `stdmcp` takes the policy as a setting.
- **Logging.** One line a request goes to the journal: time, client address, method, tool, status, and duration. Request bodies are never logged.

## Discovery

| Address | Served by | What it holds |
|---|---|---|
| `/mcp/server-card` | the MCP service | The server card: its name (`watch.tawriver/floodwatch`), title, description, version, website, repository, and endpoint with the protocol versions it speaks, as `application/mcp-server-card+json`, with CORS, an hour's caching, and an `ETag` |
| `/.well-known/ai-catalog.json` | the MCP service | One entry, `urn:air:tawriver.watch:mcp:floodwatch`, pointing at the server card, as `application/ai-catalog+json`, with the same CORS and caching |
| `/llms.txt` | the website | What Floodwatch is, its data and licences, the MCP endpoint and how to connect, and the JSON files and API routes for agents that read the web instead |
| `/robots.txt` | the website | Allows everything |

The page's `<head>` also links to `llms.txt`. Left out: HTTP `Link` headers, considered and rejected by the server card's authors; `/.well-known/ai-plugin.json`, OpenAI's retired format; and unregistered `rel` values.

## The Agents tab

The site's third tab, `#/agents`, between Map and About, tells people the same things: what the server is, its address with a copy button, how to connect from Claude, Claude Code, and other clients, the nine tools, fair use and the limits, that it is not an official warning service, and links to the server card, the AI Catalog, and `llms.txt`. The connection steps note that Dispatch needs its tools set to Always allow. A test keeps the tab and `llms.txt` listing exactly the server's tools.

## How it was tested

- `stdmcp`'s tests are named for the specification rule each checks: both protocol revisions, version negotiation, header mismatches, notifications, refused methods, the Origin policy, the body, connection, and request limits, the rate limiter, CORS, and the discovery documents. The discovery documents are also checked against the server card examples.
- The tool tests run against a fake copy of the website's JSON, including unknown IDs, a website that is down or stopped mid-answer, data gone stale, and the size limit.
- An end-to-end test runs the website and the MCP server together, through both protocol revisions.
- Live, after the first deploy: claude.ai and the Claude phone app connected as a custom connector and answered questions from it. Dispatch saw the connector only once its tools were set to Always allow, which is why the Agents tab says so.
