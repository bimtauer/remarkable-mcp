"""A stdio MCP server owns stdout: any stray print corrupts the JSON-RPC stream."""

import subprocess
import sys


def test_rendering_prints_nothing_to_stdout():
    code = (
        "from remarkable_mcp.extract import _svg_string_to_png; "
        "_svg_string_to_png("
        '\'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>\', 10, 10, None)'
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout == ""
