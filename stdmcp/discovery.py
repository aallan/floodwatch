"""The two discovery documents: an MCP Server Card and an AI Catalog that points at it.

Shapes follow modelcontextprotocol/ext-server-card at ``28db12c9b4a3``
(``schema.json`` and ``docs/discovery.md``).
"""

from stdmcp.protocol import SUPPORTED_VERSIONS, App

CARD_SCHEMA = "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json"
CARD_TYPE = "application/mcp-server-card+json"
CATALOG_TYPE = "application/ai-catalog+json"


def card_url(app: App) -> str:
    """Where the card is served: the reserved ``<streamable-http-url>/server-card``."""
    return app.url + "/server-card"


def server_card(app: App) -> dict:
    card = {"$schema": CARD_SCHEMA, "name": app.name, "version": app.version, "title": app.title, "description": app.description}
    if app.website_url:
        card["websiteUrl"] = app.website_url
    if app.repository_url:
        card["repository"] = {"url": app.repository_url, "source": "github"}
    card["remotes"] = [{"type": "streamable-http", "url": app.url, "supportedProtocolVersions": list(SUPPORTED_VERSIONS)}]
    return card


def ai_catalog(app: App, identifier: str) -> dict:
    return {"specVersion": "1.0", "entries": [{"identifier": identifier, "type": CARD_TYPE, "url": card_url(app)}]}
