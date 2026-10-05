"""The link-preview image LinkedIn, Slack and others show for trevorvaughan.dev.

Drawn on request from live data (cached for ten minutes), on top of a base map that
was rendered once with the same Natural Earth projection the website uses.
"""

import io
import math
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).parent / "assets"
W, H = 1200, 630
# Projection of og-base.png: d3.geoNaturalEarth1().fitExtent([[330,70],[1230,700]], sphere)
SCALE, TX, TY = 164.51067966315125, 780.0, 385.0

PAPER = (243, 246, 245)
INK = (20, 35, 47)
INK_2 = (62, 80, 92)
SIGNAL = (214, 40, 57)
HOME = (31, 95, 191)
PANEL = (255, 255, 255)
RULE = (195, 208, 213)

_cache: dict[str, tuple[float, bytes]] = {}
CACHE_SECONDS = 600


def project(lon: float, lat: float) -> tuple[float, float]:
    """Natural Earth I, the same formula as d3-geo's geoNaturalEarth1."""
    lam, phi = math.radians(lon), math.radians(lat)
    p2 = phi * phi
    p4 = p2 * p2
    x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return TX + SCALE * x, TY - SCALE * y


def _font(size: int, weight: int = 400, width: int = 100) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(ASSETS / "Archivo.ttf"), size)
    try:
        f.set_variation_by_axes([weight, width])
    except (OSError, ValueError):
        pass
    return f


def render(summary: dict, points: list[dict], server: tuple[float, float]) -> bytes:
    img = Image.open(ASSETS / "og-base.png").convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    biggest = max([p["count"] for p in points] or [1])
    for p in sorted(points, key=lambda p: -p["count"]):
        x, y = project(p["lon"], p["lat"])
        r = 3 + 11 * math.sqrt(p["count"] / biggest)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*SIGNAL, 150), outline=(251, 252, 251, 255))

    hx, hy = project(server[1], server[0])
    d.ellipse((hx - 14, hy - 14, hx + 14, hy + 14), outline=(*HOME, 255), width=3)
    d.ellipse((hx - 6, hy - 6, hx + 6, hy + 6), fill=(*HOME, 255))

    # Left column fades the map out so the text stays readable
    fade = Image.new("L", (W, H))
    fd = ImageDraw.Draw(fade)
    for x in range(0, 520):
        fd.line([(x, 0), (x, H)], fill=int(255 * min(1, max(0, (500 - x) / 160))))
    img.paste(Image.new("RGB", (W, H), PAPER), (0, 0), fade)
    d = ImageDraw.Draw(img, "RGBA")

    d.text((64, 62), "Who's knocking?", font=_font(68, 850, 112), fill=INK)
    d.text(
        (66, 152),
        "Live: bots breaking into my server,\nand what they do once inside",
        font=_font(30, 450, 95),
        fill=INK_2,
        spacing=8,
    )

    n, ips, countries = summary["attempts"], summary["ips"], summary["countries"]
    if n:
        rows = [
            (f"{n:,}", "login attempts"),
            (f"{ips:,}", "machines"),
            (f"{countries}", "countries"),
        ]
        y = 292
        d.text((66, y), "In the last 24 hours", font=_font(24, 500), fill=INK_2)
        y += 42
        for value, label in rows:
            d.text((64, y), value, font=_font(62, 900, 120), fill=SIGNAL)
            vw = d.textlength(value, font=_font(62, 900, 120))
            d.text((64 + vw + 14, y + 26), label, font=_font(28, 500), fill=INK)
            y += 74
    else:
        d.text(
            (66, 320), "Watching for the first\nattack right now", font=_font(40, 700), fill=SIGNAL
        )

    d.line([(0, H - 6), (W, H - 6)], fill=SIGNAL, width=12)
    d.text((W - 64, H - 46), "trevorvaughan.dev", font=_font(26, 650, 105), fill=INK, anchor="rs")

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def cached(key: str, make) -> bytes:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    data = make()
    _cache[key] = (time.time(), data)
    return data
