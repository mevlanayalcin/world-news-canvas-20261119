#!/usr/bin/env python3
"""Build the 1024x1024 crisp light-newsprint front page (entry.png), v3.

Forty-five verified stories for Thursday 19 November 2026: a ten-story Hero
Deck with bespoke inline SVG graphics on top, a seven-region World Digest
Matrix below. Layout is audited in the same headless Chromium pass (geometry,
overlaps, clipping, story census, ink contrast); the screenshot is rendered at
1x and 2x device scale, the sharper small-text candidate is chosen by an edge
variance metric, and the result is encoded as a 4:4:4 baseline JPEG.

Build-time tooling only: the shipped runtime (main.py) is standard library
only. Everything rendered is local: system fonts, inline SVG, no network.
"""

import html
import io
import math
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "entry.png"
HTML_PATH = Path("/tmp/world_news_canvas.html")
RAW_1X = Path("/tmp/world_news_canvas_1x.png")
RAW_2X = Path("/tmp/world_news_canvas_2x.png")
SUPER_1X = Path("/tmp/world_news_canvas_super.png")
PREVIEW_300 = Path("/tmp/news_v3_300.png")
PREVIEW_600 = Path("/tmp/news_v3_600.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITIES = (94, 93, 92, 91)
JPEG_TARGET = 500000

# ---------------------------------------------------------------- palette
PAPER = "#FBF8F1"
PANEL = "#FFFFFF"
INK = "#111827"
INK_SUB = "#1F2937"
INK_MUTE = "#374151"
HAIR = "#D4CDC0"
RULE = "#18181B"

REGIONS = {
    # key: (display, bar, text, short)
    "ME": ("MIDDLE EAST & GULF", "#B91C1C", "#991B1B", "MIDDLE EAST"),
    "AP": ("ASIA-PACIFIC", "#7E22CE", "#6B21A8", "ASIA-PACIFIC"),
    "EU": ("EUROPE", "#4338CA", "#4338CA", "EUROPE"),
    "AM": ("AMERICAS", "#1D4ED8", "#1E40AF", "AMERICAS"),
    "AF": ("AFRICA", "#047857", "#065F46", "AFRICA"),
    "MK": ("MARKETS &#183; TECH", "#B45309", "#7C2D12", "MARKETS"),
    "SC": ("SCIENCE &#183; SPACE", "#0F766E", "#115E59", "SCIENCE"),
}


# ---------------------------------------------------------------- svg utils

def n(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def svg(w, h, body, fit=True):
    par = ' preserveAspectRatio="none"' if fit else ""
    return ('<svg viewBox="0 0 %s %s"%s xmlns="http://www.w3.org/2000/svg">%s</svg>'
            % (n(w), n(h), par, body))


def t(x, y, s, size, fill, weight=900, anchor="start", ls=0.0, opacity=None, family="Lato"):
    attrs = ""
    if anchor != "start":
        attrs += ' text-anchor="%s"' % anchor
    if opacity is not None:
        attrs += ' opacity="%s"' % n(opacity)
    return ('<text x="%s" y="%s"%s font-family="%s" font-size="%s" font-weight="%s"'
            ' letter-spacing="%s" fill="%s">%s</text>'
            % (n(x), n(y), attrs, family, n(size), weight, n(ls), fill, s))


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=1):
    r = '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"' % (n(x), n(y), n(w), n(h), fill)
    if rx:
        r += ' rx="%s"' % n(rx)
    if stroke:
        r += ' stroke="%s" stroke-width="%s"' % (stroke, n(sw))
    return r + "/>"


def circle(cx, cy, r, fill, stroke=None, sw=1, opacity=None):
    c = '<circle cx="%s" cy="%s" r="%s" fill="%s"' % (n(cx), n(cy), n(r), fill)
    if opacity is not None:
        c += ' opacity="%s"' % n(opacity)
    if stroke:
        c += ' stroke="%s" stroke-width="%s"' % (stroke, n(sw))
    return c + "/>"


def line(x1, y1, x2, y2, stroke, sw=1, dash=None, opacity=None):
    l = '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"' % (
        n(x1), n(y1), n(x2), n(y2), stroke, n(sw))
    if dash:
        l += ' stroke-dasharray="%s"' % dash
    if opacity is not None:
        l += ' opacity="%s"' % n(opacity)
    return l + "/>"


def path(d, fill="none", stroke=None, sw=1, opacity=None):
    p = '<path d="%s" fill="%s"' % (d, fill)
    if opacity is not None:
        p += ' opacity="%s"' % n(opacity)
    if stroke:
        p += ' stroke="%s" stroke-width="%s"' % (stroke, n(sw))
    return p + "/>"


def star_pts(cx, cy, r):
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
        % (n(x0), n(y0 + i * h / 7), n(w), n(h / 7 + 0.2), "#b3261e" if i % 2 == 0 else "#f4f1e8")
        for i in range(7))
    stars = "".join(
        '<circle cx="%s" cy="%s" r="%s" fill="#f4f1e8"/>'
        % (n(x0 + w * 0.45 * (c + 1) / 4), n(y0 + h * 0.5 * (rr + 1) / 4), n(max(0.5, r * 0.06)))
        for rr in range(3) for c in range(3))
    return ('<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (cid, n(cx), n(cy), n(r))
            + '<g clip-path="url(#%s)">' % cid
            + rect(x0, y0, w, h, "#f4f1e8") + stripes
            + rect(x0, y0, w * 0.45, h * 0.5, "#1f3a6e") + stars + "</g>")


def flag_cn(cx, cy, r, cid):
    w = h = 2 * r
    x0, y0 = cx - r, cy - r
    return ('<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (cid, n(cx), n(cy), n(r))
            + '<g clip-path="url(#%s)">' % cid
            + rect(x0, y0, w, h, "#c8322b")
            + path(star_pts(x0 + w * 0.28, y0 + h * 0.3, r * 0.36), "#f2c94c")
            + path(star_pts(x0 + w * 0.54, y0 + h * 0.16, r * 0.13), "#f2c94c")
            + path(star_pts(x0 + w * 0.63, y0 + h * 0.31, r * 0.13), "#f2c94c")
            + path(star_pts(x0 + w * 0.63, y0 + h * 0.48, r * 0.13), "#f2c94c")
            + path(star_pts(x0 + w * 0.54, y0 + h * 0.62, r * 0.13), "#f2c94c")
            + "</g>")


def flag_ru(cx, cy, r, cid):
    w = h = 2 * r
    x0, y0 = cx - r, cy - r
    return ('<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (cid, n(cx), n(cy), n(r))
            + '<g clip-path="url(#%s)">' % cid
            + rect(x0, y0, w, h, "#f4f1e8")
            + rect(x0, y0 + h / 3, w, h / 3, "#2b4c8c")
            + rect(x0, y0 + 2 * h / 3, w, h / 3, "#c8322b")
            + "</g>")


STARFIELD = [(14, 12), (27, 22), (43, 10), (58, 19), (74, 11), (92, 23), (108, 10),
             (123, 19), (140, 9), (158, 17), (172, 24), (188, 12), (204, 20), (221, 9),
             (236, 19), (258, 14), (276, 26), (20, 34), (250, 62), (272, 48), (12, 52),
             (99, 66), (184, 62), (212, 54), (46, 64), (150, 70), (300, 22), (296, 66),
             (16, 78), (96, 84), (176, 82), (240, 86), (304, 78), (62, 76), (128, 78)]


# --------------------------------------------------------- hero big art (324x106)

