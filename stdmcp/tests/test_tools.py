import unittest

from stdmcp import Tool, ToolError
from stdmcp.tools import validate

SCHEMA = {
    "type": "object",
    "properties": {
        "station": {"type": "string", "pattern": "[A-Za-z0-9_-]{1,24}"},
        "days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
        "format": {"type": "string", "enum": ["brief", "full"], "default": "brief"},
        "verbose": {"type": "boolean"},
    },
    "required": ["station"],
    "additionalProperties": False,
}


class ValidateTests(unittest.TestCase):
    def test_defaults_are_filled(self):
        out = validate(SCHEMA, {"station": "50140"})
        self.assertEqual(out, {"station": "50140", "days": 7, "format": "brief"})

    def test_unknown_arguments_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "bogus"):
            validate(SCHEMA, {"station": "50140", "bogus": 1})

    def test_required(self):
        with self.assertRaisesRegex(ValueError, "station"):
            validate(SCHEMA, {})

    def test_integer_bounds(self):
        for bad in (0, 31, True, 1.5, "3"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                validate(SCHEMA, {"station": "x", "days": bad})
        self.assertEqual(validate(SCHEMA, {"station": "x", "days": 30})["days"], 30)

    def test_pattern_is_a_full_match(self):
        validate(SCHEMA, {"station": "50140"})
        for bad in ("50140 x", "a" * 25):
            with self.assertRaises(ValueError, msg=bad):
                validate(SCHEMA, {"station": bad})

    def test_enum(self):
        with self.assertRaises(ValueError):
            validate(SCHEMA, {"station": "x", "format": "xml"})
        self.assertEqual(validate(SCHEMA, {"station": "x", "format": "full"})["format"], "full")

    def test_boolean_type(self):
        with self.assertRaises(ValueError):
            validate(SCHEMA, {"station": "x", "verbose": "yes"})

    def test_non_object_arguments_are_rejected(self):
        for bad in ([], "x", 3, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                validate(SCHEMA, bad)


class ToolTests(unittest.TestCase):
    def test_listing_shape(self):
        tool = Tool("get_x", "Get X", "Gets X.", SCHEMA, lambda **kw: {})
        self.assertEqual(
            tool.listing(),
            {
                "name": "get_x",
                "title": "Get X",
                "description": "Gets X.",
                "inputSchema": SCHEMA,
                "annotations": {
                    "title": "Get X",
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            },
        )

    def test_tool_error_is_an_exception(self):
        self.assertTrue(issubclass(ToolError, Exception))


if __name__ == "__main__":
    unittest.main()
