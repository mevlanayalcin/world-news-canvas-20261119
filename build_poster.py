#!/usr/bin/env python3
"""Build the 1024x1024 visual broadsheet for Thursday 19 November 2026 (entry.png), v8.

Twenty stories, every one first reported on Thursday 19 November 2026: eight big
illustrated features (three lead cards over five crisp cards, each with an original
inline SVG scene), a Natural Earth locator with numbered pins 1-8, and twelve
one-line dispatches (9-20) in a single spacious column. A one-line DATE CHECK and
SOURCES bar names the adjacent Wednesday 18 stories that were left out on purpose.

The page is rendered in headless Chromium at 1x and 2x device scale. The same
pass runs a DOM geometry audit (exact size, no overflow, no wrapped one-line
text, no clipped or overlapping cards, labels, SVG text or map badges, a 20/20
story census and an ink-contrast floor) and the build fails on any issue. Text
comes from whichever of the native 1x and the Lanczos-downsampled 2x render is
sharper on the dispatch column; when 1x wins, the 2x Lanczos pixels are pasted
into the nine integer-aligned illustration boxes. The page is encoded as a
4:4:4 baseline JPEG.

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
HTML_PATH = Path("/tmp/world_news_canvas_v8.html")
RAW_1X = Path("/tmp/world_news_canvas_v8_1x.png")
RAW_2X = Path("/tmp/world_news_canvas_v8_2x.png")
PREVIEW_300 = Path("/tmp/news_v8_300.png")
PREVIEW_512 = Path("/tmp/news_v8_512.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITIES = (91, 90)
JPEG_MAX = 440 * 1024
HARD_LIMIT = 1048576

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
ORDER = ["AP", "AM", "EU", "ME", "AF", "OC", "GL"]


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


# ------------------------------------------------------------ art helpers
# Every scene is one inline SVG whose ids are prefixed per card (all SVGs share
# the document's id namespace). Geometry stays inside the viewBox so the audit's
# getBBox() check holds; glows are drawn with gradient-filled rects or filters,
# which never enlarge the geometric bounding box.

def radgrad(gid, stops, cx, cy, r, user=True):
    s = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (o, c, a) for o, c, a in stops)
    units = ' gradientUnits="userSpaceOnUse"' if user else ""
    return ('<radialGradient id="%s" cx="%s" cy="%s" r="%s"%s>%s</radialGradient>'
            % (gid, n(cx), n(cy), n(r), units, s))


def lingrad_a(gid, stops, x1="0", y1="0", x2="0", y2="1"):
    s = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (o, c, a) for o, c, a in stops)
    return ('<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
            % (gid, x1, y1, x2, y2, s))


def glow_filter(fid, sd, color, strength=1):
    merge = "".join('<feMergeNode in="g"/>' for _ in range(strength))
    return ('<filter id="%s" x="-40%%" y="-40%%" width="180%%" height="180%%">'
            '<feGaussianBlur in="SourceAlpha" stdDeviation="%s" result="b"/>'
            '<feFlood flood-color="%s"/><feComposite in2="b" operator="in" result="g"/>'
            '<feMerge>%s<feMergeNode in="SourceGraphic"/></feMerge></filter>' % (fid, n(sd), color, merge))


def blur_filter(fid, sd):
    return ('<filter id="%s" x="-30%%" y="-30%%" width="160%%" height="160%%">'
            '<feGaussianBlur stdDeviation="%s"/></filter>' % (fid, n(sd)))


def burst_d(cx, cy, r, inner=0.48, spikes=13):
    """An irregular explosion burst (deterministic jitter)."""
    pts = []
    for i in range(spikes * 2):
        ang = -math.pi / 2 + i * math.pi / spikes
        jit = 0.78 + 0.22 * (((i * 37) % 11) / 10.0)
        rr = r * jit if i % 2 == 0 else r * inner * (0.85 + 0.15 * ((i * 17) % 5) / 4.0)
        pts.append("%s %s" % (n(cx + rr * math.cos(ang)), n(cy + rr * math.sin(ang))))
    return "M" + " L".join(pts) + " Z"


def windows(x0, y0, cols, rows, dx, dy, w, h, colour, seed, density=0.55):
    out = ""
    for r in range(rows):
        for c in range(cols):
            v = (seed * 7919 + r * 104729 + c * 1299709) % 997 / 997.0
            if v < density:
                out += rect(x0 + c * dx, y0 + r * dy, w, h, colour,
                            extra=' fill-opacity="%s"' % n(0.45 + 0.55 * ((v * 13) % 1)))
    return out


def fold_shade(gid):
    return lingrad_a(gid, [("0", "#000000", ".22"), (".22", "#FFFFFF", ".16"), (".45", "#000000", ".18"),
                           (".7", "#FFFFFF", ".14"), ("1", "#000000", ".26")], x2="1", y2="0")


def wave_d(x, y, w, h, amp):
    """A waving flag outline: straight hoist, sinusoidal top and bottom edges."""
    pts_top = [(x + w * i / 8.0, y + amp * math.sin(i * math.pi / 4)) for i in range(9)]
    pts_bot = [(x + w * i / 8.0, y + h + amp * math.sin(i * math.pi / 4)) for i in range(8, -1, -1)]
    return "M" + " L".join("%s %s" % (n(a), n(b)) for a, b in pts_top + pts_bot) + " Z"


def flag_us(x, y, w, h, cid):
    s = "".join(rect(x, y - 2 + i * (h + 4) / 13.0, w, (h + 4) / 13.0 + 0.3,
                     "#B42318" if i % 2 == 0 else "#FAF7F0") for i in range(13))
    cw, ch = w * 0.42, (h + 4) * 7 / 13.0
    s += rect(x, y - 2, cw, ch, "#1F3A6E")
    for r in range(4):
        for c in range(5):
            s += circle(x + cw * (c + 0.6) / 5.2, y - 2 + ch * (r + 0.6) / 4.2, 0.62, "#FAF7F0")
    return s


def flag_cn(x, y, w, h, cid):
    s = rect(x, y - 2, w, h + 4, "#D52B1E")
    s += path(star_d(x + w * 0.17, y + h * 0.28, h * 0.16), "#FFDE00")
    for a, b in ((0.33, 0.1), (0.4, 0.2), (0.4, 0.35), (0.33, 0.46)):
        s += path(star_d(x + w * a, y + h * b, h * 0.055), "#FFDE00")
    return s


def flag_ru(x, y, w, h, cid):
    b = (h + 4) / 3.0
    return (rect(x, y - 2, w, b + 0.3, "#FAF7F0") + rect(x, y - 2 + b, w, b + 0.3, "#1C3F94")
            + rect(x, y - 2 + 2 * b, w, b, "#D52B1E"))


def pole_flag(px, top, w, h, fn, cid, amp=1.6):
    """A gold flagpole with a waving, fold-shaded flag."""
    d = wave_d(px + 1, top + 2, w, h, amp)
    return ('<clipPath id="%s"><path d="%s"/></clipPath>' % (cid, d)
            + '<g clip-path="url(#%s)">%s%s</g>' % (cid, fn(px + 1, top + 2, w, h, cid),
                                                     path(d, "url(#%sF)" % cid[:2]))
            + path(d, "none", "#000000", 0.4, ' stroke-opacity=".35"'))


def palm(x, base, height, lean, colour, scale=1.0):
    tx, ty = x + lean, base - height
    s = path("M%s %s Q%s %s %s %s L%s %s Q%s %s %s %s Z" % (
        n(x - 1.6 * scale), n(base), n(x + lean * 0.2 - 1.2 * scale), n(base - height * 0.55), n(tx - 0.8 * scale), n(ty),
        n(tx + 0.8 * scale), n(ty), n(x + lean * 0.2 + 1.2 * scale), n(base - height * 0.55), n(x + 1.6 * scale), n(base)),
        colour)
    for ang, ln in ((-170, 17), (-140, 15), (-105, 11), (-60, 13), (-25, 16), (10, 14), (160, 13)):
        a = math.radians(ang)
        ex, ey = tx + ln * scale * math.cos(a), ty + ln * scale * math.sin(a) + 5 * scale
        mx, my = tx + ln * scale * 0.55 * math.cos(a), ty + ln * scale * 0.55 * math.sin(a) - 3 * scale
        s += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            n(tx), n(ty), n(mx), n(my - 2.2 * scale), n(ex), n(ey), n(mx), n(my + 1.6 * scale), n(tx), n(ty + 1)),
            colour)
    return s


# ------------------------------------------------------- row 1 art (322x118)

def art_apec():
    W, H = 322, 118
    d = ("<defs>"
         + lingrad_a("apS", [("0", "#0A0F2E", "1"), (".42", "#2E1A57", "1"), (".72", "#9B3468", "1"),
                             ("1", "#F2874A", "1")])
         + radgrad("apG", [("0", "#FFC27A", ".85"), (".5", "#FF8A5B", ".25"), ("1", "#FF8A5B", "0")], 161, 84, 120)
         + lingrad_a("apW", [("0", "#2A1B4A", "1"), ("1", "#0B0820", "1")])
         + lingrad_a("apT", [("0", "#A86B33", "1"), ("1", "#5E3818", "1")])
         + lingrad_a("apP", [("0", "#7A1426", "1"), ("1", "#3A0812", "1")])
         + lingrad_a("apL", [("0", "#FFF3C4", ".34"), ("1", "#FFF3C4", "0")])
         + fold_shade("aUF") + fold_shade("aCF") + fold_shade("aRF")
         + "</defs>")
    b = d + rect(0, 0, W, 86, "url(#apS)") + rect(0, 0, W, 86, "url(#apG)")
    for x, y in ((14, 8), (40, 18), (78, 6), (120, 14), (204, 9), (236, 20), (290, 7), (306, 24)):
        b += circle(x, y, 0.8, "#FFFFFF", extra=' fill-opacity=".8"')
    # far skyline (haze)
    far = "#3E2563"
    for x, w, h in ((0, 22, 26), (20, 16, 34), (34, 20, 22), (52, 12, 40), (86, 20, 30), (104, 14, 24),
                    (190, 18, 28), (206, 14, 36), (276, 18, 30), (294, 28, 22)):
        b += rect(x, 78 - h, w, h, far)
    # near skyline: Kingkey 100 (left), Ping An Finance Centre with spire (right)
    near = "#160C2C"
    b += path("M58 78 L60 28 Q64 22 68 22 Q72 22 76 28 L78 78 Z", near)
    b += path("M242 78 L246 22 L252 14 L254 2 L256 14 L262 22 L266 78 Z", near)
    for x, w, h in ((0, 18, 18), (16, 14, 26), (30, 22, 20), (78, 18, 32), (96, 14, 22), (176, 16, 30),
                    (192, 20, 22), (212, 16, 38), (228, 14, 26), (266, 18, 34), (284, 16, 22), (300, 22, 28)):
        b += rect(x, 78 - h, w, h, near)
    lit = "#FFD27A"
    b += windows(61, 32, 4, 11, 4, 4, 1.6, 1.6, lit, 1) + windows(247, 26, 4, 13, 4, 4, 1.6, 1.6, lit, 2)
    for x, w, h, s in ((80, 18, 32, 3), (178, 16, 30, 4), (214, 16, 38, 5), (268, 18, 34, 6), (302, 22, 28, 7),
                       (18, 14, 26, 8)):
        b += windows(x + 2, 78 - h + 3, int((w - 3) // 4), int((h - 5) // 4), 4, 4, 1.6, 1.6, lit, s, 0.4)
    # harbour water with reflections
    b += rect(0, 78, W, 8, "url(#apW)")
    for x, w in ((20, 30), (58, 18), (110, 40), (150, 22), (212, 30), (244, 22), (284, 24)):
        b += rect(x, 80 + (x % 3), w, 0.8, "#FFB86B", extra=' fill-opacity=".45"')
    # stage: floor, spotlights, flags, table
    b += rect(0, 86, W, 32, "#0B0612")
    for x in (113, 173, 233):
        b += poly([(x - 6, 0), (x + 6, 0), (x + 30, 86), (x - 30, 86)], "url(#apL)")
    for px, fn, cid in ((92, flag_us, "aU"), (152, flag_cn, "aC"), (212, flag_ru, "aR")):
        b += rect(px - 1.1, 16, 2.2, 70, "#E9C46A") + circle(px, 15, 2.4, "#F6D77B")
        b += pole_flag(px, 16, 42, 25, fn, cid)
    b += poly([(66, 80), (256, 80), (266, 88), (56, 88)], "url(#apT)")
    b += rect(56, 88, 210, 13, "url(#apP)") + rect(56, 88, 210, 1.4, "#E9C46A")
    for x in (104, 161, 218):
        b += rect(x - 10, 82.5, 20, 4, "#F8F4EA", 0.6) + rect(x - 0.6, 74, 1.2, 9, "#1F1F1F")
        b += circle(x, 73.6, 1.6, "#111111")
    b += poly([(148, 84), (174, 84), (176, 87.4), (146, 87.4)], "#FFFFFF")
    b += rect(0, 104, W, 14, "#000000", extra=' fill-opacity=".55"')
    b += t(161, 114.2, "SHENZHEN &#183; APEC 2026 &#183; PEACE DECLARATION", 8.3, "#F6D98F", 900, "middle", 1.9)
    return svg(W, H, b)


ANT_SERIES = [  # (x, price): $83 IPO price, $111.53 high, $97.17 close (BBC)
    (20, 83.0), (30, 83.0), (36, 99.0), (44, 104.2), (52, 102.6), (62, 108.4), (72, 106.9), (84, 110.2),
    (96, 111.53), (106, 108.6), (116, 109.4), (128, 105.4), (140, 107.0), (152, 103.1), (164, 104.8),
    (176, 101.4), (188, 103.0), (200, 99.6), (212, 101.2), (224, 98.4), (236, 100.0), (248, 97.2),
    (260, 98.9), (272, 96.5), (284, 98.0), (296, 96.9), (304, 97.17)]


def art_anthropic():
    W, H = 322, 118

    def py(p):
        return 102 - (p - 80) / (114 - 80) * 84

    d = ("<defs>"
         + lingrad_a("anB", [("0", "#0B1730", "1"), ("1", "#050B18", "1")])
         + radgrad("anR", [("0", "#10B981", ".28"), ("1", "#10B981", "0")], 110, 30, 150)
         + lingrad_a("anA", [("0", "#34D399", ".62"), (".55", "#10B981", ".2"), ("1", "#10B981", "0")])
         + glow_filter("anGl", 2.2, "#34D399", 2)
         + glow_filter("anGb", 1.6, "#FBBF24")
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#anB)") + rect(0, 0, W, H, "url(#anR)")
    for p in (85, 90, 95, 100, 105, 110):
        b += line(12, py(p), 310, py(p), "#1D3A5F", 0.6 if p % 10 else 0.9)
    for x in range(20, 311, 24):
        b += line(x, 10, x, 102, "#152C4A", 0.5)
    # volume bars
    for i, (x, _p) in enumerate(ANT_SERIES[1:-1]):
        hgt = 3 + ((i * 37) % 11) * 0.7 + (9 if i < 4 else 0)
        b += rect(x - 2, 102 - hgt, 4, hgt, "#1E4D6B", extra=' fill-opacity=".8"')
    pts = [(x, py(p)) for x, p in ANT_SERIES]
    dl = "M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts)
    b += path(dl + " L304 102 L20 102 Z", "url(#anA)")
    b += line(12, py(83), 310, py(83), "#FBBF24", 1.1, "4 3")
    b += path(dl, "none", "#6EE7B7", 2.4, ' stroke-linejoin="round" stroke-linecap="round" filter="url(#anGl)"')
    b += circle(20, py(83), 3.4, "#FBBF24", "#0B1730", 1.2)
    b += circle(96, py(111.53), 4.6, "#FFFFFF", "#10B981", 2.4, ' filter="url(#anGl)"')
    b += circle(304, py(97.17), 4.2, "#34D399", "#FFFFFF", 1.6)
    # record-raise badge (top left), peak, close pill
    b += rect(238, 66, 68, 32, "#FBBF24", 3, extra=' filter="url(#anGb)"')
    b += t(272, 84, "$81BN", 16, "#111827", 900, "middle", -0.2)
    b += t(272, 94.6, "RECORD IPO", 6.2, "#111827", 900, "middle", 1)
    b += t(106, 17, "PEAK $111.53", 11.5, "#FFFFFF", 900, "start", 0.3)
    b += t(106, 27, "ALMOST $2TN VALUE", 7.4, "#6EE7B7", 900, "start", 1)
    b += rect(226, 26, 84, 30, "#0F2A22", 3, "#34D399", 1.2)
    b += t(268, 38.6, "CLOSE $97.17", 10.4, "#FFFFFF", 900, "middle", 0.2)
    b += t(268, 51, "+17% DAY ONE", 9, "#34D399", 900, "middle", 0.6)
    b += rect(0, 104, W, 14, "#030712")
    b += t(12, 113.8, "ANT &#183; NASDAQ &#183; THU 19 NOV", 8, "#E5E7EB", 900, "start", 1.4)
    b += t(310, 113.8, "- - $83 IPO PRICE", 8, "#FBBF24", 900, "end", 0.9)
    return svg(W, H, b)


def art_icj():
    W, H = 322, 118
    d = ("<defs>"
         + lingrad_a("icS", [("0", "#0A1024", "1"), (".6", "#22234F", "1"), ("1", "#3B2C5E", "1")])
         + radgrad("icR", [("0", "#FCD34D", ".55"), (".45", "#F59E0B", ".14"), ("1", "#F59E0B", "0")], 161, 44, 80)
         + lingrad_a("icGd", [("0", "#FEF3C7", "1"), (".5", "#F2C94C", "1"), ("1", "#B7791F", "1")])
         + lingrad_a("icW", [("0", "#1A1C3A", "1"), ("1", "#0A0B1C", "1")])
         + glow_filter("icGl", 2.4, "#FBBF24")
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#icS)") + rect(0, 0, W, H, "url(#icR)")
    for x, y in ((18, 10), (44, 30), (70, 12), (100, 24), (224, 12), (256, 30), (284, 8), (306, 22), (126, 8)):
        b += circle(x, y, 0.85, "#FFFFFF", extra=' fill-opacity=".75"')
    # Peace Palace: long brick facade, steep roofs, clock tower
    pal = "#120F26"
    b += rect(26, 70, 270, 30, pal)
    for x in range(30, 290, 16):
        b += path("M%s 70 L%s 61 L%s 70 Z" % (x, x + 8, x + 16), pal)
    b += rect(228, 40, 30, 30, pal) + path("M226 40 L243 18 L260 40 Z", pal) + rect(241.5, 8, 3, 11, pal)
    b += circle(243, 50, 5.2, "#F4C46A") + circle(243, 50, 3.6, pal) + line(243, 50, 243, 47.2, "#F4C46A", 0.8)
    b += rect(60, 54, 28, 16, pal) + path("M58 54 L74 40 L90 54 Z", pal)
    b += windows(32, 74, 33, 3, 8, 7, 3, 4, "#F4C46A", 11, 0.62)
    # reflecting pond
    b += rect(0, 100, W, 4, "url(#icW)")
    for x in range(36, 290, 22):
        b += rect(x, 101.4, 9, 0.7, "#F4C46A", extra=' fill-opacity=".45"')
    # scales of justice
    g = "url(#icGd)"
    sc = (rect(159, 20, 4, 50, g) + rect(144, 68, 34, 5, g, 1.5) + circle(161, 17, 4.6, g)
          + rect(109, 26, 104, 3.6, g, 1.6))
    for cx in (116, 206):
        sc += line(cx, 29.6, cx - 14, 53, "#F2C94C", 1.1) + line(cx, 29.6, cx + 14, 53, "#F2C94C", 1.1)
        sc += path("M%s 53 Q%s 65 %s 53 Z" % (cx - 17, cx, cx + 17), g)
    b += '<g filter="url(#icGl)">' + sc + "</g>"
    b += t(14, 18, "GAMBIA v. MYANMAR", 8.2, "#F3E3B3", 900, "start", 1.4)
    b += t(308, 18, "GUILTY", 10.5, "#FCA5A5", 900, "end", 2.2)
    b += rect(0, 104, W, 14, "#05060F", extra=' fill-opacity=".85"')
    b += t(161, 114.2, "THE HAGUE &#183; FIRST STATE EVER FOUND GUILTY OF GENOCIDE", 7.9, "#F6D98F", 900,
           "middle", 1.3)
    return svg(W, H, b)


# ------------------------------------------------------- row 2 art (240x86)

def art_gta():
    W, H = 240, 86
    d = ("<defs>"
         + lingrad_a("gt2S", [("0", "#10032A", "1"), (".3", "#3A0F62", "1"), (".58", "#8B1B7C", "1"),
                              (".82", "#DE4A7C", "1"), ("1", "#FFB45F", "1")])
         + lingrad_a("gt2Sea", [("0", "#3A0E56", "1"), (".55", "#210A3A", "1"), ("1", "#0B0220", "1")])
         + lingrad_a("gt2Road", [("0", "#1C0838", "1"), ("1", "#05010C", "1")])
         + radgrad("gt2Glow", [("0", "#FFB36B", ".7"), (".5", "#FF4F8B", ".22"), ("1", "#FF4F8B", "0")],
                   158, 49, 58)
         + radgrad("gt2Sun", [("0", "#FFF4C2", "1"), (".45", "#FFC15E", "1"), (".8", "#FF6E8A", "1"),
                              ("1", "#E23E86", "1")], 158, 49, 21)
         + lingrad_a("gt2Beam", [("0", "#FFF0B8", ".5"), ("1", "#FFF0B8", "0")], x2="1", y2="0")
         + glow_filter("gt2N", 2.0, "#FF3FD8", 2)
         + glow_filter("gt2G", 1.1, "#22C55E")
         + blur_filter("gt2B", 1.4)
         + '<clipPath id="gt2SunC"><circle cx="158" cy="49" r="21"/></clipPath>'
         + "</defs>")
    b = d + rect(0, 0, W, 62, "url(#gt2S)") + rect(0, 0, W, 62, "url(#gt2Glow)")
    for x, y in ((18, 9), (40, 15), (66, 7), (96, 12), (132, 6), (196, 9), (222, 15), (232, 6)):
        b += circle(x, y, 0.7, "#FFFFFF", extra=' fill-opacity=".8"')
    # retro sun with horizontal cut bands
    sun = circle(158, 49, 21, "url(#gt2Sun)")
    bands = "".join(rect(135, y, 46, 1.1 + i * 0.55, "#C22C74", extra=' fill-opacity=".82"')
                    for i, y in enumerate((42.5, 46.5, 50.5, 54.5)))
    b += '<g clip-path="url(#gt2SunC)">' + sun + bands + "</g>"
    for x, y, w, h, a in ((14, 30, 54, 2.4, .26), (52, 22, 40, 1.8, .16), (176, 34, 46, 2.2, .2)):
        b += rect(x, y, w, h, "#FFB8C8", 1.2, extra=' fill-opacity="%s"' % n(a))
    # distant deco skyline on the horizon
    far = "#2A0B4A"
    for x, w, h in ((2, 13, 12), (16, 10, 19), (27, 16, 9), (45, 9, 16), (57, 13, 11),
                    (188, 12, 16), (201, 16, 10), (218, 9, 20), (229, 11, 13)):
        b += rect(x, 56 - h, w, h, far)
    b += path("M72 56 L72 40 L75 40 L75 33 L78 33 L78 56 Z", "#1B0536")
    b += path("M84 56 L84 44 L88 38 L92 44 L92 56 Z", "#1B0536")
    b += line(72, 40, 78, 40, "#FF6FE0", .8, extra=' filter="url(#gt2N)"')
    b += line(84, 44, 92, 44, "#FF6FE0", .7, extra=' filter="url(#gt2N)"')
    b += windows(18, 42, 2, 3, 3, 3, 1.2, 1.2, "#FFD27A", 5, .6)
    b += windows(202, 44, 3, 3, 3, 3, 1.2, 1.2, "#FFD27A", 9, .5)
    # ocean strip and glitter
    b += rect(0, 56, W, 7, "url(#gt2Sea)")
    for i, (w, y) in enumerate(((36, 58), (26, 60), (16, 62))):
        b += rect(158 - w / 2.0, y, w, 0.9, "#FFC36B", extra=' fill-opacity="%s"' % n(.55 - i * .1))
    b += line(0, 56, W, 56, "#FF7BE8", .9, extra=' filter="url(#gt2N)"')
    # boulevard with perspective lane lines
    b += rect(0, 62, W, 24, "url(#gt2Road)")
    b += path("M118 62 L94 86 L100 86 L120 62 Z", "#5B1B78", extra=' fill-opacity=".5"')
    b += path("M124 62 L152 86 L158 86 L126 62 Z", "#5B1B78", extra=' fill-opacity=".5"')
    b += line(120, 62, 106, 86, "#FF3FD8", 1, extra=' stroke-opacity=".55" filter="url(#gt2N)"')
    b += line(126, 62, 144, 86, "#FF3FD8", 1, extra=' stroke-opacity=".55" filter="url(#gt2N)"')
    for x, y, w in ((18, 70, 20), (50, 75, 12), (188, 68, 16), (202, 77, 9), (158, 84, 14)):
        b += rect(x, y, w, .7, "#FF7BE8", extra=' fill-opacity=".22"')
    b += palm(26, 86, 54, -5, "#0A0220", .85) + palm(40, 86, 34, 4, "#12042A", .6)
    b += palm(210, 86, 46, 6, "#0A0220", .8) + palm(224, 86, 30, 3, "#12042A", .55)
    # sleek sports car on the glowing boulevard
    b += path("M84 78 L92 73 Q102 70 116 69 L128 65 Q141 61 154 65 L166 69 Q178 71 184 75 L186 78 Z",
              "#1A0A2E")
    b += path("M92 73 Q102 70 116 69 L128 65 Q141 61 154 65 L166 69 Q178 71 184 75", "none",
              "#FF7BE8", 1.1, ' stroke-opacity=".9" filter="url(#gt2N)"')
    b += path("M126 65 Q140 61.5 153 65 L158 68.5 L121 68.5 Z", "#4C1D95")
    b += line(124, 66, 151, 66, "#7DD3FC", .9, extra=' stroke-opacity=".7"')
    b += circle(110, 78, 5.4, "#03010A", "#5B21B6", 1.1)
    b += circle(110, 78, 2.3, "#A855F7", extra=' fill-opacity=".9"')
    b += circle(164, 78, 5.4, "#03010A", "#5B21B6", 1.1)
    b += circle(164, 78, 2.3, "#A855F7", extra=' fill-opacity=".9"')
    b += rect(85, 72.5, 6, 1.8, "#FF2D55", 1, extra=' filter="url(#gt2N)"')
    b += poly([(183, 73.5), (206, 69), (212, 78), (184, 77.5)], "url(#gt2Beam)")
    b += circle(183, 74.6, 1.4, "#FFF3C4", extra=' filter="url(#gt2N)"')
    b += '<ellipse cx="136" cy="83" rx="48" ry="2.6" fill="#FF3FD8" opacity=".45" filter="url(#gt2B)"/>'
    # badges
    b += rect(7, 5, 98, 13, "#12041F", 2, "#FDE68A", .8)
    b += t(56, 14.3, "$1.5BN+ PRE-SALES", 7.6, "#FDE68A", 900, "middle", .7)
    b += rect(178, 5, 58, 30, "#15803D", 3, "#BBF7D0", 1, ' filter="url(#gt2G)"')
    b += t(207, 20.5, "99", 17.5, "#FFFFFF", 900, "middle", -0.3)
    b += t(207, 32.6, "METASCORE", 5.2, "#DCFCE7", 900, "middle", .8)
    return svg(W, H, b)


def art_cop():
    W, H = 240, 86
    d = ("<defs>"
         + lingrad_a("cp2S", [("0", "#0B0A2A", "1"), (".3", "#24124E", "1"), (".58", "#5B2A6E", "1"),
                              (".78", "#C25B5A", "1"), ("1", "#F2A65A", "1")])
         + lingrad_a("cp2Sea", [("0", "#2A1C50", "1"), (".45", "#123A54", "1"), ("1", "#081C2E", "1")])
         + radgrad("cp2Glow", [("0", "#FFB86B", ".42"), (".55", "#F97316", ".12"), ("1", "#F97316", "0")],
                   120, 58, 86)
         + lingrad_a("cp2Dome", [("0", "#152A5E", "1"), (".55", "#2C5C96", "1"), ("1", "#5FA6C8", "1")])
         + lingrad_a("cp2Sol", [("0", "#0EA5E9", "1"), (".6", "#38BDF8", "1"), ("1", "#A5F3FC", "1")], x2="1", y2="1")
         + lingrad_a("cp2Enter", [("0", "#FDE68A", ".95"), ("1", "#F59E0B", ".5")])
         + glow_filter("cp2G", 1.5, "#5EEAD4")
         + glow_filter("cp2A", 1.6, "#FDE68A")
         + blur_filter("cp2B", 1.7)
         + "</defs>")
    b = d + rect(0, 0, W, 64, "url(#cp2S)") + rect(0, 0, W, 64, "url(#cp2Glow)")
    for x, y in ((10, 9), (32, 16), (58, 7), (86, 12), (150, 8), (174, 16), (196, 22)):
        b += circle(x, y, 0.7, "#FFFFFF", extra=' fill-opacity=".75"')
    b += path("M230 4 A8 8 0 1 0 230 20 A6.2 6.2 0 1 1 230 4 Z", "#FDE68A", extra=' filter="url(#cp2A)"')
    # Mediterranean mountains behind the bay
    b += path("M0 54 L18 46 L34 50 L52 42 L70 48 L90 44 L112 50 L132 46 L154 51 L174 45 L196 50 "
              "L214 47 L240 52 L240 58 L0 58 Z", "#2B1B4E", extra=' fill-opacity=".9"')
    b += rect(0, 54, W, 10, "url(#cp2Sea)")
    b += line(0, 54, W, 54, "#F2B36A", .7, extra=' stroke-opacity=".7"')
    for x, w in ((94, 18), (108, 26), (124, 14), (166, 22), (180, 12)):
        b += rect(x, 56.5, w, .7, "#FFC98A", extra=' fill-opacity=".38"')
    # COP31 conference dome on the Antalya shore
    b += path("M92 62 A26 26 0 0 1 144 62 Z", "url(#cp2Dome)", "#8FD3E8", .7)
    for k in range(1, 6):
        ang = math.pi + k * math.pi / 6
        b += line(118, 62, 118 + 26 * math.cos(ang), 62 + 26 * math.sin(ang), "#8FD3E8", .45,
                  extra=' stroke-opacity=".32"')
    for rr in (9, 17):
        b += path("M%s 62 A%s %s 0 0 1 %s 62" % (n(118 - rr), n(rr), n(rr), n(118 + rr)),
                  "none", "#8FD3E8", .4, ' stroke-opacity=".28"')
    b += rect(106, 55, 24, 7, "url(#cp2Enter)", 1, extra=' filter="url(#cp2A)"')
    b += line(118, 55, 118, 62, "#5B3A12", .7)
    b += line(118, 36, 118, 30, "#E2E8F0", .8) + poly([(118, 30), (125, 32.4), (118, 34.8)], "#FCA5A5")
    b += line(104, 62, 132, 62, "#FDE68A", .9, extra=' stroke-opacity=".55"')
    b += rect(0, 62, W, 24, "#080A1A")
    b += path("M0 74 Q60 68 120 72 Q180 76 240 70 L240 86 L0 86 Z", "#0D1226")
    b += path("M0 74 Q60 68 120 72 Q180 76 240 70", "none", "#F2B36A", .7, ' stroke-opacity=".35"')
    # fossil left: derricks fading into shadow
    def derrick(x, base, h, a):
        topx = x + h * 0.16
        s = '<g opacity="%s">' % n(a)
        s += line(x - h * .26, base, topx, base - h, "#6B4A32", 1.3)
        s += line(x + h * .26, base, topx, base - h, "#6B4A32", 1.3)
        s += line(topx, base - h, topx, base - h - 3.4, "#6B4A32", 1)
        for f in (.32, .56, .78):
            half = h * .26 * (1 - f)
            s += line(topx - half, base - h * f, topx + half, base - h * f, "#6B4A32", .7)
        s += line(x - h * .26, base, topx + h * .26, base - h, "#6B4A32", .5)
        s += line(x + h * .26, base, topx - h * .26, base - h, "#6B4A32", .5)
        return s + "</g>"
    b += derrick(16, 70, 32, .8) + derrick(40, 70, 24, .5) + derrick(60, 70, 17, .3)
    for cx, cy, r, a in ((14, 28, 7, .32), (8, 20, 8, .24), (24, 22, 6, .2), (34, 16, 7, .16)):
        b += circle(cx, cy, r, "#A8A29E", extra=' fill-opacity="%s" filter="url(#cp2B)"' % n(a))
    b += '<ellipse cx="30" cy="70" rx="28" ry="2.4" fill="#1C1917" opacity=".8"/>'
    b += circle(8, 66, 1.3, "#F59E0B", extra=' fill-opacity=".6" filter="url(#cp2B)"')
    # clean right: ridge, turbines and a solar field
    b += path("M144 86 L144 72 Q168 64 192 68 Q216 72 240 64 L240 86 Z", "#0F5132")
    b += path("M144 86 L144 76 Q176 68 204 72 Q224 75 240 70 L240 86 Z", "#166534")
    def turbine(x, base, h, s):
        top = base - h
        out = line(x, base, x, top, "#E0F2FE", 1.2 * s)
        for ang in (-90, 30, 150):
            a = math.radians(ang)
            out += line(x, top, x + h * .42 * math.cos(a), top + h * .42 * math.sin(a), "#E0F2FE", 1.1 * s,
                        extra=' stroke-linecap="round"')
        return out + circle(x, top, 1.4 * s, "#5EEAD4", extra=' filter="url(#cp2G)"')
    b += turbine(170, 72, 30, 1) + turbine(198, 71, 24, .85) + turbine(222, 72, 19, .7)
    for r, (y, bw) in enumerate(((74, 24), (78, 31), (82, 37))):
        for k in range(3):
            x0 = 150 + k * 26 - r * 3
            b += poly([(x0, y), (x0 + bw, y), (x0 + bw - 3, y + 3.4), (x0 - 3, y + 3.4)],
                      "url(#cp2Sol)", "#67E8F9", .4)
            b += line(x0 + 1, y + 1.5, x0 + bw - 2, y + 1.5, "#0C4A6E", .35,
                      extra=' stroke-opacity=".55"')
    b += rect(54, 4, 132, 13, "#080D1F", 6.5, "#F8FAFC", .7)
    b += t(120, 13.5, "COP31 ANTALYA &#183; DRAFT 2", 7.2, "#F8FAFC", 900, "middle", 1)
    b += rect(148, 24.8, 88, 9.4, "#07121F", 4, extra=' fill-opacity=".74"')
    b += t(234, 32.2, "35% ELECTRIC BY 2035", 7, "#BBF7D0", 900, "end", .4)
    b += t(8, 83, "OIL &#183; GAS &#183; COAL", 7.2, "#FCA5A5", 900, "start", .9)
    b += t(8, 72.5, "PHASE-OUT", 5, "#E7B7B7", 900, "start", 1.2)
    return svg(W, H, b)


def art_cyclone():
    W, H = 240, 86
    d = ("<defs>"
         + radgrad("cyO", [("0", "#0F6A9E", "1"), (".6", "#0A3F66", "1"), ("1", "#051F38", "1")], 186, 54, 150)
         + lingrad_a("cyL", [("0", "#6E8B4A", "1"), (".6", "#A9A36A", "1"), ("1", "#D6C894", "1")], x2="1", y2="1")
         + radgrad("cyH", [("0", "#FFFFFF", ".55"), (".55", "#E0F2FE", ".18"), ("1", "#E0F2FE", "0")], 186, 52, 34)
         + blur_filter("cyB", 1.8)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cyO)")
    land = "M0 0 L176 0 L164 8 L150 13 L138 22 L126 30 L114 38 L102 46 L90 56 L78 66 L64 76 L52 86 L0 86 Z"
    b += path(land, "url(#cyL)") + path(land, "none", "#F5EBC8", 1.6)
    b += path("M18 0 Q34 30 20 60 Q14 74 24 86", "none", "#4E6B36", 1.2, ' stroke-opacity=".7"')
    b += path("M70 0 Q60 20 74 34 Q86 44 80 58", "none", "#4E6B36", 1, ' stroke-opacity=".6"')
    b += t(24, 24, "ODISHA", 11.5, "#2A2410", 900, "start", 1.6)
    b += t(24, 35, "~300,000 MOVED", 7.4, "#2A2410", 900, "start", 0.6)
    b += t(24, 45, "69 TRAINS CANCELLED", 6.4, "#3A3216", 900, "start", 0.4)
    b += rect(0, 0, W, H, "url(#cyH)")
    cx, cy = 186, 52
    arms = ""
    for k in range(4):
        a0 = k * math.pi / 2
        pts = [(cx + (3 + i * 1.15) * math.cos(a0 + i * 0.21), cy + (3 + i * 1.15) * math.sin(a0 + i * 0.21))
               for i in range(22)]
        arms += path("M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts), "none", "#FFFFFF", 4.2,
                     ' stroke-linecap="round"')
    b += '<g filter="url(#cyB)" opacity=".8">' + arms + "</g>" + '<g opacity=".95">' + arms.replace(
        'stroke-width="4.2"', 'stroke-width="2"') + "</g>"
    b += circle(cx, cy, 3.6, "#082F49", "#E0F2FE", 1)
    b += path("M236 84 Q214 74 200 62", "none", "#FDE68A", 1.6, ' stroke-dasharray="3 3"')
    b += path("M172 44 Q150 36 128 34", "none", "#FDE68A", 1.6, ' stroke-dasharray="3 3"')
    b += path("M128 34 L136 30.6 L135 38 Z", "#FDE68A")
    b += circle(121, 33, 4, "#DC2626", "#FFFFFF", 1.4)
    b += t(234, 14, "AKVAN", 11, "#FFFFFF", 900, "end", 1.8)
    b += t(234, 23, "LANDFALL FRI", 6.4, "#FDE68A", 900, "end", 0.8)
    b += t(118, 80, "BAY OF BENGAL", 6.4, "#BAE6FD", 900, "start", 1.4)
    return svg(W, H, b)


def art_riyadh():
    W, H = 240, 86
    d = ("<defs>"
         + lingrad_a("rS", [("0", "#060A1E", "1"), (".6", "#1E1A46", "1"), ("1", "#4A2147", "1")])
         + radgrad("rG", [("0", "#FFB347", ".95"), (".25", "#FF7A2F", ".45"), ("1", "#FF5A1F", "0")], 124, 26, 60)
         + lingrad_a("rT", [("0", "#2B3A66", "1"), (".5", "#4F6AAE", "1"), ("1", "#1A2444", "1")], x2="1", y2="0")
         + lingrad_a("rM", [("0", "#FDE68A", "0"), ("1", "#FDBA74", "1")], x2="1", y2="0")
         + blur_filter("rB", 1.8)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#rS)") + rect(0, 0, W, H, "url(#rG)")
    for x, y in ((14, 8), (40, 20), (66, 6), (196, 10), (222, 28), (170, 4), (28, 36), (90, 12)):
        b += circle(x, y, 0.85, "#FFFFFF", extra=' fill-opacity=".8"')
    # smoke drifting left from the hit
    for cx, cy, r, a in ((112, 22, 8, .5), (100, 18, 9, .42), (86, 15, 8, .34), (72, 13, 6, .26)):
        b += circle(cx, cy, r, "#57534E", extra=' fill-opacity="%s" filter="url(#rB)"' % n(a))
    sky = "#04060F"
    for x, w, h in ((0, 16, 20), (14, 14, 30), (30, 18, 16), (48, 14, 26), (64, 16, 34), (82, 14, 20),
                    (140, 16, 26), (156, 14, 18), (204, 16, 30), (222, 18, 22)):
        b += rect(x, 76 - h, w, h, sky)
        b += windows(x + 2, 79 - h, int((w - 3) // 4), int((h - 4) // 4), 4, 4, 1.5, 1.5, "#FCD34D", x, 0.35)
    # Kingdom Centre (bottle-opener crown)
    b += path("M174 76 L176 30 Q186 16 196 30 L198 76 Z M180 40 Q186 26 192 40 L192 34 Q186 22 180 34 Z",
              sky, extra=' fill-rule="evenodd"')
    b += path("M180 40 Q186 28 192 40 Z", "url(#rS)")
    b += windows(177, 44, 5, 8, 4, 4, 1.5, 1.5, "#FCD34D", 44, 0.4)
    # PIF tower: tapered glass faces, damaged upper floors
    b += path("M110 76 L112 20 L118 6 L124 4 L130 6 L134 20 L136 76 Z", "url(#rT)", "#7C93D0", 0.8)
    b += line(123, 5, 123, 76, "#8FA6E0", 0.5, extra=' stroke-opacity=".6"')
    for y in range(24, 74, 5):
        b += line(113, y, 135, y, "#9DB4EE", 0.5, extra=' stroke-opacity=".55"')
    for y, w in ((24, 18), (29, 16), (34, 12)):
        b += rect(124 - w / 2.0, y, w, 2.6, "#FF8A3D", extra=' fill-opacity=".9"')
    b += path(burst_d(124, 26, 16, 0.5), "#EA580C") + path(burst_d(124, 26, 11, 0.55, 11), "#FB923C")
    b += path(burst_d(124, 26, 6.5, 0.6, 9), "#FEF08A")
    b += path("M236 3 L140 21", "none", "url(#rM)", 2)
    b += rect(0, 76, W, 10, "#020308")
    b += t(6, 84, "RIYADH &#183; PIF TOWER", 6.8, "#FDE68A", 900, "start", 1.2)
    b += t(236, 84, "TALLEST IN RIYADH", 6.8, "#CBD5E1", 900, "end", 0.8)
    return svg(W, H, b)


# ------------------------------------------------------- row 2 art (190x64)

def art_kyiv():
    W, H = 190, 64
    d = ("<defs>"
         + lingrad_a("kS", [("0", "#475569", "1"), (".6", "#94A3B8", "1"), ("1", "#E2E8F0", "1")])
         + radgrad("kG", [("0", "#FDBA74", ".9"), (".4", "#F97316", ".35"), ("1", "#F97316", "0")], 150, 40, 30)
         + lingrad_a("kD", [("0", "#FDE68A", "1"), ("1", "#B7791F", "1")])
         + blur_filter("kB", 1.5)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#kS)") + rect(0, 0, W, H, "url(#kG)")
    for cx, cy, r, a in ((150, 30, 7, .6), (144, 20, 8, .5), (136, 11, 7, .4)):
        b += circle(cx, cy, r, "#334155", extra=' fill-opacity="%s" filter="url(#kB)"' % n(a))
    # St Volodymyr's Cathedral: ochre walls, dark domes with gilt crosses
    wall = "#D9B45A"
    b += rect(50, 40, 80, 24, wall) + rect(78, 28, 24, 14, wall)
    for cx, cy, r in ((90, 20, 8.5), (60, 33, 5.5), (120, 33, 5.5), (76, 28, 4.5), (104, 28, 4.5)):
        b += rect(cx - r * 0.8, cy + r * 0.4, r * 1.6, 64 - cy - r * 0.4, wall)
        b += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            n(cx - r), n(cy + r * 0.6), n(cx - r), n(cy - r), n(cx), n(cy - r * 1.5), n(cx + r), n(cy - r),
            n(cx + r), n(cy + r * 0.6)), "#1F2937")
        b += path("M%s %s Q%s %s %s %s" % (n(cx - r * 0.5), n(cy), n(cx - r * 0.3), n(cy - r * 0.9),
                                          n(cx), n(cy - r * 1.3)), "none", "#94A3B8", 0.7)
        b += rect(cx - 0.5, cy - r * 1.5 - 5, 1, 5, "url(#kD)") + rect(cx - 1.8, cy - r * 1.5 - 3.8, 3.6, 0.9, "url(#kD)")
    for x in (56, 68, 84, 96, 112, 124):
        b += path("M%s 60 L%s 50 Q%s 47 %s 50 L%s 60 Z" % (x, x, x + 2, x + 4, x + 4), "#7C5A1E")
    # embassy blocks with the Dutch and Austrian flags
    b += rect(4, 44, 40, 20, "#334155") + rect(140, 46, 46, 18, "#334155")
    b += windows(7, 47, 9, 3, 4, 5, 2, 2.6, "#CBD5E1", 3, 0.7) + windows(143, 49, 11, 3, 4, 5, 2, 2.6, "#CBD5E1", 9, 0.7)
    b += rect(20, 30, 1, 14, "#E5E7EB") + rect(21, 30, 12, 2.7, "#AE1C28") + rect(21, 32.7, 12, 2.7, "#FFFFFF") \
        + rect(21, 35.4, 12, 2.7, "#21468B")
    b += rect(170, 32, 1, 14, "#E5E7EB") + rect(171, 32, 12, 2.7, "#C8102E") + rect(171, 34.7, 12, 2.7, "#FFFFFF") \
        + rect(171, 37.4, 12, 2.7, "#C8102E")
    b += path(burst_d(156, 42, 9.5, 0.5), "#EA580C") + path(burst_d(156, 42, 6, 0.55, 11), "#FB923C")
    b += path(burst_d(156, 42, 3.4, 0.6, 9), "#FEF08A")
    for x, y in ((40, 10), (122, 8), (170, 16), (58, 18)):
        b += path("M%s %s L%s %s L%s %s L%s %s Z" % (x, y, x + 12, y - 3.4, x + 9, y, x + 12, y + 3.4), "#0F172A")
        b += line(x + 12, y, x + 18, y, "#0F172A", 0.6, "1.5 1.5")
    b += t(4, 11, "KYIV", 8, "#0F172A", 900, "start", 1.6)
    return svg(W, H, b)


# --------------------------------------------------------------- the stories

CARDS = [
    # row 1 - three lead features
    dict(n=1, reg="AP", place="SHENZHEN", art=art_apec, lon=114.06, lat=22.54, lead=True,
         h="THREE POWERS, ONE TABLE",
         p="First-ever Trump&#8211;Xi&#8211;Putin trilateral at APEC ends in a peace declaration: "
           "nuclear war &#8220;cannot be won&#8221;; omits Ukraine and Iran.",
         src="BBC &#183; GUARDIAN"),
    dict(n=2, reg="AM", place="NEW YORK", art=art_anthropic, lon=-74.0, lat=40.71,
         h="ANTHROPIC JUMPS 17%",
         p="Record $81bn IPO: ANT peaks at $111.53, near $2tn, and closes at $97.17, up 17%.",
         src="BBC &#183; ABC &#183; DW"),
    dict(n=3, reg="GL", place="THE HAGUE", art=art_icj, lon=4.30, lat=52.08,
         h="ICJ: MYANMAR GENOCIDE",
         p="UN top court convicts Myanmar of genocide against the Rohingya &#8212; the first such ruling.",
         src="BBC &#183; UN NEWS"),
    # row 2 - five crisp features
    dict(n=4, reg="GL", place="ANTALYA", art=art_cop, lon=30.71, lat=36.90,
         h="FOSSIL FUELS CUT",
         p="COP31 draft drops fossil fuels; 35% clean power by 2035.",
         src="REUTERS &#183; UN NEWS"),
    dict(n=5, reg="EU", place="KYIV", art=art_kyiv, lon=30.52, lat=50.45,
         h="KYIV EMBASSIES HIT",
         p="Drone raid kills 1 and damages Dutch and Austrian embassies in Kyiv.",
         src="KYIV IND. &#183; BBC"),
    dict(n=6, reg="ME", place="RIYADH", art=art_riyadh, lon=46.68, lat=24.71,
         h="PIF TOWER STRUCK",
         p="Houthi strike damages Riyadh&#8217;s tallest tower and the PIF wealth fund HQ.",
         src="REUTERS &#183; AL JAZEERA"),
    dict(n=7, reg="AP", place="ODISHA", art=art_cyclone, lon=84.90, lat=19.27,
         h="300,000 EVACUATED",
         p="Odisha moves 300,000 and cancels 69 trains before Friday&#8217;s landfall.",
         src="TNIE &#183; DW"),
    dict(n=8, reg="GL", place="WORLDWIDE", pin="MIAMI", art=art_gta, lon=-80.19, lat=25.76,
         h="GTA VI: 99 SCORE",
         p="99 Metascore beats Zelda&#8217;s record, with $1.5bn+ in pre-sales.",
         src="BBC &#183; GUARDIAN"),
]

DISPATCHES = [
    # 9-12 Africa
    ("AF", "KENYA", "Frontier Minerals wins $60bn+ US-led Mrima Hill niobium bid", "BBC"),
    ("AF", "SUDAN", "UN reports drone strikes have killed 1,630 civilians", "UN NEWS &#183; REUTERS"),
    ("AF", "SENEGAL", "Faye bypasses parliament to salvage $2.2bn IMF deal", "AFRICANEWS"),
    ("AF", "SOMALIA", "Mogadishu gives UAE envoy 72 hours to leave the country", "REUTERS"),
    # 13-14 Oceania
    ("OC", "TONGA", "27-day national emergency declared over El Ni&#241;o drought", "RNZ PACIFIC"),
    ("OC", "COOK ISLANDS", "Nassau placed on alert as Cyclone Xavier slows", "RNZ"),
    # 15-16 Americas
    ("AM", "WASHINGTON", "Senate rejects Iran war-powers curb in 51&#8211;48 vote", "AL JAZEERA"),
    ("AM", "HAITI", "Police raid in Port-au-Prince kills 34 gang members", "AL JAZEERA"),
    # 17-18 Europe
    ("EU", "COPENHAGEN", "MPs unanimously ratify US&#8211;Greenland security pact, 109&#8211;0", "DW"),
    ("EU", "BRUSSELS", "Commission reports first AI-driven cyberattack on its network", "DW"),
    # 19-20 Asia-Pacific / Global
    ("AP", "SEOUL", "Top court overturns ex-PM Han&#8217;s 15-year martial-law term", "DW"),
    ("GL", "PARIS", "IEA: datacentre power, CO2 up 70% by 2030 &#183; IMF sees 4.7%", "GUARDIAN &#183; REUTERS"),
]

NUMBERS = [
    ("$81BN", "ANTHROPIC IPO", "AM"),
    ("99", "GTA VI METASCORE", "GL"),
    ("300K", "ODISHA EVACUATED", "AP"),
    ("51&#8211;48", "SENATE IRAN VOTE", "AM"),
    ("4.7%", "IMF INFLATION", "GL"),
]

DATE_CHECK = (
    "<b>VERIFIED THU 19 NOV 2026 UTC</b> &#183; Excluded <b>WED 18</b>: Mo&#239;se plot verdict "
    "&#183; Fed minutes &#183; Van Gogh $190.4m"
)

SOURCES = (
    "BBC &#183; Reuters &#183; Guardian &#183; DW &#183; Al Jazeera &#183; UN News "
    "&#183; RNZ &#183; Africanews &#183; IEA"
)

# map badge offsets (px in the 338-wide map) for the eight card pins
BADGES = {
    1: (303, 99), 2: (79, 46), 3: (153, 30), 4: (204, 94),
    5: (221, 36), 6: (181, 102), 7: (268, 107), 8: (71, 95),
}
MAP_W = 338
MAP_SCALE = MAP_W / 1000.0
MAP_H = round(486.99 * MAP_SCALE, 1)
PIN_R = 8.5


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
    b = rect(0, 0, MAP_W, MAP_H, "#E7F0F5")
    for lat in (60, 30, 0, -30):
        y = project(0, lat)[1]
        b += line(0, y, MAP_W, y, "#C9DCE7", 0.6, "2 3" if lat else None)
    b += ('<g transform="scale(%.4f)"><path d="%s" fill="#EEE5D0" stroke="#A2906B" '
          'stroke-width="2.2" stroke-linejoin="round"/></g>' % (MAP_SCALE, land))
    leaders, dots, badges = "", "", ""
    for c in CARDS:
        _l, fill, ink = REGIONS[c["reg"]]
        x, y = project(c["lon"], c["lat"])
        bx, by = BADGES[c["n"]]
        dx, dy = bx - x, by - y
        dist = math.hypot(dx, dy) or 1
        ex, ey = bx - dx / dist * (PIN_R + 1.6), by - dy / dist * (PIN_R + 1.6)
        leaders += line(x, y, ex, ey, ink, 1)
        dots += circle(x, y, 2.4, fill, "#FFFFFF", 1, ' class="pin-dot"')
        badges += ('<g class="pin-badge" data-n="%d">' % c["n"]
                   + circle(bx, by, PIN_R, ink, "#FFFFFF", 1.3)
                   + t(bx, by + 3.5, str(c["n"]), 10, "#FFFFFF", 900, "middle")
                   + "</g>")
    b += leaders + dots + badges
    return svg(MAP_W, MAP_H, b, "map-svg")


# --------------------------------------------------------------------- css

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:1024px;height:1024px;overflow:hidden;background:#FAF8F4;}
body{font-family:Lato,sans-serif;color:#111827;-webkit-font-smoothing:antialiased;}
.page{position:relative;width:1024px;height:1024px;overflow:hidden;background:#FAF8F4;}
.rule-top{position:absolute;left:16px;right:16px;top:6px;height:3px;background:#111827;}
.dateline{position:absolute;left:14px;top:9px;height:62px;line-height:60px;font-weight:900;
 font-size:52px;letter-spacing:-1.6px;white-space:nowrap;color:#111827;}
.dateline .d{color:#B91C1C;}
.edition{position:absolute;right:16px;top:12px;width:212px;height:52px;border:2px solid #111827;
 background:#FFFFFF;text-align:center;padding-top:4px;}
.edition div{white-space:nowrap;}
.edition .e1{font-weight:900;font-size:7.6px;letter-spacing:1.5px;line-height:11px;color:#374151;}
.edition .e2{font-weight:900;font-size:15px;letter-spacing:1.1px;line-height:17px;color:#111827;}
.edition .e3{font-weight:900;font-size:7.4px;letter-spacing:.6px;line-height:12px;color:#991B1B;}
.regionbar{position:absolute;left:16px;right:16px;top:72px;height:18px;display:flex;gap:2px;}
.seg{flex:1 1 0;height:18px;line-height:18px;color:#FFFFFF;font-weight:900;font-size:8.6px;
 letter-spacing:.6px;text-align:center;white-space:nowrap;overflow:hidden;}
.seg b{font-weight:900;margin-left:5px;padding:0 4px;background:rgba(0,0,0,.28);border-radius:2px;}
.numbers{position:absolute;left:16px;right:16px;top:93px;height:26px;display:flex;
 border-top:1px solid #111827;border-bottom:2px solid #111827;background:#FFFFFF;}
.numbers .lab{flex:none;background:#111827;color:#FAF8F4;font-weight:900;font-size:8.4px;
 letter-spacing:1.4px;line-height:23px;padding:0 10px;white-space:nowrap;}
.cell{flex:1 1 0;display:flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap;
 border-left:1px solid #DCD3C2;overflow:hidden;}
.cell:first-of-type{border-left:none;}
.cell .v{font-weight:900;font-size:15px;color:var(--ink);letter-spacing:-.2px;line-height:18px;}
.cell .k{font-weight:900;font-size:7.4px;letter-spacing:.5px;color:#374151;line-height:10px;}
.row{position:absolute;left:16px;width:992px;display:grid;}
.r1{top:127px;height:218px;grid-template-columns:repeat(3,324px);column-gap:10px;}
.r2{top:353px;height:154px;grid-template-columns:repeat(5,192px);column-gap:8px;}
.card{position:relative;background:#FFFFFF;border:1px solid #D6CCBA;border-top:3px solid var(--fill);
 display:flex;flex-direction:column;overflow:hidden;}
.art{flex:none;overflow:hidden;border-bottom:1px solid #E6DDCD;}
.art svg{display:block;width:100%;height:100%;}
.r1 .art{height:118px;}.r2 .art{height:68px;}
.body{flex:1;display:flex;flex-direction:column;min-height:0;}
.r1 .body{padding:0 11px 5px;}.r2 .body{padding:0 8px 4px;}
.kick{display:flex;align-items:center;gap:5px;white-space:nowrap;flex:none;overflow:hidden;}
.badge{flex:none;display:inline-block;background:var(--ink);color:#FFFFFF;font-weight:900;
 text-align:center;border-radius:2px;}
.kick .rg{font-weight:900;color:var(--ink);}
.kick .pl{font-weight:900;color:#374151;}
.lead{flex:none;font-weight:900;font-size:7px;letter-spacing:.8px;color:#FFFFFF;background:#B91C1C;
 padding:2px 4px;border-radius:2px;line-height:9px;}
.card h2{font-weight:900;color:#111827;white-space:nowrap;flex:none;overflow:hidden;}
.card p{color:#1F2937;flex:none;overflow:hidden;}
.src{margin-top:auto;border-top:1px solid #E6DDCD;font-weight:900;color:#374151;white-space:nowrap;
 flex:none;overflow:hidden;display:flex;justify-content:space-between;}
.src .dt{color:#6B7280;}
.r1 .kick{margin-top:5px;height:16px;}
.r1 .badge{width:16px;height:16px;line-height:16px;font-size:10px;}
.r1 .kick .rg,.r1 .kick .pl{font-size:8.8px;letter-spacing:.7px;}
.r1 h2{margin-top:3px;font-size:21px;line-height:24px;letter-spacing:-.35px;}
.r1 p{margin-top:3px;font-size:10.5px;line-height:13.4px;height:26.8px;}
.r1 .src{font-size:7.8px;letter-spacing:.7px;padding-top:3px;line-height:9px;}
.r2 .kick{margin-top:4px;height:13px;}
.r2 .badge{width:13px;height:13px;line-height:13px;font-size:8.6px;}
.r2 .kick .rg,.r2 .kick .pl{font-size:7.8px;letter-spacing:.35px;}
.r2 h2{margin-top:2px;font-size:16.5px;line-height:18.5px;letter-spacing:-.3px;}
.r2 p{margin-top:2px;font-size:10.5px;line-height:13px;height:26px;}
.r2 .src{font-size:7px;letter-spacing:.4px;padding-top:2px;line-height:8px;}
.panel{position:absolute;top:517px;height:463px;background:#FFFFFF;border:1px solid #D6CCBA;
 border-top:3px solid #111827;overflow:hidden;}
.mappanel{left:16px;width:356px;padding:0 7px;display:flex;flex-direction:column;}
.digest{left:380px;width:636px;padding:0 11px;display:flex;flex-direction:column;}
.pcap{height:26px;display:flex;justify-content:space-between;align-items:center;white-space:nowrap;
 border-bottom:1px solid #E6DDCD;overflow:hidden;flex:none;}
.pcap .l{font-weight:900;font-size:9.6px;letter-spacing:1.6px;color:#111827;}
.pcap .r{font-weight:900;font-size:7.4px;letter-spacing:.6px;color:#374151;}
.mapbox{margin-top:8px;width:340px;border:1px solid #A9BCCB;flex:none;}
.map-svg{display:block;width:338px;}
.legend{margin-top:10px;display:grid;grid-template-columns:1fr 1fr;column-gap:12px;row-gap:2px;flex:none;}
.lg{display:flex;align-items:center;gap:5px;height:15px;white-space:nowrap;overflow:hidden;}
.lg i{flex:none;width:10px;height:10px;background:var(--fill);border-radius:1px;}
.lg .nm{font-weight:900;font-size:8.2px;letter-spacing:.5px;color:var(--ink);}
.lg .ct{margin-left:auto;font-weight:900;font-size:8.6px;color:#111827;}
.pinkey{margin-top:10px;border-top:1px solid #E6DDCD;padding-top:5px;display:flex;flex-direction:column;
 flex:1;min-height:0;}
.pk{flex:1 1 0;min-height:0;display:flex;align-items:center;gap:6px;white-space:nowrap;overflow:hidden;}
.pk b{flex:none;width:14px;height:13px;line-height:13px;font-size:8px;text-align:center;color:#FFFFFF;
 background:var(--ink);border-radius:2px;font-weight:900;}
.pk span{font-weight:900;font-size:7.8px;letter-spacing:.4px;color:#1F2937;}
.pk .rg{margin-left:auto;font-weight:900;font-size:7px;letter-spacing:.4px;color:var(--ink);}
.mnote{margin-top:auto;padding-top:4px;border-top:1px solid #E6DDCD;font-weight:900;font-size:7.2px;
 letter-spacing:.5px;color:#374151;white-space:nowrap;overflow:hidden;}
.cols{margin-top:4px;display:flex;flex-direction:column;flex:1;min-height:0;}
.dl{flex:1 1 0;min-height:0;display:flex;align-items:center;gap:6px;white-space:nowrap;overflow:hidden;
 border-bottom:1px dotted #DCD3C2;}
.dl:last-child{border-bottom:none;}
.dl .nb{flex:none;width:20px;height:16px;line-height:16px;text-align:center;font-weight:900;
 font-size:9.4px;color:#FFFFFF;background:var(--ink);border-radius:2px;}
.dl .tg{flex:none;display:flex;align-items:center;gap:4px;font-weight:900;font-size:9.6px;
 letter-spacing:.3px;color:#111827;}
.dl .tg .rg{font-size:7.8px;letter-spacing:.6px;color:var(--ink);}
.dl .tg .sep{font-size:8px;color:#9CA3AF;}
.dl .tx{flex:none;font-size:12.3px;font-weight:400;color:#111827;}
.dl .so{margin-left:auto;flex:none;padding-left:6px;font-weight:900;font-size:7px;letter-spacing:.4px;
 color:#4B5563;}
.footer{position:absolute;left:16px;right:16px;top:984px;height:32px;background:#111827;
 padding:0 12px;display:flex;align-items:center;}
.f1{font-size:8px;color:#F3EEE4;font-weight:400;white-space:nowrap;overflow:hidden;}
.f1 .k{font-weight:900;color:#FBBF24;letter-spacing:1px;margin-right:6px;}
.f1 .s{font-weight:900;color:#FBBF24;letter-spacing:1px;margin-right:6px;}
.f1 b{font-weight:900;color:#FFFFFF;}
.f1 .sep{color:#6B7280;margin:0 9px;}
"""


