#!/usr/bin/env python3
"""Fetch the River Taw catchment, Devon, and the waterways, railways and roads.

The catchment boundary comes from the Environment Agency's WFD operational
catchments and Catchment Data Explorer; everything else comes from
OpenStreetMap through the Overpass API. Writes simplified GeoJSON overlays
to site/data/:

    catchment.geojson  the Taw catchment, which the data is drawn for
    rivers.geojson     the catchment's rivers and canals, one feature per named river
    streams.geojson    the catchment's streams (minor waterways), simplified
    railways.geojson   the Tarka and Dartmoor lines
    roads.geojson      the major roads that reach the catchment, across Devon
    stations.geojson   National Rail stations on those lines
    meta.json          when the snapshot was taken, and feature counts

and, for the server only, data/places.json (the towns, villages and hamlets
around the catchment, used to name rain gauges and power cuts) and
data/neighbours.geojson (the catchments around the Taw's, used to tell its
storm overflows, power cuts and flood areas from theirs).

Standard library only. Run occasionally (``make data``; add ``--refresh`` to bypass the cache, or
``--cached`` to reprocess the cached downloads without fetching); the overlays change
slowly, so the site serves these static snapshots rather than querying live.
"""

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor.geo import LandMask, perp_dist, simplify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data"
SERVER_DATA = ROOT / "data"  # server-side files, not served to browsers
# Raw downloads, so a failure late in a run doesn't mean re-downloading
# everything. Reused for a day unless --refresh is given.
CACHE = ROOT / ".cache" / "overpass"
CACHE_MAX_AGE = 24 * 3600
REFRESH = "--refresh" in sys.argv
CACHED_ONLY = "--cached" in sys.argv  # reprocess from the cache, however old
FETCHED = []  # when each dataset was downloaded; the oldest dates the snapshot

# The catchment is built from two Environment Agency datasets (OGL):
#
# - The WFD operational catchment 'Taw and North Devon Streams' (3441). Its
#   outline covers all the land that drains to the Taw, including Barnstaple
#   and the other land draining straight into the estuary, and stops at the
#   estuary's banks, where the 'Taw and Torridge Estuary' catchment begins.
#   But it also holds the Exmoor coast: the Lyns, Heddon, Umber and
#   Sterridge, and the coastal land from Croyde round to Lynmouth.
# - The river water bodies in that catchment, from the Catchment Data
#   Explorer. They're numbered by hydrometric area, and those draining to
#   the Taw are in area 50 (GB108050...), the same area as the Taw's gauging
#   station at Umberleigh. They leave out the land draining straight into
#   the estuary.
#
# The Taw catchment is the operational catchment's outline, kept where it's
# in one of the Taw's water bodies or in ESTUARY_LAND, a box round the
# estuary that takes in Barnstaple, Fremington and the land beside them. The
# two datasets were digitised separately, so the areas are combined on a
# fine grid and the outline traced from it.
OUTLINE_URL = ("https://services3.arcgis.com/Bb8lfThdhugyc4G3/ArcGIS/rest/services/"
               "WFD_Surface_Water_Operational_Catchments_Cycle3/FeatureServer/0/query")
OPERATIONAL_CATCHMENT = "3441"
CATCHMENT_URL = f"https://environment.data.gov.uk/catchment-planning/OperationalCatchment/{OPERATIONAL_CATCHMENT}.geojson"
TAW_WATER_BODIES = "GB108050"
# The box stops short of Instow and Westleigh: they're in the operational
# catchment, but their outfalls and streams run into the Torridge's side of
# the estuary.
ESTUARY_LAND = (-4.172, 51.03, -4.00, 51.115)  # west, south, east, north
GRID_DY = 0.00005  # degrees of latitude, ~5.5 m, the height of each row of the grid
MIN_PART_KM2 = 0.05  # smaller pieces of the outline are slivers, not land

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "floodwatch/2.0 (+https://github.com/aallan/floodwatch)"

# Overpass queries are made by bounding box: the catchment isn't an
# OpenStreetMap area. Waterways are clipped to the catchment; roads and
# railways run on a little past it, under the dimmed land outside, so they
# don't stop dead at the watershed.
PAD_DEG = 0.04  # ~3-4 km

# Simplification tolerance in degrees (~1e-4 deg is ~7-11 m here).
SIMPLIFY_RIVER = 0.00004
SIMPLIFY_STREAM = 0.00012
SIMPLIFY_RAIL = 0.00003
SIMPLIFY_BOUNDARY = 0.0001
# Waterways are kept inside the catchment, and within this distance of its edge.
EDGE_TOLERANCE_M = 60
PRECISION = 5  # decimal places, ~1 m

