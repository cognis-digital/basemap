"""Smoke tests for BASEMAP. Stdlib unittest, no network, no install."""
import json
import os
import tempfile
import unittest

from basemap import (
    Catalog,
    Installation,
    CatalogError,
    haversine_km,
    initial_bearing_deg,
    bearing_to_sector,
    TOOL_NAME,
    TOOL_VERSION,
)
from basemap.cli import main

DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos", "01-basic", "installations.json",
)


class TestGeo(unittest.TestCase):
    def test_haversine_known_distance(self):
        # Denver -> Colorado Springs is ~100 km.
        d = haversine_km(39.7392, -104.9903, 38.8339, -104.8214)
        self.assertTrue(95 <= d <= 110, d)

    def test_haversine_zero(self):
        self.assertEqual(haversine_km(10, 20, 10, 20), 0.0)

    def test_bearing_due_north(self):
        b = initial_bearing_deg(0, 0, 10, 0)
        self.assertAlmostEqual(b, 0.0, places=3)

    def test_bearing_due_east(self):
        b = initial_bearing_deg(0, 0, 0, 10)
        self.assertAlmostEqual(b, 90.0, places=3)

    def test_sector_labels(self):
        self.assertEqual(bearing_to_sector(0), "N")
        self.assertEqual(bearing_to_sector(90), "E")
        self.assertEqual(bearing_to_sector(180), "S")
        self.assertEqual(bearing_to_sector(270), "W")
        self.assertEqual(bearing_to_sector(359), "N")


class TestInstallation(unittest.TestCase):
    def test_validation_lat(self):
        with self.assertRaises(CatalogError):
            Installation(id="x", name="x", lat=200, lon=0)

    def test_validation_id(self):
        with self.assertRaises(CatalogError):
            Installation(id="", name="x", lat=0, lon=0)

    def test_negative_coverage(self):
        with self.assertRaises(CatalogError):
            Installation(id="x", name="x", lat=0, lon=0, coverage_km=-1)


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog.load(DEMO)

    def test_load_count(self):
        self.assertEqual(len(self.cat), 6)

    def test_duplicate_id_rejected(self):
        recs = [
            {"id": "a", "name": "a", "lat": 0, "lon": 0},
            {"id": "a", "name": "b", "lat": 1, "lon": 1},
        ]
        with self.assertRaises(CatalogError):
            Catalog.from_records(recs)

    def test_unknown_field_rejected(self):
        with self.assertRaises(CatalogError):
            Catalog.from_records([{"id": "a", "name": "a", "lat": 0, "lon": 0, "zzz": 1}])

    def test_nearest_orders_by_distance(self):
        rows = self.cat.nearest(39.74, -104.99, limit=3)
        self.assertEqual(len(rows), 3)
        dists = [r["distance_km"] for r in rows]
        self.assertEqual(dists, sorted(dists))
        self.assertEqual(rows[0]["id"], "DEN-CIV-01")

    def test_nearest_bad_limit(self):
        with self.assertRaises(CatalogError):
            self.cat.nearest(0, 0, limit=0)

    def test_radius_filters_and_margin(self):
        rows = self.cat.radius(39.74, -104.99, 600)
        ids = {r["id"] for r in rows}
        self.assertIn("DEN-CIV-01", ids)
        self.assertIn("CYS-CIV-03", ids)
        self.assertNotIn("RAM-CIV-06", ids)
        for r in rows:
            self.assertIn("coverage_margin_km", r)
            self.assertIn("within_coverage", r)

    def test_radius_bad_value(self):
        with self.assertRaises(CatalogError):
            self.cat.radius(0, 0, -5)

    def test_bbox(self):
        rows = self.cat.bbox(32, -125, 49, -100)
        ids = {r["id"] for r in rows}
        self.assertIn("DEN-CIV-01", ids)
        self.assertNotIn("DCA-CIV-05", ids)
        self.assertNotIn("RAM-CIV-06", ids)

    def test_bbox_invalid_order(self):
        with self.assertRaises(CatalogError):
            self.cat.bbox(49, -100, 32, -125)

    def test_sector_east(self):
        # East-facing sector from Denver should include DC, exclude Grand Junction (west).
        rows = self.cat.sector(39.74, -104.99, 90, 50)
        ids = {r["id"] for r in rows}
        self.assertIn("DCA-CIV-05", ids)
        self.assertNotIn("GJT-CIV-04", ids)

    def test_sector_bad_width(self):
        with self.assertRaises(CatalogError):
            self.cat.sector(0, 0, 90, 0)

    def test_missing_file(self):
        with self.assertRaises(CatalogError):
            Catalog.load("/no/such/catalog_basemap.json")

    def test_bad_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write("{not json")
            with self.assertRaises(CatalogError):
                Catalog.load(path)
        finally:
            os.remove(path)


class TestCLI(unittest.TestCase):
    def test_meta(self):
        self.assertEqual(TOOL_NAME, "basemap")
        self.assertTrue(TOOL_VERSION)

    def test_list_ok(self):
        rc = main(["-c", DEMO, "--format", "json", "list"])
        self.assertEqual(rc, 0)

    def test_nearest_ok(self):
        rc = main(["-c", DEMO, "nearest", "--lat", "39.74", "--lon", "-104.99", "--limit", "2"])
        self.assertEqual(rc, 0)

    def test_radius_failure_exit_code(self):
        rc = main(["-c", DEMO, "radius", "--lat", "39.74", "--lon", "-104.99", "--km", "-5"])
        self.assertEqual(rc, 1)

    def test_missing_catalog_exit_code(self):
        rc = main(["-c", "/no/such/file.json", "list"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
