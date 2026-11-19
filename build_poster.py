#!/usr/bin/env python3
"""Build the 1024x1024 visual broadsheet for Thursday 19 November 2026 (entry.png), v5.

Forty-four stories, every one first reported on Thursday 19 November 2026:
twelve illustrated cards in rows of 3 / 4 / 5 (each with an original inline SVG
scene), a world locator map with numbered pins for those twelve cards, and 32
single-line dispatches in two columns. A DATE CHECK footer names the adjacent
Wednesday 18 and Friday 20 stories that were left out on purpose.

The page is rendered in headless Chromium at 1x and 2x device scale. The same
pass runs a DOM geometry audit (exact size, no overflow, no wrapped one-line
text, no clipped or overlapping cards, labels, SVG text or map badges, a 44/44
story census and an ink-contrast floor) and the build fails on any issue. The
sharper of the native 1x and the Lanczos-downsampled 2x render (measured on the
dispatch columns) is encoded as a 4:4:4 baseline JPEG.

Build-time tooling only (Playwright + Pillow). The shipped runtime (main.py) is
standard library only. Everything rendered is local: system Lato, inline SVG
and the Natural Earth 1:110m land outline stored in world_land_110m.svgpath.
"""

import io
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "entry.png"
WORLD_PATH = ROOT / "world_land_110m.svgpath"
HTML_PATH = Path("/tmp/world_news_canvas_v5.html")
RAW_1X = Path("/tmp/world_news_canvas_v5_1x.png")
RAW_2X = Path("/tmp/world_news_canvas_v5_2x.png")
PREVIEW_300 = Path("/tmp/news_v5_300.png")
PREVIEW_512 = Path("/tmp/news_v5_512.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITIES = (94, 93)
JPEG_MAX = 680 * 1024
HARD_LIMIT = 1048576

PAPER = "#FAF6EE"
INK = "#111827"

# key: (label, bright fill, dark ink)
REGIONS = {
    "EU": ("EUROPE", "#1D4ED8", "#1E40AF"),
    "AM": ("AMERICAS", "#B91C1C", "#991B1B"),
    "AP": ("ASIA-PACIFIC", "#7E22CE", "#6B21A8"),
    "AF": ("AFRICA", "#B45309", "#92400E"),
    "ME": ("MIDDLE EAST", "#0E7490", "#155E75"),
    "OC": ("OCEANIA", "#BE185D", "#9D174D"),
    "GL": ("GLOBAL/SCIENCE", "#15803D", "#166534"),
}
ORDER = ["EU", "AM", "AP", "AF", "ME", "OC", "GL"]


# ------------------------------------------------------------------ svg utils

def n(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def svg(w, h, body, cls="art-svg"):
    return ('<svg class="%s" viewBox="0 0 %s %s" preserveAspectRatio="none" '
            'xmlns="http://www.w3.org/2000/svg">%s</svg>' % (cls, n(w), n(h), body))


def t(x, y, s, size, fill, weight=900, anchor="start", ls=0.0, extra=""):
    a = ' text-anchor="%s"' % anchor if anchor != "start" else ""
    return ('<text class="lbl" x="%s" y="%s"%s font-family="Lato" font-size="%s" '
            'font-weight="%s" letter-spacing="%s" fill="%s"%s>%s</text>'
            % (n(x), n(y), a, n(size), weight, n(ls), fill, extra, s))


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=1, extra=""):
    r = '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"' % (n(x), n(y), n(w), n(h), fill)
    if rx:
        r += ' rx="%s"' % n(rx)
    if stroke:
        r += ' stroke="%s" stroke-width="%s"' % (stroke, n(sw))
    return r + extra + "/>"


def circle(cx, cy, r, fill, stroke=None, sw=1, extra=""):
    c = '<circle cx="%s" cy="%s" r="%s" fill="%s"' % (n(cx), n(cy), n(r), fill)
    if stroke:
        c += ' stroke="%s" stroke-width="%s"' % (stroke, n(sw))
    return c + extra + "/>"


def line(x1, y1, x2, y2, stroke, sw=1, dash=None, extra=""):
    s = ('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"'
         % (n(x1), n(y1), n(x2), n(y2), stroke, n(sw)))
    if dash:
        s += ' stroke-dasharray="%s"' % dash
    return s + extra + "/>"


def path(d, fill="none", stroke=None, sw=1, extra=""):
    p = '<path d="%s" fill="%s"' % (d, fill)
    if stroke:
        p += ' stroke="%s" stroke-width="%s"' % (stroke, n(sw))
    return p + extra + "/>"


def poly(pts, fill, stroke=None, sw=1):
    d = "M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts) + " Z"
    return path(d, fill, stroke, sw)


def star_d(cx, cy, r, inner=0.42):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * inner
        pts.append("%s %s" % (n(cx + rr * math.cos(ang)), n(cy + rr * math.sin(ang))))
    return "M" + " L".join(pts) + " Z"


def lingrad(gid, stops, x2="0", y2="1"):
    s = "".join('<stop offset="%s" stop-color="%s"/>' % (o, c) for o, c in stops)
    return ('<linearGradient id="%s" x1="0" y1="0" x2="%s" y2="%s">%s</linearGradient>'
            % (gid, x2, y2, s))


# ------------------------------------------------------------ flag medallions

def flag_us(cx, cy, r, cid):
    x0, y0, w = cx - r, cy - r, 2 * r
    stripes = "".join(rect(x0, y0 + i * w / 7, w, w / 7 + 0.3, "#B42318" if i % 2 == 0 else "#F8F5EE")
                      for i in range(7))
    stars = "".join(circle(x0 + w * 0.46 * (c + 0.75) / 3.6, y0 + w * 0.54 * (rr + 0.8) / 3.6,
                           max(0.6, r * 0.055), "#F8F5EE") for rr in range(3) for c in range(3))
    return ('<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (cid, n(cx), n(cy), n(r))
            + '<g clip-path="url(#%s)">' % cid + stripes
            + rect(x0, y0, w * 0.46, w * 0.54, "#1F3A6E") + stars + "</g>")


def flag_cn(cx, cy, r, cid):
    x0, y0, w = cx - r, cy - r, 2 * r
    small = "".join(path(star_d(x0 + w * a, y0 + w * b, r * 0.13), "#F6C945")
                    for a, b in ((0.56, 0.18), (0.66, 0.32), (0.66, 0.49), (0.56, 0.63)))
    return ('<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (cid, n(cx), n(cy), n(r))
            + '<g clip-path="url(#%s)">' % cid + rect(x0, y0, w, w, "#D0312D")
            + path(star_d(x0 + w * 0.3, y0 + w * 0.34, r * 0.38), "#F6C945") + small + "</g>")


def flag_ru(cx, cy, r, cid):
    x0, y0, w = cx - r, cy - r, 2 * r
    return ('<clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (cid, n(cx), n(cy), n(r))
            + '<g clip-path="url(#%s)">' % cid + rect(x0, y0, w, w, "#F8F5EE")
            + rect(x0, y0 + w / 3, w, w / 3 + 0.2, "#2B4C9B")
            + rect(x0, y0 + 2 * w / 3, w, w / 3, "#D0312D") + "</g>")


# ------------------------------------------------------- row 1 art (322x118)

def art_apec():
    W, H = 322, 118
    b = ('<defs><radialGradient id="aG" cx="50%" cy="38%" r="70%">'
         '<stop offset="0" stop-color="#22345E"/><stop offset="1" stop-color="#0A1226"/>'
         '</radialGradient></defs>' + rect(0, 0, W, H, "url(#aG)"))
    # spotlight rays
    for x in (60, 161, 262):
        b += poly([(x - 8, 0), (x + 8, 0), (x + 34, 92), (x - 34, 92)], "#FFFFFF") \
            .replace('fill="#FFFFFF"', 'fill="#FFFFFF" fill-opacity=".05"')
    # round table
    b += '<ellipse cx="161" cy="94" rx="118" ry="17" fill="#5B3A1E"/>'
    b += '<ellipse cx="161" cy="91" rx="118" ry="16" fill="#9A6634"/>'
    b += '<ellipse cx="161" cy="91" rx="96" ry="11" fill="none" stroke="#C38A4E" stroke-width="1.2"/>'
    # gold triangle linking the three
    b += path("M60 46 L161 40 L262 46", "none", "#E9B949", 1.4, ' stroke-dasharray="3 3"')
    for cx, cy, fn, cid in ((60, 48, flag_us, "fUS"), (161, 42, flag_cn, "fCN"), (262, 48, flag_ru, "fRU")):
        b += circle(cx, cy + 2, 29, "#000000", extra=' fill-opacity=".35"')
        b += fn(cx, cy, 27, cid)
        b += circle(cx, cy, 27, "none", "#F2C94C", 2.4)
    # dove of the declaration, centred above the table
    # the signed declaration lying on the table
    b += poly([(143, 84), (177, 84), (181, 94), (139, 94)], "#F8F5EE", "#C9A227", 0.8)
    for y in (87.5, 90.5):
        b += line(146, y, 174, y, "#B8A985", 0.8)
    b += t(161, 113, "SHENZHEN &#183; APEC 2026", 8.4, "#E9D49A", 900, "middle", 2.2)
    return svg(W, H, b)


ANT_SERIES = [  # (x, price) — allocation, opening pop, $111.50 high, $97.17 close
    (24, 83.0), (34, 83.0), (40, 101.0), (48, 106.5), (56, 104.0), (64, 109.2), (72, 111.5),
    (80, 108.4), (90, 109.6), (100, 105.8), (112, 107.2), (124, 103.0), (138, 104.6),
    (152, 101.2), (166, 102.8), (180, 99.4), (194, 101.0), (208, 98.2), (222, 99.8),
    (236, 97.0), (250, 98.6), (262, 96.4), (274, 97.8), (284, 97.17)]


def art_anthropic():
    W, H = 322, 118

    def py(p):
        return 104 - (p - 80) / (112 - 80) * 62

    b = (lingrad("anG", [("0", "#FFF7EC"), ("1", "#F6E7D3")]) + lingrad("anF", [("0", "#D97757"), ("1", "#F6E7D3")]))
    b = "<defs>" + b + "</defs>" + rect(0, 0, W, H, "url(#anG)")
    for p in (90, 100, 110):
        b += line(18, py(p), 304, py(p), "#E7D3BA", 0.8)
    pts = [(x, py(p)) for x, p in ANT_SERIES]
    d = "M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts)
    b += path(d + " L284 104 L24 104 Z", "url(#anF)", extra=' fill-opacity=".45"')
    b += line(18, py(83), 304, py(83), "#7C2D12", 1.2, "4 3")
    b += path(d, "none", "#B4482B", 2.6, ' stroke-linejoin="round" stroke-linecap="round"')
    b += circle(24, py(83), 3.6, "#7C2D12")
    b += circle(72, py(111.5), 4.4, "#FFFFFF", "#B4482B", 2.4)
    b += circle(284, py(97.17), 4.4, "#B4482B", "#FFFFFF", 1.6)
    b += line(72, py(111.5) - 6, 72, 31, "#B4482B", 1)
    # labels sit in empty bands: above the curve, and under the allocation line
    b += t(66, 17, "PEAK $111.50", 11, "#7C2D12", 900, "start", 0.4)
    b += t(66, 28, "&#8776; $2TN VALUE", 7.6, "#9A3412", 900, "start", 0.9)
    b += t(304, 36, "CLOSE $97.17", 11, "#7C2D12", 900, "end", 0.3)
    b += t(304, 47, "+17% ON DAY ONE", 7.6, "#9A3412", 900, "end", 0.9)
    b += t(16, 114, "ANT &#183; NASDAQ", 8.6, "#111827", 900, "start", 1.4)
    b += t(304, 114, "$83 ALLOCATION", 8.6, "#7C2D12", 900, "end", 0.9)
    return svg(W, H, b)


def art_icj():
    W, H = 322, 118
    b = ("<defs>" + lingrad("icG", [("0", "#24324F"), ("1", "#3D2E5C")]) + "</defs>"
         + rect(0, 0, W, H, "url(#icG)"))
    # Peace Palace silhouette
    pal = "#151B2E"
    b += rect(40, 86, 242, 32, pal)
    for x in range(48, 276, 14):
        b += path("M%s 86 L%s 79 L%s 86 Z" % (x, x + 6, x + 12), pal)
        b += rect(x + 3, 92, 5, 12, "#2E3A5C")
    b += rect(240, 52, 26, 34, pal) + path("M238 52 L253 34 L268 52 Z", pal) + rect(251, 26, 4, 9, pal)
    b += circle(253, 64, 4.5, "#E9C46A")
    b += rect(70, 70, 34, 16, pal) + path("M68 70 L87 58 L106 70 Z", pal)
    # scales of justice
    g = "#F2C94C"
    b += rect(159, 18, 4, 62, g) + rect(146, 78, 30, 5, g, 1.5) + circle(161, 16, 4.5, g)
    b += rect(111, 26, 100, 3.4, g, 1.5)
    for cx in (118, 204):
        b += line(cx, 29, cx - 13, 55, g, 1.2) + line(cx, 29, cx + 13, 55, g, 1.2)
        b += path("M%s 55 Q%s 66 %s 55 Z" % (cx - 16, cx, cx + 16), g)
    b += t(161, 112, "THE HAGUE &#183; FIRST STATE GENOCIDE RULING", 7.8, "#F3E9C6", 900, "middle", 1.6)
    return svg(W, H, b)


# ------------------------------------------------------- row 2 art (240x86)

def art_gta():
    W, H = 240, 86
    b = ("<defs>" + lingrad("gtG", [("0", "#2B1055"), ("0.55", "#D53A9D"), ("1", "#FFB347")])
         + lingrad("gtS", [("0", "#FFE29A"), ("1", "#FF7A59")]) + "</defs>"
         + rect(0, 0, W, H, "url(#gtG)"))
    b += circle(150, 56, 28, "url(#gtS)")
    for i, y in enumerate((58, 65, 71, 76)):
        b += rect(118, y, 64, 1.6 + i * 0.6, "#E2558F")
    b += rect(0, 72, W, 14, "#1A0B33")
    # palms
    for x, s in ((206, 1.0), (224, 0.8)):
        b += path("M%s 86 Q%s %s %s %s" % (x, x - 4 * s, 60, x + 2 * s, 34 * s + 10 * (1 - s) + 6),
                  "none", "#1A0B33", 3 * s)
        top = (x + 2 * s, 34 * s + 10 * (1 - s) + 6)
        for dx, dy in ((-18, 6), (-14, -4), (16, 4), (12, -6), (2, -10)):
            b += path("M%s %s Q%s %s %s %s" % (n(top[0]), n(top[1]), n(top[0] + dx * 0.6 * s),
                      n(top[1] + dy - 6 * s), n(top[0] + dx * s), n(top[1] + dy * s + 8 * s)),
                      "none", "#1A0B33", 2.6 * s)
    b += t(16, 60, "VI", 54, "#FFFFFF", 900, "start", -1,
           ' stroke="#3B0A57" stroke-width="2.4" paint-order="stroke"')
    # metascore chip
    b += rect(90, 12, 34, 30, "#16A34A", 3)
    b += t(107, 35, "99", 20, "#FFFFFF", 900, "middle")
    b += t(107, 52, "METASCORE", 6.6, "#FFFFFF", 900, "middle", 0.8)
    return svg(W, H, b)


def art_cop():
    W, H = 240, 86
    b = rect(0, 0, W, H, "#EFE6D3")
    b += circle(196, 43, 40, "#E3D5B8")
    # draft sheet
    b += rect(22, 9, 112, 72, "#000000", 2, extra=' fill-opacity=".12"')
    b += rect(18, 6, 112, 72, "#FFFFFF", 2, "#B8A985", 1)
    b += t(26, 19, "COP31 DRAFT 2", 7.4, "#374151", 900, "start", 1.2)
    for y in (27, 33, 55, 61, 67):
        b += rect(26, y, 96 if y != 67 else 60, 2.4, "#CBBF9F", 1)
    b += t(26, 48, "FOSSIL FUELS", 11.5, "#111827", 900, "start", 0.4)
    b += rect(23, 43, 104, 3, "#DC2626", 1)
    # electrification badge
    b += circle(190, 43, 30, "#15803D")
    b += path("M192 20 L180 45 L189 45 L185 63 L200 37 L191 37 L196 20 Z", "#FDE68A")
    b += t(190, 82, "35% ELECTRIC BY 2035", 6.8, "#14532D", 900, "middle", 0.6)
    return svg(W, H, b)


def art_cyclone():
    W, H = 240, 86
    b = ("<defs>" + lingrad("cyG", [("0", "#0E4C7A"), ("1", "#0A2E4D")]) + "</defs>"
         + rect(0, 0, W, H, "url(#cyG)"))
    land = "M0 0 L172 0 L160 8 L148 13 L136 22 L124 31 L114 38 L102 46 L90 56 L78 66 L64 76 L52 86 L0 86 Z"
    b += path(land, "#C9B98F") + path(land, "none", "#E9DDB8", 1.4)
    b += t(26, 30, "ODISHA", 11, "#3F3418", 900, "start", 1.6)
    b += t(26, 42, "~300,000 MOVED", 7, "#3F3418", 900, "start", 0.6)
    # track
    b += path("M226 82 Q200 70 184 56 Q160 42 126 34", "none", "#FDE68A", 1.6, ' stroke-dasharray="3 3"')
    b += path("M126 34 L135 31 L133 39 Z", "#FDE68A")
    b += circle(119, 33, 4, "#DC2626", "#FFFFFF", 1.4)
    # spiral storm
    cx, cy = 186, 54
    b += circle(cx, cy, 21, "#FFFFFF", extra=' fill-opacity=".14"')
    for k in range(3):
        a0 = k * 2 * math.pi / 3
        pts = []
        for i in range(18):
            a = a0 + i * 0.22
            r = 4 + i * 1.0
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        b += path("M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts), "none", "#FFFFFF", 3,
                  ' stroke-linecap="round"')
    b += circle(cx, cy, 3.4, "#0A2E4D")
    b += t(232, 16, "AKVAN", 10, "#FFFFFF", 900, "end", 1.6)
    return svg(W, H, b)


def art_riyadh():
    W, H = 240, 86
    b = ("<defs>" + lingrad("rG", [("0", "#0B1530"), ("1", "#2A2350")]) + "</defs>"
         + rect(0, 0, W, H, "url(#rG)"))
    for x, y in ((18, 10), (44, 22), (70, 8), (196, 12), (222, 30), (166, 6), (30, 40)):
        b += circle(x, y, 0.9, "#FFFFFF")
    sky = "#05070F"
    b += rect(0, 72, W, 14, sky)
    for x, w, h in ((8, 18, 22), (30, 14, 30), (48, 20, 18), (72, 16, 34), (150, 18, 28),
                    (172, 14, 40), (190, 22, 24), (216, 16, 32)):
        b += rect(x, 86 - h - 14, w, h + 14, sky)
    # PIF tower: tapered tall glass tower
    b += path("M106 86 L108 22 L116 8 L124 22 L126 86 Z", "#0E1426", "#3B4A7A", 1)
    for y in range(28, 80, 7):
        b += line(110, y, 122, y, "#3B4A7A", 0.6)
    # missile streak and impact
    b += path("M232 2 L136 22", "none", "#FDBA74", 1.6, ' stroke-dasharray="1 0"')
    b += path("M232 2 L180 13", "none", "#FB923C", 3, ' stroke-opacity=".35"')
    b += path(star_d(124, 26, 16, 0.45), "#F97316")
    b += path(star_d(124, 26, 9, 0.5), "#FDE047")
    return svg(W, H, b)


# ------------------------------------------------------- row 3 art (190x64)

def art_kyiv():
    W, H = 190, 64
    b = ("<defs>" + lingrad("kG", [("0", "#94A3B8"), ("1", "#E2E8F0")]) + "</defs>"
         + rect(0, 0, W, H, "url(#kG)"))
    c = "#1E293B"
    b += rect(52, 40, 86, 24, c)
    b += rect(80, 30, 30, 12, c)
    for cx, cy, r in ((95, 22, 9), (66, 34, 6), (124, 34, 6), (80, 30, 5), (110, 30, 5)):
        b += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (n(cx - r), n(cy + r * 0.6), n(cx - r), n(cy - r),
                  n(cx), n(cy - r * 1.5), n(cx + r), n(cy - r), n(cx + r), n(cy + r * 0.6)), "#C9A227")
        b += rect(cx - r, cy + r * 0.6, 2 * r, 64 - (cy + r * 0.6), c)
        b += rect(cx - 0.6, cy - r * 1.5 - 5, 1.2, 5, "#C9A227")
    for x in (58, 74, 116, 132):
        b += rect(x, 48, 3, 8, "#475569")
    # drones (Shahed-style deltas)
    for x, y in ((18, 12), (150, 9), (168, 22), (36, 26)):
        b += path("M%s %s L%s %s L%s %s L%s %s Z" % (x, y, x + 12, y - 3, x + 9, y, x + 12, y + 3), "#111827")
    b += path(star_d(148, 44, 9, 0.45), "#F97316") + path(star_d(148, 44, 4.5, 0.5), "#FDE047")
    return svg(W, H, b)