def art_summit():
    W, H = 324, 106
    body = (
        '<defs><radialGradient id="gSummit" cx="50%" cy="40%" r="75%">'
        '<stop offset="0%" stop-color="#1c2c48"/><stop offset="100%" stop-color="#0a1220"/>'
        '</radialGradient></defs>'
        + rect(0, 0, W, H, "url(#gSummit)")
        + '<g stroke="#ffffff" stroke-opacity=".09" fill="none">'
        + '<ellipse cx="162" cy="44" rx="118" ry="40"/><ellipse cx="162" cy="44" rx="46" ry="40"/>'
        + '<line x1="44" y1="44" x2="280" y2="44"/><line x1="52" y1="24" x2="272" y2="24"/>'
        + '<line x1="52" y1="64" x2="272" y2="64"/></g>'
        + flag_us(62, 40, 21, "sUS") + flag_cn(162, 38, 22, "sCN") + flag_ru(262, 40, 21, "sRU")
        + line(85, 40, 138, 39, "#d9a441", 1.2, "2 3")
        + line(186, 39, 239, 40, "#d9a441", 1.2, "2 3")
        + circle(62, 40, 21, "none", "#d9a441", 1.6)
        + circle(162, 38, 22, "none", "#f2c94c", 2)
        + circle(262, 40, 21, "none", "#d9a441", 1.6)
        + t(62, 72, "USA", 7, "#cbb27a", 700, "middle", 1.6)
        + t(162, 70, "CHINA", 7, "#e8cf8c", 700, "middle", 1.6)
        + t(262, 72, "RUSSIA", 7, "#cbb27a", 700, "middle", 1.6)
        + '<ellipse cx="162" cy="88" rx="76" ry="8" fill="#16233a" stroke="#38527a" stroke-width="1"/>'
        + '<ellipse cx="162" cy="88" rx="62" ry="5" fill="none" stroke="#2a4166" stroke-width=".8"/>'
        + t(162, 103, "SHENZHEN &#183; APEC 2026 &#183; FIRST TRILATERAL", 6.2, "#8ba0bd", 700, "middle", 1.8)
    )
    return svg(W, H, body)


def art_ipo():
    W, H = 324, 106
    candles = []
    data = [(196, 74, 12, "#1f8a5b"), (218, 66, 14, "#1f4e8c"), (240, 56, 16, "#1f8a5b"),
            (262, 44, 18, "#1f4e8c"), (284, 34, 16, "#1f8a5b"), (304, 22, 20, "#1f4e8c")]
    for x, top, hh, col in data:
        candles.append(line(x, top - 5, x, top + hh + 5, col, 1.3))
        candles.append(rect(x - 4.5, top, 9, hh, col))
    body = (
        '<defs><linearGradient id="gIpo" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#f4f8fd"/><stop offset="100%" stop-color="#e3ecf8"/>'
        '</linearGradient></defs>'
        + rect(0, 0, W, H, "url(#gIpo)")
        + '<g stroke="#cddbeb" stroke-width="1">'
        + line(180, 24, 316, 24, "#cddbeb", 1) + line(180, 46, 316, 46, "#cddbeb", 1)
        + line(180, 68, 316, 68, "#cddbeb", 1)
        + line(180, 90, 316, 90, "#cddbeb", 1) + "</g>"
        + line(168, 8, 168, 98, "#c3d4e6", 1)
        + t(12, 52, "$1.5TN", 40, "#173d6b", 900, "start", -1.8)
        + t(13, 64, "ANTHROPIC ON NASDAQ &#183; ANT", 6.6, "#33587c", 900, "start", 1.1)
        + t(13, 74, "PRICES AT $83 &#183; RAISES $81BN", 6.6, "#5a7796", 900, "start", 0.8)
        + t(13, 86, "LARGEST IPO IN HISTORY", 7, "#b3261e", 900, "start", 1.4)
        + "".join(candles)
        + '<line x1="196" y1="84" x2="306" y2="24" stroke="#173d6b" stroke-width="2"/>'
        + '<path d="M306 24 L294 26 L298 35 Z" fill="#173d6b"/>'
        + rect(196, 3, 84, 14, "#173d6b", rx=2)
        + t(238, 13.2, "PEAK $2TN &#183; $111 HIGH", 6.2, "#f2e6c8", 900, "middle", 0.7)
        + rect(232, 90, 80, 12, "#b3261e", rx=2)
        + t(272, 98.8, "CLOSE $97.17 +17%", 6.2, "#ffffff", 900, "middle", 0.5)
    )
    return svg(W, H, body)


def art_voyager():
    W, H = 324, 106
    stars = "".join(circle(x, y, 1.0 if (x + y) % 3 else 0.7, "#cfe6f5", opacity=0.7)
                    for x, y in STARFIELD)
    body = (
        rect(0, 0, W, H, "#070c18") + stars
        + circle(28, 52, 15, "none", "#7fd1e8", 1, 0.25)
        + circle(28, 52, 12, "#1f6f9e")
        + '<path d="M20 49 Q25 42 29 47 Q33 43 36 50 Q34 57 28 58 Q21 57 20 49 Z" fill="#2f8a5c"/>'
        + '<path d="M42 54 C110 60 190 52 248 30" fill="none" stroke="#7fd1e8" stroke-width="1.2"'
        ' stroke-dasharray="2 4" opacity=".85"/>'
        + '<g transform="translate(256,26) rotate(-18)">'
        + '<ellipse cx="0" cy="0" rx="9" ry="5" fill="#d9c9a0" stroke="#f2e6c8" stroke-width=".8"/>'
        + line(-2, 0, -13, 0, "#d9c9a0", 1) + line(0, 4, 0, 12, "#d9c9a0", 1)
        + rect(-3.5, 4, 7, 5, "#bfae86") + line(6, -2, 14, -8, "#d9c9a0", 1) + "</g>"
        + t(66, 34, "1 LIGHT-DAY", 26, "#f2e6c8", 900, "start", 0)
        + t(67, 45, "25.9BN KM &#183; 49 YEARS FLYING", 6.8, "#8fa6bd", 700, "start", 1)
        + t(67, 55, "RADIO: TWO DAYS THERE AND BACK", 6.4, "#d9a441", 900, "start", 0.9)
        + line(16, 92, 300, 92, "#3b4a5e", 1)
        + '<g stroke="#3b4a5e" stroke-width="1">'
        + line(16, 88, 16, 96, "#3b4a5e", 1) + line(87, 89, 87, 95, "#3b4a5e", 1)
        + line(158, 89, 158, 95, "#3b4a5e", 1)
        + line(229, 89, 229, 95, "#3b4a5e", 1) + line(300, 88, 300, 96, "#3b4a5e", 1) + "</g>"
        + t(16, 103, "EARTH", 6, "#8fa6bd", 700, "start", 0.9)
        + t(158, 103, "HELIOPAUSE", 6, "#8fa6bd", 700, "middle", 0.9)
        + t(300, 103, "INTERSTELLAR", 6, "#8fa6bd", 700, "end", 0.9)
    )
    return svg(W, H, body)


# ------------------------------------------------------- hero mini art (136x90)

def art_icj_m():
    W, H = 136, 90
    body = (
        rect(0, 0, W, H, "#e9eef5")
        + rect(14, 74, 56, 4, "#1f3f6e", rx=1)
        + rect(39, 22, 4, 54, "#1f3f6e")
        + circle(41, 19, 3, "#c8a24a")
        + rect(6, 24, 70, 2.6, "#1f3f6e")
        + line(11, 26, 11, 40, "#1f3f6e", 1) + line(21, 26, 11, 40, "#1f3f6e", 1)
        + line(61, 26, 61, 40, "#1f3f6e", 1) + line(71, 26, 61, 40, "#1f3f6e", 1)
        + '<path d="M0 40 Q11 52 22 40 Z" fill="#1f3f6e"/>'
        + '<path d="M50 40 Q61 52 72 40 Z" fill="#1f3f6e"/>'
        + '<g transform="translate(84,26) rotate(-24)">'
        + rect(0, 0, 26, 9, "#8a6a3a", rx=2) + rect(10, 9, 6, 20, "#8a6a3a", rx=2) + "</g>"
        + '<g transform="translate(66,58) rotate(-8)">'
        + rect(0, 0, 60, 18, "none", stroke="#b3261e", sw=2)
        + t(30, 13, "GENOCIDE", 9.5, "#b3261e", 900, "middle", 0.8) + "</g>"
        + rect(6, 6, 58, 12, "#1f3f6e", rx=2)
        + t(35, 14.8, "1ST EVER FINDING", 6.2, "#f2e6c8", 900, "middle", 0.6)
    )
    return svg(W, H, body)


