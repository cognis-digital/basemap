"""BASEMAP MCP server — exposes catalog queries as MCP tools for Cognis.Studio."""
from __future__ import annotations

import json
import sys

from basemap.core import Catalog, CatalogError


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-basemap[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("Install the MCP extra: pip install 'cognis-basemap[mcp]'", file=sys.stderr)
        return 1
    app = FastMCP("basemap")

    @app.tool()
    def basemap_nearest(catalog_path: str, lat: float, lon: float, limit: int = 5) -> str:
        """Return the nearest installations from a catalog JSON file.

        Args:
            catalog_path: Path to the catalog JSON file.
            lat: Query latitude in degrees [-90, 90].
            lon: Query longitude in degrees [-180, 180].
            limit: Maximum number of results to return (default 5).

        Returns JSON array of installations ordered by distance ascending.
        """
        try:
            cat = Catalog.load(catalog_path)
            rows = cat.nearest(lat, lon, limit)
            return json.dumps(rows, indent=2, sort_keys=True)
        except CatalogError as exc:
            return json.dumps({"error": str(exc)})

    @app.tool()
    def basemap_radius(catalog_path: str, lat: float, lon: float, radius_km: float) -> str:
        """Return installations within a radius of a point from a catalog JSON file.

        Args:
            catalog_path: Path to the catalog JSON file.
            lat: Query latitude in degrees [-90, 90].
            lon: Query longitude in degrees [-180, 180].
            radius_km: Search radius in kilometers (must be > 0).

        Returns JSON array of installations within the radius.
        """
        try:
            cat = Catalog.load(catalog_path)
            rows = cat.radius(lat, lon, radius_km)
            return json.dumps(rows, indent=2, sort_keys=True)
        except CatalogError as exc:
            return json.dumps({"error": str(exc)})

    app.run()
    return 0
