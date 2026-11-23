#!/usr/bin/env python3
"""Draw the site's Open Graph image, site/img/og-image.png (1200 x 630).

The card is HTML, with the catchment's outline and rivers drawn as SVG from the
map's own overlays in site/data/, so run `make data` first. Google Chrome,
headless, renders it to a PNG.

    python3 scripts/og_image.py
    python3 scripts/og_image.py --html card.html   # write the HTML only

Standard library only.
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from monitor.geo import simplify  # noqa: E402

DATA = ROOT / "site" / "data"
OUT = ROOT / "site" / "img" / "og-image.png"
WIDTH, HEIGHT = 1200, 630
MAP_BOX = (640, 36, 1150, 452)   # left, top, right, bottom
CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]

# The site's colours (site/css/style.css): the light page, the slate header,
# Floodwatch's teal, and each layer's own colour.
BG, TEXT, SECONDARY, ACCENT = "#eceef2", "#2c3345", "#5d6782", "#1a8a7d"
WATER = "#7fa9c9"
RIVER_COLOURS = {"River Taw": "#1a8a7d", "River Mole": "#2e7dab", "River Bray": "#b5476e", "Little Dart River": "#8a6e1a",
                 "River Yeo": "#7a4a8a", "Lapford Yeo": "#ab5e2e", "Crooked Oak": "#5a8a3a",
                 "Hollocombe Water": "#6a7a3a"}
BANDS = [("River levels", "#1a8a7d"), ("Rain", "#4f6fc0"),
         ("Flood warnings", "#c9a227"), ("Storm overflows", "#5b2a8a")]


def mercator(lon, lat):
    return lon, math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def lines(fc, keep=lambda f: True):
    """Every ring and line in a FeatureCollection's features, as lists of (lon, lat)."""
    for f in fc["features"]:
        if not keep(f):
            continue
        g = f["geometry"]
        parts = {"Polygon": lambda c: c, "MultiPolygon": lambda c: [r for p in c for r in p],
                 "LineString": lambda c: [c], "MultiLineString": lambda c: c}[g["type"]](g["coordinates"])
        yield from parts


def svg_map(boundary, rivers):
    rings = [[mercator(*p[:2]) for p in r] for r in lines(boundary)]
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    left, top, right, bottom = MAP_BOX
    scale = min((right - left) / (max(xs) - min(xs)), (bottom - top) / (max(ys) - min(ys)))
    w, h = (max(xs) - min(xs)) * scale, (max(ys) - min(ys)) * scale
    ox, oy = left + (right - left - w) / 2, top + (bottom - top - h) / 2

    def path(pts, closed):
        pts = simplify([(ox + (x - min(xs)) * scale, oy + (max(ys) - y) * scale) for x, y in pts], 0.5)
        if len(pts) < 2:
            return ""
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + ("Z" if closed else "")

    land = "".join(path(r, True) for r in rings)

    def river_paths(keep, colour, width):
        d = "".join(path([mercator(*p[:2]) for p in ln], False) for ln in lines(rivers, keep))
        return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
                'stroke-linecap="round" stroke-linejoin="round"/>')
    # Other rivers first, thin and pale; then the coloured ones over them.
    water = river_paths(lambda f: f["properties"].get("name") not in RIVER_COLOURS, WATER, 1.5)
    water += "".join(river_paths(lambda f, n=name: f["properties"].get("name") == n, colour, 3.2)
                     for name, colour in RIVER_COLOURS.items())
    return (f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
            f'<path d="{land}" fill="#ffffff" stroke="{SECONDARY}" stroke-width="1.5" stroke-linejoin="round" '
            f'fill-rule="evenodd"/>{water}</svg>')


def html(boundary, rivers):
    bands = "".join(f'<div style="background:{c}">{name}</div>' for name, c in BANDS)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden; background: {BG}; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; color: {TEXT}; position: relative; }}
  .map {{ position: absolute; inset: 0; }}
  .text {{ position: absolute; left: 80px; top: 112px; width: 600px; }}
  .kicker {{ font-size: 21px; letter-spacing: 0.16em; text-transform: uppercase; color: {SECONDARY}; }}
  h1 {{ font-size: 76px; font-weight: 650; letter-spacing: -0.02em; margin: 26px 0 22px; line-height: 1; }}
  h1 span {{ color: {ACCENT}; }}
  p {{ font-size: 29px; line-height: 1.35; margin: 0; color: {SECONDARY}; }}
  .bands {{ position: absolute; left: 0; right: 0; bottom: 0; height: 150px;
    display: grid; grid-template-columns: repeat({len(BANDS)}, 1fr); }}
  .bands div {{ display: flex; align-items: center; justify-content: center; color: #fff;
    font-size: 19px; letter-spacing: 0.16em; text-transform: uppercase; }}
</style></head><body>
<div class="map">{svg_map(boundary, rivers)}</div>
<div class="text">
  <div class="kicker">Floodwatch · River Taw</div>
  <h1>tawriver<span>.</span>watch</h1>
  <p>River levels, rain, flood warnings and storm overflows across the Taw catchment, live.</p>
</div>
<div class="bands">{bands}</div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--html", type=Path, help="write the card's HTML here and stop")
    args = ap.parse_args()
    try:
        boundary = json.loads((DATA / "catchment.geojson").read_text())
        rivers = json.loads((DATA / "rivers.geojson").read_text())
    except FileNotFoundError as e:
        sys.exit(f"{e.filename} is missing; run `make data` first")
    page = html(boundary, rivers)
    if args.html:
        args.html.write_text(page)
        return
    chrome = next((c for c in CHROME if Path(c).exists() or shutil.which(c)), None)
    if not chrome:
        sys.exit("Google Chrome or Chromium is needed to render the PNG; use --html to write the card only")
    with tempfile.TemporaryDirectory() as tmp:
        card = Path(tmp) / "card.html"
        card.write_text(page)
        # A throwaway profile and a stand-in keychain, so Chrome leaves the
        # user's own profile and keychain alone and asks for nothing.
        subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--user-data-dir={Path(tmp) / 'profile'}", "--use-mock-keychain", "--no-first-run",
                        f"--window-size={WIDTH},{HEIGHT}", f"--screenshot={OUT}", card.as_uri()],
                       check=True, capture_output=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
