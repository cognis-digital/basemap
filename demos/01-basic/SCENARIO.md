# Demo 01 - Basic catalog queries

This demo uses a small open catalog of well-known civil/airfield reference
points (`installations.json`) to exercise every BASEMAP query family. All
coordinates are public, approximate, and used purely for distance/bearing
bookkeeping analysis. There is no targeting or operational coupling.

## Catalog

`installations.json` holds 6 reference sites across the continental US plus one
in Europe, each with a nominal `coverage_km` radius (e.g. a notional sensor or
comms footprint) for coverage-margin analysis.

## Run it

From the repository root (zero install, stdlib only):

```sh
# List the whole catalog
python -m basemap -c demos/01-basic/installations.json list

# 3 nearest sites to a point near Denver, CO (JSON for piping)
python -m basemap -c demos/01-basic/installations.json --format json \
    nearest --lat 39.74 --lon -104.99 --limit 3

# Everything within 600 km of that point, with coverage margins
python -m basemap -c demos/01-basic/installations.json \
    radius --lat 39.74 --lon -104.99 --km 600

# Sites inside a CONUS-west bounding box
python -m basemap -c demos/01-basic/installations.json \
    bbox --min-lat 32 --min-lon -125 --max-lat 49 --max-lon -100

# Sites in a 45-degree sector centered on bearing 90 (east) from Denver
python -m basemap -c demos/01-basic/installations.json \
    sector --lat 39.74 --lon -104.99 --bearing 90 --width 45
```

## Expected highlights

- `nearest` ranks Buckley/Denver-area first (smallest `distance_km`).
- `radius --km 600` includes the Denver-area and Cheyenne sites; the European
  site is excluded.
- `sector --bearing 90 --width 45` returns only sites roughly east of Denver.
- A bad query (e.g. `radius --km -5`) prints an `error:` line and exits 1.