# Devon: the county council's area with the two unitary authorities inside
# it, Plymouth and Torbay. Roads are drawn across it and end at its edge.
DEVON_GSS = ("E10000008", "E06000026", "E06000027")
SIMPLIFY_DEVON = 0.0003  # ~20-30 m: it's drawn only as the edge of the dimmed land

# The railway lines drawn, as OpenStreetMap route relations. A route lists
# all the track its trains run on, so the Tarka Line runs from Barnstaple
# right into Exeter St Davids and Exeter Central, over track OSM names after
# other lines. The Dartmoor Line shares the Tarka's track from Exeter to
# Coleford Junction, and is drawn only where it leaves it, for Okehampton.
RAIL_ROUTES = {275887: "Tarka Line", 276920: "Dartmoor Line"}
STATION_NEAR_M = 250  # a station this close to a line is on it

# The major roads drawn: the A377, which runs down the Taw valley from Exeter
# to Barnstaple, and the A30 from Exeter west past the foot of the catchment
# at Sticklepath, ending at Devon's edge. East of Exeter the A30 is cut off
# at ROAD_EAST_LIMIT, where it leaves the M5 for Honiton.
MAJOR_ROADS = ("A30", "A377")
ROAD_EAST_LIMIT = {"A30": -3.49}


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------

def cached(label):
    """A cached download that's fresh enough to use, or None."""
    path = CACHE / f"{label}.json"
    fresh = path.exists() and (CACHED_ONLY or time.time() - path.stat().st_mtime < CACHE_MAX_AGE)
    if REFRESH or not fresh:
        return None
    FETCHED.append(path.stat().st_mtime)
    return json.loads(path.read_text())


def keep(label, data):
    FETCHED.append(time.time())
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{label}.json").write_text(json.dumps(data))
    return data


def overpass(query, label):
    """POST a query, retrying with exponential backoff across endpoints."""
    els = cached(label)
    if els is not None:
        print(f"  {label}: {len(els)} elements (cached)")
        return els
    data = urllib.parse.urlencode({"data": query}).encode()
    delay = 5
    for attempt in range(8):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                body = json.loads(r.read())
            remark = body.get("remark", "")
            if "runtime error" in remark or "timed out" in remark:
                raise RuntimeError(remark)
            print(f"  {label}: {len(body['elements'])} elements ({urllib.parse.urlparse(url).netloc})")
            return keep(label, body["elements"])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as e:
            print(f"  {label}: attempt {attempt + 1} failed ({e}); retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    sys.exit(f"Overpass query failed after retries: {label}")


def geojson_features(label, url, data=None, source=""):
    """GeoJSON features from a URL (POSTing `data` if given), cached like the Overpass queries."""
    features = cached(label)
    if features is not None:
        print(f"  {label}: {len(features)} features (cached)")
        return features
    body = urllib.parse.urlencode(data).encode() if data else None
    delay = 5
    for attempt in range(5):
        req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                features = json.loads(r.read())["features"]
            if not features:
                raise ValueError("no features")
            print(f"  {label}: {len(features)} features ({source})")
            return keep(label, features)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"  {label}: attempt {attempt + 1} failed ({e}); retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    sys.exit(f"{source} download failed after retries: {label}")


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def pause():
    """Be polite between live queries; no need when reading the cache."""
    if not CACHED_ONLY:
        time.sleep(3)


def coords_of(way):
    return [(p["lon"], p["lat"]) for p in way.get("geometry", []) if p]


def rnd(pts):
    return [[round(x, PRECISION), round(y, PRECISION)] for x, y in pts]


def length_km(pts):
    total = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        # Equirectangular is plenty at this scale.
        kx = 111.32 * math.cos(math.radians((y1 + y2) / 2))
        total += math.hypot((x2 - x1) * kx, (y2 - y1) * 110.57)
    return total


def area_km2(ring):
    """A ring's area, by the shoelace formula on locally scaled degrees."""
    lat = sum(p[1] for p in ring) / len(ring)
    kx, ky = 111.32 * math.cos(math.radians(lat)), 110.57
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))) / 2 * kx * ky


def merge_lines(lines):
    """Join line strings end-to-start where they meet, keeping direction.

    OSM waterways are drawn source-to-mouth, so joining only end->start keeps
    the flow direction intact for the arrows on the map.
    """
    lines = [list(l) for l in lines if len(l) >= 2]
    merged = True
    while merged:
        merged = False
        starts = {}
        for i, l in enumerate(lines):
            starts.setdefault(l[0], []).append(i)
        used = set()
        out = []
        for i, l in enumerate(lines):
            if i in used:
                continue
            used.add(i)
            cur = l
            while True:
                nxt = [j for j in starts.get(cur[-1], []) if j not in used]
                if not nxt:
                    break
                j = nxt[0]
                used.add(j)
                cur = cur + lines[j][1:]
                merged = True
            out.append(cur)
        lines = out
    return lines


