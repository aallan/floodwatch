#!/usr/bin/env python3
"""Draw the README's screenshot, docs/screenshot.png: the map in a Safari window.

Google Chrome, headless, captures the page from a running server at the size
of a 1250 x 768 point Safari window, the size of v1's screenshot, at which the
map opens at zoom 10 with the whole catchment beside the legend. A second pass
draws Safari's toolbar, rounded corners and the macOS window shadow around it,
on a transparent background, so it sits on GitHub's light and dark pages alike.

    make serve                         # in another terminal
    python3 scripts/screenshot.py
    python3 scripts/screenshot.py --url http://localhost:8090/ --wait 20

Standard library only.
"""

import argparse
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from og_image import CHROME  # noqa: E402

OUT = ROOT / "docs" / "screenshot.png"
WIDTH, HEIGHT = 1250, 768          # the page, in CSS pixels
TOOLBAR = 52                       # Safari's toolbar
MARGIN = (37, 56, 76, 56)          # top, right, bottom, left: room for the shadow, as macOS captures a window
SCALE = 1.5                        # device pixels per CSS pixel in the PNG
# Leaflet leaves hairline gaps between tiles at a fractional pixel ratio, so
# the page is captured at 2x and scaled down into the frame.
PAGE_SCALE = 2

ICON = 'fill="none" stroke="#6b6b6b" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'


def svg(w, h, body, extra=""):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" {extra}>{body}</svg>'


