#!/usr/bin/env python3
"""Draw the README's figures as SVG, into docs/.

    docs/catchment.svg       how the catchment's outline is made, in three
                             panels, from the overlay builder's cached
                             downloads (run `make data` first)
    docs/flow-forecast.svg   the Taw's flow forecast at Umberleigh before and
                             after it's scaled to the measured flow, from a
                             running server's /api/forecast/flow/50140

    python3 scripts/figures.py
    python3 scripts/figures.py --url http://localhost:8090   # forecast from a local server

Each figure carries its own light background, so it reads the same on
GitHub's light and dark pages. Standard library only.
"""

import argparse
import json
import math
import sys
import time
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_geodata import ESTUARY_LAND, TAW_WATER_BODIES  # noqa: E402
from monitor.geo import simplify  # noqa: E402

DOCS = ROOT / "docs"
CACHE = ROOT / ".cache" / "overpass"

# The site's colours (site/css/style.css).
BG, TEXT, SECONDARY, GRID = "#f6f7f9", "#2c3345", "#5d6782", "#dfe2e8"
TEAL, TEAL_LIGHT, AMBER, BLUE, GREY = "#1a8a7d", "#b9e0da", "#c98a1a", "#2e7dab", "#9aa2b4"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"


def rings(geometry):
    """The outer rings of a Polygon or MultiPolygon."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [p[0] for p in geometry["coordinates"]]
    return []


def load(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        sys.exit(f"{path.relative_to(ROOT)} is missing; run `make data` first")


# ---------------------------------------------------------------- catchment

def catchment_svg():
    operational = [r for f in load(CACHE / "catchment_outline.json") for r in rings(f["geometry"])]
    bodies = [r for f in load(CACHE / "catchment.json")
              if str(f["properties"].get("id", "")).startswith(TAW_WATER_BODIES)
              and str(f["properties"].get("geometry-type", "")).endswith("/Catchment")
              for r in rings(f["geometry"])]
    outline = [r for f in load(ROOT / "site" / "data" / "catchment.geojson")["features"] for r in rings(f["geometry"])]
    neighbours = [r for f in load(ROOT / "data" / "neighbours.geojson")["features"] for r in rings(f["geometry"])]

    xs = [p[0] for r in operational for p in r]
    ys = [p[1] for r in operational for p in r]
    w, s, e, n = min(xs) - 0.03, min(ys) - 0.03, max(xs) + 0.03, max(ys) + 0.03
    k = math.cos(math.radians((s + n) / 2))     # degrees of longitude are shorter
    panel_w, top, gap, pad = 300, 70, 24, 24
    scale = panel_w / ((e - w) * k)
    panel_h = (n - s) * scale
    width, height = pad * 2 + panel_w * 3 + gap * 2, top + panel_h + 64

    def project(ox):
        return lambda lon, lat: (ox + (lon - w) * k * scale, top + (n - lat) * scale)

    def path(ring, at, tolerance=0.4):
        pts = simplify([at(*p[:2]) for p in ring], tolerance)
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z" if len(pts) > 2 else ""

    def shapes(rs, at, **style):
        attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in style.items())
        return f'<path d="{"".join(path(r, at) for r in rs)}" fill-rule="evenodd" {attrs}/>'

    def label(at, lon, lat, text, dx=0, dy=0, anchor="middle", size=11, colour=SECONDARY, dot=False):
        x, y = at(lon, lat)
        mark = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{TEXT}"/>' if dot else ""
        return (mark + f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" font-size="{size}" '
                f'fill="{colour}">{escape(text)}</text>')

    titles = ["1. The operational catchment", "2. The Taw’s water bodies, and the estuary",
              "3. Where they overlap: the outline"]
    notes = ["Taw and North Devon Streams: all the land draining to the Taw, and the Exmoor coast too",
             "Hydrometric area 50, which leaves out the estuary’s banks, plus a box round the estuary",
             "Gauges and overflows belong when inside it, or close by and nearer to it than to any neighbour"]
    parts = []
    for i in range(3):
        ox = pad + i * (panel_w + gap)
        at = project(ox)
        clip = f"clip{i}"
        parts.append(f'<clipPath id="{clip}"><rect x="{ox}" y="{top}" width="{panel_w}" height="{panel_h:.0f}" rx="8"/></clipPath>')
        parts.append(f'<rect x="{ox}" y="{top}" width="{panel_w}" height="{panel_h:.0f}" rx="8" fill="#fff" stroke="{GRID}"/>')
        body = []
        if i == 0:
            body.append(shapes(operational, at, fill="#dde1ea", stroke=GREY, stroke_width=1))
            body.append(label(at, -3.92, 51.2, "Exmoor coast", dy=-4))
        elif i == 1:
            body.append(shapes(operational, at, fill="none", stroke=GREY, stroke_width=0.8, stroke_dasharray="3 3"))
            body.append(shapes(bodies, at, fill=TEAL_LIGHT, stroke="#fff", stroke_width=0.6))
            bw, bs, be, bn = ESTUARY_LAND
            (x0, y0), (x1, y1) = at(bw, bn), at(be, bs)
            body.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                        f'fill="{AMBER}" fill-opacity="0.12" stroke="{AMBER}" stroke-width="1.4" stroke-dasharray="5 3"/>')
            body.append(label(at, be, bn, "estuary box", dx=4, dy=-4, anchor="start", colour=AMBER))
        else:
            body.append(shapes(neighbours, at, fill="none", stroke=GREY, stroke_width=0.8))
            body.append(shapes(outline, at, fill=TEAL, fill_opacity="0.85", stroke=TEAL, stroke_width=1))
            body.append(label(at, -4.22, 50.93, "Torridge", anchor="start"))
            body.append(label(at, -3.92, 51.2, "Exmoor coast", dy=-4))
            body.append(label(at, -3.62, 50.98, "Exe", anchor="start"))
        body.append(label(at, -4.058, 51.08, "Barnstaple", dx=-6, dy=-6, anchor="end", colour=TEXT, dot=True))
        parts.append(f'<g clip-path="url(#{clip})">{"".join(body)}</g>')
        parts.append(f'<text x="{ox}" y="{top - 30}" font-size="14" font-weight="600" fill="{TEXT}">{escape(titles[i])}</text>')
        parts.append(f'<text x="{ox}" y="{top + panel_h + 22:.0f}" font-size="11.5" fill="{SECONDARY}">'
                     + "".join(f'<tspan x="{ox}" dy="{0 if j == 0 else 15}">{escape(line)}</tspan>'
                               for j, line in enumerate(wrap(notes[i], 50))) + "</text>")
    return svg(width, height, "".join(parts),
               "How Floodwatch makes the River Taw’s catchment outline: the operational catchment, intersected "
               "with the Taw’s water bodies and a box round the estuary, shown among its neighbours")


def wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width and line:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line]


# ---------------------------------------------------------------- flow forecast

def scaled(days, ratio, now):
    """The forecast's mean flow as the popup draws it (site/js/stations.js,
    scaleForecast): the lowest flow so far multiplied by the ratio, and any
    rise from rain added at the model's own size."""
    out, base, last = [], None, None
    for t, mean, *_ in days:
        if t + 86400 <= now:
            last = mean
            continue
        start = base if base is not None else (last if last is not None else mean)
        base = min(start, mean)
        out.append((t, ratio * base + (mean - base)))
    return out