def style_vars(reg):
    _l, fill, ink = REGIONS[reg]
    return "--fill:%s;--ink:%s;" % (fill, ink)


def card_html(c):
    label = REGIONS[c["reg"]][0]
    lead = '<span class="lead">LEAD</span>' if c.get("lead") else ""
    return (
        '<section class="card" data-story="c%02d" style="%s">' % (c["n"], style_vars(c["reg"]))
        + '<div class="art">%s</div>' % c["art"]()
        + '<div class="body"><div class="kick"><span class="badge">%d</span>%s'
          '<span class="rg">%s</span><span class="pl">&#183; %s</span></div>' % (c["n"], lead, label, c["place"])
        + '<h2>%s</h2><p>%s</p>' % (c["h"], c["p"])
        + '<div class="src"><span>[%s]</span><span class="dt">THU 19 NOV</span></div></div>' % c["src"]
        + "</section>"
    )


def dispatch_html(num, d):
    reg, tag, text, src = d
    return ('<div class="dl" data-story="d%02d" style="%s"><span class="nb">%d</span>'
            '<span class="tg"><span class="rg">%s</span><span class="sep">&#183;</span>%s</span>'
            '<span class="tx">%s</span><span class="so">%s</span></div>'
            % (num, style_vars(reg), num, REGIONS[reg][0], tag, text, src))