def art_cop_m():
    W, H = 136, 90
    lines = "".join(rect(10, 16 + i * 7, [40, 30, 34, 24][i], 2, "#ddd0b8") for i in range(4))
    body = (
        rect(0, 0, W, H, "#f6ecda")
        + '<path d="M5 5 H62 L73 16 V85 H5 Z" fill="#fffdf7" stroke="#c2b49a" stroke-width="1"/>'
        + '<path d="M62 5 V16 H73" fill="#ece1cb" stroke="#c2b49a" stroke-width="1"/>'
        + lines
        + t(10, 47, "FOSSIL", 8.5, "#8a7a64", 900) + t(10, 58, "FUELS", 8.5, "#8a7a64", 900)
        + line(8, 41, 40, 62, "#b3261e", 2.6)
        + rect(48, 30, 20, 11, "#b3261e", rx=1)
        + t(58, 38, "0x", 6.5, "#fffdf7", 900, "middle", 0.4)
        + '<g><circle cx="106" cy="34" r="20" fill="#fffdf7" stroke="#c2b49a" stroke-width="1.4"/>'
        + '<path d="M92 40 A17 17 0 0 1 120 40" fill="none" stroke="#b3261e" stroke-width="2.4"/>'
        + '<line x1="106" y1="34" x2="117" y2="24" stroke="#8a1a14" stroke-width="2"/>'
        + circle(106, 34, 2.4, "#8a1a14")
        + t(106, 52, "1.5 &#8594; 2.0&#176;C", 6.2, "#8a5a12", 900, "middle", 0.3) + "</g>"
        + rect(80, 62, 50, 13, "#175e46", rx=2)
        + t(105, 71, "35-BY-35 KEEP", 6.2, "#e8f3ea", 900, "middle", 0.5)
        + t(68, 85, "ANTALYA COVER DECISION", 5.8, "#8a5a12", 900, "middle", 0.6)
    )
    return svg(W, H, body)


def art_jwst_m():
    W, H = 136, 90
    stars = "".join(circle(x % 136, y % 90, 0.8, "#cfe6f5", opacity=.6)
                    for x, y in [(10, 12), (30, 8), (52, 18), (90, 10), (118, 16),
                                 (126, 40), (8, 60), (64, 78), (100, 82), (120, 70), (44, 64)])
    hexes = ""
    r = 6.2
    for (hx, hy) in [(20, 20), (20 + r * 1.74, 20 + r), (20 - r * 1.74, 20 + r),
                     (20, 20 + r * 2), (20 + r * 1.74, 20 - r), (20 - r * 1.74, 20 - r)]:
        pts = " ".join("%.1f,%.1f" % (hx + r * 0.9 * math.cos(math.pi / 6 + k * math.pi / 3),
                                      hy + r * 0.9 * math.sin(math.pi / 6 + k * math.pi / 3))
                       for k in range(6))
        hexes += '<polygon points="%s" fill="#e8b34a" stroke="#8a5a12" stroke-width=".8"/>' % pts
    body = (
        rect(0, 0, W, H, "#0a1020") + stars + hexes
        + circle(88, 46, 24, "#b3261e", "#e8b34a", 1.4, 0.92)
        + '<path d="M88 22 A24 24 0 0 0 66 52 Q74 38 88 30 Z" fill="#d96a3a" opacity=".8"/>'
        + circle(64, 54, 7, "#7fb3f2")
        + '<path d="M64 47 Q70 34 80 30" fill="none" stroke="#e8b34a" stroke-width="1.6"/>'
        + t(114, 80, "2.5M LY", 6.2, "#8fa6bd", 700, "middle", 0.8)
        + t(68, 84, "AT2025abao", 6, "#d9a441", 700, "middle", 0.4)
    )
    return svg(W, H, body)


def art_gaza_m():
    W, H = 136, 90
    body = (
        rect(0, 0, W, H, "#f7e7dc")
        + '<g stroke="#e2c9b4" stroke-width="1" fill="none" opacity=".8">'
        + line(34, 6, 34, 84, "#e2c9b4", 1) + line(84, 6, 84, 84, "#e2c9b4", 1)
        + line(6, 44, 130, 44, "#e2c9b4", 1) + "</g>"
        + '<g transform="translate(34,44)">'
        + circle(0, 0, 26, "none", "#a8421f", 1.2, 0.3)
        + circle(0, 0, 17, "none", "#a8421f", 1.3, 0.45)
        + circle(0, 0, 8, "none", "#a8421f", 1.4, 0.6) + "</g>"
        + '<path d="M34 62 L28 50 A7 7 0 1 1 40 50 Z" fill="#b3261e"/>'
        + circle(34, 47, 2.4, "#fff5e8")
        + '<path d="M9 12 Q12 30 9 48 Q7 66 11 82" fill="none" stroke="#d9a441" stroke-width="2.4"'
        ' stroke-dasharray="4 3"/>'
        + '<path d="M40 30 L58 30 L54 26 M58 30 L54 34" fill="none" stroke="#8f3418" stroke-width="2"/>'
        + t(96, 26, "CENTRAL", 6.4, "#8a5a12", 900, "middle", 0.8)
        + t(96, 34, "GAZA", 6.8, "#8f3418", 900, "middle", 1.2)
        + t(17, 26, "ISRAEL", 5.8, "#8a7a64", 700, "middle", 0.7)
        + t(96, 60, "YELLOW LINE", 5.8, "#a8621a", 900, "middle", 0.8)
        + '<path d="M112 66 L124 78 L100 78 Z" fill="#f2c94c" stroke="#8a5a12" stroke-width="1"/>'
        + t(112, 76, "!", 9, "#5a3a08", 900, "middle")
    )
    return svg(W, H, body)


def art_berlin_m():
    W, H = 136, 90
    body = (
        rect(0, 0, W, H, "#e9edf6")
        + '<g stroke="#c7cfe2" stroke-width="1" fill="none" opacity=".8">'
        + '<path d="M10 78 Q40 66 68 74"/><path d="M70 20 Q100 14 128 22"/>'
        + '<path d="M12 22 Q30 30 40 46"/></g>'
        + '<path d="M52 30 H84 V54 Q68 66 52 54 Z" fill="#ffffff" stroke="#4338CA" stroke-width="2.2"/>'
        + '<path d="M68 30 H84 V54 Q76 60 68 62 Z" fill="#1D4ED8" opacity=".85"/>'
        + '<path d="M68 30 H52 V54 Q60 60 68 62 Z" fill="#f2c94c" opacity=".9"/>'
        + '<path d="M10 66 Q46 8 118 26" fill="none" stroke="#991B1B" stroke-width="2"/>'
        + '<path d="M118 26 L106 24 L110 33 Z" fill="#991B1B"/>'
        + rect(74, 6, 54, 12, "#991B1B", rx=2)
        + t(101, 14.8, "LONG-RANGE", 6.2, "#ffffff", 900, "middle", 0.6)
        + t(24, 84, "UKRAINE", 6.4, "#4338CA", 900, "middle", 0.8)
        + t(104, 84, "NO 'YALTA 2.0'", 6.2, "#4338CA", 900, "middle", 0.4)
    )
    return svg(W, H, body)