def art_berlin():
    W, H = 190, 64
    b = rect(0, 0, W, H, "#1E3A8A")
    for i in range(12):
        a = math.pi + i * math.pi / 11
        b += path(star_d(95 + 46 * math.cos(a), 58 + 46 * math.sin(a), 3.6), "#FACC15")
    g = "#F8FAFC"
    b += rect(66, 32, 58, 5, g) + path("M70 32 L95 24 L120 32 Z", g)
    for x in (67, 77, 87, 99, 109, 119):
        b += rect(x, 37, 4, 21, g)
    b += rect(64, 58, 62, 3, g)
    b += rect(90, 19, 10, 5, g)
    return svg(W, H, b)


def art_kenya():
    W, H = 190, 64
    b = ("<defs>" + lingrad("keG", [("0", "#FDE7B0"), ("1", "#F5C16C")]) + "</defs>"
         + rect(0, 0, W, H, "url(#keG)"))
    b += circle(30, 16, 8, "#FFF4D6")
    b += path("M0 64 L0 46 Q40 14 80 30 Q104 38 124 64 Z", "#3F7D3A")
    b += path("M8 64 Q44 34 76 42 Q96 48 110 64 Z", "#6B4F2A")
    b += path("M20 64 Q50 46 74 52 Q90 56 98 64 Z", "#8B6A3A")
    for x, y in ((46, 52), (62, 56), (78, 58)):
        b += path("M%s %s L%s %s L%s %s L%s %s Z" % (x, y - 5, x + 4, y, x, y + 4, x - 4, y), "#93C5FD")
    # element tile
    b += rect(134, 8, 46, 48, "#FFFFFF", 3, "#92400E", 2)
    b += t(139, 19, "41", 8.4, "#92400E", 900)
    b += t(157, 45, "Nb", 22, "#111827", 900, "middle")
    return svg(W, H, b)