class Spans:
    """Where a set of rings is crossed by each row of a grid.

    Rows are GRID_DY high from y0; a row's spans are the stretches of its
    centre line inside the rings, by the even-odd rule. Rings that tile an
    area without overlapping, such as water body catchments, give the area
    they cover between them.
    """

    def __init__(self, rings, y0, rows):
        self.y0, self.rows = y0, rows
        self.crossings = defaultdict(list)
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                if y1 == y2:
                    continue
                lo, hi = sorted((y1, y2))
                first = max(0, math.ceil((lo - y0) / GRID_DY - 0.5))
                last = min(rows - 1, math.floor((hi - y0) / GRID_DY - 0.5))
                for j in range(first, last + 1):
                    y = y0 + (j + 0.5) * GRID_DY
                    if (y1 > y) != (y2 > y):
                        self.crossings[j].append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))

    def row(self, j):
        xs = sorted(self.crossings.get(j, ()))
        return [(a, b) for a, b in zip(xs[::2], xs[1::2]) if b > a]


def union_spans(a, b):
    out = []
    for lo, hi in sorted(a + b):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def intersect_spans(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if lo < hi:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def xor_spans(a, b):
    """The stretches covered by exactly one of a and b."""
    edges = sorted([x for s in a for x in s] + [x for s in b for x in s])
    out = []
    for lo, hi in zip(edges, edges[1:]):
        mid = (lo + hi) / 2
        if hi > lo and (any(s <= mid < e for s, e in a) != any(s <= mid < e for s, e in b)):
            if out and out[-1][1] == lo:
                out[-1] = (out[-1][0], hi)
            else:
                out.append((lo, hi))
    return out


def trace(rows, y0):
    """Outline the area covered by each row's spans, as closed rings.

    Each span is a strip GRID_DY high. The outline is the strips' sides, plus
    the stretches of each line between rows that one row covers and the
    other doesn't. Returns rings largest first.
    """
    segs = []
    for j, spans in enumerate(rows):
        ylo, yhi = y0 + j * GRID_DY, y0 + (j + 1) * GRID_DY
        for a, b in spans:
            segs += [((a, ylo), (a, yhi)), ((b, ylo), (b, yhi))]
        below = rows[j - 1] if j else []
        for a, b in xor_spans(spans, below):
            segs.append(((a, ylo), (b, ylo)))
    top = y0 + len(rows) * GRID_DY
    segs += [((a, top), (b, top)) for a, b in rows[-1]] if rows else []
    adjacent = defaultdict(list)
    for p, q in segs:
        adjacent[p].append(q)
        adjacent[q].append(p)
    out, used = [], set()
    for start in list(adjacent):
        for first in adjacent[start]:
            if frozenset((start, first)) in used:
                continue
            ring, prev, cur = [start], start, first
            used.add(frozenset((start, first)))
            while cur != start:
                ring.append(cur)
                nxt = [p for p in adjacent[cur] if frozenset((cur, p)) not in used]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                used.add(frozenset((prev, cur)))
            if cur == start and len(ring) >= 3:
                out.append(drop_collinear(ring + [start]))
    return sorted(out, key=len, reverse=True)


def drop_collinear(ring):
    """Remove the points along straight runs, so a strip's side is one segment."""
    out = [ring[0]]
    for p, q in zip(ring[1:], ring[2:]):
        a = out[-1]
        if (q[0] - a[0]) * (p[1] - a[1]) != (p[0] - a[0]) * (q[1] - a[1]):
            out.append(p)
    out.append(ring[-1])
    return out


class Coastline:
    """Cuts a river line where it first crosses the coastline.

    In UK OSM the coastline runs up each estuary to about the tidal limit and
    closes across the river there, so the first crossing on a line drawn
    source-to-mouth is where the river meets tidal water.
    """

    CELL = 0.002

    def __init__(self, ways):
        self.cells = defaultdict(list)
        c = self.CELL
        for w in ways:
            g = coords_of(w)
            for a, b in zip(g, g[1:]):
                for gx in range(math.floor(min(a[0], b[0]) / c), math.floor(max(a[0], b[0]) / c) + 1):
                    for gy in range(math.floor(min(a[1], b[1]) / c), math.floor(max(a[1], b[1]) / c) + 1):
                        self.cells[(gx, gy)].append((a, b))

    @staticmethod
    def _cross(p, q, a, b):
        """Fraction along p->q where it meets a->b, or None."""
        rx, ry = q[0] - p[0], q[1] - p[1]
        sx, sy = b[0] - a[0], b[1] - a[1]
        den = rx * sy - ry * sx
        if den == 0:
            return None
        t = ((a[0] - p[0]) * sy - (a[1] - p[1]) * sx) / den
        u = ((a[0] - p[0]) * ry - (a[1] - p[1]) * rx) / den
        return t if 0 <= t <= 1 and 0 <= u <= 1 else None

    def cut(self, line):
        c = self.CELL
        for i, (p, q) in enumerate(zip(line, line[1:])):
            near = set()
            for gx in range(math.floor(min(p[0], q[0]) / c), math.floor(max(p[0], q[0]) / c) + 1):
                for gy in range(math.floor(min(p[1], q[1]) / c), math.floor(max(p[1], q[1]) / c) + 1):
                    near.update(self.cells.get((gx, gy), ()))
            ts = [t for a, b in near
                  if (t := self._cross(p, q, a, b)) is not None and not (i == 0 and t == 0)]
            if ts:
                t = min(ts)
                end = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
                return line[:i + 1] + [end]
        return line


def feature(geom_type, coords, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": geom_type, "coordinates": coords}}


def write(name, features):
    path = OUT / name
    fc = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(fc, separators=(",", ":"), ensure_ascii=False))
    print(f"  wrote {path.relative_to(OUT.parent.parent)} ({len(features)} features, {path.stat().st_size // 1024} KB)")


# --------------------------------------------------------------------------
# Layers
# --------------------------------------------------------------------------

def outer_rings(features):
    rings = []
    for f in features:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
        rings += [[tuple(pt) for pt in poly[0]] for poly in polys]
    return rings


def fetch_boundary():
    """Return the boundary feature, the rings for clipping, and the Overpass
    bounding box (south, west, north, east) around them."""
    outline = outer_rings(geojson_features(
        "catchment_outline", OUTLINE_URL, source="EA WFD operational catchments",
        data={"where": f"Operation0='{OPERATIONAL_CATCHMENT}'", "outFields": "Operation0",
              "returnGeometry": "true", "outSR": "4326", "f": "geojson"}))
    water_bodies = outer_rings([
        f for f in geojson_features("catchment", CATCHMENT_URL, source="Catchment Data Explorer")
        if str(f.get("properties", {}).get("id", "")).startswith(TAW_WATER_BODIES)
        and str(f.get("properties", {}).get("geometry-type", "")).endswith("/Catchment")])
    ys = [p[1] for r in outline for p in r]
    y0 = min(ys) - GRID_DY
    rows = math.ceil((max(ys) - y0) / GRID_DY) + 1
    inside, taw = Spans(outline, y0, rows), Spans(water_bodies, y0, rows)
    w, s, e, n = ESTUARY_LAND
    covered = []
    for j in range(rows):
        y = y0 + (j + 0.5) * GRID_DY
        keep_here = union_spans(taw.row(j), [(w, e)] if s <= y <= n else [])
        covered.append(intersect_spans(inside.row(j), keep_here))
    # Drop slivers: specks along the estuary and the box's edges, where the
    # two datasets' borders disagree by a few metres.
    rings = [r for r in trace(covered, y0) if area_km2(r) >= MIN_PART_KM2]
    if not rings:
        sys.exit("The Taw's catchment outline came out empty")
    # The rest of the operational catchment, the Exmoor coast, is one of the
    # catchment's neighbours.
    rest = [xor_spans(inside.row(j), covered[j]) for j in range(rows)]
    north_coast = [simplify(r, SIMPLIFY_BOUNDARY) for r in trace(rest, y0) if area_km2(r) >= MIN_PART_KM2]
    outline = [simplify(r, SIMPLIFY_RAIL) for r in rings]
    polys = [[rnd(r)] for r in (simplify(r, SIMPLIFY_BOUNDARY) for r in outline) if len(r) >= 4]
    xs = [p[0] for r in outline for p in r]
    ys = [p[1] for r in outline for p in r]
    bbox = (round(min(ys) - PAD_DEG, 3), round(min(xs) - PAD_DEG, 3), round(max(ys) + PAD_DEG, 3), round(max(xs) + PAD_DEG, 3))
    return [feature("MultiPolygon", polys, name="River Taw catchment")], outline, bbox, north_coast


# The estuary's own catchment is water, not a neighbour: outfalls in it can
# belong to the Taw.
ESTUARY_CATCHMENT = "3442"


def fetch_neighbours(bbox, north_coast):
    """The land around the catchment, for telling the Taw's storm overflows,
    power cuts and flood areas from their neighbours': the other operational
    catchments that reach into the bounding box, such as the Torridge, and
    the Exmoor coast."""
    s, w, n, e = bbox
    features = geojson_features(
        "neighbours", OUTLINE_URL, source="EA WFD operational catchments",
        data={"where": f"Operation0 NOT IN ('{OPERATIONAL_CATCHMENT}', '{ESTUARY_CATCHMENT}')",
              "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope", "inSR": "4326",
              "spatialRel": "esriSpatialRelIntersects", "outFields": "Operation0,Operationa",
              "returnGeometry": "true", "outSR": "4326", "maxAllowableOffset": "0.0002", "f": "geojson"})
    polys = [[rnd(simplify(r, SIMPLIFY_BOUNDARY))] for r in outer_rings(features) + north_coast]
    names = sorted({f["properties"].get("Operationa", "") for f in features} - {""})
    return [feature("MultiPolygon", [p for p in polys if len(p[0]) >= 4],
                    name="Around the Taw: " + ", ".join(names + ["the Exmoor coast"]))]


def river_name(raw):
    """Normalise names so tidal reaches group with their river.

    e.g. 'River Lynher or St Germans River' -> 'River Lynher', 'Yeo' -> 'River Yeo'.
    """
    name = raw.split(" or ")[0].strip()
    return RENAME.get(name, name)


RENAME = {"Yeo": "River Yeo"}

# Rivers that share a name: each stretch is named after the place it's
# nearest. The catchment has three River Yeos: Barnstaple's, gauged at
# Collard Bridge; Lapford's, which joins the Taw below Lapford; and
# Molland's, which joins the Mole.
SAME_NAME = {
    "River Yeo": [("River Yeo", (-4.010, 51.100)),
                  ("Lapford Yeo", (-3.811, 50.858)),
                  ("Molland Yeo", (-3.720, 51.030))],
}

# Streams drawn with the rivers rather than the streams: in OpenStreetMap
# these are tagged as streams, but they're the size of the rivers here.
PROMOTED_STREAMS = {"Hollocombe Water"}


def nearest_name(line, places):
    def dist(p, q):
        return math.hypot((p[0] - q[0]) * math.cos(math.radians(q[1])), p[1] - q[1])
    return min(places, key=lambda nq: min(dist(p, nq[1]) for p in line[::5] + [line[-1]]))[0]


# The most unnamed ways a gap in a river is bridged across: enough for the
# Little Dart above Witheridge, few enough not to wander down another stream.
MAX_BRIDGE_WAYS = 6


def bridge_gaps(by_name, streams):
    """Join unnamed waterways that fill a gap in a named river.

    OSM sometimes leaves a stretch of a river unnamed: below the Lapford
    Yeo's headwaters, where the way doubles as a parish boundary, and on the
    Little Dart above Witheridge, where a chain of unnamed ways carries it
    for 3.5 km. A chain of up to MAX_BRIDGE_WAYS unnamed ways, followed
    downstream from the end of one stretch of a river to the start of
    another stretch of the same river, is part of it. A way can be joined
    part-way along, where the river meets it at one of its points: the river
    takes the part below that point, and the part above stays a stream.
    """
    unnamed = [pts for pts in by_name.get("", []) if len(pts) >= 2] + \
              [pts for nm, pts in streams if not nm and len(pts) >= 2]
    at_point = defaultdict(list)  # a point -> (way, index) for each unnamed way through it
    for i, pts in enumerate(unnamed):
        for k, pt in enumerate(pts[:-1]):
            at_point[pt].append((i, k))
    cut = {}  # way -> the index the river takes it from
    for name, lines in list(by_name.items()):
        if not name:
            continue
        starts = {l[0] for l in lines}
        for gap_end in {l[-1] for l in lines} - starts:
            # Breadth first, so the shortest chain wins.
            frontier, seen, found = [(gap_end, [])], {gap_end}, None
            while frontier and found is None:
                nxt = []
                for point, path in frontier:
                    for i, k in at_point.get(point, ()):
                        end = unnamed[i][-1]
                        if i in cut or end in seen:
                            continue
                        if end in starts:
                            found = path + [(i, k)]
                            break
                        if len(path) + 1 < MAX_BRIDGE_WAYS:
                            seen.add(end)
                            nxt.append((end, path + [(i, k)]))
                    if found:
                        break
                frontier = nxt
            for i, k in found or ():
                cut[i] = k
                by_name[name].append(unnamed[i][k:])
    if not cut:
        return
    # What's left of each way joined part-way stays where it was.
    rest = {id(unnamed[i]): unnamed[i][:k + 1] if k else None for i, k in cut.items()}

    def trim(pts):
        return rest.get(id(pts), pts)
    if "" in by_name:
        by_name[""] = [t for t in (trim(pts) for pts in by_name[""]) if t]
    streams[:] = [(nm, t) for nm, t in ((nm, trim(pts)) for nm, pts in streams) if t]


def fetch_waterways(land, coast, bbox):
    box = ",".join(map(str, bbox))
    river_ways = overpass(f'[out:json][timeout:240];way["waterway"~"^(river|canal)$"]({box});out tags geom;', "rivers")
    pause()
    stream_ways = overpass(f'[out:json][timeout:240];way["waterway"="stream"]({box});out tags geom;', "streams")

    def usable(t):
        if t.get("waterway") == "canal" and (t.get("disused") or t.get("abandoned") or t.get("usage") == "disused"):
            return False
        # Each river ends at its tidal limit: its tidal ways are dropped, and
        # below it is cut where it crosses the coastline, which in UK OSM
        # closes across each river there. The catchment stops at the
        # estuary's banks too, so either way a river ends where it meets
        # the estuary rather than running down the middle of it.
        return t.get("tidal") != "yes"

    by_name = defaultdict(list)
    kind_of = {}
    for w in river_ways:
        t = w.get("tags", {})
        if usable(t):
            name = river_name(t["name"]) if t.get("name") else ""
            by_name[name].append(coords_of(w))
            kind_of.setdefault(name, t.get("waterway"))
    # A stream that shares a river's name, such as a headwater of the Mole
    # tagged as a stream, is drawn as part of the river.
    streams_left = []
    for w in stream_ways:
        t = w.get("tags", {})
        name = river_name(t["name"]) if t.get("name") else ""
        if not usable(t):
            continue
        if name and (name in by_name or name in PROMOTED_STREAMS):
            by_name[name].append(coords_of(w))
            kind_of.setdefault(name, "river")
        else:
            streams_left.append((name, coords_of(w)))
    bridge_gaps(by_name, streams_left)

    named_lines = defaultdict(list)
    for name, lines in by_name.items():
        for l in merge_lines(lines):
            label = nearest_name(l, SAME_NAME[name]) if name in SAME_NAME else name
            named_lines[label] += [run for run in land.clip(coast.cut(l)) if len(run) >= 2]
            kind_of.setdefault(label, kind_of[name])
    rivers = []
    for name, merged in named_lines.items():
        if not merged:
            continue
        parts = [rnd(simplify(l, SIMPLIFY_RIVER)) for l in merged]
        km = sum(length_km(l) for l in merged)
        rivers.append(feature("MultiLineString", parts, name=name, kind=kind_of[name], length_km=round(km, 1)))
    rivers.sort(key=lambda f: -f["properties"]["length_km"])

    named = defaultdict(list)
    unnamed = []
    for nm, pts in streams_left:
        runs = [run for run in land.clip(pts) if len(run) >= 2]
        (named[nm] if nm else unnamed).extend(runs)
    streams = []
    for nm, lines in named.items():
        parts = [rnd(simplify(l, SIMPLIFY_STREAM)) for l in merge_lines(lines)]
        streams.append(feature("MultiLineString", parts, name=nm))
    # Unnamed streams go out as one feature: thousands of tiny ways otherwise.
    parts = [rnd(simplify(l, SIMPLIFY_STREAM)) for l in merge_lines(unnamed)]
    streams.append(feature("MultiLineString", parts, name=""))
    return rivers, streams


def assemble_rings(segs):
    """Stitch boundary ways, in any order and direction, into closed rings."""
    segs = [list(seg) for seg in segs if len(seg) >= 2]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, seg in enumerate(segs):
                if seg[0] == ring[-1]:
                    ring += seg[1:]
                elif seg[-1] == ring[-1]:
                    ring += seg[-2::-1]
                elif seg[-1] == ring[0]:
                    ring = seg[:-1] + ring
                elif seg[0] == ring[0]:
                    ring = seg[:0:-1] + ring
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
        else:
            print(f"  warning: dropped an unclosed boundary ring ({len(ring)} points)", file=sys.stderr)
    return rings


def outline_of(relations):
    """The outer rings of the area that relations tile between them.

    Neighbouring areas share the ways along their common border, so a way
    that's an outer member of two of the relations is inside the whole, and
    is left out; the rest make up its outline.
    """
    uses = defaultdict(int)
    ways = {}
    for rel in relations:
        for m in rel.get("members", []):
            if m["type"] == "way" and m.get("role") in ("outer", ""):
                uses[m["ref"]] += 1
                ways[m["ref"]] = coords_of(m)
    return assemble_rings([ways[ref] for ref, n in uses.items() if n == 1])


def fetch_devon():
    """Devon's outline: its feature, the rings for clipping, and the bounding box."""
    gss = "|".join(DEVON_GSS)
    rings = outline_of(overpass(f'[out:json][timeout:240];rel["ref:gss"~"^({gss})$"];out geom;', "devon"))
    if not rings:
        sys.exit("Devon's outline came out empty")
    polys = [[rnd(r)] for r in (simplify(r, SIMPLIFY_DEVON) for r in rings) if len(r) >= 4]
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    bbox = (round(min(ys), 3), round(min(xs), 3), round(max(ys), 3), round(max(xs), 3))
    return [feature("MultiPolygon", polys, name="Devon")], rings, bbox


def touches(lines, land):
    """True if any of the lines comes into the catchment."""
    return any(land.keep(p) for l in lines for p in l[::3] + [l[-1]])


def metres_to_line(p, lines, within_m):
    """How far p is from the nearest of the lines, if within within_m; else infinity."""
    kx, ky = 111_320 * math.cos(math.radians(p[1])), 110_570
    best = math.inf
    for line in lines:
        for a, b in zip(line, line[1:]):
            if min(abs(a[0] - p[0]), abs(b[0] - p[0])) * kx > within_m + 5000:
                continue
            pa, pb = ((a[0] - p[0]) * kx, (a[1] - p[1]) * ky), ((b[0] - p[0]) * kx, (b[1] - p[1]) * ky)
            best = min(best, perp_dist((0.0, 0.0), pa, pb))
    return best if best <= within_m else math.inf


SHARED_TRACK_M = 30  # a way this close to an earlier route's track runs beside it


def route_lines(relations):
    """{line name: [way coordinates]} from route relations. Track on more than
    one route is drawn once, on the first: the Tarka Line before the Dartmoor.
    The routes don't always list the same ways for the track they share, so a
    way lying along an earlier route's track, within SHARED_TRACK_M at both
    ends and in the middle, counts as shared too."""
    seen, lines, earlier = set(), defaultdict(list), []
    for rel in sorted(relations, key=lambda r: list(RAIL_ROUTES).index(r["id"])):
        mine = []
        for m in rel.get("members", []):
            if m["type"] != "way" or m.get("role") not in ("", "forward", "backward") or m["ref"] in seen:
                continue
            seen.add(m["ref"])
            pts = coords_of(m)
            if len(pts) < 2:
                continue
            if earlier and all(metres_to_line(p, earlier, SHARED_TRACK_M) < math.inf
                               for p in (pts[0], pts[len(pts) // 2], pts[-1])):
                continue
            mine.append(pts)
        lines[RAIL_ROUTES[rel["id"]]] = mine
        earlier += mine
    return lines


def fetch_railways(land):
    ids = ",".join(map(str, RAIL_ROUTES))
    lines = route_lines(overpass(f"[out:json][timeout:240];rel(id:{ids});out geom;", "railways"))
    rails, all_track = [], []
    for name in RAIL_ROUTES.values():
        merged = merge_lines(lines.get(name, []))
        if not merged:
            print(f"  warning: no track found for the {name}", file=sys.stderr)
            continue
        all_track += merged
        parts = [rnd(simplify(l, SIMPLIFY_RAIL)) for l in merged]
        rails.append(feature("MultiLineString", parts, kind="passenger", line=name,
                             length_km=round(sum(length_km(l) for l in merged), 1)))

    xs = [p[0] for l in all_track for p in l]
    ys = [p[1] for l in all_track for p in l]
    box = f"{min(ys) - 0.01},{min(xs) - 0.01},{max(ys) + 0.01},{max(xs) + 0.01}"
    pause()
    els = overpass(f'[out:json][timeout:180];node["railway"~"^(station|halt)$"]({box});out body;', "stations")
    stations = []
    for n in els:
        t = n.get("tags", {})
        if not t.get("name") or "disused" in t or t.get("railway:historic"):
            continue
        # National Rail stations on the lines drawn; heritage and miniature
        # railway halts, and stations on other lines, are left off.
        if not ("ref:crs" in t or t.get("network") == "National Rail"):
            continue
        if metres_to_line((n["lon"], n["lat"]), all_track, STATION_NEAR_M) == math.inf:
            continue
        stations.append(feature("Point", [round(n["lon"], PRECISION), round(n["lat"], PRECISION)],
                                name=t["name"], crs=t.get("ref:crs", ""), operator=t.get("operator", ""),
                                inside=land.keep((n["lon"], n["lat"]))))
    stations.sort(key=lambda f: f["properties"]["name"])
    return rails, stations


def major_ref(tag):
    """The road's number, if it's one of MAJOR_ROADS."""
    for r in (r.strip() for r in tag.split(";")):
        if r in MAJOR_ROADS:
            return r
    return None


def west_of(lines, limit):
    """The runs of each line that lie west of a longitude."""
    runs = []
    for line in lines:
        cur = []
        for p in line:
            if p[0] <= limit:
                cur.append(p)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
        if len(cur) >= 2:
            runs.append(cur)
    return runs


def fetch_roads(land, devon, devon_bbox):
    """The A30 and A377 across Devon, ending at its edge, and the A30 east of
    Exeter cut off.

    Slip roads (``*_link``) are left out. Dual carriageways stay as two lines,
    as OSM draws them.
    """
    box = ",".join(map(str, devon_bbox))
    refs = "|".join(MAJOR_ROADS)
    els = overpass(
        f'[out:json][timeout:240];way["highway"~"^(motorway|trunk|primary)$"]'
        f'["ref"~"(^|;) *({refs})( *;|$)"]({box});out tags geom;', "roads")
    by_ref = defaultdict(list)
    for w in els:
        ref = major_ref(w.get("tags", {}).get("ref", ""))
        if ref:
            by_ref[ref].append(coords_of(w))
    roads = []
    for ref, lines in sorted(by_ref.items()):
        merged = merge_lines(lines)
        if not touches(merged, land):
            continue
        merged = [run for l in merged for run in devon.clip(l)]
        if ref in ROAD_EAST_LIMIT:
            merged = west_of(merged, ROAD_EAST_LIMIT[ref])
        parts = [rnd(simplify(l, SIMPLIFY_RAIL)) for l in merged]
        roads.append(feature("MultiLineString", parts, ref=ref,
                             length_km=round(sum(length_km(l) for l in merged), 1)))
    return roads


def fetch_places(bbox):
    """Towns, villages and hamlets, used to name the rain gauges and power cuts."""
    box = ",".join(map(str, bbox))
    els = overpass(f'[out:json][timeout:180];node["place"~"^(town|village|hamlet)$"]["name"]({box});out body;', "places")
    return [{"name": n["tags"]["name"], "place": n["tags"]["place"],
             "lat": round(n["lat"], PRECISION), "lon": round(n["lon"], PRECISION)} for n in els]


def main():
    sys.stdout.reconfigure(line_buffering=True)  # show progress when piped
    OUT.mkdir(parents=True, exist_ok=True)
    print("Fetching the catchment (Catchment Data Explorer) and map data (OpenStreetMap, Overpass API)…")
    catchment, rings, bbox, north_coast = fetch_boundary()
    neighbours = fetch_neighbours(bbox, north_coast)
    land = LandMask(rings, EDGE_TOLERANCE_M)
    pause()
    devon, devon_rings, devon_bbox = fetch_devon()
    devon_land = LandMask(devon_rings, 100)
    box = ",".join(map(str, bbox))
    coast = Coastline(overpass(f'[out:json][timeout:240];way["natural"="coastline"]({box});out geom;', "coastline"))
    pause()
    rivers, streams = fetch_waterways(land, coast, bbox)
    pause()
    rails, stations = fetch_railways(land)
    pause()
    roads = fetch_roads(land, devon_land, devon_bbox)
    pause()
    places = fetch_places(bbox)

    print("Writing overlays…")
    write("catchment.geojson", catchment)
    write("rivers.geojson", rivers)
    write("streams.geojson", streams)
    write("railways.geojson", rails)
    write("roads.geojson", roads)
    write("stations.geojson", stations)
    SERVER_DATA.mkdir(exist_ok=True)
    (SERVER_DATA / "places.json").write_text(json.dumps(places, ensure_ascii=False))
    print(f"  wrote data/places.json ({len(places)} places)")
    (SERVER_DATA / "neighbours.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": neighbours}, separators=(",", ":")))
    print(f"  wrote data/neighbours.geojson ({len(neighbours[0]['geometry']['coordinates'])} polygons)")
    meta = {
        "generated": datetime.fromtimestamp(min(FETCHED), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Environment Agency Catchment Data Explorer (OGL); OpenStreetMap contributors, via the Overpass API (ODbL)",
        "bbox": bbox,
        "counts": {
            "rivers": len([f for f in rivers if f["properties"]["name"]]),
            "stations": len(stations),
        },
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("Done.")


if __name__ == "__main__":
    main()