def art_gta_m():
    W, H = 136, 90
    body = (
        rect(0, 0, W, H, "#ece7f5")
        + '<g stroke="#b9a6d8" stroke-width="1.4" fill="none">'
        + '<path d="M14 78 V58 M14 58 Q8 52 4 54 M14 58 Q20 50 26 54 M14 58 Q12 50 8 46 M14 58 Q18 48 22 46"/>'
        + '<path d="M112 78 V52 M112 52 Q106 46 102 48 M112 52 Q118 44 124 48 M112 52 Q110 44 106 40 M112 52 Q116 42 120 40"/>'
        + "</g>"
        + '<g fill="#5b3a7e" opacity=".75">'
        + rect(34, 62, 8, 16, "#5b3a7e") + rect(46, 54, 10, 24, "#5b3a7e")
        + rect(60, 66, 8, 12, "#5b3a7e")
        + rect(72, 58, 9, 20, "#5b3a7e") + rect(86, 68, 8, 10, "#5b3a7e") + "</g>"
        + t(66, 52, "VI", 42, "#5b3a7e", 900, "middle", -2)
        + circle(26, 24, 15, "#b3261e")
        + t(26, 29, "99", 13, "#ffffff", 900, "middle")
        + t(26, 45, "METACRITIC", 5, "#6b5a8a", 900, "middle", 0.6)
        + rect(64, 8, 64, 13, "#5b3a7e", rx=2)
        + t(96, 17.4, "~$2BN DAY ONE", 6.2, "#ffffff", 900, "middle", 0.5)
        + t(66, 88, "13-YEAR WAIT &#183; 212 GB", 5.8, "#6b5a8a", 900, "middle", 0.7)
    )
    return svg(W, H, body)


def art_imf_m():
    W, H = 136, 90
    body = (
        rect(0, 0, W, H, "#e3efee")
        + circle(26, 30, 17, "#d9ece8", "#175e63", 1.4)
        + '<g clip-path="url(#gGlobe)" stroke="#7fb3ad" fill="none" stroke-width="1">'
        + '<clipPath id="gGlobe"><circle cx="26" cy="30" r="17"/></clipPath>'
        + '<ellipse cx="26" cy="30" rx="6.5" ry="17"/><ellipse cx="26" cy="30" rx="12" ry="17"/>'
        + line(9, 22, 43, 22, "#7fb3ad", 1) + line(9, 30, 43, 30, "#7fb3ad", 1)
        + line(9, 38, 43, 38, "#7fb3ad", 1) + "</g>"
        + t(52, 36, "4.7%", 27, "#175e63", 900, "start", -0.8)
        + t(53, 46, "GLOBAL INFLATION", 6.2, "#3f6f6c", 900, "start", 0.9)
        + rect(88, 58, 10, 10, "#7fb3ad") + rect(102, 46, 10, 22, "#3f8f89")
        + rect(116, 32, 10, 36, "#175e63")
        + '<line x1="88" y1="62" x2="126" y2="34" stroke="#b3261e" stroke-width="2"/>'
        + '<path d="M126 34 L115 35 L119 44 Z" fill="#b3261e"/>'
        + t(12, 78, "AI HARDWARE + ENERGY", 5.8, "#3f6f6c", 900, "start", 0.7)
        + t(12, 87, "GEORGIEVA: RATES TO RISE", 5.6, "#175e63", 700, "start", 0.4)
    )
    return svg(W, H, body)


# ------------------------------------------------------------------ hero deck

HERO_A = [
    {"id": "summit", "reg": "AP", "beat": "DIPLOMACY", "place": "SHENZHEN",
     "headline": "THREE POWERS,<br><span class='hl'>ONE TABLE</span>",
     "sub": "Trump, Xi and Putin hold the first-ever trilateral at APEC and sign a "
            "&#8216;peace declaration&#8217;: nuclear war &#8216;cannot be won&#8217;, "
            "yet no breakthrough on Ukraine or Iran.",
     "art": art_summit, "tags": "AP &#183; REUTERS", "dark": False, "accent": "#7E22CE"},
    {"id": "ipo", "reg": "MK", "beat": "LISTINGS", "place": "NEW YORK",
     "headline": "ANTHROPIC&#8217;S<br>$1.5TN IPO",
     "sub": "ANT prices at $83, raises a record $81bn &#8212; the biggest listing ever "
            "&#8212; peaks at $111 and a $2tn value, then closes +17% at $97.17.",
     "art": art_ipo, "tags": "BBC &#183; CNBC", "dark": False, "accent": "#B45309"},
    {"id": "voyager", "reg": "SC", "beat": "ASTRO", "place": "PASADENA",
     "headline": "VOYAGER 1:<br>ONE LIGHT-DAY",
     "sub": "NASA confirms the 49-year-old probe is 25.9bn km away &#8212; one light-day. "
            "Radio now takes two days there and back; &#8216;not done yet&#8217;; New York "
            "glows gold for the milestone.",
     "art": art_voyager, "tags": "NASA &#183; AP", "dark": False, "accent": "#0F766E"},
]

HERO_B = [
    {"id": "icj", "reg": "AP", "beat": "LAW", "place": "HAGUE",
     "headline": "ICJ:<br>GENOCIDE",
     "sub": "The World Court&#8217;s 1st genocide finding: Myanmar, against the Rohingya. "
            "Reparation ordered; survivors weep in the camps.",
     "art": art_icj_m, "tags": "ICJ &#183; REUTERS"},
    {"id": "cop31", "reg": "SC", "beat": "CLIMATE", "place": "ANTALYA",
     "headline": "GHOST COP?",
     "sub": "COP31&#8217;s 2nd Antalya draft deletes all fossil-fuel mentions &#8212; "
            "&#8216;ghost summit&#8217;, warn critics; no deal could be the first since 2009.",
     "art": art_cop_m, "tags": "UN NEWS &#183; GUARDIAN"},
    {"id": "jwst", "reg": "SC", "beat": "ASTRO", "place": "ANDROMEDA",
     "headline": "A STAR<br>EATS A STAR",
     "sub": "NASA data clinch the first watch of a red giant engulfing its companion star "
            "&#8212; in Andromeda, 2.5m light-years away.",
     "art": art_jwst_m, "tags": "NASA &#183; NATURE"},
    {"id": "gaza", "reg": "ME", "beat": "SECURITY", "place": "GAZA",
     "headline": "BEYOND<br>YELLOW LINE",
     "sub": "IDF completes its ground operation past the Yellow Line into central Gaza; "
            "Senate clears Trump&#8217;s Iran options as he eyes 2027.",
     "art": art_gaza_m, "tags": "BBC &#183; REUTERS"},
    {"id": "berlin", "reg": "EU", "beat": "SECURITY", "place": "BERLIN",
     "headline": "EUROPE HOLDS<br>THE LINE",
     "sub": "Berlin allies reject &#8216;Yalta 2.0&#8217;: UK sends long-range missiles; "
            "Putin says he won&#8217;t negotiate after the bridge strike.",
     "art": art_berlin_m, "tags": "BLOOMBERG &#183; BBC"},
    {"id": "gta", "reg": "MK", "beat": "GAMING", "place": "GLOBAL",
     "headline": "GTA VI<br>DAY ONE",
     "sub": "The 13-year wait is over: a 99 Metacritic, $1.65bn preorders, near-$2bn day "
            "one, &#8216;GTA flu&#8217; absences, 2m+ NZ-trick players.",
     "art": art_gta_m, "tags": "GUARDIAN &#183; EUROGAMER"},
    {"id": "imf", "reg": "MK", "beat": "ECONOMY", "place": "SHENZHEN",
     "headline": "THE 4.7%<br>WARNING",
     "sub": "Georgieva: AI-hardware demand and energy shocks hold global inflation near "
            "4.7% &#8212; and push interest rates up.",
     "art": art_imf_m, "tags": "IMF &#183; GUARDIAN"},
]