def art_tonga():
    W, H = 190, 64
    b = ("<defs>" + lingrad("toG", [("0", "#FDBA74"), ("1", "#FEF3C7")]) + "</defs>"
         + rect(0, 0, W, H, "url(#toG)"))
    b += circle(150, 22, 12, "#F97316")
    for i in range(12):
        a = i * math.pi / 6
        b += line(150 + 15.5 * math.cos(a), 22 + 15.5 * math.sin(a), 150 + 20 * math.cos(a),
                  22 + 20 * math.sin(a), "#F97316", 2)
    b += rect(0, 44, W, 20, "#A16207")
    for d in ("M10 50 L28 54 L40 49 L58 56", "M70 48 L84 55 L100 51 L112 58 L128 52",
              "M140 49 L156 55 L172 50 L188 57", "M30 60 L48 58 L60 63", "M110 62 L126 59 L142 63"):
        b += path(d, "none", "#5B3A12", 1.4)
    # withered palm
    b += path("M44 44 Q40 30 46 16", "none", "#5B3A12", 3)
    for dx, dy in ((-14, 10), (-10, 4), (12, 9), (9, 3)):
        b += path("M46 16 Q%s %s %s %s" % (46 + dx * 0.6, 16 + dy - 6, 46 + dx, 16 + dy + 8),
                  "none", "#7C5A23", 2.2)
    # empty water drop
    b += path("M98 16 Q108 30 108 34 A10 10 0 0 1 88 34 Q88 30 98 16 Z", "none", "#1D4ED8", 2)
    return svg(W, H, b)


