"""Run Floodwatch's MCP server, on loopback only, behind Caddy.

    python3 -m floodwatch_mcp                     # http://127.0.0.1:8091/mcp
    python3 -m floodwatch_mcp --port 9001 --site http://127.0.0.1:9000 --url http://localhost:9001/mcp
"""

import argparse

import serve as website
from floodwatch_mcp.site import Site
from floodwatch_mcp.tools import INSTRUCTIONS, make_tools
from stdmcp import App, serve

HOST = "127.0.0.1"
CATALOG_IDENTIFIER = "urn:air:tawriver.watch:mcp:floodwatch"
DESCRIPTION = ("Floodwatch shows what the River Taw in north Devon is doing: river levels, rainfall, flood and weather "
               "warnings, storm overflows, drought and power cuts. This server is read-only.")


def version():
    """The version running, as the site shows it, without the tag's leading v."""
    return (website.git_version() or "unknown").removeprefix("v")


def make_app(site_url, url):
    return App(
        name="watch.tawriver/floodwatch",
        version=version(),
        title="Floodwatch",
        description=DESCRIPTION,
        instructions=INSTRUCTIONS,
        url=url,
        tools=make_tools(Site(site_url)),
        website_url="https://tawriver.watch",
        repository_url="https://github.com/aallan/floodwatch",
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Floodwatch's read-only MCP server.")
    ap.add_argument("--port", type=int, default=8091, help="port to listen on, on 127.0.0.1 (default: 8091)")
    ap.add_argument("--site", default="http://127.0.0.1:8090", help="the website to read from (default: %(default)s)")
    ap.add_argument("--url", default="https://tawriver.watch/mcp", help="the public URL of the endpoint (default: %(default)s)")
    args = ap.parse_args(argv)
    # Caddy, on loopback, is the only client, so its X-Forwarded-For names the real one.
    serve(make_app(args.site, args.url), HOST, args.port, catalog_identifier=CATALOG_IDENTIFIER, trust_forwarded=True)


if __name__ == "__main__":
    main()
