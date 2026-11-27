"""The server card and AI Catalog, checked against the pinned ext-server-card schema rules.

The rules below are the parts of ``schema.json`` at modelcontextprotocol/ext-server-card
``28db12c9b4a3`` that a card from ``server_card`` can break. The fixtures are that
commit's examples: the valid ones must pass, and every invalid one must fail a rule.
"""

import json
import pathlib
import re
import unittest

from stdmcp import App, SUPPORTED_VERSIONS, ai_catalog, server_card

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

SCHEMA_URL = re.compile(r"^https://static\.modelcontextprotocol\.io/schemas/v1/server-card\.schema\.json$")
NAME = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
REMOTE_URL = re.compile(r"^(https?://[^\s]+|\{[a-zA-Z_][a-zA-Z0-9_]*\}[^\s]*)$")


def problems(card):
    """Every way ``card`` breaks the schema rules that matter here (an empty list if none)."""
    found = [f"missing {key}" for key in ("$schema", "name", "version", "description") if key not in card]
    if "$schema" in card and not (isinstance(card["$schema"], str) and SCHEMA_URL.match(card["$schema"])):
        found.append("$schema is not the v1 server card schema")
    name = card.get("name")
    if "name" in card and not (isinstance(name, str) and 3 <= len(name) <= 200 and NAME.match(name)):
        found.append("name does not match the pattern")
    for key, longest in (("version", 255), ("description", None), ("title", 100), ("websiteUrl", None)):
        if key in card and not isinstance(card[key], str):
            found.append(f"{key} is not a string")
        elif key in card and longest and len(card[key]) > longest:
            found.append(f"{key} is too long")
    if "title" in card and card["title"] == "":
        found.append("title is empty")
    repository = card.get("repository")
    if repository is not None and not (isinstance(repository, dict) and isinstance(repository.get("url"), str)
                                       and isinstance(repository.get("source"), str)):
        found.append("repository needs url and source")
    for remote in card.get("remotes", []):
        if remote.get("type") not in ("sse", "streamable-http"):
            found.append("remote type")
        if not (isinstance(remote.get("url"), str) and REMOTE_URL.match(remote["url"])):
            found.append("remote url")
        versions = remote.get("supportedProtocolVersions", [])
        if not (isinstance(versions, list) and all(isinstance(v, str) for v in versions)):
            found.append("remote supportedProtocolVersions")
        info = remote.get("extensionsInfo", {})
        if not (isinstance(info, dict) and all(isinstance(v, dict) for v in info.values())):
            found.append("remote extensionsInfo values must be objects")
    return found


APP = App(
    name="watch.tawriver/floodwatch", version="v2.4.0-12-gabc1234", title="Floodwatch",
    description="River levels, rain and flood warnings for the River Taff.", instructions="Ask about rivers.",
    url="https://tawriver.watch/mcp", tools=(), website_url="https://tawriver.watch",
    repository_url="https://github.com/example/floodwatch",
)


class Fixtures(unittest.TestCase):
    def test_source_is_pinned(self):
        self.assertIn("28db12c9b4a3", (FIXTURES / "SOURCE").read_text(encoding="utf-8"))

    def test_valid_examples_pass(self):
        for name in ("minimal.json", "templated-remote.json"):
            with self.subTest(name=name):
                self.assertEqual(problems(json.loads((FIXTURES / name).read_text(encoding="utf-8"))), [])

    def test_each_invalid_example_breaks_a_rule(self):
        files = sorted((FIXTURES / "invalid").glob("*.json"))
        self.assertEqual(len(files), 6)
        for path in files:
            with self.subTest(name=path.name):
                self.assertNotEqual(problems(json.loads(path.read_text(encoding="utf-8"))), [])


class ServerCard(unittest.TestCase):
    def test_card_passes_the_rules(self):
        self.assertEqual(problems(server_card(APP)), [])

    def test_card_contents(self):
        self.assertEqual(server_card(APP), {
            "$schema": "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json",
            "name": "watch.tawriver/floodwatch",
            "version": "v2.4.0-12-gabc1234",
            "title": "Floodwatch",
            "description": "River levels, rain and flood warnings for the River Taff.",
            "websiteUrl": "https://tawriver.watch",
            "repository": {"url": "https://github.com/example/floodwatch", "source": "github"},
            "remotes": [{
                "type": "streamable-http",
                "url": "https://tawriver.watch/mcp",
                "supportedProtocolVersions": list(SUPPORTED_VERSIONS),
            }],
        })

    def test_optional_fields_are_left_out_when_unset(self):
        app = App(name="org.example/bare", version="1", title="Bare", description="Bare.", instructions="",
                  url="https://example.org/mcp", tools=())
        card = server_card(app)
        self.assertNotIn("websiteUrl", card)
        self.assertNotIn("repository", card)
        self.assertEqual(problems(card), [])

    def test_card_agrees_with_runtime_server_info(self):
        # discovery.md, "Consistency with Runtime Behavior".
        card, info = server_card(APP), APP.server_info()
        for key in ("name", "version", "title", "description", "websiteUrl"):
            self.assertEqual(card[key], info[key])


class Catalog(unittest.TestCase):
    def test_catalog(self):
        self.assertEqual(ai_catalog(APP, "urn:air:tawriver.watch:mcp:floodwatch"), {
            "specVersion": "1.0",
            "entries": [{
                "identifier": "urn:air:tawriver.watch:mcp:floodwatch",
                "type": "application/mcp-server-card+json",
                "url": "https://tawriver.watch/mcp/server-card",
            }],
        })


if __name__ == "__main__":
    unittest.main()