def art_iea():
    W, H = 190, 64
    b = rect(0, 0, W, H, "#0F172A")
    for i, x in enumerate((10, 38, 66)):
        b += rect(x, 14, 24, 46, "#1E293B", 2, "#334155", 1)
        for j in range(6):
            y = 18 + j * 7
            b += rect(x + 3, y, 18, 4, "#334155")
            b += circle(x + 18, y + 2, 1.1, "#22C55E" if (i + j) % 3 else "#F59E0B")
    # smoke cloud
    for cx, cy, r in ((106, 22, 10), (120, 16, 12), (136, 22, 10), (120, 26, 10)):
        b += circle(cx, cy, r, "#64748B")
    b += t(120, 26, "CO&#8322;", 10, "#F8FAFC", 900, "middle")
    # bars 2024 -> 2030
    b += rect(152, 40, 12, 20, "#94A3B8") + rect(170, 26, 12, 34, "#EF4444")
    b += t(176, 20, "+70%", 9, "#FCA5A5", 900, "middle")
    return svg(W, H, b)


# --------------------------------------------------------------- the stories

CARDS = [
    # row 1
    dict(n=1, reg="AP", place="SHENZHEN", art=art_apec, lon=114.06, lat=22.54,
         h="THREE POWERS, ONE TABLE",
         p="First-ever Trump&#8211;Xi&#8211;Putin trilateral ends in a peace declaration: "
           "nuclear war &#8220;cannot be won&#8221;. Silent on Ukraine and Iran.",
         src="BBC &#183; GUARDIAN &#183; DW"),
    dict(n=2, reg="AM", place="NEW YORK", art=art_anthropic, lon=-74.0, lat=40.71,
         h="ANTHROPIC JUMPS 17%",
         p="After a record $81bn raise, ANT soars from its $83 allocation to $111.50 "
           "(near $2tn) and closes at $97.17.",
         src="BBC &#183; FT &#183; GUARDIAN"),
    dict(n=3, reg="GL", place="THE HAGUE", art=art_icj, lon=4.30, lat=52.08,
         h="ICJ: MYANMAR GENOCIDE",
         p="Myanmar is the first state ever found guilty of genocide by an international "
           "court, over the Rohingya. Cheers in the camps.",
         src="BBC &#183; GUARDIAN &#183; AL JAZEERA"),
    # row 2
    dict(n=4, reg="GL", place="WORLDWIDE", pin="MIAMI", art=art_gta, lon=-80.19, lat=25.76,
         h="GTA VI FINALLY LANDS",
         p="After 13 years: a 99 Metascore that tops Zelda, est. $1.84bn by release day, leave "
           "requests up 32%.",
         src="BBC &#183; GUARDIAN &#183; FOX 5"),
    dict(n=5, reg="GL", place="ANTALYA", art=art_cop, lon=30.71, lat=36.90,
         h="FOSSIL FUELS DELETED",
         p="COP31&#8217;s new draft strips every fossil-fuel mention, keeping only a 35%-by-2035 "
           "electrification goal.",
         src="DW &#183; UN NEWS &#183; GUARDIAN"),
    dict(n=6, reg="AP", place="ODISHA", art=art_cyclone, lon=84.90, lat=19.27,
         h="CYCLONE AKVAN CLOSES IN",
         p="Odisha shifts nearly 300,000 people and cancels 69 trains; landfall due Friday near "
           "Gopalpur.",
         src="TNIE &#183; REUTERS &#183; DW"),
    dict(n=7, reg="ME", place="RIYADH", art=art_riyadh, lon=46.68, lat=24.71,
         h="RIYADH TOWER HIT",
         p="A Houthi strike damages the PIF tower, Riyadh&#8217;s tallest and the wealth "
           "fund&#8217;s HQ.",
         src="REUTERS &#183; AL JAZEERA &#183; NYT"),
    # row 3
    dict(n=8, reg="EU", place="KYIV", art=art_kyiv, lon=30.52, lat=50.45,
         h="EMBASSIES HIT IN KYIV",
         p="Daytime drone raid kills 1, damages Dutch and Austrian embassies and a cathedral.",
         src="KYIV INDEPENDENT &#183; REUTERS"),
    dict(n=9, reg="EU", place="BERLIN", art=art_berlin, lon=13.40, lat=52.52,
         h="EUROPE READY TO TALK",
         p="Allies claim a &#8220;united&#8221; line for Russia talks; Macron reopens the NATO "
           "question.",
         src="BBC &#183; FRANCE 24"),
    dict(n=10, reg="AF", place="MRIMA HILL", art=art_kenya, lon=39.25, lat=-4.48,
         h="KENYA PICKS US MINERS",
         p="Frontier Minerals wins the $60bn+ niobium site, beating seven rival bidders.",
         src="BBC &#183; REUTERS"),
    dict(n=11, reg="OC", place="NUKU&#8216;ALOFA", art=art_tonga, lon=-175.20, lat=-21.14,
         h="TONGA EMERGENCY",
         p="A 27-day state of emergency over El Ni&#241;o drought covers all land and sea.",
         src="RNZ &#183; MATANGI TONGA"),
    dict(n=12, reg="GL", place="PARIS", art=art_iea, lon=2.35, lat=48.86,
         h="DATACENTRE CO&#8322; +70%",
         p="IEA: datacentre power use doubles by 2030; AI adds 350TWh a year.",
         src="GUARDIAN &#183; IEA"),
]

DISPATCHES = [
    # Europe
    ("EU", "MOSCOW", "Putin vows &#8216;far more painful&#8217; reply to bridge strikes", "BBC"),
    ("EU", "COPENHAGEN", "Danish MPs ratify US&#8211;Greenland deal, 109&#8211;0", "DW"),
    ("EU", "BRUSSELS", "Commission confirms its first AI-assisted cyberattack", "DW"),
    ("EU", "THE HAGUE", "Watchdog: don&#8217;t buy camera smart glasses", "REUTERS"),
    ("EU", "PARIS", "Greens leader eyes a Mélenchon alliance", "LE MONDE"),
    # Americas
    ("AM", "WASHINGTON", "Senate rejects Iran war-powers curb, 51&#8211;48", "AL JAZEERA"),
    ("AM", "TAMPA", "Judge lets Trump&#8217;s NYT&#8211;Penguin libel suit proceed", "REUTERS"),
    ("AM", "HAITI", "Police raid kills 34 suspected gang members", "AL JAZEERA"),
    ("AM", "CINCINNATI", "Fiona the hippo dies after swallowing a knitted hat", "BBC"),
    ("AM", "HOUSTON", "J&amp;J installs its first OTTAVA surgical robot", "MD+DI"),
    ("AM", "LOS ANGELES", "Over a dozen charged in $22m rail heists", "GUARDIAN"),
    # Asia-Pacific
    ("AP", "SEOUL", "Top court voids ex-PM Han&#8217;s 15-year martial-law term", "DW"),
    ("AP", "DHAKA", "Hasina protests: Yunus family home torched", "GUARDIAN"),
    ("AP", "PAKISTAN", "Bus hits LPG tanker: 10 dead, 27 hurt", "AL JAZEERA"),
    ("AP", "SHENZHEN", "Takaichi presses Putin to free journalist Yuki Imai", "AP"),
    # Africa
    ("AF", "MOGADISHU", "UAE envoy given 72 hours to leave", "AFRICANEWS"),
    ("AF", "DAKAR", "Faye decrees budget to save $2.2bn IMF deal", "AFRICANEWS"),
    ("AF", "ZIMBABWE", "HALO Trust destroys its 250,000th landmine", "AFRICANEWS"),
    ("AF", "UGANDA", "48 Bududa landslide survivors take climate case to UN", "BBC"),
    ("AF", "BANJUL", "Gambia, the ICJ plaintiff, salutes Rohingya", "AFRICANEWS"),
    # Middle East
    ("ME", "GAZA", "Third of all child-rights violations hit Palestinians", "AL JAZEERA"),
    ("ME", "HORMUZ", "Iran: strait deal close; ship attacks go on", "REUTERS"),
    ("ME", "IRAQ", "Baghdad and Kataib Hezbollah agree joint Jurf force", "AL JAZEERA"),
    ("ME", "LEBANON", "Israel bombs Hezbollah missile site in Bekaa", "TOI"),
    ("ME", "IRAN / US", "Trump: &#8216;no rush&#8217; on Iran decision, eyes next year", "REUTERS"),
    # Oceania
    ("OC", "SYDNEY", "Ex-leader Speakman quits, warns Liberals", "GUARDIAN"),
    ("OC", "WELLINGTON", "Court: pay-equity cuts breached women&#8217;s rights", "RNZ"),
    ("OC", "TAURANGA", "130kg of cocaine (~NZ$47m) seized at port", "RNZ"),
    ("OC", "AUSTRALIA", "Foord wins AFC international player award", "ABC"),
    # Global / science
    ("GL", "MIT", "First whole-body cell atlas of an adult vertebrate", "MIT NEWS"),
    ("GL", "IMF", "Georgieva: AI and energy shocks lift inflation to 4.7%", "GUARDIAN"),
    ("GL", "UNFPA", "1 in 4 women can&#8217;t refuse sex in marriage", "GUARDIAN"),
]

