"""Core engine for BASEMAP.

A Catalog holds Installation records loaded from JSON. All geospatial math uses
the spherical-earth (haversine / great-circle) model with the WGS-84 mean radius.
The engine answers four analytical query families:

  * nearest  - rank installations by great-circle distance from a point
  * radius   - which installations fall inside a coverage radius (e.g. sensor
               range, patrol radius, comms footprint) and the unused margin
  * bbox     - installations inside a lat/lon bounding box
  * sector   - installations within an angular sector (bearing window) from a
               point, useful for line-of-sight / coverage-gap analysis

Everything here is descriptive analysis of static reference data.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

# WGS-84 mean (authalic) radius in kilometers.
EARTH_RADIUS_KM = 6371.0088

_COMPASS_16 = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


class CatalogError(Exception):
    """Raised on malformed input or invalid query parameters."""


def _valid_lat(lat: float) -> bool:
    return -90.0 <= lat <= 90.0


def _valid_lon(lon: float) -> bool:
    return -180.0 <= lon <= 180.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometers."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_KM * c


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, in degrees [0,360)."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360.0) % 360.0


def bearing_to_sector(bearing: float) -> str:
    """Map a bearing in degrees to a 16-point compass sector label."""
    idx = int((bearing % 360.0) / 22.5 + 0.5) % 16
    return _COMPASS_16[idx]


def _angular_in_window(bearing: float, center: float, half_width: float) -> bool:
    """True if `bearing` is within +/- half_width of `center` (all degrees)."""
    diff = abs((bearing - center + 180.0) % 360.0 - 180.0)
    return diff <= half_width


@dataclass
class Installation:
    """A single catalog entry (base, site, sensor, AOI, etc.)."""

    id: str
    name: str
    lat: float
    lon: float
    category: str = "unknown"
    country: str = ""
    coverage_km: float = 0.0  # nominal coverage / range radius for this site
    tags: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise CatalogError("installation requires a non-empty 'id'")
        try:
            self.lat = float(self.lat)
            self.lon = float(self.lon)
            self.coverage_km = float(self.coverage_km)
        except (TypeError, ValueError) as exc:
            raise CatalogError(f"{self.id}: lat/lon/coverage_km must be numeric ({exc})")
        if not _valid_lat(self.lat):
            raise CatalogError(f"{self.id}: latitude {self.lat} out of range [-90,90]")
        if not _valid_lon(self.lon):
            raise CatalogError(f"{self.id}: longitude {self.lon} out of range [-180,180]")
        if self.coverage_km < 0:
            raise CatalogError(f"{self.id}: coverage_km must be >= 0")
        if not isinstance(self.tags, list):
            raise CatalogError(f"{self.id}: tags must be a list")

    def to_dict(self) -> dict:
        return asdict(self)


class Catalog:
    """An in-memory collection of installations with query operations."""

    def __init__(self, installations: Optional[Iterable[Installation]] = None) -> None:
        self._items: dict = {}
        for inst in installations or []:
            self.add(inst)

    # ---- construction -------------------------------------------------
    def add(self, inst: Installation) -> None:
        if inst.id in self._items:
            raise CatalogError(f"duplicate installation id: {inst.id}")
        self._items[inst.id] = inst

    @property
    def installations(self) -> list:
        return list(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    @classmethod
    def from_records(cls, records: Iterable[dict]) -> "Catalog":
        cat = cls()
        for rec in records:
            if not isinstance(rec, dict):
                raise CatalogError("each installation record must be an object")
            allowed = {f for f in Installation.__dataclass_fields__}
            unknown = set(rec) - allowed
            if unknown:
                raise CatalogError(f"unknown field(s): {', '.join(sorted(unknown))}")
            cat.add(Installation(**rec))
        return cat

    @classmethod
    def load(cls, path: str) -> "Catalog":
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError as exc:
            raise CatalogError(f"catalog file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise CatalogError(f"invalid JSON in {path}: {exc}") from exc
        if isinstance(data, dict) and "installations" in data:
            data = data["installations"]
        if not isinstance(data, list):
            raise CatalogError("catalog must be a JSON array or {'installations': [...]}")
        return cls.from_records(data)

    # ---- queries ------------------------------------------------------
    def nearest(self, lat: float, lon: float, limit: int = 5) -> list:
        """Return up to `limit` installations sorted by distance ascending.

        Each result is a dict with the installation plus distance, bearing,
        and compass sector relative to the query point.
        """
        self._check_point(lat, lon)
        if limit <= 0:
            raise CatalogError("limit must be positive")
        scored = [self._annotate(inst, lat, lon) for inst in self._items.values()]
        scored.sort(key=lambda r: r["distance_km"])
        return scored[:limit]

    def radius(self, lat: float, lon: float, radius_km: float) -> list:
        """Installations whose center lies within `radius_km` of the point."""
        self._check_point(lat, lon)
        if radius_km <= 0:
            raise CatalogError("radius_km must be positive")
        out = []
        for inst in self._items.values():
            row = self._annotate(inst, lat, lon)
            if row["distance_km"] <= radius_km:
                # how much of the site's own coverage reaches the query point
                row["within_coverage"] = (
                    inst.coverage_km > 0 and row["distance_km"] <= inst.coverage_km
                )
                row["coverage_margin_km"] = round(radius_km - row["distance_km"], 3)
                out.append(row)
        out.sort(key=lambda r: r["distance_km"])
        return out

    def bbox(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> list:
        """Installations inside an axis-aligned lat/lon bounding box."""
        for v in (min_lat, max_lat):
            if not _valid_lat(v):
                raise CatalogError(f"latitude {v} out of range")
        for v in (min_lon, max_lon):
            if not _valid_lon(v):
                raise CatalogError(f"longitude {v} out of range")
        if min_lat > max_lat:
            raise CatalogError("min_lat must be <= max_lat")
        if min_lon > max_lon:
            raise CatalogError("min_lon must be <= max_lon")
        out = [
            inst.to_dict()
            for inst in self._items.values()
            if min_lat <= inst.lat <= max_lat and min_lon <= inst.lon <= max_lon
        ]
        out.sort(key=lambda r: r["id"])
        return out

    def sector(
        self,
        lat: float,
        lon: float,
        center_bearing: float,
        half_width_deg: float,
        max_km: Optional[float] = None,
    ) -> list:
        """Installations within an angular sector (bearing window) from a point.

        center_bearing in degrees; half_width_deg is the +/- spread. Optional
        max_km caps range. Useful for line-of-sight / coverage-gap reasoning.
        """
        self._check_point(lat, lon)
        if not 0 < half_width_deg <= 180:
            raise CatalogError("half_width_deg must be in (0, 180]")
        if max_km is not None and max_km <= 0:
            raise CatalogError("max_km must be positive")
        out = []
        for inst in self._items.values():
            row = self._annotate(inst, lat, lon)
            if max_km is not None and row["distance_km"] > max_km:
                continue
            if _angular_in_window(row["bearing_deg"], center_bearing % 360.0, half_width_deg):
                out.append(row)
        out.sort(key=lambda r: r["bearing_deg"])
        return out

    # ---- helpers ------------------------------------------------------
    def _annotate(self, inst: Installation, lat: float, lon: float) -> dict:
        dist = haversine_km(lat, lon, inst.lat, inst.lon)
        brng = initial_bearing_deg(lat, lon, inst.lat, inst.lon)
        row = inst.to_dict()
        row["distance_km"] = round(dist, 3)
        row["bearing_deg"] = round(brng, 1)
        row["sector"] = bearing_to_sector(brng)
        return row

    @staticmethod
    def _check_point(lat: float, lon: float) -> None:
        if not _valid_lat(lat):
            raise CatalogError(f"latitude {lat} out of range [-90,90]")
        if not _valid_lon(lon):
            raise CatalogError(f"longitude {lon} out of range [-180,180]")