# ------------------------------------------------------------------- digest

MATRIX = [
    ("AP", [
        ("NO KIM MEETING", "Trump leaves Asia without a Kim meeting; Seoul welcomes the "
         "nuclear-risk dialogue track.", ["YONHAP"]),
        ("TAIWAN WARNING", "Xi tells Trump to &#8216;do the right thing&#8217; on Taiwan in "
         "their Shenzhen session.", ["SCMP"]),
        ("HAN RETRIAL ORDERED", "South Korea&#8217;s top court scraps ex-PM Han&#8217;s "
         "15-year term over martial law; retrial next.", ["YONHAP"]),
        ("JT&#8217;S $8.9BN RUSSIA HIT", "Japan Tobacco books an $8.9bn charge on Russia&#8217;s "
         "seizure of its business.", ["JAPAN TIMES"]),
        ("PAKISTAN ROAD SLAM", "Ten killed as a bus rams a gas tanker on a Pakistani motorway.",
         ["AL JAZEERA"]),
    ]),
    ("ME", [
        ("$48BN WAR BILL", "Iran-war costs pass $48bn; voices demand open estimates of base "
         "damage.", ["ARAB NEWS"]),
        ("RIYADH TOWER STRUCK", "Houthi attack damages the PIF tower &#8212; Riyadh&#8217;s "
         "tallest; Saudi Arabia condemns.", ["FT"]),
        ("HORMUZ MINES BLAZE", "Three tankers burn on Hormuz mines; flow lowest since May; "
         "IEA: worst-ever energy threat.", ["NYT", "EURONEWS"]),
        ("KATAIB STANDOFF ENDS", "Iraqi forces reach a compromise with Kataib Hezbollah after "
         "the armed showdown.", ["REUTERS"]),
        ("IAEA PRESSURE", "The West presses Iran at the IAEA board to let inspectors back into "
         "bombed sites.", ["REUTERS"]),
    ]),
    ("EU", [
        ("DRONES HIT EU EMBASSIES", "Kyiv drone raid damages Dutch and Austrian embassies; the "
         "Netherlands summons Russia&#8217;s envoy.", ["REUTERS"]),
        ("APPLE ORDER UNSEALED", "A tribunal upholds TM:315; the UK must disclose its secret "
         "Apple data order.", ["FT"]),
        ("EU-UK RESET TO WIRE", "Brussels reset summit goes down to the wire after a "
         "last-minute snag with France.", ["GUARDIAN"]),
        ("DON&#8217;T BUY AI GLASSES", "Dutch data watchdog AP: don&#8217;t buy camera AI "
         "glasses &#8212; privacy risk.", ["REUTERS"]),
        ("BRAND VIDEO STALEMATE", "Google refuses the Brand prison-message takedown; London "
         "warns of a new law.", ["GUARDIAN"]),
    ]),
    ("AM", [
        ("31.5M-ACRE OCEAN SALE", "US auctions 31.5m acres of Pacific seabed over a court "
         "ruling.", ["NYT"]),
        ("$15BN NYT CASE", "Judge lets Trump&#8217;s $15bn NYT&#8211;Penguin defamation suit "
         "proceed.", ["REUTERS"]),
        ("TPS FOR VENEZUELANS ENDS", "Appeals court lifts the order restoring TPS.", ["AP"]),
        ("CARACAS-WASH PACT", "Venezuela signs a US military pact post-Maduro; Hegseth tours.",
         ["BBC"]),
        ("MUSK: NOT MAGA", "Musk quits MAGA after a &#8216;foolish&#8217; record $446m midterm "
         "spend.", ["AP"]),
        ("WAYMO LEAVES FREEWAYS", "Waymo pulls all its robotaxis off US freeway routes.",
         ["BBC"]),
    ]),
    ("AF", [
        ("AFRICA: NO.1 CYBER TARGET", "Africa retakes top spot as the most-attacked region, a "
         "Nigeria surge led.", ["DARK READING"]),
        ("SENEGAL BOAT LOST", "Migrant boat bound for Spain capsizes off Senegal; dozens "
         "missing.", ["BBC"]),
        ("KENYA MINERALS TO US BID", "A US consortium wins Kenya&#8217;s minerals contract, "
         "beating China.", ["BBC"]),
        ("HEMEDTI DEATH SENTENCE", "Sudan: RSF&#8217;s Hemedti gets a 2nd death sentence over "
         "$396m.", ["AFRICANEWS"]),
        ("SOMALIA EXPELS UAE ENVOY", "Mogadishu calls the envoy &#8216;persona non grata&#8217; "
         "over invasion claims.", ["REUTERS"]),
        ("$2.3BN EGYPT IMF DEAL", "The IMF seals a $2.3bn Egypt deal as recovery gathers pace.",
         ["AFRICANEWS"]),
    ]),
    ("MK", [
        ("AI BUST DEEPENS", "S&P 500 falls 2%+ for a 6th straight losing week; Nvidia sheds "
         "$611bn in six sessions; AMD on a China report.", ["FT", "MARKETWATCH"]),
        ("VENDOR CYBER BLITZ", "JPMorgan, Visa and Mastercard report third-party-vendor "
         "attacks; Nadella: infrastructure &#8216;unpatchable&#8217;.", ["REUTERS"]),
        ("AI CHIP CRACKDOWN", "Commerce OKed 879,000+ AI-chip sales to Chinese firms; TSMC "
         "shuts a manufacturing loophole.", ["CNBC", "REUTERS"]),
        ("VAN GOGH $190.4M", "A Van Gogh hits a record $190.4m after the Nazi-era ownership "
         "row is resolved.", ["BBC"]),
    ]),
    ("SC", [
        ("ICE-CLIFF BRAKE", "MIT model: surface ridges buffer Antarctic ice cliffs &#8212; a "
         "brake on the collapse.", ["MIT", "SCIENCE DAILY"]),
        ("CROOKED WHALE UNVEILED", "Peru&#8217;s 6m-year-old pygmy sperm whale "
         "&#8216;huachafo&#8217; &#8212; mammaldom&#8217;s most lopsided face.",
         ["SCIENCE DAILY"]),
        ("OTTAVA: FIRST IN US", "J&amp;J&#8217;s FDA-cleared OTTAVA surgical robot is installed "
         "first in Houston &#8212; 10 procedures.", ["J&amp;J"]),
        ("MEASLES COMEBACK", "Vaccine fear drives the US measles resurgence; Pennsylvania logs "
         "its 8th measles-linked death.", ["AL JAZEERA", "REUTERS"]),
    ]),
]

PULSE = [
    ("GTA VI: $2BN DAY 1", "#B45309"),
    ("ANT $2TN PEAK +17%", "#1D4ED8"),
    ("ICJ: GENOCIDE VERDICT", "#7E22CE"),
    ("IMF: 4.7% INFLATION", "#0F766E"),
    ("FOSSIL FUELS DELETED", "#B91C1C"),
    ("VOYAGER: LIGHT-DAY", "#047857"),
]

SOURCES = ("AP &#183; REUTERS &#183; BBC &#183; GUARDIAN &#183; AL JAZEERA &#183; BLOOMBERG "
           "&#183; FT &#183; NYT &#183; CNBC &#183; MARKETWATCH &#183; UN NEWS &#183; ICJ "
           "&#183; IMF &#183; NASA &#183; NATURE &#183; SCIENCE DAILY &#183; YONHAP &#183; "
           "SCMP &#183; JAPAN TIMES &#183; ARAB NEWS &#183; AFRICANEWS &#183; DARK READING "
           "&#183; EUROGAMER &#183; EURONEWS &#183; MIT &#183; J&amp;J")