def flow_svg(data, now):
    days, measured, ratio = data["days"], data["measured"], data["anchor"]["ratio"]
    future = scaled(days, ratio, now)
    width, height, left, right, top, bottom = 1000, 396, 62, 214, 78, 48
    t0, t1 = days[0][0], days[-1][0] + 86400
    peak = max([v for _, v in future] + [v for _, v in measured] + [data["normal"]])
    step = 10 if peak <= 80 else 20
    hi = math.ceil(peak * 1.1 / step) * step
    x = lambda t: left + (t - t0) / (t1 - t0) * (width - left - right)  # noqa: E731
    y = lambda v: top + (1 - v / hi) * (height - top - bottom)  # noqa: E731
    noon = 43200

    parts = []
    for v in range(0, hi + 1, step):
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}"/>'
                     f'<text x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="11" fill="{SECONDARY}">{v}</text>')
    for t, *_ in days[::2]:
        label = time.strftime("%-d %b", time.gmtime(t))
        parts.append(f'<text x="{x(t + noon):.1f}" y="{height - bottom + 18}" text-anchor="middle" font-size="11" '
                     f'fill="{SECONDARY}">{label}</text>')
    parts.append(f'<text x="18" y="{top + (height - top - bottom) / 2:.0f}" font-size="11" fill="{SECONDARY}" '
                 f'transform="rotate(-90 18 {top + (height - top - bottom) / 2:.0f})" text-anchor="middle">flow, m³/s</text>')
    # Mean flow, and now.
    parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y(data["normal"]):.1f}" y2="{y(data["normal"]):.1f}" '
                 f'stroke="{GREY}" stroke-dasharray="2 3"/>')
    parts.append(f'<line x1="{x(now):.1f}" x2="{x(now):.1f}" y1="{top}" y2="{height - bottom}" stroke="{TEXT}" stroke-width="1"/>'
                 f'<text x="{x(now) + 5:.1f}" y="{top + 12}" font-size="11" fill="{TEXT}">now</text>')

    def line(pts, colour, w, dash=""):
        d = "M" + "L".join(f"{x(t):.1f},{y(v):.1f}" for t, v in pts)
        return f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{w}" stroke-linejoin="round"' + \
            (f' stroke-dasharray="{dash}"' if dash else "") + "/>"

    model = [(t + noon, mean) for t, mean, *_ in days]
    parts.append(line(model, AMBER, 1.6, "5 4"))
    parts.append(line(measured, BLUE, 2))
    parts.append(line([(t + noon, v) for t, v in future], AMBER, 3))
    a = data["anchor"]["day"] + noon
    am = next(mean for t, mean, *_ in days if t + noon == a)
    parts.append(f'<circle cx="{x(a):.1f}" cy="{y(am):.1f}" r="3.5" fill="{AMBER}"/>')

    keys = [(BLUE, "", "Measured at Umberleigh"), (AMBER, "5 4", "The model’s own flow"),
            (AMBER, "", f"Forecast, scaled ×{ratio:.3g}"), (GREY, "2 3", f"Mean flow, {data['normal']:g} m³/s")]
    for i, (colour, dash, text) in enumerate(keys):
        ky = top + 20 + i * 24
        kx = width - right + 16
        parts.append(f'<line x1="{kx}" x2="{kx + 22}" y1="{ky}" y2="{ky}" stroke="{colour}" stroke-width="{3 if i == 2 else 2}"'
                     + (f' stroke-dasharray="{dash}"' if dash else "") + "/>"
                     f'<text x="{kx + 28}" y="{ky + 4}" font-size="11" fill="{TEXT}">{escape(text)}</text>')
    when = time.strftime("%-d %B %Y", time.gmtime(now))
    anchor_day = time.strftime("%-d %B", time.gmtime(data["anchor"]["day"]))
    parts.append(f'<text x="{left}" y="26" font-size="14" font-weight="600" fill="{TEXT}">'
                 f'River Taw at Umberleigh, {escape(when)}</text>'
                 f'<text x="{left}" y="46" font-size="11.5" fill="{SECONDARY}">'
                 f'<tspan x="{left}">On {anchor_day} the model put the flow at {am:.1f} m³/s, and the gauge measured '
                 f'{am * ratio:.1f}. The forecast is scaled to start from the river as it is,</tspan>'
                 f'<tspan x="{left}" dy="15">and the rises the model expects from rain are added at their own size.</tspan></text>')
    return svg(width, height, "".join(parts),
               f"The River Taw’s flow at Umberleigh on {when}: the flow measured at the gauge, the GloFAS model’s "
               f"own flow, and its forecast scaled by {ratio:.3g} to start from the measured flow")


def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT}" role="img">'
            f'<title>{escape(title)}</title><rect width="100%" height="100%" rx="12" fill="{BG}"/>{body}</svg>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="https://tawriver.watch", help="the server to read the forecast from")
    args = ap.parse_args()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "catchment.svg").write_text(catchment_svg())
    print("wrote docs/catchment.svg")
    with urllib.request.urlopen(f"{args.url.rstrip('/')}/api/forecast/flow/50140", timeout=60) as r:
        data = json.loads(r.read())
    if not data.get("anchor"):
        sys.exit("the forecast has no anchor to scale by today; try again later")
    (DOCS / "flow-forecast.svg").write_text(flow_svg(data, time.time()))
    print("wrote docs/flow-forecast.svg")


if __name__ == "__main__":
    main()