NUMBERS = [
    ("$81BN", "ANTHROPIC IPO RAISE", "AM"),
    ("$97.17", "ANT CLOSE, +17%", "AM"),
    ("99", "GTA VI METASCORE", "GL"),
    ("300K", "MOVED IN ODISHA", "AP"),
    ("51&#8211;48", "SENATE IRAN VOTE", "AM"),
    ("4.7%", "IMF GLOBAL INFLATION", "GL"),
]

DATE_CHECK = (
    "Excluded as <b>WED 18</b>: Voyager 1 at one light-day &#183; JWST star merger &#183; "
    "US&#8211;Venezuela pact &#183; Jeffries 251&#8211;11 &#183; UK 3.6% CPI &#183; Van Gogh $190.4m &#183; "
    "Gaza raid launch &#183; Hemedti verdict &#183; Peru whale. As <b>FRI 20</b>: UK&#8211;EU summit &#183; Akvan landfall."
)

SOURCES = (
    "BBC &#183; Reuters &#183; AP &#183; Guardian &#183; Al Jazeera &#183; DW &#183; France 24 "
    "&#183; FT &#183; NYT &#183; UN News &#183; Africanews &#183; RNZ &#183; ABC &#183; Le Monde "
    "&#183; Kyiv Independent &#183; MIT News &#183; TNIE &#183; Times of Israel &#183; Matangi Tonga &#183; MD+DI"
)

# map badge offsets (px in the 284-wide map) for the twelve card pins
BADGES = {
    1: (246, 57), 2: (96, 38), 3: (130, 24), 4: (64, 78), 5: (150, 64), 6: (214, 85),
    7: (192, 58), 8: (174, 26), 9: (152, 19), 10: (188, 99), 11: (17, 94), 12: (122, 50),
}
MAP_W = 284
MAP_SCALE = MAP_W / 1000.0
MAP_H = round(486.99 * MAP_SCALE, 1)


def miller(lat):
    p = math.radians(lat)
    return 1.25 * math.log(math.tan(math.pi / 4 + 0.4 * p))


def project(lon, lat):
    k = 1000.0 / (2 * math.pi)
    x = (lon + 180.0) / 360.0 * 1000.0
    y = (miller(82.0) - miller(lat)) * k
    return x * MAP_SCALE, y * MAP_SCALE


def region_counts():
    counts = {k: 0 for k in ORDER}
    for c in CARDS:
        counts[c["reg"]] += 1
    for d in DISPATCHES:
        counts[d[0]] += 1
    return counts


def world_map_svg():
    land = WORLD_PATH.read_text().strip()
    b = rect(0, 0, MAP_W, MAP_H, "#DCEAF2")
    for lat in (60, 30, 0, -30):
        y = project(0, lat)[1]
        b += line(0, y, MAP_W, y, "#C3D8E4", 0.6, "2 3" if lat else None)
    b += ('<g transform="scale(%s)"><path d="%s" fill="#EDE3CC" stroke="#9C8B66" '
          'stroke-width="2.2" stroke-linejoin="round"/></g>' % (n(MAP_SCALE), land))
    leaders, dots, badges = "", "", ""
    for c in CARDS:
        _l, fill, ink = REGIONS[c["reg"]]
        x, y = project(c["lon"], c["lat"])
        bx, by = BADGES[c["n"]]
        dx, dy = bx - x, by - y
        dist = math.hypot(dx, dy) or 1
        ex, ey = bx - dx / dist * 6.6, by - dy / dist * 6.6
        leaders += line(x, y, ex, ey, ink, 1)
        dots += circle(x, y, 2.1, fill, "#FFFFFF", 0.9, ' class="pin-dot"')
        badges += ('<g class="pin-badge" data-n="%d">' % c["n"]
                   + circle(bx, by, 6.6, ink, "#FFFFFF", 1.2)
                   + t(bx, by + 2.9, str(c["n"]), 8 if c["n"] < 10 else 7, "#FFFFFF", 900, "middle")
                   + "</g>")
    b += leaders + dots + badges
    return svg(MAP_W, MAP_H, b, "map-svg")


