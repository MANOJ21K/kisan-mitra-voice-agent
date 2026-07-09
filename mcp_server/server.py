"""MCP server exposing the Kisan Mitra farmer-advisory tools.

Any MCP client (Claude Desktop, Cursor, a custom agent) can mount this server and call
the same four tools the in-process agent uses. This demonstrates the "build MCP servers"
line in both target JDs — the tool logic is imported from src/tools.py, not duplicated.

The directory is named mcp_server/ (not mcp/) so it can't shadow the installed `mcp`
package this file imports from.

Run:  python mcp_server/server.py         (stdio transport)
Register in an MCP client's config with command="python", args=["mcp_server/server.py"].
"""
from __future__ import annotations

import os
import sys

# Allow "python mcp_server/server.py" from the repo root to import src/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from src import tools  # noqa: E402

app = FastMCP("kisan-mitra")


@app.tool()
def get_weather(location: str) -> dict:
    """3-day local weather outlook with spraying/irrigation advice."""
    return tools.get_weather(location)


@app.tool()
def get_mandi_price(commodity: str, market: str | None = None) -> dict:
    """Today's wholesale mandi price (min/modal/max, INR per quintal) for a commodity."""
    return tools.get_mandi_price(commodity, market)


@app.tool()
def get_crop_advisory(crop: str, season: str | None = None) -> dict:
    """Agronomy advice (pests, irrigation, nutrients) for a crop this season."""
    return tools.get_crop_advisory(crop, season)


@app.tool()
def get_govt_scheme(query: str) -> dict:
    """Look up an Indian government agriculture scheme (PM-Kisan, Fasal Bima, KCC, ...)."""
    return tools.get_govt_scheme(query)


if __name__ == "__main__":
    app.run()
