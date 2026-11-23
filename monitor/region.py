"""Which positions belong to the Taw catchment.

The catchment's outline, site/data/catchment.geojson, stops at the estuary's
banks; data/neighbours.geojson holds the catchments around it. Both are
written by scripts/fetch_geodata.py.
"""

import json
import math
from pathlib import Path

from .geo import LandMask

ROOT = Path(__file__).resolve().parent.parent
BOUNDARY = ROOT / "site" / "data" / "catchment.geojson"
NEIGHBOURS = ROOT / "data" / "neighbours.geojson"


def rings(path):
    fc = json.loads(Path(path).read_text())
    return [[tuple(p) for p in poly[0]] for f in fc["features"] for poly in f["geometry"]["coordinates"]]


def membership(edge_m):
    """A test for whether a position belongs to the catchment: inside it, or
    within edge_m of it and nearer to it than to any of its neighbours (the
    Torridge, Barnstaple Bay, the Exmoor coast and the rest). That takes in
    outfalls and gauges in the estuary, which is outside the outline, and
    leaves out those just over the watershed."""
    taw = LandMask(rings(BOUNDARY), 0)
    neighbours = LandMask(rings(NEIGHBOURS), 0) if NEIGHBOURS.exists() else None

    def belongs(lon, lat):
        p = (lon, lat)
        if taw.inside(p):
            return True
        if neighbours and neighbours.inside(p):
            return False
        near = taw.distance_m(p, edge_m)
        if near == math.inf:
            return False
        return neighbours is None or near < neighbours.distance_m(p, edge_m)
    return belongs
