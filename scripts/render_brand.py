#!/usr/bin/env python3
"""Render the Home Assistant brands assets for this integration.

Rasterizes the locked Layered Logic primary mark into transparent-background
PNGs (icon / icon@2x / logo / logo@2x) under custom_components/.../brand/, as
required by the HACS brands check. Geometry is copied verbatim from the canonical
rest-pose SVG (Independent_Study/assets/brand/logo/logo-primary-dark.svg, params
2026-04-21) so this does NOT redesign the logo — it only re-rasterizes it.

    pip install pillow
    python scripts/render_brand.py            # write brand assets
    python scripts/render_brand.py --preview C:/path/to/preview.png

Requires only Pillow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# Two nested L's, straight stroke segments, round caps (from logo-primary-dark.svg).
OUTER = [((22.32, -319.22), (0.0, 0.0)), ((0.0, 0.0), (220.0, 0.0))]
INNER = [((40.05, -305.91), (19.95, -18.60)), ((19.95, -18.60), (199.95, -18.60))]
SEGS = [(OUTER, 7, (0x4A, 0x25, 0xFF)), (INNER, 6, (0x32, 0x14, 0xFF))]
SS = 4  # supersample factor for anti-aliasing


def render(size: int, pad_frac: float = 0.10) -> Image.Image:
    s = size * SS
    pts = [p for lines, _, _ in SEGS for seg in lines for p in seg]
    maxr = max(w for _, w, _ in SEGS) / 2
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs) - maxr, max(xs) + maxr
    miny, maxy = min(ys) - maxr, max(ys) + maxr
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    scale = (s * (1 - 2 * pad_frac)) / max(maxx - minx, maxy - miny)

    def tf(p):
        return (s / 2 + (p[0] - cx) * scale, s / 2 + (p[1] - cy) * scale)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for lines, w, c in SEGS:
        wr = w * scale
        col = c + (255,)
        r = wr / 2
        for p, q in lines:
            a, b = tf(p), tf(q)
            d.line([a, b], fill=col, width=max(1, round(wr)))
            for e in (a, b):  # round caps + corner join
                d.ellipse([e[0] - r, e[1] - r, e[0] + r, e[1] + r], fill=col)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="also write a light/dark preview PNG here")
    args = ap.parse_args()

    brand = (
        Path(__file__).resolve().parent.parent
        / "custom_components" / "layered_logic_mirror" / "brand"
    )
    brand.mkdir(parents=True, exist_ok=True)

    icon256, icon512 = render(256), render(512)
    icon256.save(brand / "icon.png")
    icon512.save(brand / "icon@2x.png")
    icon256.save(brand / "logo.png")
    icon512.save(brand / "logo@2x.png")
    print(f"wrote icon.png/icon@2x.png/logo.png/logo@2x.png to {brand}")

    if args.preview:
        pad = 48
        tile = 256
        canvas = Image.new("RGBA", (tile * 2 + pad * 3, tile + pad * 2), (255, 255, 255, 0))
        # dark swatch
        dark = Image.new("RGBA", (tile, tile), (0x0A, 0x0A, 0x0A, 255))
        dark.alpha_composite(render(tile))
        canvas.alpha_composite(dark, (pad, pad))
        # light swatch
        light = Image.new("RGBA", (tile, tile), (0xF4, 0xEF, 0xE6, 255))
        light.alpha_composite(render(tile))
        canvas.alpha_composite(light, (pad * 2 + tile, pad))
        canvas.convert("RGB").save(args.preview)
        print(f"wrote preview to {args.preview}")


if __name__ == "__main__":
    main()
