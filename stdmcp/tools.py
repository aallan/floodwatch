"""Tool registry entries and a small JSON Schema subset validator."""

import re
from dataclasses import dataclass
from typing import Callable


TYPES = ("string", "integer", "boolean")  # the property types validate() checks


class ToolError(Exception):
    """A message for the agent; becomes an ``isError`` tool result."""


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict
    handler: Callable[..., dict]

    def __post_init__(self) -> None:
        # validate() checks only what it knows, so a schema outside its subset
        # would let arguments through unchecked; refuse it at start instead.
        schema = self.input_schema
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError(f"{self.name}: the input schema must be an object schema")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"{self.name}: properties must be an object")
        for name, sub in properties.items():
            if not isinstance(sub, dict) or sub.get("type") not in TYPES:
                raise ValueError(f"{self.name}: argument {name} needs a type, one of {', '.join(TYPES)}")

    def annotations(self) -> dict:
        return {
            "title": self.title,
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }

    def listing(self) -> dict:
        """The entry for this tool in a ``tools/list`` result."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": self.annotations(),
        }


def _check_value(name: str, schema: dict, value: object) -> None:
    kind = schema.get("type")
    if kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(pattern, value) is None:
            raise ValueError(f"{name} does not match the required pattern {pattern}")
    elif kind == "integer":
        # bool subclasses int, so it has to be excluded explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{name} must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{name} must be at most {schema['maximum']}")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be a boolean")
    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(v) for v in schema["enum"])
        raise ValueError(f"{name} must be one of: {allowed}")


def validate(schema: dict, args: object) -> dict:
    """Return ``args`` with defaults filled in, or raise ``ValueError``."""
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(args) - set(properties))
        if unknown:
            raise ValueError(f"unknown argument: {', '.join(unknown)}")
    for name in schema.get("required", []):
        if name not in args:
            raise ValueError(f"missing required argument: {name}")
    out = dict(args)
    for name, sub in properties.items():
        if name in out:
            _check_value(name, sub, out[name])
        elif "default" in sub:
            out[name] = sub["default"]
    return out