# --------------------------------------------------------------------- css

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:1024px;height:1024px;overflow:hidden;background:#FAF6EE;}
body{font-family:Lato,sans-serif;color:#111827;-webkit-font-smoothing:antialiased;}
.page{position:relative;width:1024px;height:1024px;overflow:hidden;background:#FAF6EE;}
.rule-top{position:absolute;left:16px;right:16px;top:6px;height:3px;background:#111827;}
.dateline{position:absolute;left:14px;top:9px;height:56px;line-height:56px;font-weight:900;
 font-size:47px;letter-spacing:-.9px;white-space:nowrap;color:#111827;}
.dateline .d{color:#B91C1C;}
.edition{position:absolute;right:16px;top:13px;width:214px;height:46px;border:2px solid #111827;
 background:#FFFFFF;text-align:center;padding-top:2px;}
.edition div{white-space:nowrap;}
.edition .e1{font-weight:900;font-size:7.6px;letter-spacing:2.6px;line-height:11px;color:#374151;}
.edition .e2{font-weight:900;font-size:14px;letter-spacing:1.3px;line-height:16px;color:#111827;}
.edition .e3{font-weight:900;font-size:7.4px;letter-spacing:.75px;line-height:12px;color:#111827;}
.regionbar{position:absolute;left:16px;right:16px;top:65px;height:17px;display:flex;gap:2px;}
.seg{height:17px;line-height:17px;color:#FFFFFF;font-weight:900;font-size:8.4px;letter-spacing:.8px;
 text-align:center;white-space:nowrap;overflow:hidden;}
.seg b{font-weight:900;margin-left:5px;padding:0 4px;background:rgba(0,0,0,.28);border-radius:2px;}
.numbers{position:absolute;left:16px;right:16px;top:86px;height:24px;display:flex;
 border-top:1px solid #111827;border-bottom:2px solid #111827;background:#FFFFFF;}
.numbers .lab{flex:none;background:#111827;color:#FAF6EE;font-weight:900;font-size:8.4px;
 letter-spacing:1.5px;line-height:21px;padding:0 9px;white-space:nowrap;}
.cell{flex:1;display:flex;align-items:center;justify-content:center;gap:5px;line-height:21px;
 white-space:nowrap;border-left:1px solid #D6CCBA;overflow:hidden;}
.cell:first-of-type{border-left:none;}
.cell .v{line-height:16px;font-weight:900;font-size:14.5px;color:var(--ink);letter-spacing:-.2px;}
.cell .k{line-height:10px;padding-top:2px;font-weight:900;font-size:7.3px;letter-spacing:.6px;color:#374151;}
.row{position:absolute;left:16px;width:992px;display:grid;}
.r1{top:114px;height:224px;grid-template-columns:repeat(3,324px);column-gap:10px;}
.r2{top:346px;height:182px;grid-template-columns:repeat(4,242px);column-gap:8px;}
.r3{top:536px;height:150px;grid-template-columns:repeat(5,192px);column-gap:8px;}
.card{position:relative;background:#FFFFFF;border:1px solid #CDC2AD;border-top:3px solid var(--fill);
 display:flex;flex-direction:column;overflow:hidden;}
.art{flex:none;overflow:hidden;border-bottom:1px solid #E2D8C6;}
.art svg{display:block;width:100%;height:100%;}
.r1 .art{height:118px;}.r2 .art{height:86px;}.r3 .art{height:64px;}
.body{flex:1;display:flex;flex-direction:column;min-height:0;}
.r1 .body{padding:0 11px 6px;}.r2 .body{padding:0 9px 5px;}.r3 .body{padding:0 8px 4px;}
.kick{display:flex;align-items:center;gap:5px;white-space:nowrap;flex:none;overflow:hidden;}
.badge{flex:none;display:inline-block;background:var(--ink);color:#FFFFFF;font-weight:900;
 text-align:center;border-radius:2px;}
.kick .rg{font-weight:900;color:var(--ink);}
.kick .pl{font-weight:900;color:#374151;}
.card h2{font-weight:900;color:#111827;white-space:nowrap;flex:none;overflow:hidden;}
.card p{color:#1F2937;flex:none;overflow:hidden;}
.src{margin-top:auto;border-top:1px solid #E2D8C6;font-weight:900;color:#374151;white-space:nowrap;
 flex:none;overflow:hidden;display:flex;justify-content:space-between;}
.src .dt{color:#6B7280;}
.r1 .kick{margin-top:6px;height:15px;}
.r1 .badge{width:15px;height:15px;line-height:15px;font-size:9.6px;}
.r1 .kick .rg,.r1 .kick .pl{font-size:8.6px;letter-spacing:1px;}
.r1 h2{margin-top:4px;font-size:22px;line-height:26px;letter-spacing:-.3px;}
.r1 p{margin-top:3px;font-size:10.4px;line-height:13.4px;height:26.8px;}
.r1 .src{font-size:7.6px;letter-spacing:.8px;padding-top:3px;}
.r2 .kick{margin-top:5px;height:13px;}
.r2 .badge{width:13px;height:13px;line-height:13px;font-size:8.6px;}
.r2 .kick .rg,.r2 .kick .pl{font-size:7.6px;letter-spacing:.8px;}
.r2 h2{margin-top:3px;font-size:16.4px;line-height:18px;letter-spacing:-.25px;}
.r2 p{margin-top:2px;font-size:9.5px;line-height:12px;height:24px;}
.r2 .src{font-size:7px;letter-spacing:.6px;padding-top:3px;}
.r3 .kick{margin-top:5px;height:12px;}
.r3 .badge{width:12px;height:12px;line-height:12px;font-size:8px;}
.r3 .kick .rg,.r3 .kick .pl{font-size:7px;letter-spacing:.6px;}
.r3 h2{margin-top:3px;font-size:13px;line-height:15px;letter-spacing:-.2px;}
.r3 p{margin-top:2px;font-size:8.8px;line-height:11px;height:22px;}
.r3 .src{font-size:6.6px;letter-spacing:.5px;padding-top:2px;}
.panel{position:absolute;top:694px;height:290px;background:#FFFFFF;border:1px solid #CDC2AD;
 border-top:3px solid #111827;overflow:hidden;}
.mappanel{left:16px;width:300px;padding:0 7px;}
.digest{left:324px;width:684px;padding:0 10px;}
.pcap{height:19px;display:flex;justify-content:space-between;align-items:center;white-space:nowrap;
 border-bottom:1px solid #E2D8C6;overflow:hidden;}
.pcap .l{font-weight:900;font-size:9.4px;letter-spacing:1.8px;color:#111827;}
.pcap .r{font-weight:900;font-size:7.2px;letter-spacing:.8px;color:#374151;}
.mapbox{margin-top:5px;width:284px;border:1px solid #9FB8C8;}
.map-svg{display:block;width:282px;}
.legend{margin-top:5px;display:grid;grid-template-columns:1fr 1fr;column-gap:12px;row-gap:1px;}
.lg{display:flex;align-items:center;gap:5px;height:12px;white-space:nowrap;overflow:hidden;}
.lg i{flex:none;width:9px;height:9px;background:var(--fill);border-radius:1px;}
.lg .nm{font-weight:900;font-size:8px;letter-spacing:.6px;color:var(--ink);}
.lg .ct{margin-left:auto;font-weight:900;font-size:8.4px;color:#111827;}
.pinkey{margin-top:4px;border-top:1px solid #E2D8C6;padding-top:3px;display:grid;
 grid-template-columns:repeat(3,1fr);row-gap:1px;column-gap:6px;}
.pk{display:flex;align-items:center;gap:4px;height:12px;white-space:nowrap;overflow:hidden;}
.pk b{flex:none;width:12px;height:11px;line-height:11px;font-size:7.4px;text-align:center;color:#FFFFFF;
 background:var(--ink);border-radius:2px;font-weight:900;}
.pk span{font-weight:900;font-size:7.3px;letter-spacing:.4px;color:#1F2937;}
.cols{margin-top:4px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:14px;}
.col{display:flex;flex-direction:column;min-width:0;}
.dl{height:16px;display:flex;align-items:center;gap:5px;white-space:nowrap;overflow:hidden;
 border-bottom:1px dotted #D8CDB8;}
.dl:last-child{border-bottom:none;}
.dl .nb{flex:none;width:17px;height:12px;line-height:12px;text-align:center;font-weight:900;
 font-size:8px;color:#FFFFFF;background:var(--ink);border-radius:2px;}
.dl .tg{flex:none;font-weight:900;font-size:8.4px;letter-spacing:.5px;color:var(--ink);}
.dl .tx{flex:none;font-size:9.5px;font-weight:400;color:#111827;}
.dl .so{margin-left:auto;flex:none;padding-left:4px;font-weight:900;font-size:6.6px;letter-spacing:.4px;
 color:#4B5563;}
.footer{position:absolute;left:16px;right:16px;top:988px;height:31px;background:#111827;
 padding:3px 9px 0;}
.footer div{white-space:nowrap;overflow:hidden;height:13px;line-height:13px;}
.f1{font-size:7.6px;color:#F3EEE4;font-weight:400;}
.f1 .k{font-weight:900;color:#FBBF24;letter-spacing:1px;margin-right:5px;}
.f1 b{font-weight:900;color:#FFFFFF;}
.f2{font-size:7.2px;color:#D9D3C7;font-weight:700;display:flex;justify-content:space-between;}
.f2 .k{font-weight:900;color:#FBBF24;letter-spacing:1px;margin-right:5px;}
.f2 .r{font-weight:900;color:#FFFFFF;letter-spacing:.6px;}
"""


def style_vars(reg):
    _l, fill, ink = REGIONS[reg]
    return "--fill:%s;--ink:%s;" % (fill, ink)


def card_html(c):
    label = REGIONS[c["reg"]][0]
    return (
        '<section class="card" data-story="c%02d" style="%s">' % (c["n"], style_vars(c["reg"]))
        + '<div class="art">%s</div>' % c["art"]()
        + '<div class="body"><div class="kick"><span class="badge">%d</span>'
          '<span class="rg">%s</span><span class="pl">&#183; %s</span></div>' % (c["n"], label, c["place"])
        + '<h2>%s</h2><p>%s</p>' % (c["h"], c["p"])
        + '<div class="src"><span>[%s]</span><span class="dt">THU 19 NOV</span></div></div>' % c["src"]
        + "</section>"
    )


def dispatch_html(num, d):
    reg, tag, text, src = d
    return ('<div class="dl" data-story="d%02d" style="%s"><span class="nb">%d</span>'
            '<span class="tg">%s</span><span class="tx">%s</span><span class="so">%s</span></div>'
            % (num, style_vars(reg), num, tag, text, src))


def build_html():
    counts = region_counts()
    total = sum(counts.values())
    segs = "".join(
        '<div class="seg" style="flex:%d 1 0;background:%s">%s<b>%d</b></div>'
        % (counts[k], REGIONS[k][1], REGIONS[k][0], counts[k]) for k in ORDER)
    nums = "".join(
        '<div class="cell" style="%s"><span class="v">%s</span><span class="k">%s</span></div>'
        % (style_vars(r), v, k) for v, k, r in NUMBERS)
    rows = [CARDS[0:3], CARDS[3:7], CARDS[7:12]]
    rows_html = "".join('<div class="row r%d">%s</div>' % (i + 1, "".join(card_html(c) for c in r))
                        for i, r in enumerate(rows))
    legend = "".join(
        '<div class="lg" style="%s"><i></i><span class="nm">%s</span><span class="ct">%d</span></div>'
        % (style_vars(k), REGIONS[k][0], counts[k]) for k in ORDER)
    legend += ('<div class="lg" style="--fill:#111827;--ink:#111827"><i></i>'
               '<span class="nm">ALL STORIES</span><span class="ct">%d</span></div>' % total)
    pinkey = "".join('<div class="pk" style="%s"><b>%d</b><span>%s</span></div>'
                     % (style_vars(c["reg"]), c["n"], c.get("pin", c["place"])) for c in CARDS)
    lines = [dispatch_html(13 + i, d) for i, d in enumerate(DISPATCHES)]
    half = len(lines) // 2
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>THURSDAY, 19 NOVEMBER 2026</title><style>' + CSS + '</style></head><body>'
        '<div class="page">'
        '<div class="rule-top"></div>'
        '<div class="dateline"><span class="d">THURSDAY,</span> 19 NOVEMBER 2026</div>'
        '<div class="edition"><div class="e1">THE WORLD CANVAS &#183; LATE FINAL</div>'
        '<div class="e2">NOV 19 &#183; THU 2026</div>'
        '<div class="e3">%d STORIES &#183; 7 REGIONS &#183; 12 ILLUSTRATED</div></div>' % total
        + '<div class="regionbar">' + segs + '</div>'
        '<div class="numbers"><div class="lab">DAY IN NUMBERS</div>' + nums + '</div>'
        + rows_html
        + '<div class="panel mappanel"><div class="pcap"><span class="l">WORLD LOCATOR</span>'
          '<span class="r">PINS = CARDS 1&#8211;12</span></div>'
          '<div class="mapbox">' + world_map_svg() + '</div>'
          '<div class="legend">' + legend + '</div><div class="pinkey">' + pinkey + '</div></div>'
        + '<div class="panel digest"><div class="pcap"><span class="l">WORLD DISPATCHES &#183; 13&#8211;%d</span>'
          '<span class="r">%d ONE-LINE BRIEFS &#183; EVERY ONE FIRST REPORTED THU 19 NOV 2026</span></div>'
          % (12 + len(DISPATCHES), len(DISPATCHES))
        + '<div class="cols"><div class="col">' + "".join(lines[:half]) + '</div><div class="col">'
        + "".join(lines[half:]) + '</div></div></div>'
        + '<div class="footer"><div class="f1"><span class="k">DATE CHECK</span>' + DATE_CHECK + '</div>'
          '<div class="f2"><span><span class="k">SOURCES</span>' + SOURCES + '</span>'
          '<span class="r">ORIGINAL CUSTOM GRAPHICS &#183; NATURAL EARTH BASEMAP &#183; 1024&#215;1024</span>'
          '</div></div>'
        '</div></body></html>'
    )


# --------------------------------------------------------------------- audit

AUDIT_JS = r"""() => {
  const out = {doc:[document.documentElement.scrollWidth, document.documentElement.scrollHeight],
               issues:[], notes:[]};
  const add = (m) => { if (out.issues.length < 120) out.issues.push(m); };
  if (out.doc[0] !== 1024 || out.doc[1] !== 1024) add('document ' + out.doc.join('x'));
  const lab = (el) => { const s = el.closest('[data-story]'); return (s ? s.dataset.story + ' ' : '') +
      el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className : '')
      + ' "' + (el.textContent || '').trim().slice(0, 28) + '"'; };
  const R = (el) => el.getBoundingClientRect();
  const inter = (a, b, tol) => !(a.right <= b.left + tol || b.right <= a.left + tol ||
      a.bottom <= b.top + tol || b.bottom <= a.top + tol);

  // census
  const seen = {};
  document.querySelectorAll('[data-story]').forEach(el => { seen[el.dataset.story] = (seen[el.dataset.story]||0)+1; });
  out.ids = Object.keys(seen).sort();
  Object.keys(seen).filter(k => seen[k] > 1).forEach(k => add('duplicate id ' + k));

  // overflow / wrapping on every text container
  document.querySelectorAll('.dateline,.edition div,.seg,.numbers .lab,.cell,.kick,.card h2,.card p,.src,' +
      '.pcap,.lg,.pk,.dl,.footer div,.panel,.card,.art').forEach(el => {
    if (el.scrollWidth - el.clientWidth > 0.5) add('overflow-x ' + lab(el) + ' +' + (el.scrollWidth - el.clientWidth));
    if (el.scrollHeight - el.clientHeight > 0.5) add('overflow-y ' + lab(el) + ' +' + (el.scrollHeight - el.clientHeight));
  });
  // card paragraphs: real line count must be <= 2, headline exactly 1
  const lines = (el) => { const r = document.createRange(); r.selectNodeContents(el);
      const ys = new Set(); [...r.getClientRects()].forEach(q => { if (q.width > 1) ys.add(Math.round(q.top)); });
      return ys.size; };
  document.querySelectorAll('.card').forEach(c => {
    const h = c.querySelector('h2'), p = c.querySelector('p');
    const lh = lines(h), lp = lines(p);
    out.notes.push(c.dataset.story + ' h' + lh + ' p' + lp + ' fill ' + (R(p).width ? (Math.round(
        [...(() => { const r = document.createRange(); r.selectNodeContents(p); return r.getClientRects(); })()]
        .slice(-1)[0].width)) : 0));
    if (lh !== 1) add('headline wraps ' + c.dataset.story);
    if (lp > 2) add('summary >2 lines ' + c.dataset.story + ' (' + lp + ')');
    if (lp < 1) add('summary empty ' + c.dataset.story);
  });
  document.querySelectorAll('.dl').forEach(d => {
    const tx = d.querySelector('.tx'), so = d.querySelector('.so');
    if (lines(tx) !== 1) add('dispatch wraps ' + d.dataset.story);
    if (R(tx).right > R(so).left + 0.5) add('dispatch text hits source ' + d.dataset.story);
    out.notes.push(d.dataset.story + ' slack ' + Math.round(R(so).left - R(tx).right));
  });

  // everything stays inside the page, every card child inside its card
  document.querySelectorAll('.page *').forEach(el => {
    const b = R(el); if (!b.width && !b.height) return;
    if (b.left < -0.5 || b.top < -0.5 || b.right > 1024.5 || b.bottom > 1024.5) add('page escape ' + lab(el));
  });
  document.querySelectorAll('.card,.panel').forEach(p => {
    const pb = R(p);
    p.querySelectorAll('*').forEach(el => { const b = R(el); if (!b.width && !b.height) return;
      if (b.top < pb.top - 0.6 || b.left < pb.left - 0.6 || b.bottom > pb.bottom + 0.6 || b.right > pb.right + 0.6)
        add('escape ' + lab(p) + ' / ' + lab(el)); });
  });
  // sibling overlaps
  const sib = (sel) => document.querySelectorAll(sel).forEach(par => {
    const kids = [...par.children];
    for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++)
      if (inter(R(kids[i]), R(kids[j]), 0.5)) add('overlap ' + lab(kids[i]) + ' x ' + lab(kids[j]));
  });
  sib('.row'); sib('.col'); sib('.cols'); sib('.legend'); sib('.pinkey'); sib('.regionbar'); sib('.numbers');
  sib('.body'); sib('.kick'); sib('.dl'); sib('.edition'); sib('.footer');
  const secs = ['.rule-top','.dateline','.edition','.regionbar','.numbers','.r1','.r2','.r3','.mappanel',
                '.digest','.footer'].map(s => [s, R(document.querySelector(s))]);
  for (let i = 0; i < secs.length; i++) for (let j = i + 1; j < secs.length; j++)
    if (inter(secs[i][1], secs[j][1], 0.5)) add('section overlap ' + secs[i][0] + ' x ' + secs[j][0]);

  // svg: ink inside the viewBox, text labels inside the svg box and never touching each other
  document.querySelectorAll('svg').forEach((s, i) => {
    const vb = s.viewBox.baseVal, bb = s.getBBox(), tol = 0.6;
    if (bb.x < vb.x - tol || bb.y < vb.y - tol || bb.x + bb.width > vb.x + vb.width + tol ||
        bb.y + bb.height > vb.y + vb.height + tol) add('svg' + i + ' ink outside viewBox');
    const sb = R(s);
    const texts = [...s.querySelectorAll('text')];
    texts.forEach(tx => { const b = R(tx);
      if (b.left < sb.left + 1 || b.right > sb.right - 1 || b.top < sb.top + 1 || b.bottom > sb.bottom - 0.5)
        add('svg' + i + ' label clipped "' + tx.textContent + '"'); });
    for (let a = 0; a < texts.length; a++) for (let b = a + 1; b < texts.length; b++) {
      if (texts[a].closest('.pin-badge') || texts[b].closest('.pin-badge')) continue;
      if (inter(R(texts[a]), R(texts[b]), 0)) add('svg' + i + ' labels touch "' + texts[a].textContent +
          '" x "' + texts[b].textContent + '"');
    }
  });
  // map badges: no two badges overlap, no badge covers a foreign pin dot
  const badges = [...document.querySelectorAll('.pin-badge')].map(g => [g.dataset.n, R(g.querySelector('circle'))]);
  const dots = [...document.querySelectorAll('.pin-dot')].map(d => R(d));
  for (let a = 0; a < badges.length; a++) {
    for (let b = a + 1; b < badges.length; b++) if (inter(badges[a][1], badges[b][1], -1.5))
      add('map badges crowd ' + badges[a][0] + ' x ' + badges[b][0]);
    dots.forEach((d, k) => { if (inter(badges[a][1], d, 0)) add('badge ' + badges[a][0] + ' covers dot ' + (k+1)); });
  }
  out.badges = badges.length;

  // contrast
  const parse = (s) => s.match(/[\d.]+/g).slice(0, 4).map(Number);
  const lum = (c) => { const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = Math.max(lum(a), lum(b)), y = Math.min(lum(a), lum(b)); return (x + .05) / (y + .05); };
  const bgOf = (el) => { let n = el; while (n) { const c = parse(getComputedStyle(n).backgroundColor);
      if (c.length < 4 || c[3] > 0) { if (c.length < 4 || c[3] === 1) return c.slice(0, 3); }
      n = n.parentElement; } return [250, 246, 238]; };
  const floor = (sel, min) => document.querySelectorAll(sel).forEach(el => {
    const r = ratio(parse(getComputedStyle(el).color).slice(0, 3), bgOf(el));
    if (r < min) add('contrast ' + lab(el) + ' ' + r.toFixed(2));
  });
  floor('.card h2,.card p,.dl .tx,.dateline,.edition div,.cell .k,.lg .ct,.pk span,.f1,.f2', 7);
  floor('.kick .rg,.kick .pl,.src,.dl .tg,.dl .so,.cell .v,.lg .nm,.pcap .l,.pcap .r,.badge,.dl .nb,.pk b,.seg,.f1 .k', 4.5);
  return out;
}"""


# ------------------------------------------------------------------- render

def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("screenshot is not a PNG")
    return struct.unpack(">II", data[16:24])


def render(expect):
    from playwright.sync_api import sync_playwright

    shots, audit = {}, None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-color-profile=srgb",
                  "--font-render-hinting=none", "--disable-lcd-text"])
        for scale, dest in ((1, RAW_1X), (2, RAW_2X)):
            page = browser.new_page(viewport={"width": 1024, "height": 1024}, device_scale_factor=scale)
            page.goto(HTML_PATH.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(300)
            if scale == 1:
                audit = page.evaluate(AUDIT_JS)
            page.screenshot(path=str(dest), clip={"x": 0, "y": 0, "width": 1024, "height": 1024})
            shots[scale] = dest.read_bytes()
            page.close()
        page = browser.new_page(viewport={"width": 1024, "height": 1024}, device_scale_factor=1)
        page.goto(HTML_PATH.as_uri())
        page.wait_for_timeout(300)
        again = page.screenshot(clip={"x": 0, "y": 0, "width": 1024, "height": 1024})
        page.close()
        browser.close()
    audit["repeat_identical"] = again == shots[1]
    return audit


def sharpness(img, box):
    from PIL import ImageFilter, ImageStat
    g = img.convert("L").crop(box).filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(g).var[0]


def encode_jpeg(image):
    best = None
    for q in JPEG_QUALITIES:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=q, subsampling=0, optimize=True, progressive=False)
        data = buf.getvalue()
        best = (q, data)
        if len(data) <= JPEG_MAX:
            break
    return best


def main():
    expect = {"c%02d" % c["n"] for c in CARDS} | {"d%02d" % (13 + i) for i in range(len(DISPATCHES))}
    assert len(expect) == 44, len(expect)
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    audit = render(sorted(expect))

    missing = sorted(expect - set(audit["ids"]))
    extra = sorted(set(audit["ids"]) - expect)
    print("AUDIT doc=%s stories=%d/%d badges=%d repeat_identical=%s"
          % (audit["doc"], len(audit["ids"]), len(expect), audit["badges"],
             audit["repeat_identical"]))
    slack = [x for x in audit["notes"] if " slack " in x]
    tight = sorted(slack, key=lambda s: int(s.split()[-1]))[:4]
    print("  tightest dispatch slack (px):", ", ".join(tight))
    print("  card lines:", " | ".join(x for x in audit["notes"] if " slack " not in x))
    for issue in audit["issues"]:
        print("  ISSUE", issue)
    assert not missing and not extra, ("census", missing, extra)
    assert not audit["issues"], "layout audit reported %d issues" % len(audit["issues"])

    from PIL import Image
    raw1, raw2 = RAW_1X.read_bytes(), RAW_2X.read_bytes()
    assert png_size(raw1) == (1024, 1024) and png_size(raw2) == (2048, 2048)
    native = Image.open(io.BytesIO(raw1)).convert("RGB")
    down = Image.open(io.BytesIO(raw2)).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    box = (324, 716, 1008, 984)  # the dispatch columns
    sn, sd = sharpness(native, box), sharpness(down, box)
    print("digest edge variance: native 1x %.1f | 2x->Lanczos %.1f" % (sn, sd))
    chosen, mode = (down, "2x supersampled -> Lanczos") if sd >= sn else (native, "native 1x")

    quality, data = encode_jpeg(chosen)
    assert data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
    assert len(data) < HARD_LIMIT
    ENTRY.write_bytes(data)
    chosen.resize((300, 300), Image.LANCZOS).save(PREVIEW_300)
    chosen.resize((512, 512), Image.LANCZOS).save(PREVIEW_512)
    print("entry.png: 1024x1024 JPEG q%d 4:4:4 via %s, %d bytes (%.1f KiB)"
          % (quality, mode, len(data), len(data) / 1024))


if __name__ == "__main__":
    main()