# --------------------------------------------------------------------- css

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:1024px;height:1024px;overflow:hidden;}
body{font-family:Lato,Arial,sans-serif;-webkit-font-smoothing:antialiased;color:#111827;
 background:#FBF8F1;}
.page{position:relative;width:1024px;height:1024px;overflow:hidden;background:#FBF8F1;}
.rule-top{position:absolute;top:6px;left:16px;right:16px;height:3px;background:#18181B;}
.mast-top{position:absolute;top:13px;left:16px;right:16px;height:16px;display:flex;
 justify-content:space-between;align-items:baseline;}
.papername{font-weight:900;font-size:13px;letter-spacing:2.6px;color:#111827;white-space:nowrap;}
.volumeline{font-weight:700;font-size:8.2px;letter-spacing:1.5px;color:#374151;white-space:nowrap;}
.dateline{position:absolute;top:30px;left:16px;height:34px;line-height:34px;white-space:nowrap;
 font-weight:900;font-size:29px;letter-spacing:-0.4px;color:#111827;}
.dateline .day{color:#991B1B;}
.counter{position:absolute;top:41px;right:16px;height:20px;line-height:17px;white-space:nowrap;
 font-weight:900;font-size:9px;letter-spacing:1.15px;color:#111827;
 border:1px solid #18181B;padding:1px 7px;background:#FFFFFF;}
.counter i{display:inline-block;width:6px;height:6px;background:#B91C1C;margin-right:6px;}
.pulse{position:absolute;top:70px;left:16px;right:16px;height:21px;background:#111827;
 display:flex;align-items:center;justify-content:space-between;padding:0 12px;}
.pulse b{font-weight:900;font-size:10.5px;letter-spacing:1px;color:#FBF8F1;white-space:nowrap;}
.pulse s{text-decoration:none;display:inline-block;width:6px;height:6px;margin-right:6px;
 vertical-align:1px;}
.rule-mast{position:absolute;top:93px;left:16px;right:16px;height:2px;background:#18181B;}
.hero{position:absolute;top:100px;left:16px;width:992px;height:506px;}
.hero-cap{position:absolute;top:0;left:0;right:0;height:11px;display:flex;
 justify-content:space-between;align-items:baseline;}
.hero-cap .l{font-weight:900;font-size:8.4px;letter-spacing:2.2px;color:#111827;}
.hero-cap .r{font-weight:700;font-size:7.4px;letter-spacing:1.3px;color:#374151;}
.rowA{position:absolute;top:13px;left:0;right:0;height:250px;display:grid;
 grid-template-columns:repeat(3,1fr);gap:10px;}
.rowB{position:absolute;top:271px;left:0;right:0;height:232px;display:grid;
 grid-template-columns:repeat(7,1fr);gap:7px;}
.panel{position:relative;background:#FFFFFF;border:1px solid #18181B;border-top:3px solid
 var(--accent);overflow:hidden;display:flex;flex-direction:column;}
.panel.a{padding:9px 12px 8px;}
.panel.b{padding:7px 9px 7px;}
.ptop{height:12px;display:flex;justify-content:space-between;align-items:baseline;flex:none;}
.panel.a .ptop{height:13px;}
.region{display:inline-flex;align-items:center;gap:4px;font-weight:900;letter-spacing:1.1px;
 color:var(--regtxt);white-space:nowrap;}
.region i{width:6px;height:6px;background:var(--accent);display:inline-block;flex:none;}
.panel.a .region{font-size:9px;}
.panel.b .region{font-size:7.4px;letter-spacing:.75px;}
.panel.b .region i{width:5px;height:5px;}
.place{font-weight:900;color:#374151;white-space:nowrap;}
.panel.a .place{font-size:7.4px;letter-spacing:1.2px;}
.panel.b .place{font-size:6.6px;letter-spacing:.9px;}
.art{width:auto;background:#000;overflow:hidden;flex:none;margin:5px -12px 0;}
.panel.a .art{height:104px;}
.art{background:var(--artbg,#FFFFFF);}
.panel.b .art{height:92px;margin:4px -9px 0;}
.art svg{display:block;width:100%;height:100%;}
.panel h2{font-weight:900;color:#111827;flex:none;}
.panel.a h2{margin-top:6px;font-size:20px;line-height:.95;letter-spacing:-.3px;}
.panel.b h2{margin-top:5px;font-size:13.2px;line-height:.99;letter-spacing:-.15px;}
.panel h2 .hl{color:#991B1B;}
.panel p{color:#1F2937;flex:none;}
.panel.a p{margin-top:5px;font-size:9.6px;line-height:1.26;}
.panel.b p{margin-top:4px;font-size:8.4px;line-height:1.16;}
.pfoot{margin-top:auto;border-top:1px solid #D4CDC0;padding-top:3px;display:flex;
 justify-content:space-between;align-items:baseline;flex:none;}
.pfoot .dl{font-weight:700;font-size:6.8px;letter-spacing:1.2px;color:#374151;white-space:nowrap;}
.pfoot .tags{font-weight:900;font-size:7px;letter-spacing:.8px;color:#111827;white-space:nowrap;}
.digest-head{position:absolute;top:610px;left:16px;right:16px;height:2px;background:#18181B;}
.digest-cap{position:absolute;top:614px;left:16px;right:16px;height:12px;display:flex;
 justify-content:space-between;align-items:baseline;}
.digest-cap .l{font-weight:900;font-size:9.4px;letter-spacing:2.4px;color:#111827;}
.digest-cap .r{font-weight:700;font-size:8px;letter-spacing:1.2px;color:#374151;}
.cols{position:absolute;top:630px;left:16px;width:992px;height:372px;display:grid;
 grid-template-columns:repeat(7,1fr);gap:6px;}
.col{background:#FFFFFF;border:1px solid #D4CDC0;border-top:3px solid var(--accent);
 overflow:hidden;padding:0 7px 3px;}
.colhead{height:19px;display:flex;justify-content:space-between;align-items:baseline;
 border-bottom:1px solid #D4CDC0;padding-top:3px;}
.colhead .cn{font-weight:900;font-size:8.2px;letter-spacing:.55px;color:var(--regtxt);
 white-space:nowrap;}
.colhead .cc{font-weight:900;font-size:6.8px;letter-spacing:.7px;color:#374151;white-space:nowrap;}
.st{padding:4px 0 0;}
.st + .st{margin-top:5px;padding-top:5px;border-top:1px solid #E7E1D6;}
.st-lead{display:block;font-weight:900;font-size:9.4px;line-height:1.04;color:#111827;}
.st-fact{display:block;margin-top:1px;font-weight:400;font-size:8.4px;line-height:1.14;
 color:#1F2937;}
.st-tag{font-weight:900;font-size:7px;letter-spacing:.35px;color:var(--regtxt);}
.footer{position:absolute;top:1006px;left:16px;right:16px;height:14px;background:#111827;
 display:flex;justify-content:space-between;align-items:center;padding:0 8px;}
.footer .fl{font-weight:700;font-size:5.6px;letter-spacing:.1px;color:#F1EADB;white-space:nowrap;}
.footer .fr{font-weight:900;font-size:5.6px;letter-spacing:.4px;color:#FBF8F1;white-space:nowrap;}
"""


def panel_a_html(p):
    label, _, regtxt, _short = REGIONS[p["reg"]]
    style = "--accent:%s;--regtxt:%s;--artbg:#FBF8F1;" % (p["accent"], regtxt)
    return (
        '<section class="panel a" data-story="%s" style="%s">' % (p["id"], style)
        + '<div class="ptop"><span class="region"><i></i>%s &#183; %s</span>'
          '<span class="place">%s</span></div>' % (label, p["beat"], p["place"])
        + '<div class="art">%s</div>' % p["art"]()
        + '<h2>%s</h2>' % p["headline"]
        + '<p>%s</p>' % p["sub"]
        + '<div class="pfoot"><span class="dl">THU 19 NOV 2026</span>'
          '<span class="tags">[%s]</span></div>' % p["tags"]
        + "</section>"
    )


def panel_b_html(p):
    _label, accent, regtxt, short = REGIONS[p["reg"]]
    style = "--accent:%s;--regtxt:%s;--artbg:#FBF8F1;" % (accent, regtxt)
    return (
        '<section class="panel b" data-story="%s" style="%s">' % (p["id"], style)
        + '<div class="ptop"><span class="region"><i></i>%s</span>'
          '<span class="place">%s</span></div>' % (short, p["place"])
        + '<div class="art">%s</div>' % p["art"]()
        + '<h2>%s</h2>' % p["headline"]
        + '<p>%s</p>' % p["sub"]
        + '<div class="pfoot"><span class="tags">[%s]</span></div>' % p["tags"]
        + "</section>"
    )


def story_html(sid, st):
    lead, fact, tags = st
    tag_txt = " ".join("[%s]" % x for x in tags)
    return (
        '<div class="st" data-story="%s"><span class="st-lead">%s</span>'
        '<span class="st-fact">%s <span class="st-tag">%s</span></span></div>'
        % (sid, lead, fact, tag_txt)
    )


def col_html(key, stories):
    _label, accent, regtxt, short = REGIONS[key]
    style = "--accent:%s;--regtxt:%s;" % (accent, regtxt)
    return (
        '<div class="col" style="%s">' % style
        + '<div class="colhead"><span class="cn">%s</span><span class="cc">%d BRIEFS</span></div>'
          % (short, len(stories))
        + "".join(story_html("m-%s-%d" % (key, i), s) for i, s in enumerate(stories))
        + "</div>"
    )


def build_html():
    pulse = "".join('<b><s style="background:%s"></s>%s</b>' % (c, txt) for txt, c in PULSE)
    cols = "".join(col_html(k, stories) for k, stories in MATRIX)
    hero_a = "".join(panel_a_html(p) for p in HERO_A)
    hero_b = "".join(panel_b_html(p) for p in HERO_B)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>THURSDAY, NOVEMBER 19, 2026</title><style>' + CSS + '</style></head><body>'
        '<div class="page">'
        '<div class="rule-top"></div>'
        '<div class="mast-top"><span class="papername">THE WORLD CANVAS DAILY</span>'
        '<span class="volumeline">VOL. II &#183; NO. 20 &#183; LATE FINAL EDITION</span></div>'
        '<div class="dateline"><span class="day">THURSDAY,</span> NOVEMBER 19, 2026</div>'
        '<div class="counter"><i></i>45 VERIFIED STORIES &#183; 7 REGIONS &#183; 26 SOURCES</div>'
        '<div class="pulse">' + pulse + '</div>'
        '<div class="rule-mast"></div>'
        '<div class="hero"><div class="hero-cap"><span class="l">TODAY&#8217;S TOP 10</span>'
        '<span class="r">EVERY STORY DATED 19 NOV 2026 &#183; SOURCES IN BRACKETS</span></div>'
        + '<div class="rowA">' + hero_a + '</div>' + '<div class="rowB">' + hero_b + '</div></div>'
        '<div class="digest-head"></div>'
        '<div class="digest-cap"><span class="l">WORLD DIGEST MATRIX</span>'
        '<span class="r">35 MORE VERIFIED BRIEFS &#183; ALL 7 REGIONS &#183; 0 CLIPPED</span></div>'
        '<div class="cols">' + cols + '</div>'
        '<div class="footer"><span class="fl">SOURCES: ' + SOURCES + '</span>'
        '<span class="fr">45/45 VERIFIED &#183; OFFLINE DETERMINISTIC RENDER</span></div>'
        '</div></body></html>'
    )


# --------------------------------------------------------------------- audit

AUDIT_JS = """() => {
  const out = {doc:[document.documentElement.scrollWidth, document.documentElement.scrollHeight],
               stories:0, issues:[], contrast:[], notes:[]};
  const add = (m) => { if (out.issues.length < 80) out.issues.push(m); };
  if (out.doc[0] !== 1024 || out.doc[1] !== 1024) add('document ' + out.doc.join('x'));

  // story census
  const seen = {};
  document.querySelectorAll('[data-story]').forEach(el => { seen[el.dataset.story] = (seen[el.dataset.story] || 0) + 1; });
  out.ids = Object.keys(seen).sort();
  out.stories = out.ids.length;
  const dupes = Object.keys(seen).filter(k => seen[k] > 1);
  dupes.forEach(k => add('duplicate story id ' + k));

  const label = (el) => el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className
      ? '.' + el.className.trim().split(/\\s+/).join('.') : '');

  // overflow inside boxes
  document.querySelectorAll('.panel,.col,.st,.pulse,.footer,.mast-top,.dateline,.counter,' +
      '.digest-cap,.hero-cap,.ptop,.pfoot,.colhead').forEach(el => {
    if (el.scrollHeight - el.clientHeight > 1)
      add('scroll-y ' + label(el) + ' +' + (el.scrollHeight - el.clientHeight));
    if (el.scrollWidth - el.clientWidth > 1)
      add('scroll-x ' + label(el) + ' +' + (el.scrollWidth - el.clientWidth));
  });

  // nothing may stick outside the page or outside its card
  const page = document.querySelector('.page').getBoundingClientRect();
  document.querySelectorAll('.panel,.col,.digest-head,.digest-cap,.cols,.footer,.pulse,' +
      '.dateline,.counter,.rule-top,.rule-mast,.mast-top,.hero').forEach(el => {
    const b = el.getBoundingClientRect();
    if (b.left < page.left - 0.5 || b.top < page.top - 0.5 ||
        b.right > page.right + 0.5 || b.bottom > page.bottom + 0.5)
      add('page escape ' + label(el));
  });
  document.querySelectorAll('.panel').forEach(p => {
    const pb = p.getBoundingClientRect();
    p.querySelectorAll('*').forEach(el => {
      const b = el.getBoundingClientRect();
      if (!b.width && !b.height) return;
      if (b.top < pb.top - 0.6 || b.left < pb.left - 0.6 ||
          b.bottom > pb.bottom + 0.6 || b.right > pb.right + 0.6)
        add('card escape ' + label(p) + ' / ' + label(el));
    });
  });

  // overlap between sibling cards and stories
  const inter = (a, b) => !(a.right <= b.left + 0.5 || b.right <= a.left + 0.5 ||
      a.bottom <= b.top + 0.5 || b.bottom <= a.top + 0.5);
  const sibs = (sel, parent) => document.querySelectorAll(parent).forEach(p => {
    const kids = [...p.querySelectorAll(':scope > ' + sel)];
    for (let i = 0; i < kids.length; i++)
      for (let j = i + 1; j < kids.length; j++)
        if (inter(kids[i].getBoundingClientRect(), kids[j].getBoundingClientRect()))
          add('overlap ' + label(kids[i]) + ' x ' + label(kids[j]));
  });
  sibs('.panel', '.rowA'); sibs('.panel', '.rowB'); sibs('.col', '.cols');
  sibs('.st', '.col'); sibs('.pfoot', '.panel');
  const sec = ['.rule-top','.mast-top','.dateline','.counter','.pulse','.rule-mast',
               '.hero','.digest-head','.digest-cap','.cols','.footer']
      .map(s => [s, document.querySelector(s).getBoundingClientRect()]);
  for (let i = 0; i < sec.length; i++)
    for (let j = i + 1; j < sec.length; j++)
      if (inter(sec[i][1], sec[j][1])) add('section overlap ' + sec[i][0] + ' x ' + sec[j][0]);

  // story text must not touch its own bounds AND must fit the column
  document.querySelectorAll('.col').forEach((c, ci) => {
    const cb = c.getBoundingClientRect();
    const last = c.querySelector('.st:last-child');
    if (last && last.getBoundingClientRect().bottom > cb.bottom - 1)
      add('col' + (ci+1) + ' stories overflow');
  });

  // svg ink inside its viewBox
  document.querySelectorAll('svg').forEach((s, i) => {
    const vb = s.viewBox.baseVal; let b;
    try { b = s.getBBox(); } catch (e) { add('svg' + i + ' bbox failed'); return; }
    const tol = 0.6;
    if (b.x < vb.x - tol || b.y < vb.y - tol ||
        b.x + b.width > vb.x + vb.width + tol || b.y + b.height > vb.y + vb.height + tol)
      add('svg' + i + ' ink outside viewBox');
  });

  // contrast: story-bearing text must clear 7:1 on its real background
  const parse = (s) => s.match(/\\d+(\\.\\d+)?/g).slice(0,3).map(Number);
  const lum = ([r,g,b]) => { const f = v => { v/=255; return v <= 0.04045 ? v/12.92 :
      Math.pow((v+0.055)/1.055, 2.4); };
      return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b); };
  const ratio = (a, b) => { const l1 = Math.max(lum(a), lum(b)), l2 = Math.min(lum(a), lum(b));
      return (l1 + 0.05) / (l2 + 0.05); };
  const bgOf = (el) => { let n = el;
      while (n) { const c = getComputedStyle(n).backgroundColor;
          if (c && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(c)) return parse(c);
          n = n.parentElement; }
      return [255,255,255]; };
  document.querySelectorAll('.st-lead,.st-fact,.st-tag,.panel h2,.panel h2 .hl,.panel p,' +
      '.panel .region,.panel .place,.panel .tags,.pulse b,.papername,.volumeline,.dateline,' +
      '.dateline .day,.counter,.hero-cap .l,.hero-cap .r,.digest-cap .l,.digest-cap .r,' +
      '.colhead .cn,.colhead .cc,.pfoot .dl,.footer .fl,.footer .fr').forEach(el => {
    const r = ratio(parse(getComputedStyle(el).color), bgOf(el));
    if (r < 7) add('contrast ' + label(el) + ' ' + r.toFixed(2) + ':1');
  });
  out.contrast = [...document.querySelectorAll('.st-lead')].slice(0,4).map(el =>
      ratio(parse(getComputedStyle(el).color), bgOf(el)).toFixed(1));
  return out;
}"""


# ------------------------------------------------------------------- render

def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("screenshot is not a PNG")
    return struct.unpack(">II", data[16:24])


def render_with_playwright(expect_stories):
    from playwright.sync_api import sync_playwright

    shots = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                  "--force-color-profile=srgb", "--font-render-hinting=none",
                  "--disable-lcd-text"],
        )
        for scale, dest in ((1, RAW_1X), (2, RAW_2X)):
            page = browser.new_page(viewport={"width": 1024, "height": 1024},
                                    device_scale_factor=scale)
            page.goto(HTML_PATH.as_uri())
            page.wait_for_timeout(350)
            if scale == 1:
                audit = page.evaluate(AUDIT_JS)
                audit["expected"] = expect_stories
            page.screenshot(path=str(dest),
                            clip={"x": 0, "y": 0, "width": 1024, "height": 1024})
            shots[scale] = dest.read_bytes()
            page.close()
        page = browser.new_page(viewport={"width": 1024, "height": 1024},
                                device_scale_factor=1)
        page.goto(HTML_PATH.as_uri())
        page.wait_for_timeout(300)
        shot_b = page.screenshot(clip={"x": 0, "y": 0, "width": 1024, "height": 1024})
        page.close()
        browser.close()
    audit["repeat_identical"] = (shot_b == shots[1])
    return audit


def sharpness_metrics(img):
    from PIL import ImageFilter, ImageStat

    g = img.convert("L")
    full = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]
    text = g.crop((16, 630, 1008, 1000)).filter(ImageFilter.FIND_EDGES)
    return full, ImageStat.Stat(text).var[0]


def encode_jpeg(image):
    best = None
    for quality in JPEG_QUALITIES:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, subsampling=0,
                   optimize=True, progressive=False)
        data = buf.getvalue()
        if best is None:
            best = (quality, data)
        if len(data) <= JPEG_TARGET:
            return quality, data
    return best


def main():
    expect = set(p["id"] for p in HERO_A) | set(p["id"] for p in HERO_B)
    expect |= {"m-%s-%d" % (key, i) for key, stories in MATRIX for i, _ in enumerate(stories)}

    html_text = build_html()
    HTML_PATH.write_text(html_text, encoding="utf-8")

    try:
        audit = render_with_playwright(sorted(expect))
    except ImportError:
        print("Playwright unavailable; falling back to Chrome CLI (no audit).")
        subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--window-size=1024,1024", "--screenshot=" + str(RAW_1X),
                        HTML_PATH.as_uri()], check=True)
        RAW_2X.write_bytes(RAW_1X.read_bytes())
        audit = None

    if audit is not None:
        print("AUDIT doc=%s stories=%d repeat_identical=%s"
              % (audit["doc"], audit["stories"], audit["repeat_identical"]))
        missing = sorted(expect - set(audit["ids"]))
        extra = sorted(set(audit["ids"]) - expect)
        if missing:
            print("  MISSING story ids:", missing)
        if extra:
            print("  EXTRA story ids:", extra)
        if audit["issues"]:
            print("AUDIT ISSUES:", len(audit["issues"]))
            for issue in audit["issues"]:
                print("  -", issue)
        assert audit["stories"] == len(expect) and not missing and not extra, \
            "story census mismatch"
        assert not audit["issues"], "layout audit reported issues"
        print("  sample lead contrast: %s:1" % ", ".join(audit["contrast"]))

    raw1 = RAW_1X.read_bytes()
    raw2 = RAW_2X.read_bytes()
    assert png_size(raw1) == (1024, 1024), "1x screenshot wrong size"
    assert png_size(raw2) == (2048, 2048), "2x screenshot wrong size"

    from PIL import Image

    native = Image.open(io.BytesIO(raw1)).convert("RGB")
    super1 = Image.open(io.BytesIO(raw2)).convert("RGB").resize(
        (1024, 1024), Image.LANCZOS)

    (nf, nt) = sharpness_metrics(native)
    (sf, st) = sharpness_metrics(super1)
    print("sharpness  full / small-text-region variance")
    print("  native 1x: %.1f / %.1f" % (nf, nt))
    print("  2x->1x   : %.1f / %.1f" % (sf, st))
    super1.save(SUPER_1X)
    if st >= nt:
        chosen, mode = super1, "2x supersampled -> Lanczos"
    else:
        chosen, mode = native, "native 1x"

    quality, data = encode_jpeg(chosen)
    assert data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9", "not a complete JPEG"
    assert len(data) <= JPEG_TARGET, "entry.png over %d bytes" % JPEG_TARGET
    ENTRY.write_bytes(data)

    for size, dest in ((300, PREVIEW_300), (600, PREVIEW_600)):
        chosen.resize((size, size), Image.LANCZOS).save(dest)

    print("entry.png: 1024x1024 JPEG q%d 4:4:4 via %s, %d bytes (%.1f KiB)"
          % (quality, mode, len(data), len(data) / 1024))
    for preview in (PREVIEW_300, PREVIEW_600):
        print("%s: %dx%d %d bytes" % (preview, *png_size(preview.read_bytes()),
                                      preview.stat().st_size))


if __name__ == "__main__":
    main()
