"""BASEMAP MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from basemap.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-basemap[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-basemap[mcp]'")
        return 1
    app = FastMCP("basemap")

    @app.tool()
    def basemap_scan(target: str) -> str:
        """Build and query a structured catalog of installations/AOIs with distance, sector, and coverage queries.. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
