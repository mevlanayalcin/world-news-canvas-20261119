#!/usr/bin/env python3
"""Build the 1024x1024 editorial front page (entry.png) and audit previews.

Rendering uses Playwright driving the system Chrome; Pillow then encodes the
screenshot as a 4:4:4 JPEG (baseline, optimised) so coloured type stays sharp
at a fraction of the PNG size. Build-time tooling only: the shipped runtime
(main.py) is standard library only.
"""

import io
import math
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "entry.png"
HTML_PATH = Path("/tmp/world_news_canvas.html")
RAW_PNG = Path("/tmp/world_news_canvas_raw.png")
PREVIEW_300 = Path("/tmp/news_v2_300.png")
PREVIEW_600 = Path("/tmp/news_v2_600.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITY = 92
JPEG_TARGET = 352000

HERO_W, HERO_H = 289, 104
MID_W, MID_H = 291, 74
LOW_W, LOW_H = 291, 60


# ---------------------------------------------------------------- svg helpers

def n(v):
    """Compact numeric literal for SVG attributes."""
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def svg(w, h, body):
    return (
        '<svg viewBox="0 0 %d %d" preserveAspectRatio="none"'
        ' xmlns="http://www.w3.org/2000/svg">%s</svg>' % (w, h, body)
    )


def t(x, y, s, size, fill, weight=900, anchor="start", ls=0.0, opacity=None):
    attrs = ""
    if anchor != "start":
        attrs += ' text-anchor="%s"' % anchor
    if opacity is not None:
        attrs += ' opacity="%s"' % n(opacity)
    return (
        '<text x="%s" y="%s"%s font-family="Lato" font-size="%s" font-weight="%s"'
        ' letter-spacing="%s" fill="%s">%s</text>'
        % (n(x), n(y), attrs, n(size), weight, n(ls), fill, s)
    )


def star(cx, cy, r):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append("%.2f,%.2f" % (cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return "M" + " L".join(pts) + " Z"


def flag_us(cx, cy, r, cid):
    w = h = 2 * r
    x0, y0 = cx - r, cy - r
    stripes = "".join(
        '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>'
        % (n(x0), n(y0 + i * h / 7), n(w), n(h / 7 + 0.2),
           "#b3261e" if i % 2 == 0 else "#f4f1e8")
        for i in range(7)
    )
    stars = "".join(
        '<circle cx="%s" cy="%s" r="%s" fill="#f4f1e8"/>'
        % (n(x0 + w * 0.45 * (c + 1) / 4), n(y0 + h * 0.5 * (rr + 1) / 4), n(max(0.55, r * 0.065)))
        for rr in range(3) for c in range(3)
    )
    return (
        '<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>'
        % (cid, n(cx), n(cy), n(r))
        + '<g clip-path="url(#%s)">' % cid
        + '<rect x="%s" y="%s" width="%s" height="%s" fill="#f4f1e8"/>' % (n(x0), n(y0), n(w), n(h))
        + stripes
        + '<rect x="%s" y="%s" width="%s" height="%s" fill="#1f3a6e"/>'
        % (n(x0), n(y0), n(w * 0.45), n(h * 0.5))
        + stars
        + "</g>"
    )


def flag_cn(cx, cy, r, cid):
    w = h = 2 * r
    x0, y0 = cx - r, cy - r
    return (
        '<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>'
        % (cid, n(cx), n(cy), n(r))
        + '<g clip-path="url(#%s)">' % cid
        + '<rect x="%s" y="%s" width="%s" height="%s" fill="#c8322b"/>' % (n(x0), n(y0), n(w), n(h))
        + '<path d="%s" fill="#f2c94c"/>' % star(x0 + w * 0.28, y0 + h * 0.3, r * 0.36)
        + '<path d="%s" fill="#f2c94c"/>' % star(x0 + w * 0.54, y0 + h * 0.16, r * 0.13)
        + '<path d="%s" fill="#f2c94c"/>' % star(x0 + w * 0.63, y0 + h * 0.31, r * 0.13)
        + '<path d="%s" fill="#f2c94c"/>' % star(x0 + w * 0.63, y0 + h * 0.48, r * 0.13)
        + '<path d="%s" fill="#f2c94c"/>' % star(x0 + w * 0.54, y0 + h * 0.62, r * 0.13)
        + "</g>"
    )


def flag_ru(cx, cy, r, cid):
    w = h = 2 * r
    x0, y0 = cx - r, cy - r
    return (
        '<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>'
        % (cid, n(cx), n(cy), n(r))
        + '<g clip-path="url(#%s)">' % cid
        + '<rect x="%s" y="%s" width="%s" height="%s" fill="#f4f1e8"/>' % (n(x0), n(y0), n(w), n(h / 3))
        + '<rect x="%s" y="%s" width="%s" height="%s" fill="#2b4c8c"/>' % (n(x0), n(y0 + h / 3), n(w), n(h / 3))
        + '<rect x="%s" y="%s" width="%s" height="%s" fill="#c8322b"/>' % (n(x0), n(y0 + 2 * h / 3), n(w), n(h / 3))
        + "</g>"
    )


def dot_map(polys, lon_range, lat_range, box, step, r, fill):
    """Fill lon/lat polygons with a crisp dot matrix (stylised landmass)."""
    lx0, lx1 = lon_range
    ly0, ly1 = lat_range
    bx, by, bw, bh = box

    def project(lon, lat):
        return (
            bx + (lon - lx0) / (lx1 - lx0) * bw,
            by + (ly1 - lat) / (ly1 - ly0) * bh,
        )

    rings = [[project(lo, la) for lo, la in poly] for poly in polys]

    def covered(x, y):
        for pts in rings:
            inside = False
            j = len(pts) - 1
            for i in range(len(pts)):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                return True
        return False

    out = []
    y = by + step * 0.6
    while y < by + bh:
        x = bx + step * 0.6
        while x < bx + bw:
            if covered(x, y):
                out.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (n(x), n(y), n(r), fill))
            x += step
        y += step
    return "".join(out)


AFRICA_POLY = [
    (-17, 21), (-16, 14), (-13, 9), (-8, 4.5), (-2, 5), (3, 6), (9, 4), (9, 0),
    (12, -5), (13, -17), (15, -28), (18, -34), (22, -34.5), (27, -33), (32, -28),
    (35, -24), (40, -16), (41, -11), (40, -3), (43, 0), (51, 11), (45, 12),
    (43, 11), (38, 17), (37, 22), (34, 28), (32, 31), (25, 32), (18, 30),
    (11, 33), (10, 37), (-6, 36), (-9, 32), (-13, 28),
]

MADAGASCAR_POLY = [
    (43.5, -12.5), (49.6, -15.2), (50.2, -19), (47.4, -25), (45.2, -25.2),
    (43.8, -21), (43.0, -16),
]


# ------------------------------------------------------------- hero drawings

def art_summit():
    body = (
        '<defs>'
        '<radialGradient id="gSummit" cx="50%" cy="42%" r="72%">'
        '<stop offset="0%" stop-color="#1c2c48"/><stop offset="100%" stop-color="#0a1220"/>'
        '</radialGradient>'
        '</defs>'
        f'<rect width="{HERO_W}" height="{HERO_H}" fill="url(#gSummit)"/>'
        '<g stroke="#ffffff" stroke-opacity=".08" fill="none">'
        '<ellipse cx="144" cy="40" rx="88" ry="33"/>'
        '<ellipse cx="144" cy="40" rx="34" ry="33"/>'
        '<line x1="56" y1="40" x2="232" y2="40"/>'
        '<line x1="62" y1="20" x2="226" y2="20"/>'
        '</g>'
        + flag_us(52, 32, 21, "sUS")
        + flag_cn(144, 32, 22, "sCN")
        + flag_ru(236, 32, 21, "sRU")
        + '<line x1="75" y1="32" x2="120" y2="32" stroke="#d9a441" stroke-width="1.2" stroke-dasharray="2 3"/>'
        '<line x1="168" y1="32" x2="213" y2="32" stroke="#d9a441" stroke-width="1.2" stroke-dasharray="2 3"/>'
        '<circle cx="52" cy="32" r="21" fill="none" stroke="#d9a441" stroke-width="1.6"/>'
        '<circle cx="144" cy="32" r="22" fill="none" stroke="#f2c94c" stroke-width="2"/>'
        '<circle cx="236" cy="32" r="21" fill="none" stroke="#d9a441" stroke-width="1.6"/>'
        + t(52, 64, "USA", 7.6, "#cbb27a", 700, "middle", 1.7)
        + t(144, 64, "CHINA", 7.6, "#e8cf8c", 700, "middle", 1.7)
        + t(236, 64, "RUSSIA", 7.6, "#cbb27a", 700, "middle", 1.7)
        + '<ellipse cx="144" cy="82" rx="74" ry="8" fill="#16233a" stroke="#38527a" stroke-width="1"/>'
        '<ellipse cx="144" cy="82" rx="60" ry="5" fill="none" stroke="#2a4166" stroke-width=".8"/>'
        + t(144, 100, "SHENZHEN &#183; APEC SUMMIT", 6.4, "#8ba0bd", 700, "middle", 2.0)
    )
    return svg(HERO_W, HERO_H, body)


def art_ipo():
    candles = []
    data = [(156, 70, 12, "#1f8a5b"), (178, 64, 14, "#1f4e8c"),
            (200, 56, 16, "#1f8a5b"), (222, 46, 18, "#1f4e8c"),
            (244, 38, 16, "#1f8a5b"), (266, 26, 20, "#1f4e8c")]
    for x, top, h, col in data:
        candles.append('<line x1="%d" y1="%s" x2="%d" y2="%s" stroke="%s" stroke-width="1.3"/>'
                       % (x, n(top - 5), x, n(top + h + 5), col))
        candles.append('<rect x="%s" y="%s" width="9" height="%s" fill="%s"/>'
                       % (n(x - 4.5), n(top), n(h), col))
    body = (
        '<defs><linearGradient id="gIpo" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#f2f7fd"/><stop offset="100%" stop-color="#e2ebf7"/>'
        '</linearGradient></defs>'
        f'<rect width="{HERO_W}" height="{HERO_H}" fill="url(#gIpo)"/>'
        '<g stroke="#cddbeb" stroke-width="1">'
        '<line x1="146" y1="22" x2="284" y2="22"/><line x1="146" y1="44" x2="284" y2="44"/>'
        '<line x1="146" y1="66" x2="284" y2="66"/><line x1="146" y1="88" x2="284" y2="88"/>'
        '</g>'
        '<line x1="134" y1="8" x2="134" y2="98" stroke="#c3d4e6" stroke-width="1"/>'
        + t(10, 46, "$1.5T", 42, "#173d6b", 900, "start", -1.6)
        + t(11, 58, "ANTHROPIC'S IPO", 7.2, "#33587c", 900, "start", 1.3)
        + t(11, 68, "NASDAQ &#183; ANT &#183; $83/SHARE", 6.6, "#5a7796", 900, "start", 0.9)
        + t(11, 79, "RAISES $81BN", 7.2, "#b3261e", 900, "start", 1.5)
        + "".join(candles)
        + '<line x1="150" y1="88" x2="277" y2="28" stroke="#173d6b" stroke-width="2.2"/>'
        '<path d="M277 28 L265 30 L269 39 Z" fill="#173d6b"/>'
        '<rect x="166" y="3" width="96" height="15" rx="2" fill="#173d6b"/>'
        + t(214, 13.6, "LARGEST IPO EVER", 6.6, "#f2e6c8", 900, "middle", 1.2)
    )
    return svg(HERO_W, HERO_H, body)


def art_voyager():
    stars = [(14, 12, 1.1), (27, 22, 0.8), (43, 10, 1.2), (58, 19, 0.9), (74, 11, 1.0),
             (92, 23, 0.8), (108, 10, 1.1), (123, 19, 0.9), (140, 9, 1.2), (158, 17, 0.8),
             (172, 24, 1.0), (188, 12, 0.9), (204, 20, 1.1), (221, 9, 0.8), (236, 19, 1.0),
             (272, 14, 1.1), (283, 26, 0.8), (20, 34, 0.9), (264, 60, 1.0), (274, 46, 0.8),
             (12, 50, 1.0), (99, 62, 0.8), (184, 56, 0.9), (208, 50, 0.8), (46, 60, 0.7),
             (150, 68, 0.8), (254, 78, 0.9)]
    body = (
        f'<rect width="{HERO_W}" height="{HERO_H}" fill="#070c18"/>'
        + "".join('<circle cx="%d" cy="%d" r="%.1f" fill="#cfe6f5" opacity=".7"/>' % s
                  for s in stars)
        + '<circle cx="30" cy="62" r="13" fill="none" stroke="#7fd1e8" stroke-opacity=".22"/>'
        '<circle cx="30" cy="62" r="10.5" fill="#1f6f9e"/>'
        '<path d="M22 59 Q27 52 31 57 Q35 53 38 60 Q36 67 30 68 Q23 67 22 59 Z" fill="#2f8a5c"/>'
        '<path d="M42 64 C96 68 168 60 230 32" fill="none" stroke="#7fd1e8" stroke-width="1.2"'
        ' stroke-dasharray="2 4" opacity=".85"/>'
        '<g transform="translate(238,28) rotate(-18)">'
        '<ellipse cx="0" cy="0" rx="9" ry="5" fill="#d9c9a0" stroke="#f2e6c8" stroke-width="0.8"/>'
        '<line x1="-2" y1="0" x2="-13" y2="0" stroke="#d9c9a0" stroke-width="1"/>'
        '<line x1="0" y1="4" x2="0" y2="12" stroke="#d9c9a0" stroke-width="1"/>'
        '<rect x="-3.5" y="4" width="7" height="5" fill="#bfae86"/>'
        '<line x1="6" y1="-2" x2="14" y2="-8" stroke="#d9c9a0" stroke-width="1"/>'
        '</g>'
        + t(62, 31, "1 LIGHT-DAY", 24, "#f2e6c8", 900, "start", 0.2)
        + t(63, 42, "25.9 BILLION KM FROM EARTH", 7, "#8fa6bd", 700, "start", 1.1)
        + t(63, 52, "EMPIRE STATE GLOWS GOLD", 6.4, "#d9a441", 900, "start", 1.0)
        + '<line x1="16" y1="90" x2="274" y2="90" stroke="#3b4a5e" stroke-width="1"/>'
        '<g stroke="#3b4a5e" stroke-width="1">'
        '<line x1="16" y1="86" x2="16" y2="94"/><line x1="80" y1="87" x2="80" y2="93"/>'
        '<line x1="144" y1="87" x2="144" y2="93"/><line x1="208" y1="87" x2="208" y2="93"/>'
        '<line x1="274" y1="86" x2="274" y2="94"/>'
        '</g>'
        + t(16, 102, "EARTH", 6.2, "#8fa6bd", 700, "start", 1.0)
        + t(145, 102, "49 YEARS", 6.2, "#8fa6bd", 700, "middle", 1.0)
        + t(274, 102, "VOYAGER 1", 6.2, "#8fa6bd", 700, "end", 1.0)
    )
    return svg(HERO_W, HERO_H, body)


# ------------------------------------------------------------- mid drawings

def art_climate():
    lines = "".join(
        '<rect x="12" y="%d" width="%d" height="2" fill="#ddd0b8"/>' % (14 + i * 6, [52, 40, 46, 34][i])
        for i in range(4)
    )
    smoke = "".join(
        '<circle cx="%d" cy="%d" r="%d" fill="#c9b89c" opacity=".7"/>' % (x, y, r)
        for x, y, r in [(140, 17, 4), (145, 10, 4.5), (151, 5, 4), (160, 6, 3.5)]
    )
    ticks = "".join(
        '<line x1="228" y1="%d" x2="233" y2="%d" stroke="#b9a98c" stroke-width="1"/>' % (12 + i * 8, 12 + i * 8)
        for i in range(5)
    )
    body = (
        f'<rect width="{MID_W}" height="{MID_H}" fill="#f6ecda"/>'
        # draft document
        '<path d="M6 6 H86 L100 20 V70 H6 Z" fill="#fffdf7" stroke="#c2b49a" stroke-width="1"/>'
        '<path d="M86 6 V20 H100" fill="#ece1cb" stroke="#c2b49a" stroke-width="1"/>'
        + lines
        + t(12, 44, "FOSSIL", 10, "#8a7a64", 900, "start", 0.4)
        + t(12, 57, "FUELS", 10, "#8a7a64", 900, "start", 0.4)
        + '<line x1="10" y1="38" x2="52" y2="61" stroke="#b3261e" stroke-width="2.6"/>'
        '<rect x="74" y="26" width="22" height="11" fill="#b3261e"/>'
        + t(85, 34, "9 PP.", 6.2, "#fffdf7", 900, "middle", 0.6)
        # factory, transition struck out
        + smoke
        + '<rect x="146" y="36" width="12" height="30" fill="#9a8a74"/>'
        '<rect x="163" y="28" width="14" height="38" fill="#8a7a64"/>'
        '<rect x="145" y="34" width="14" height="3" fill="#c9b89c"/>'
        '<rect x="162" y="26" width="16" height="3" fill="#c9b89c"/>'
        '<circle cx="160" cy="48" r="24" fill="none" stroke="#b3261e" stroke-width="3"/>'
        '<line x1="143" y1="31" x2="177" y2="65" stroke="#b3261e" stroke-width="3"/>'
        # thermometer
        '<g>'
        '<rect x="236" y="10" width="9" height="44" rx="4.5" fill="#fffdf7" stroke="#c2b49a" stroke-width="1"/>'
        '<rect x="238.5" y="26" width="4" height="30" rx="2" fill="#b3261e"/>'
        '<circle cx="240.5" cy="61" r="9" fill="#b3261e" stroke="#8a1a14" stroke-width="1"/>'
        + ticks
        + '</g>'
        + t(178, 72, "NO PHASE-OUT", 6.2, "#8a5a12", 900, "middle", 1.0)
    )
    return svg(MID_W, MID_H, body)


def art_icj():
    body = (
        f'<rect width="{MID_W}" height="{MID_H}" fill="#e8edf3"/>'
        '<g>'
        '<rect x="34" y="63" width="62" height="4" rx="1" fill="#1f3f6e"/>'
        '<rect x="63" y="12" width="4" height="52" fill="#1f3f6e"/>'
        '<circle cx="65" cy="9" r="3" fill="#c8a24a"/>'
        '<rect x="14" y="14" width="102" height="2.6" fill="#1f3f6e"/>'
        '<rect x="14" y="14" width="10" height="2.6" fill="#c8a24a"/>'
        '<rect x="106" y="14" width="10" height="2.6" fill="#c8a24a"/>'
        '<line x1="19" y1="16" x2="19" y2="31" stroke="#1f3f6e" stroke-width="1"/>'
        '<line x1="29" y1="16" x2="19" y2="31" stroke="#1f3f6e" stroke-width="1"/>'
        '<line x1="101" y1="16" x2="101" y2="31" stroke="#1f3f6e" stroke-width="1"/>'
        '<line x1="111" y1="16" x2="101" y2="31" stroke="#1f3f6e" stroke-width="1"/>'
        '<path d="M7 31 Q19 45 31 31 Z" fill="#1f3f6e"/>'
        '<path d="M89 31 Q101 45 113 31 Z" fill="#1f3f6e"/>'
        '</g>'
        '<g transform="translate(160,18) rotate(-20)">'
        '<rect x="0" y="0" width="30" height="10" rx="2" fill="#8a6a3a"/>'
        '<rect x="-6" y="-2" width="6" height="14" rx="2" fill="#c8a24a"/>'
        '<rect x="30" y="-2" width="6" height="14" rx="2" fill="#c8a24a"/>'
        '<rect x="11" y="10" width="7" height="24" rx="2" fill="#8a6a3a"/>'
        '</g>'
        '<rect x="170" y="52" width="44" height="7" rx="2" fill="#1f3f6e"/>'
        '<g transform="translate(214,42) rotate(-8)">'
        '<rect x="0" y="0" width="66" height="22" fill="none" stroke="#b3261e" stroke-width="2"/>'
        + t(33, 15.4, "GUILTY", 11, "#b3261e", 900, "middle", 1.6)
        + '</g>'
        + t(14, 72, "THE HAGUE &#183; ICJ", 6.2, "#4a5f78", 900, "start", 1.8)
    )
    return svg(MID_W, MID_H, body)


def art_mideast():
    body = (
        f'<rect width="{MID_W}" height="{MID_H}" fill="#f7e7dc"/>'
        '<g stroke="#d8b9a2" fill="none" opacity=".8">'
        '<path d="M6 68 Q50 56 96 66"/>'
        '<path d="M18 62 Q58 52 104 60"/>'
        '<path d="M150 72 Q196 60 240 68"/>'
        '</g>'
        '<g stroke="#e2c9b4" stroke-width="1" fill="none" opacity=".8">'
        '<line x1="104" y1="6" x2="104" y2="62"/><line x1="188" y1="10" x2="188" y2="62"/>'
        '<line x1="60" y1="34" x2="262" y2="34"/>'
        '</g>'
        '<g transform="translate(104,34)">'
        '<circle r="24" fill="none" stroke="#a8421f" stroke-opacity=".3"/>'
        '<circle r="16" fill="none" stroke="#a8421f" stroke-opacity=".42"/>'
        '<circle r="8" fill="none" stroke="#a8421f" stroke-opacity=".55"/>'
        '<path d="M0 0 L24 -11 A26 26 0 0 1 25 10 Z" fill="#b3261e" opacity=".12"/>'
        '<line x1="0" y1="0" x2="24" y2="-11" stroke="#b3261e" stroke-width="1.3" opacity=".75"/>'
        '</g>'
        '<path d="M104 56 L97 44 A7.4 7.4 0 1 1 111 44 Z" fill="#b3261e"/>'
        '<circle cx="104" cy="41" r="2.6" fill="#fff5e8"/>'
        '<path d="M188 60 L182 50 A6.2 6.2 0 1 1 194 50 Z" fill="#a8621a"/>'
        '<circle cx="188" cy="47.5" r="2.2" fill="#fff5e8"/>'
        + t(104, 72, "IRAN", 7.6, "#8f3418", 900, "middle", 1.4)
        + t(188, 72, "GAZA", 7.6, "#8a5a12", 900, "middle", 1.4)
        + '<path d="M246 22 L262 54 H230 Z" fill="#f2c94c" stroke="#8a5a12" stroke-width="1"/>'
        + t(246, 48, "!", 12, "#5a3a08", 900, "middle")
        + '<line x1="132" y1="42" x2="224" y2="46" stroke="#a8421f" stroke-width="1" stroke-dasharray="2 3"/>'
    )
    return svg(MID_W, MID_H, body)


# ------------------------------------------------------------- low drawings

def art_africa():
    box = (4, 1, 58, 57)
    mapping = ((-18, 52), (-36, 38))
    dots = dot_map([AFRICA_POLY, MADAGASCAR_POLY], mapping[0], mapping[1], box,
                   3.5, 1.1, "#1f6b4a")

    def project(lon, lat):
        bx, by, bw, bh = box
        return (bx + (lon + 18) / 70 * bw, by + (38 - lat) / 74 * bh)

    hotspots = [project(4, 9), project(16, -12), project(37, 0)]
    pulses = "".join(
        '<circle cx="%s" cy="%s" r="5" fill="none" stroke="#b3261e" stroke-opacity=".5" stroke-width="1.2"/>'
        % (n(x), n(y)) for x, y in hotspots
    )
    pins = "".join('<circle cx="%s" cy="%s" r="2.2" fill="#b3261e"/>' % (n(x), n(y))
                   for x, y in hotspots)
    body = (
        f'<rect width="{LOW_W}" height="{LOW_H}" fill="#e6efe7"/>'
        + dots + pulses + pins
        + t(74, 30, "NO.1", 26, "#b3261e", 900, "start", -0.6)
        + t(75, 40, "MOST-TARGETED", 6.2, "#1f6b4a", 900, "start", 1.2)
        + t(75, 49, "CYBER REGION", 6.2, "#1f6b4a", 900, "start", 1.2)
        + '<circle cx="208" cy="28" r="21" fill="none" stroke="#b3261e" stroke-opacity=".3" stroke-width="1.4"/>'
        '<rect x="196" y="26" width="24" height="18" rx="2" fill="#175e46"/>'
        '<path d="M201 26 V19 A7 7 0 0 1 215 19 V26" fill="none" stroke="#175e46" stroke-width="2.6"/>'
        '<circle cx="208" cy="34" r="2.2" fill="#e8f3ea"/>'
        '<rect x="207" y="35" width="2" height="5" fill="#e8f3ea"/>'
    )
    return svg(LOW_W, LOW_H, body)


def art_gta():
    body = (
        f'<rect width="{LOW_W}" height="{LOW_H}" fill="#ece7f5"/>'
        '<g>'
        '<path d="M14 42 L16 28 Q18 20 30 20 H62 Q74 20 76 28 L78 42 Q78 48 70 44 L66 40 H26 '
        'L22 44 Q14 48 14 42 Z" fill="#2c2444" stroke="#6b4a94" stroke-width="1.2"/>'
        '<rect x="28" y="24" width="30" height="5" rx="2" fill="#cfc6e8"/>'
        '<circle cx="58" cy="38" r="4" fill="none" stroke="#cfc6e8" stroke-width="1.8"/>'
        '<circle cx="42" cy="38" r="4" fill="none" stroke="#cfc6e8" stroke-width="1.8"/>'
        '<circle cx="24" cy="34" r="1.8" fill="#cfc6e8"/><circle cx="68" cy="34" r="1.8" fill="#cfc6e8"/>'
        '</g>'
        + t(96, 47, "VI", 38, "#5b3a7e", 900, "start", -2)
        + t(96, 57, "PS5 &#183; XBOX &#183; 212 GB", 6, "#6b5a8a", 700, "start", 0.8)
        + '<circle cx="196" cy="24" r="15" fill="#b3261e"/>'
        + t(196, 29, "99", 13, "#ffffff", 900, "middle")
        + t(196, 45, "METACRITIC", 5.4, "#6b5a8a", 900, "middle", 1.0)
        + '<rect x="230" y="14" width="52" height="30" rx="3" fill="none" stroke="#8a76a8" stroke-width="1"/>'
        + t(256, 27, "13", 14, "#5b3a7e", 900, "middle")
        + t(256, 38, "YEAR WAIT", 5.2, "#6b5a8a", 900, "middle", 0.9)
    )
    return svg(LOW_W, LOW_H, body)


def art_imf():
    body = (
        f'<rect width="{LOW_W}" height="{LOW_H}" fill="#e3efee"/>'
        '<defs><clipPath id="clipGlobe"><circle cx="34" cy="28" r="21"/></clipPath></defs>'
        '<circle cx="34" cy="28" r="21" fill="#d9ece8" stroke="#175e63" stroke-width="1.4"/>'
        '<g clip-path="url(#clipGlobe)" stroke="#7fb3ad" fill="none" stroke-width="1">'
        '<ellipse cx="34" cy="28" rx="8" ry="21"/><ellipse cx="34" cy="28" rx="15" ry="21"/>'
        '<line x1="13" y1="19" x2="55" y2="19"/><line x1="13" y1="28" x2="55" y2="28"/>'
        '<line x1="13" y1="37" x2="55" y2="37"/>'
        '</g>'
        + t(64, 31, "4.7%", 25, "#175e63", 900, "start", -0.8)
        + t(65, 41, "GLOBAL INFLATION", 6.2, "#3f6f6c", 900, "start", 1.1)
        + t(65, 50, "IMF WARNS ON PRICES", 6, "#2b6f74", 700, "start", 0.9)
        + '<g>'
        '<rect x="190" y="36" width="12" height="12" fill="#7fb3ad"/>'
        '<rect x="206" y="26" width="12" height="22" fill="#3f8f89"/>'
        '<rect x="222" y="14" width="12" height="34" fill="#175e63"/>'
        '</g>'
        '<line x1="240" y1="42" x2="280" y2="12" stroke="#b3261e" stroke-width="2"/>'
        '<path d="M280 12 L269 13 L273 22 Z" fill="#b3261e"/>'
        + t(196, 56, "AI HARDWARE + ENERGY", 5.4, "#3f6f6c", 900, "start", 0.9)
    )
    return svg(LOW_W, LOW_H, body)


# --------------------------------------------------------------- brief icons

def icon_glasses():
    return (
        '<svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="2.5" y="10" width="11" height="9" rx="2.5" fill="none" stroke="#6b4494" stroke-width="1.8"/>'
        '<rect x="16.5" y="10" width="11" height="9" rx="2.5" fill="none" stroke="#6b4494" stroke-width="1.8"/>'
        '<path d="M13.5 13.5 Q15 12 16.5 13.5" fill="none" stroke="#6b4494" stroke-width="1.6"/>'
        '<path d="M2.5 12 L0.5 9 M27.5 12 L29.5 9" stroke="#6b4494" stroke-width="1.6"/>'
        '<circle cx="20.5" cy="14.5" r="1.9" fill="#b3261e"/>'
        '<path d="M6 22 L24 22" stroke="#b3261e" stroke-width="1.6" stroke-dasharray="2 2"/>'
        '</svg>'
    )


def icon_whale():
    return (
        '<svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M3 17 C5 11 12 8 17 10 C21 11.5 23 14 23.5 16 L27 13.5 L26.5 18.5 L23.5 19.5 '
        'C21 23 13 24 8 21 C5 19.5 3.5 18.5 3 17 Z" fill="#0f7b78"/>'
        '<circle cx="7.5" cy="15.5" r="1.1" fill="#e8f6f5"/>'
        '<path d="M9 20 L10.5 24 M13 20.5 L13.8 24.5 M17 20 L17.4 24" stroke="#b6dcd9" stroke-width="1.2"/>'
        '</svg>'
    )


def icon_star():
    return (
        '<svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="13" cy="16" r="8" fill="#b3261e"/>'
        '<circle cx="22.5" cy="9.5" r="3.2" fill="#2b6f74"/>'
        '<path d="M22 12.5 C19 15 16 16.5 13.5 17" fill="none" stroke="#e8b34a" stroke-width="1.6"/>'
        '<path d="M6 8 L7.2 11 L10 12 L7.2 13 L6 16 L4.8 13 L2 12 L4.8 11 Z" fill="#e8b34a"/>'
        '<circle cx="26" cy="21" r="1.4" fill="#2b6f74"/>'
        '</svg>'
    )


def icon_ice():
    return (
        '<svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M3 4 H20 L22 15 H3 Z" fill="#dbe7f0" stroke="#4b6a8c" stroke-width="1.4"/>'
        '<path d="M22 15 L24 19 L21 18 L19 22 L16 18 L13 21 L11 17 L8 20 L6 16 L3 18" '
        'fill="none" stroke="#4b6a8c" stroke-width="1.4"/>'
        '<path d="M2 22 H28" stroke="#4b6a8c" stroke-width="1.4"/>'
        '<path d="M5 26 L9 22 L13 26 Z M14 26 L18 21 L22 26 Z" fill="#8fb4cf"/>'
        '</svg>'
    )


def icon_robot():
    return (
        '<svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="3" y="24" width="10" height="3.5" rx="1" fill="#1f4e8c"/>'
        '<path d="M8 24 L8 17 L16 17 L16 10 L21 10" fill="none" stroke="#1f4e8c" stroke-width="2.2"/>'
        '<circle cx="8" cy="17" r="2.4" fill="#1f4e8c"/>'
        '<circle cx="16" cy="17" r="2.4" fill="#1f4e8c"/>'
        '<rect x="21" y="5.5" width="5" height="9" rx="1.4" fill="#1f4e8c"/>'
        '<path d="M20 12 L27 12 M23.5 8.5 L23.5 15.5" stroke="#b3261e" stroke-width="1.4"/>'
        '</svg>'
    )


# ------------------------------------------------------------------- content

PANELS = [
    {
        "row": "hero",
        "region": "ASIA-PACIFIC &#183; GLOBAL", "beat": "DIPLOMACY",
        "headline": 'THREE POWERS,<br><span class="hl">ONE TABLE</span>',
        "sub": "Trump, Xi and Putin sign a Shenzhen peace declaration: nuclear war "
               "&#8220;cannot be won&#8221;.",
        "art": art_summit, "place": "SHENZHEN", "accent": "#d9a441", "reg": "#e2bb6a",
        "artbg": "#0a1220", "dark": True,
    },
    {
        "row": "hero",
        "region": "AMERICAS", "beat": "MARKETS &#183; TECH",
        "headline": "ANTHROPIC'S<br>$1.5TN IPO",
        "sub": "A record Nasdaq debut for ANT at $83 a share raises $81bn &#8212; the "
               "largest listing ever.",
        "art": art_ipo, "place": "NASDAQ", "accent": "#1f4e8c", "reg": "#1f4e8c",
        "artbg": "#e2ebf7", "dark": False,
    },
    {
        "row": "hero",
        "region": "SPACE", "beat": "SCIENCE",
        "headline": "VOYAGER 1:<br>ONE LIGHT-DAY",
        "sub": "NASA confirms the probe is 25.9bn km from Earth after 49 years; the "
               "Empire State glows gold.",
        "art": art_voyager, "place": "PASADENA", "accent": "#2b6f74", "reg": "#3f8f89",
        "artbg": "#070c18", "dark": False,
    },
    {
        "row": "mid",
        "region": "EUROPE", "beat": "CLIMATE",
        "headline": "CLIMATE DRAFT<br>DROPS FOSSIL FUELS",
        "sub": "COP31's 9-page Antalya text omits any shift away from fossil fuels, "
               "drawing a fierce backlash.",
        "art": art_climate, "place": "ANTALYA", "accent": "#6b4494", "reg": "#6b4494",
        "artbg": "#f6ecda", "dark": False,
    },
    {
        "row": "mid",
        "region": "SOUTH-EAST ASIA", "beat": "INTERNATIONAL LAW",
        "headline": "ICJ FINDS<br>GENOCIDE",
        "sub": "The Hague court rules Myanmar committed genocide against the Rohingya "
               "and orders a safe return.",
        "art": art_icj, "place": "THE HAGUE", "accent": "#b3261e", "reg": "#b3261e",
        "artbg": "#e8edf3", "dark": False,
    },
    {
        "row": "mid",
        "region": "MIDDLE EAST", "beat": "SECURITY",
        "headline": "IRAN STRIKE<br>OPTION WEIGHED",
        "sub": "Trump weighs military options as Netanyahu lobbies Washington; Israel "
               "raids central Gaza.",
        "art": art_mideast, "place": "GAZA", "accent": "#a8621a", "reg": "#a8621a",
        "artbg": "#f7e7dc", "dark": False,
    },
    {
        "row": "low",
        "region": "AFRICA", "beat": "CYBERSECURITY",
        "headline": "AFRICA: TOP<br>CYBER TARGET",
        "sub": "The world's most-attacked region, with surges in Nigeria, Angola and Kenya.",
        "art": art_africa, "place": "LAGOS", "accent": "#1f6b4a", "reg": "#1f6b4a",
        "artbg": "#e6efe7", "dark": False,
    },
    {
        "row": "low",
        "region": "GLOBAL", "beat": "CULTURE &#183; GAMING",
        "headline": "GTA VI<br>ARRIVES AT LAST",
        "sub": "After 13 years the game lands on PS5 and Xbox with a 99 Metacritic score.",
        "art": art_gta, "place": "WORLDWIDE", "accent": "#5b3a7e", "reg": "#5b3a7e",
        "artbg": "#ece7f5", "dark": False,
    },
    {
        "row": "low",
        "region": "GLOBAL", "beat": "ECONOMY",
        "headline": "AI BOOM KEEPS<br>INFLATION HIGH",
        "sub": "The IMF's Georgieva warns AI hardware demand and energy shocks hold "
               "inflation near 4.7%.",
        "art": art_imf, "place": "SHENZHEN", "accent": "#2b6f74", "reg": "#2b6f74",
        "artbg": "#e3efee", "dark": False,
    },
]

ZONES = [
    ("ASIA-PACIFIC", "#b3261e", 2),
    ("AMERICAS", "#1f4e8c", 2),
    ("EUROPE", "#6b4494", 2),
    ("MIDDLE EAST", "#a8621a", 1),
    ("AFRICA", "#1f6b4a", 1),
    ("LATIN AMERICA", "#0f7b78", 1),
    ("ANTARCTICA", "#4b6a8c", 1),
    ("SPACE &#183; GLOBAL", "#2b6f74", 4),
]

BRIEFS = [
    {
        "tag": "EUROPE &#183; TECH", "col": "#6b4494", "icon": icon_glasses,
        "head": "DUTCH AP: DON'T BUY<br>AI CAMERA GLASSES",
        "detail": "UK challenges Google over prison video",
    },
    {
        "tag": "LATIN AMERICA &#183; SCIENCE", "col": "#0f7b78", "icon": icon_whale,
        "head": "PERU: 6M-YEAR<br>WHALE FOSSIL",
        "detail": "Unveiled: asymmetrical pygmy sperm whale",
    },
    {
        "tag": "ASTRONOMY &#183; SPACE", "col": "#2b6f74", "icon": icon_star,
        "head": "JWST SEES RED GIANT<br>SWALLOW A STAR",
        "detail": "Dying star in Andromeda, 2.5m ly away",
    },
    {
        "tag": "ANTARCTICA &#183; CLIMATE", "col": "#4b6a8c", "icon": icon_ice,
        "head": "RIDGES BUFFER<br>ANTARCTIC ICE CLIFFS",
        "detail": "MIT model finds a brake on collapse",
    },
    {
        "tag": "US &#183; MEDICINE", "col": "#1f4e8c", "icon": icon_robot,
        "head": "J&amp;J INSTALLS FIRST<br>OTTAVA ROBOT IN US",
        "detail": "Commercial surgical system, Houston",
    },
]

CSS = """
html,body{margin:0;padding:0;width:1024px;height:1024px;overflow:hidden;background:#ece4d1;}
body{font-family:Lato,Arial,sans-serif;-webkit-font-smoothing:antialiased;color:#15171b;}
.page{position:relative;width:1024px;height:1024px;overflow:hidden;
 background:radial-gradient(1000px 780px at 48% 26%,#f7f1e4 0%,#efe8d7 56%,#e6dcc5 100%);}
.rule-top{position:absolute;top:16px;left:24px;right:24px;height:6px;background:#15171b;}
.kicker{position:absolute;top:30px;left:24px;font-weight:900;font-size:13.5px;letter-spacing:3.6px;color:#b3261e;}
.meta{position:absolute;top:31px;right:24px;font-weight:700;font-size:11px;letter-spacing:2.1px;color:#6d6352;}
.masthead{position:absolute;top:44px;left:24px;width:976px;margin:0;font-weight:900;font-size:61px;
 line-height:1.2;letter-spacing:-1.3px;white-space:nowrap;}
.masthead .day{color:#b3261e;}
.masthead .dot{color:#b3261e;font-size:40px;}
.masthead .date{color:#15171b;}
.zoneband{position:absolute;top:118px;left:24px;width:976px;height:30px;box-sizing:border-box;
 border-top:1px solid #24231f;border-bottom:1px solid #24231f;background:rgba(255,252,244,.55);
 display:flex;align-items:center;justify-content:space-between;padding:0 10px;}
.zone{display:flex;align-items:center;gap:6px;font-weight:900;font-size:10px;letter-spacing:1.25px;color:#33363c;white-space:nowrap;}
.zone i{width:7px;height:7px;display:inline-block;}
.zone b{font-weight:700;font-size:9px;color:#8a7f6a;margin-left:1px;}
.zonecap{font-weight:900;font-size:10px;letter-spacing:1.6px;color:#b3261e;white-space:nowrap;}
.rule-bottom{position:absolute;top:152px;left:24px;right:24px;height:3px;background:#15171b;}
.grid{position:absolute;top:162px;left:24px;width:976px;height:794px;display:grid;
 grid-template-columns:repeat(3,1fr);grid-template-rows:280px 224px 180px 80px;gap:10px;}
.panel{position:relative;box-sizing:border-box;background:#fbf7ec;border:1px solid #201f1c;
 border-top:3px solid var(--accent);overflow:hidden;display:flex;flex-direction:column;}
.panel.hero{padding:11px 13px 12px;}
.panel.mid{padding:8px 12px 10px;}
.panel.low{padding:7px 12px 9px;}
.ptop{display:flex;justify-content:space-between;align-items:center;}
.hero .ptop{height:16px;}
.mid .ptop{height:15px;}
.low .ptop{height:14px;}
.region{display:flex;align-items:center;gap:5px;font-weight:900;letter-spacing:1.3px;color:var(--reg);white-space:nowrap;}
.region:before{content:"";width:6px;height:6px;background:var(--reg);display:inline-block;}
.hero .region{font-size:10.5px;}
.mid .region{font-size:10px;}
.low .region{font-size:9.5px;}
.beat{font-weight:900;letter-spacing:1.05px;color:#8a7f6a;white-space:nowrap;}
.hero .beat{font-size:9px;}
.mid .beat{font-size:8.6px;}
.low .beat{font-size:8.2px;}
.art{width:100%;background:var(--artbg);overflow:hidden;display:block;flex:none;}
.hero .art{height:104px;margin-top:6px;}
.mid .art{height:74px;margin-top:6px;}
.low .art{height:60px;margin-top:5px;}
.art svg{display:block;width:100%;height:100%;}
.panel h2{margin:0;font-weight:900;line-height:1;color:#15171b;white-space:nowrap;flex:none;}
.pfoot{margin-top:auto;border-top:1px solid #d5cab3;padding-top:4px;display:flex;
 justify-content:space-between;align-items:baseline;font-weight:700;font-size:7.2px;
 letter-spacing:1.3px;color:#8a7f6a;flex:none;}
.pfoot b{font-weight:900;color:#4a4d54;letter-spacing:1.5px;}
.panel.dark .pfoot{border-color:#27364f;color:#8fa0b8;}
.panel.dark .pfoot b{color:#cbb27a;}
.hero h2{margin-top:6px;font-size:30px;letter-spacing:-.5px;}
.mid h2{margin-top:6px;font-size:21.5px;letter-spacing:-.35px;}
.low h2{margin-top:5px;font-size:19px;letter-spacing:-.3px;}
.panel h2 .hl{color:#d9a441;}
.panel p{margin:0;font-weight:400;color:#33363c;flex:none;}
.hero p{margin-top:6px;font-size:13.2px;line-height:1.26;}
.mid p{margin-top:5px;font-size:12.4px;line-height:1.24;}
.low p{margin-top:4px;font-size:11.4px;line-height:1.23;}
.panel.dark{background:#0f1a2e;border-color:#0a101d;}
.panel.dark h2{color:#f6efdc;}
.panel.dark h2 .hl{color:#e8c46a;}
.panel.dark p{color:#c2cbda;}
.panel.dark .beat{color:#8fa0b8;}
.briefs{grid-column:1 / -1;position:relative;box-sizing:border-box;display:grid;
 grid-template-columns:repeat(5,1fr);
 background:#f7f1e2;border:1px solid #201f1c;border-top:3px solid #15171b;overflow:hidden;}
.brief{position:relative;box-sizing:border-box;padding:7px 8px 6px;border-left:1px solid #d6cbb4;}
.brief:first-child{border-left:0;}
.btag{display:block;font-weight:900;font-size:8.4px;line-height:1.15;letter-spacing:1.1px;
 color:var(--bcol);white-space:nowrap;}
.bhead{display:block;margin-top:2px;font-weight:900;font-size:12px;line-height:1.08;color:#1b1d22;}
.bdetail{display:block;margin-top:2px;font-weight:400;font-size:9.3px;line-height:1.12;color:#5a5445;}
.bicon{position:absolute;left:8px;top:27px;width:30px;height:30px;}
.btext{margin-left:37px;}
.footer{position:absolute;top:960px;left:24px;width:976px;height:40px;background:#15171b;color:#f3ecdb;
 display:flex;justify-content:space-between;align-items:center;box-sizing:border-box;padding:0 14px;}
.footer .left{font-weight:700;font-size:10.2px;letter-spacing:1.15px;}
.footer .right{font-weight:900;font-size:10.2px;letter-spacing:1.15px;color:#d9a441;}
.grain{position:absolute;left:0;top:0;width:1024px;height:1024px;pointer-events:none;opacity:.035;
 mix-blend-mode:multiply;}
"""


def panel_html(p):
    cls = "panel %s%s" % (p["row"], " dark" if p["dark"] else "")
    style = "--accent:%s;--reg:%s;--artbg:%s;" % (p["accent"], p["reg"], p["artbg"])
    return (
        '<section class="%s" style="%s">' % (cls, style)
        + '<div class="ptop"><span class="region">%s</span><span class="beat">%s</span></div>'
        % (p["region"], p["beat"])
        + '<div class="art">%s</div>' % p["art"]()
        + '<h2>%s</h2>' % p["headline"]
        + '<p>%s</p>' % p["sub"]
        + ('' if p["row"] == "low" else
           '<div class="pfoot"><span>THU 19 NOV 2026</span><b>%s</b></div>' % p["place"])
        + "</section>"
    )


def brief_html(b):
    return (
        '<div class="brief" style="--bcol:%s">' % b["col"]
        + '<div class="bicon">%s</div>' % b["icon"]()
        + '<div class="btext"><span class="btag">%s</span>'
        '<span class="bhead">%s</span>'
        '<span class="bdetail">%s</span></div>' % (b["tag"], b["head"], b["detail"])
        + "</div>"
    )


def build_html():
    zones = "".join(
        '<span class="zone"><i style="background:%s"></i>%s<b>%d</b></span>' % (col, label, count)
        for label, col, count in ZONES
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>19 November 2026</title>'
        '<style>' + CSS + '</style></head><body><div class="page">'
        '<div class="rule-top"></div>'
        '<div class="kicker">THE WORLD IN ONE DAY</div>'
        '<div class="meta">VOL. II &#183; NO. 19 &#183; FOURTEEN VERIFIED STORIES</div>'
        '<h1 class="masthead"><span class="day">THURSDAY</span><span class="dot">&#183;</span>'
        '<span class="date">19 NOVEMBER 2026</span></h1>'
        '<div class="zoneband">' + zones + '<span class="zonecap">14 STORIES &#183; 8 ZONES</span></div>'
        '<div class="rule-bottom"></div>'
        '<div class="grid">' + "".join(panel_html(p) for p in PANELS)
        + '<div class="briefs">' + "".join(brief_html(b) for b in BRIEFS) + "</div>"
        + "</div>"
        '<div class="footer"><span class="left">SOURCES: AP &#183; REUTERS &#183; NASA &#183; '
        'IMF &#183; ICJ &#183; MIT &#183; UK GOV</span>'
        '<span class="right">14 STORIES &#183; 8 ZONES &#183; ONE DAY</span></div>'
        '<svg class="grain" width="1024" height="1024" viewBox="0 0 1024 1024" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<filter id="grainfilter"><feTurbulence type="fractalNoise" baseFrequency="0.8" '
        'numOctaves="3" seed="17" stitchTiles="stitch"/>'
        '<feColorMatrix type="saturate" values="0"/></filter>'
        '<rect width="1024" height="1024" filter="url(#grainfilter)"/></svg>'
        "</div></body></html>"
    )


AUDIT_JS = """() => {
  const out = {doc:[document.documentElement.scrollWidth, document.documentElement.scrollHeight],
               issues:[], rows:{}};
  const add = (m) => { if (out.issues.length < 60) out.issues.push(m); };
  if (out.doc[0] !== 1024 || out.doc[1] !== 1024) add('document ' + out.doc.join('x'));
  const label = (el) => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
  document.querySelectorAll('.panel, .brief, .briefs, .grid, .zoneband, .footer, .masthead').forEach((el, i) => {
    if (el.scrollHeight - el.clientHeight > 1) add('scroll-y ' + label(el) + ' +' + (el.scrollHeight - el.clientHeight));
    if (el.scrollWidth - el.clientWidth > 1) add('scroll-x ' + label(el) + ' +' + (el.scrollWidth - el.clientWidth));
  });
  document.querySelectorAll('.panel').forEach((p, i) => {
    const pb = p.getBoundingClientRect();
    const boxes = [];
    p.querySelectorAll('*').forEach((el) => {
      const b = el.getBoundingClientRect();
      if (!b.width && !b.height) return;
      if (el.tagName.toLowerCase() === 'svg') boxes.push([b, el]);
      if (b.bottom > pb.bottom + 0.6 || b.right > pb.right + 0.6 ||
          b.top < pb.top - 0.6 || b.left < pb.left - 0.6) {
        add('panel' + (i+1) + ' escape ' + label(el) + ' t=' + b.top.toFixed(1) +
            ' r=' + b.right.toFixed(1) + ' b=' + b.bottom.toFixed(1));
      }
    });
    const s = p.querySelector('p');
    if (s.scrollHeight - s.clientHeight > 1) add('panel' + (i+1) + ' sub clipped');
    const h = p.querySelector('h2');
    if (h.scrollWidth - h.clientWidth > 1) add('panel' + (i+1) + ' headline too wide ' +
        (h.scrollWidth - h.clientWidth));
    out.rows['p' + (i+1)] = [Math.round(pb.width*10)/10, Math.round(pb.height*10)/10,
      Math.round(s.getBoundingClientRect().bottom - pb.bottom)];
  });
  document.querySelectorAll('.briefs, .zoneband, .footer').forEach((p, i) => {
    const pb = p.getBoundingClientRect();
    p.querySelectorAll('*').forEach((el) => {
      const b = el.getBoundingClientRect();
      if (!b.width && !b.height) return;
      if (b.bottom > pb.bottom + 0.6 || b.right > pb.right + 0.6 ||
          b.top < pb.top - 0.6 || b.left < pb.left - 0.6) {
        add('strip escape ' + label(el) + ' b=' + b.bottom.toFixed(1) + ' pb=' + pb.bottom.toFixed(1));
      }
    });
  });
  document.querySelectorAll('svg').forEach((s, i) => {
    if (s.classList.contains('grain')) return;
    const vb = s.viewBox.baseVal;
    let b;
    try { b = s.getBBox(); } catch (e) { add('svg' + i + ' bbox failed'); return; }
    const tol = 0.6;
    if (b.x < vb.x - tol || b.y < vb.y - tol ||
        b.x + b.width > vb.x + vb.width + tol || b.y + b.height > vb.y + vb.height + tol) {
      add('svg' + i + ' ink ' + [b.x, b.y, b.x+b.width, b.y+b.height].map(v=>v.toFixed(1)).join(',') +
          ' outside ' + [vb.x, vb.y, vb.width, vb.height].join(','));
    }
  });
  return out;
}"""

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


def png_size(data):
    if data[:8] != PNG_SIG:
        raise SystemExit("screenshot is not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def encode_jpeg(png_bytes):
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    choose = None
    for quality in range(JPEG_QUALITY, 69, -1):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, subsampling=0,
                   optimize=True, progressive=False)
        data = buf.getvalue()
        if choose is None:
            choose = (quality, data)
        if len(data) <= JPEG_TARGET:
            return quality, data
    return choose


def render_with_playwright():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                  "--force-color-profile=srgb", "--font-render-hinting=none",
                  "--disable-lcd-text"],
        )
        page = browser.new_page(viewport={"width": 1024, "height": 1024}, device_scale_factor=1)
        page.goto(HTML_PATH.as_uri())
        page.wait_for_timeout(400)
        audit = page.evaluate(AUDIT_JS)
        print("AUDIT", audit)
        page.screenshot(path=str(RAW_PNG), clip={"x": 0, "y": 0, "width": 1024, "height": 1024})
        browser.close()
    return audit