def frame(page_png, address):
    page = base64.b64encode(page_png).decode()
    top, right, bottom, left = MARGIN
    lights = "".join(f'<span style="background:{c};border-color:{b}"></span>'
                     for c, b in (("#ff5f57", "#e0443e"), ("#febc2e", "#dea123"), ("#28c840", "#1aab29")))
    sidebar = svg(22, 18, f'<rect x="1.5" y="2" width="19" height="14" rx="3" {ICON}/>'
                          f'<path d="M8 2v14" {ICON}/><path d="M3.8 5.5h2M3.8 8h2M3.8 10.5h2" {ICON} stroke-width="1.2"/>')
    chevron_down = svg(10, 10, f'<path d="M2 3.5l3 3 3-3" {ICON} stroke-width="1.4"/>')
    back = svg(12, 18, f'<path d="M9 2.5L3 9l6 6.5" {ICON} stroke="#545454" stroke-width="1.9"/>')
    forward = svg(12, 18, f'<path d="M3 2.5L9 9l-6 6.5" {ICON} stroke="#b4b4b4" stroke-width="1.9"/>')
    page_icon = svg(18, 16, f'<rect x="1.5" y="1.5" width="15" height="13" rx="2.5" {ICON} stroke-width="1.3"/>'
                            f'<path d="M4.5 5.5h9M4.5 8h6M4.5 10.5h7" {ICON} stroke-width="1.2"/>')
    reload = svg(16, 16, f'<path d="M13 8a5 5 0 1 1-1.6-3.7" {ICON} stroke-width="1.4"/>'
                         f'<path d="M12 1.8v3h-3" {ICON} stroke-width="1.4"/>')
    share = svg(18, 22, '<path d="M6 8H4.5a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 4.5 20h9'
                        f'a1.5 1.5 0 0 0 1.5-1.5v-9A1.5 1.5 0 0 0 13.5 8H12" {ICON}/>'
                        f'<path d="M9 13V2M5.5 5.3L9 1.8l3.5 3.5" {ICON}/>')
    plus = svg(18, 18, f'<path d="M9 2.5v13M2.5 9h13" {ICON} stroke-width="1.7"/>')
    tabs = svg(20, 20, f'<rect x="1.5" y="5.5" width="13" height="13" rx="2.5" {ICON}/>'
                       f'<path d="M5.5 3.5A2 2 0 0 1 7.5 1.5h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2" {ICON}/>')
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; background: transparent; }}
  body {{ padding: {top}px {right}px {bottom}px {left}px; width: {WIDTH}px;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', sans-serif; }}
  .window {{ border-radius: 12px; overflow: hidden; background: #fff;
    box-shadow: 0 0 0 0.5px rgba(0,0,0,0.28), 0 22px 48px rgba(0,0,0,0.30), 0 6px 14px rgba(0,0,0,0.12); }}
  .toolbar {{ height: {TOOLBAR}px; display: flex; align-items: center; padding: 0 16px 0 20px;
    background: #fbfbfb; border-bottom: 1px solid #dedede; position: relative; }}
  .lights {{ display: flex; gap: 8px; margin-right: 26px; }}
  .lights span {{ width: 12px; height: 12px; border-radius: 50%; box-sizing: border-box; border: 0.5px solid; }}
  .group {{ display: flex; align-items: center; gap: 4px; }}
  .group svg {{ display: block; }}
  .nav {{ display: flex; gap: 22px; margin-left: 24px; }}
  .address {{ position: absolute; left: 50%; transform: translateX(-50%); width: 492px; height: 30px;
    border-radius: 8px; background: #fff; border: 1px solid #e3e3e3; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center; font-size: 13.5px; color: #262626; }}
  .address .page {{ position: absolute; left: 10px; top: 6px; }}
  .address .reload {{ position: absolute; right: 10px; top: 6px; }}
  .right {{ margin-left: auto; display: flex; align-items: center; gap: 24px; }}
  .content {{ display: block; image-rendering: auto; width: {WIDTH}px; height: {HEIGHT}px; }}
</style></head><body>
<div class="window">
  <div class="toolbar">
    <div class="lights">{lights}</div>
    <div class="group">{sidebar}{chevron_down}</div>
    <div class="nav">{back}{forward}</div>
    <div class="address"><span class="page">{page_icon}</span>{address}<span class="reload">{reload}</span></div>
    <div class="right">{share}{plus}{tabs}</div>
  </div>
  <img class="content" src="data:image/png;base64,{page}">
</div>
</body></html>"""


def chrome(binary, tmp, url, size, out, scale, wait_ms=0):
    # The GPU stays on: headless Chrome lays the page out 87 px short of the
    # window, then grows it, and without the GPU it never draws a map tile
    # that was offscreen before the page grew.
    args = [binary, "--headless", "--hide-scrollbars", f"--force-device-scale-factor={scale}",
            f"--user-data-dir={Path(tmp) / 'profile'}", "--use-mock-keychain", "--no-first-run",
            "--default-background-color=00000000", f"--window-size={size[0]},{size[1]}", f"--screenshot={out}"]
    if wait_ms:
        # Time for live.json, the overlays and the basemap tiles to arrive, in
        # real time: a virtual time budget doesn't wait for the tiles.
        args.append(f"--timeout={wait_ms}")
    subprocess.run(args + [url], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8090/", help="the running site (default %(default)s)")
    ap.add_argument("--address", default="tawriver.watch", help="what the address bar shows (default %(default)s)")
    ap.add_argument("--wait", type=float, default=15, help="seconds to let the page load (default %(default)s)")
    args = ap.parse_args()
    binary = next((c for c in CHROME if Path(c).exists() or __import__("shutil").which(c)), None)
    if not binary:
        sys.exit("Google Chrome or Chromium is needed to take the screenshot")
    with tempfile.TemporaryDirectory() as tmp:
        shot = Path(tmp) / "page.png"
        chrome(binary, tmp, args.url, (WIDTH, HEIGHT), shot, PAGE_SCALE, int(args.wait * 1000))
        card = Path(tmp) / "frame.html"
        card.write_text(frame(shot.read_bytes(), args.address))
        top, right, bottom, left = MARGIN
        chrome(binary, tmp, card.as_uri(), (left + WIDTH + right, top + TOOLBAR + 1 + HEIGHT + bottom), OUT, SCALE)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
