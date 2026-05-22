"""Command-line interface for BASEMAP.

Subcommands:
  list     - dump the catalog
  nearest  - rank installations by distance from a point
  radius   - installations within a coverage radius of a point
  bbox     - installations inside a bounding box
  sector   - installations within a bearing window from a point

Global:
  --version, --format {table,json}

Exit codes: 0 ok, 1 query/IO error, 2 argparse usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import Catalog, CatalogError


def _print(rows, fmt: str, columns) -> None:
    if fmt == "json":
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    if not rows:
        print("(no results)")
        return
    widths = {c: len(c) for c in columns}
    str_rows = []
    for r in rows:
        sr = {}
        for c in columns:
            val = r.get(c, "")
            if isinstance(val, list):
                val = ",".join(str(x) for x in val)
            elif isinstance(val, bool):
                val = "yes" if val else "no"
            sr[c] = str(val)
            widths[c] = max(widths[c], len(sr[c]))
        str_rows.append(sr)
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("  ".join("-" * widths[c] for c in columns))
    for sr in str_rows:
        print("  ".join(sr[c].ljust(widths[c]) for c in columns))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="BASEMAP - structured installations/AOI catalog and geospatial queries (analytical/OSINT).",
    )
    p.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=("table", "json"), default="table")
    p.add_argument("-c", "--catalog", help="path to catalog JSON file")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all installations")

    sp = sub.add_parser("nearest", help="rank installations by distance from a point")
    sp.add_argument("--lat", type=float, required=True)
    sp.add_argument("--lon", type=float, required=True)
    sp.add_argument("--limit", type=int, default=5)

    sp = sub.add_parser("radius", help="installations within a radius of a point")
    sp.add_argument("--lat", type=float, required=True)
    sp.add_argument("--lon", type=float, required=True)
    sp.add_argument("--km", type=float, required=True, help="radius in kilometers")

    sp = sub.add_parser("bbox", help="installations inside a bounding box")
    sp.add_argument("--min-lat", type=float, required=True)
    sp.add_argument("--min-lon", type=float, required=True)
    sp.add_argument("--max-lat", type=float, required=True)
    sp.add_argument("--max-lon", type=float, required=True)

    sp = sub.add_parser("sector", help="installations within a bearing window from a point")
    sp.add_argument("--lat", type=float, required=True)
    sp.add_argument("--lon", type=float, required=True)
    sp.add_argument("--bearing", type=float, required=True, help="center bearing in degrees")
    sp.add_argument("--width", type=float, required=True, help="half-width in degrees (+/-)")
    sp.add_argument("--max-km", type=float, default=None)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.catalog:
        print("error: --catalog/-c is required", file=sys.stderr)
        return 1

    try:
        cat = Catalog.load(args.catalog)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    base_cols = ["id", "name", "category", "country", "lat", "lon"]
    geo_cols = base_cols + ["distance_km", "bearing_deg", "sector"]

    try:
        if args.cmd == "list":
            rows = [i.to_dict() for i in sorted(cat.installations, key=lambda x: x.id)]
            _print(rows, args.format, base_cols + ["coverage_km"])
        elif args.cmd == "nearest":
            rows = cat.nearest(args.lat, args.lon, args.limit)
            _print(rows, args.format, geo_cols)
        elif args.cmd == "radius":
            rows = cat.radius(args.lat, args.lon, args.km)
            _print(rows, args.format, geo_cols + ["within_coverage", "coverage_margin_km"])
        elif args.cmd == "bbox":
            rows = cat.bbox(args.min_lat, args.min_lon, args.max_lat, args.max_lon)
            _print(rows, args.format, base_cols + ["coverage_km"])
        elif args.cmd == "sector":
            rows = cat.sector(args.lat, args.lon, args.bearing, args.width, args.max_km)
            _print(rows, args.format, geo_cols)
        else:  # pragma: no cover - argparse enforces choices
            parser.error(f"unknown command: {args.cmd}")
            return 2
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