def render_with_chrome():
    subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--window-size=1024,1024",
         "--screenshot=" + str(RAW_PNG), HTML_PATH.as_uri()],
        check=True,
    )


def write_previews():
    from PIL import Image

    image = Image.open(ENTRY).convert("RGB")
    for size, dest in ((300, PREVIEW_300), (600, PREVIEW_600)):
        image.resize((size, size), Image.LANCZOS).save(dest)


def main():
    html = build_html()
    HTML_PATH.write_text(html, encoding="utf-8")
    try:
        audit = render_with_playwright()
    except ImportError:
        print("Playwright unavailable; falling back to Chrome CLI.")
        render_with_chrome()
        audit = None

    if audit and audit["issues"]:
        print("AUDIT ISSUES:", len(audit["issues"]))
        for issue in audit["issues"]:
            print("  -", issue)
    assert not (audit and audit["issues"]), "layout audit reported issues"

    raw = RAW_PNG.read_bytes()
    rw, rh = png_size(raw)
    assert (rw, rh) == (1024, 1024), "screenshot is %dx%d" % (rw, rh)

    quality, data = encode_jpeg(raw)
    assert data[:2] == JPEG_SOI and data[-2:] == JPEG_EOI, "not a complete JPEG"
    assert 180000 <= len(data) <= 360000, "entry.png outside the size band"
    ENTRY.write_bytes(data)
    write_previews()

    print("entry.png: 1024x1024 JPEG quality=%d subsampling=4:4:4, %d bytes (%.1f KiB)"
          % (quality, len(data), len(data) / 1024))
    for preview in (PREVIEW_300, PREVIEW_600):
        print("%s: %dx%d, %d bytes" % (preview, *png_size(preview.read_bytes()),
                                       preview.stat().st_size))


if __name__ == "__main__":
    main()
