import ast
import pathlib
import unittest

FORBIDDEN = {"monitor", "serve", "floodwatch_mcp"}
PACKAGE = pathlib.Path(__file__).resolve().parent.parent


class IndependenceTests(unittest.TestCase):
    def test_stdmcp_imports_nothing_from_floodwatch(self):
        files = sorted(PACKAGE.glob("*.py"))
        self.assertTrue(files)
        for path in files:
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    self.assertNotIn(name.split(".")[0], FORBIDDEN, f"{path.name} imports {name}")


if __name__ == "__main__":
    unittest.main()