def build_html():
    counts = region_counts()
    total = sum(counts.values())
    segs = "".join(
        '<div class="seg" style="background:%s">%s<b>%d</b></div>'
        % (REGIONS[k][1], REGIONS[k][0], counts[k]) for k in ORDER)
    nums = "".join(
        '<div class="cell" style="%s"><span class="v">%s</span><span class="k">%s</span></div>'
        % (style_vars(r), v, k) for v, k, r in NUMBERS)
    rows = [CARDS[0:3], CARDS[3:8]]
    rows_html = "".join('<div class="row r%d">%s</div>' % (i + 1, "".join(card_html(c) for c in r))
                        for i, r in enumerate(rows))
    legend = "".join(
        '<div class="lg" style="%s"><i></i><span class="nm">%s</span><span class="ct">%d</span></div>'
        % (style_vars(k), REGIONS[k][0], counts[k]) for k in ORDER)
    legend += ('<div class="lg" style="--fill:#111827;--ink:#111827"><i></i>'
               '<span class="nm">ALL STORIES</span><span class="ct">%d</span></div>' % total)
    pinkey = "".join('<div class="pk" style="%s"><b>%d</b><span>%s</span><span class="rg">%s</span></div>'
                     % (style_vars(c["reg"]), c["n"], c.get("pin", c["place"]),
                        REGIONS[c["reg"]][0]) for c in CARDS)
    lines = [dispatch_html(9 + i, d) for i, d in enumerate(DISPATCHES)]
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>THURSDAY, 19 NOVEMBER 2026</title><style>' + CSS + '</style></head><body>'
        '<div class="page">'
        '<div class="rule-top"></div>'
        '<div class="dateline"><span class="d">THURSDAY,</span> 19 NOVEMBER 2026</div>'
        '<div class="edition"><div class="e1">THE WORLD CANVAS &#183; LATE FINAL</div>'
        '<div class="e2">%d STORIES &#183; 7 REGIONS</div>'
        '<div class="e3">ALL VERIFIED THU 19 NOV 2026</div></div>' % total
        + '<div class="regionbar">' + segs + '</div>'
        '<div class="numbers"><div class="lab">DAY IN NUMBERS</div>' + nums + '</div>'
        + rows_html
        + '<div class="panel mappanel"><div class="pcap"><span class="l">WORLD LOCATOR</span>'
          '<span class="r">PINS 1&#8211;8 = FEATURES</span></div>'
          '<div class="mapbox">' + world_map_svg() + '</div>'
          '<div class="legend">' + legend + '</div><div class="pinkey">' + pinkey + '</div>'
          '<div class="mnote">20 STORIES &#183; 7 REGIONS &#183; ALL THU 19 NOV 2026</div></div>'
        + '<div class="panel digest"><div class="pcap"><span class="l">WORLD DISPATCHES &#183; 9&#8211;%d</span>'
          '<span class="r">12 ONE-LINE BRIEFS &#183; EACH FIRST REPORTED THU 19 NOV 2026</span></div>'
          % (8 + len(DISPATCHES))
        + '<div class="cols">' + "".join(lines) + '</div></div>'
        + '<div class="footer"><div class="f1"><span class="k">DATE CHECK</span>' + DATE_CHECK
        + '<span class="sep">|</span><span class="s">SOURCES</span>' + SOURCES + '</div></div>'
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
      '.pcap,.lg,.pk,.dl,.footer div,.panel,.card,.art,.mnote').forEach(el => {
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
    out.notes.push(c.dataset.story + ' h' + lh + ' p' + lp);
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
  sib('.row'); sib('.cols'); sib('.legend'); sib('.pinkey'); sib('.regionbar'); sib('.numbers');
  sib('.body'); sib('.kick'); sib('.dl'); sib('.edition'); sib('.footer'); sib('.tg');
  const secs = ['.rule-top','.dateline','.edition','.regionbar','.numbers','.r1','.r2','.mappanel',
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
      n = n.parentElement; } return [250, 248, 244]; };
  const floor = (sel, min) => document.querySelectorAll(sel).forEach(el => {
    const r = ratio(parse(getComputedStyle(el).color).slice(0, 3), bgOf(el));
    if (r < min) add('contrast ' + lab(el) + ' ' + r.toFixed(2));
  });
  floor('.card h2,.card p,.dl .tx,.dateline,.edition div,.cell .k,.lg .ct,.pk span,.f1', 7);
  floor('.kick .rg,.kick .pl,.src,.dl .tg,.dl .so,.cell .v,.lg .nm,.pcap .l,.pcap .r,.badge,.dl .nb,.pk b,.seg,.f1 .k,.f1 .s,.lead,.mnote,.dl .tg .rg,.pk .rg', 4.5);
  return out;
}"""


ART_BOXES_JS = r"""() => [...document.querySelectorAll('.art svg, .map-svg')].map(e => {
  const r = e.getBoundingClientRect();
  return [Math.ceil(r.left), Math.ceil(r.top), Math.floor(r.right), Math.floor(r.bottom)];
})"""


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
                audit["art_boxes"] = page.evaluate(ART_BOXES_JS)
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
    expect = {"c%02d" % c["n"] for c in CARDS} | {"d%02d" % (9 + i) for i in range(len(DISPATCHES))}
    assert len(expect) == 20, len(expect)
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
    box = (392, 545, 1008, 976)  # the dispatch column
    sn, sd = sharpness(native, box), sharpness(down, box)
    print("digest edge variance: native 1x %.1f | 2x->Lanczos %.1f" % (sn, sd))
    # Text: keep whichever render is sharper on the dispatch column. Illustrations:
    # always take the 2x-supersampled Lanczos pixels (cleaner anti-aliasing on flags,
    # stripes, spirals and skylines), pasted back on the integer-aligned SVG boxes.
    chosen, mode = (down, "2x supersampled -> Lanczos") if sd >= sn else (native, "native 1x")
    if chosen is native:
        boxes = [tuple(b) for b in audit["art_boxes"]]
        assert len(boxes) == 9, boxes
        for b in boxes:
            chosen.paste(down.crop(b), b[:2])
        mode += " text + 2x Lanczos in %d illustration boxes" % len(boxes)

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
