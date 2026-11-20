#!/usr/bin/env python3
"""Build the 1024x1024 visual broadsheet for Thursday 19 November 2026 (entry.png), v10.

A classic archival editorial broadsheet: warm cream newsprint, a giant Title-Case
serif masthead, an italic crimson deck, a seven-region balance bar, a parchment
Day-in-Numbers strip, thirteen bold high-contrast editorial graphics in three
rows (3 + 5 + 5), a Natural Earth locator with numbered pins 1-13, and twenty
numbered dispatches (14-33) as one crisp line each in two balanced columns. A
crimson-boxed DATE CHECK names the Wednesday and Friday stories that were
deliberately left out.

The page is rendered in headless Chromium at 1x and 2x device scale. The same
pass runs a strict DOM geometry audit (exact size, 33/33 story census, 13 map
badges, exact region sums, no overflow, no overlaps, no clipped text, headline
and summary line limits, >=15px dispatch slack, SVG ink inside every viewBox
and an ink-contrast floor); the build fails on any issue. Text comes from native
1x Playwright text; the 2x Lanczos pixels are pasted into all fourteen
integer-aligned illustration and map boxes. The result is a 4:4:4 baseline JPEG.

Build-time tooling only (Playwright + Pillow). The shipped runtime (main.py) is
standard library only. Everything rendered is local: system Liberation Serif /
Lato, inline SVG and the Natural Earth 1:110m outline stored in
world_land_110m.svgpath.
"""

import io
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "entry.png"
WORLD_PATH = ROOT / "world_land_110m.svgpath"
HTML_PATH = Path("/tmp/world_news_canvas_v10.html")
RAW_1X = Path("/tmp/world_news_canvas_v10_1x.png")
RAW_2X = Path("/tmp/world_news_canvas_v10_2x.png")
PREVIEW_300 = Path("/tmp/news_v10_300.png")
PREVIEW_512 = Path("/tmp/news_v10_512.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITIES = (92, 91, 90)
JPEG_MAX = 450 * 1000
HARD_LIMIT = 1048576

SERIF = "Liberation Serif, DejaVu Serif, Georgia, serif"
SANS = "Lato, Liberation Sans, sans-serif"

# key: (label, fill, ink) - muted archival region inks, used for chips and pins
REGIONS = {
    "EU": ("EUROPE", "#1F4E79", "#1B4467"),
    "AM": ("AMERICAS", "#8C2F39", "#7A2730"),
    "AP": ("ASIA-PACIFIC", "#5B3F80", "#4F366F"),
    "AF": ("AFRICA", "#8A4A12", "#783F0F"),
    "ME": ("MIDDLE EAST", "#12606F", "#0F5360"),
    "OC": ("OCEANIA", "#8F2F55", "#7C2849"),
    "GL": ("GLOBAL/SCIENCE", "#2A5F45", "#24523B"),
}
ORDER = ["AP", "AM", "EU", "ME", "AF", "OC", "GL"]


# ------------------------------------------------------------------ svg utils

def n(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def svg(w, h, body, cls="art-svg"):
    return ('<svg class="%s" viewBox="0 0 %s %s" preserveAspectRatio="none" '
            'xmlns="http://www.w3.org/2000/svg">%s</svg>' % (cls, n(w), n(h), body))


def t(x, y, s, size, fill, weight=700, anchor="start", ls=0.0, extra=""):
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

def radgrad(gid, stops, cx, cy, r, user=True):
    s = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (o, c, a) for o, c, a in stops)
    units = ' gradientUnits="userSpaceOnUse"' if user else ""
    return ('<radialGradient id="%s" cx="%s" cy="%s" r="%s"%s>%s</radialGradient>'
            % (gid, n(cx), n(cy), n(r), units, s))


def lingrad(gid, stops, x1="0", y1="0", x2="0", y2="1"):
    s = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (o, c, a) for o, c, a in stops)
    return ('<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
            % (gid, x1, y1, x2, y2, s))


def fold_shade(gid):
    return lingrad(gid, [("0", "#FFFFFF", ".30"), (".28", "#000000", ".14"), (".52", "#FFFFFF", ".22"),
                         (".78", "#000000", ".10"), ("1", "#000000", ".26")], x2="1", y2="0")


def burst_d(cx, cy, r, inner=0.48, spikes=13):
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


def wave_d(x, y, w, h, amp):
    pts_top = [(x + w * i / 8.0, y + amp * math.sin(i * math.pi / 4)) for i in range(9)]
    pts_bot = [(x + w * i / 8.0, y + h + amp * math.sin(i * math.pi / 4)) for i in range(8, -1, -1)]
    return "M" + " L".join("%s %s" % (n(a), n(b)) for a, b in pts_top + pts_bot) + " Z"


def flag_us(x, y, w, h, _cid):
    s = "".join(rect(x, y - 2 + i * (h + 4) / 13.0, w, (h + 4) / 13.0 + 0.3,
                     "#B42318" if i % 2 == 0 else "#FAF7F0") for i in range(13))
    cw, ch = w * 0.42, (h + 4) * 7 / 13.0
    s += rect(x, y - 2, cw, ch, "#1F3A6E")
    for r in range(3):
        for c in range(4):
            s += circle(x + cw * (c + 0.7) / 4.4, y - 2 + ch * (r + 0.7) / 3.4, 0.55, "#FAF7F0")
    return s


def flag_cn(x, y, w, h, _cid):
    s = rect(x, y - 2, w, h + 4, "#D52B1E")
    s += path(star_d(x + w * 0.17, y + h * 0.28, h * 0.16), "#FFDE00")
    for a, b in ((0.33, 0.1), (0.4, 0.2), (0.4, 0.35), (0.33, 0.46)):
        s += path(star_d(x + w * a, y + h * b, h * 0.055), "#FFDE00")
    return s


def flag_ru(x, y, w, h, _cid):
    b = (h + 4) / 3.0
    return (rect(x, y - 2, w, b + 0.3, "#FAF7F0") + rect(x, y - 2 + b, w, b + 0.3, "#1C3F94")
            + rect(x, y - 2 + 2 * b, w, b, "#D52B1E"))


def pole_flag(px, top, w, h, fn, cid, amp=1.6):
    d = wave_d(px + 1, top + 2, w, h, amp)
    return ('<clipPath id="%s"><path d="%s"/></clipPath>' % (cid, d)
            + '<g clip-path="url(#%s)">%s%s</g>' % (cid, fn(px + 1, top + 2, w, h, cid),
                                                     path(d, "url(#%sF)" % cid))
            + path(d, "none", "#000000", 0.4, ' stroke-opacity=".28"'))


def palm(x, base, height, lean, colour, scale=1.0):
    tx, ty = x + lean, base - height
    s = path("M%s %s Q%s %s %s %s L%s %s Q%s %s %s %s Z" % (
        n(x - 1.6 * scale), n(base), n(x + lean * 0.2 - 1.2 * scale), n(base - height * 0.55), n(tx - 0.8 * scale), n(ty),
        n(tx + 0.8 * scale), n(ty), n(x + lean * 0.2 + 1.2 * scale), n(base - height * 0.55), n(x + 1.6 * scale), n(base)),
        colour)
    for ang, ln in ((-170, 18), (-140, 16), (-105, 12), (-60, 14), (-25, 17), (10, 15), (160, 14)):
        a = math.radians(ang)
        ex, ey = tx + ln * scale * math.cos(a), ty + ln * scale * math.sin(a) + 5 * scale
        mx, my = tx + ln * scale * 0.55 * math.cos(a), ty + ln * scale * 0.55 * math.sin(a) - 3 * scale
        s += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            n(tx), n(ty), n(mx), n(my - 2.2 * scale), n(ex), n(ey), n(mx), n(my + 1.6 * scale), n(tx), n(ty + 1)),
            colour)
    return s


# ------------------------------------------------------ v10 bold editorial art
# Every illustration is a high-contrast editorial graphic: large shapes, a
# strong focal object, one unmistakable crimson/emerald callout and generous
# padding so nothing clips at 300px.  Row 1 is 322x102; rows 2-3 are 190x58.

def art_apec():
    """Shenzhen: a bold summit table under three crisp flags and podium tags."""
    W, H = 322, 102
    d = ("<defs>"
         + lingrad("apSky", [("0", "#082743", "1"), (".55", "#14507E", "1"), ("1", "#2A7FAE", "1")])
         + lingrad("apSea", [("0", "#1D6E92", "1"), ("1", "#0B3B55", "1")])
         + lingrad("apT", [("0", "#F8E9C8", "1"), ("1", "#D9BE8A", "1")])
         + fold_shade("FUF") + fold_shade("FCF") + fold_shade("FRF")
         + "</defs>")
    b = d + rect(0, 0, W, 72, "url(#apSky)")
    b += circle(280, 30, 17, "#FFD36B", extra=' fill-opacity=".28"')
    b += circle(280, 30, 9, "#FFE7A0")
    for x, w, h in ((0, 18, 14), (18, 12, 25), (30, 16, 18), (46, 10, 28), (56, 14, 20),
                    (190, 16, 21), (206, 12, 29), (218, 16, 17), (238, 10, 24), (302, 12, 18)):
        b += rect(x, 72 - h, w, h, "#082743", extra=' fill-opacity=".8"')
    b += rect(0, 72, W, 8, "url(#apSea)")
    for x, w in ((14, 22), (48, 14), (92, 30), (140, 18), (196, 24), (250, 16), (288, 20)):
        b += rect(x, 74 + (x % 3), w, .9, "#FFFFFF", extra=' fill-opacity=".5"')
    b += rect(0, 80, W, 22, "#E8D2A8")
    b += poly([(30, 80), (292, 80), (306, 92), (16, 92)], "url(#apT)")
    b += rect(16, 92, 290, 10, "#6E4A2C")
    b += rect(24, 94, 274, 4, "#9A1B1F")
    for px, fn, cid in ((57, flag_us, "FU"), (161, flag_cn, "FC"), (265, flag_ru, "FR")):
        b += rect(px - 1, 18, 2, 58, "#D8C7A2")
        b += circle(px, 17.5, 2.4, "#E8B84B", "#3A2A16", .5)
        b += pole_flag(px, 18, 44, 28, fn, cid, 1.2)
    for x, lab in ((57, "TRUMP"), (161, "XI"), (265, "PUTIN")):
        b += rect(x - 29, 54, 58, 13, "#FDFBF6", 2, "#1A1F2B", .9)
        b += t(x, 63.2, lab, 8.4, "#1A1F2B", 900, "middle", .9)
    b += rect(0, 0, W, 17, "#9A1B1F")
    b += rect(0, 17, W, 1.6, "#E8B84B")
    b += t(9, 12, "APEC 2026 &#183; SHENZHEN", 8.4, "#FFFFFF", 900, "start", 1.0)
    b += t(313, 12, "3 LEADERS", 7.4, "#F7E7C2", 900, "end", .8)
    return svg(W, H, b)


def art_icj():
    """The Hague: crisp Peace Palace, oversized gold scales and a 9-6 GUILTY stamp."""
    W, H = 322, 102
    d = ("<defs>"
         + lingrad("icS", [("0", "#0D304C", "1"), (".55", "#2A658E", "1"), ("1", "#C8E1ED", "1")])
         + lingrad("icL", [("0", "#F7E8C4", "1"), ("1", "#D6B87F", "1")])
         + lingrad("icR", [("0", "#8E3A28", "1"), ("1", "#5E2418", "1")])
         + lingrad("icG", [("0", "#FFE08A", "1"), ("1", "#B8861E", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#icS)")
    b += circle(286, 18, 18, "#FFE7A0", extra=' fill-opacity=".25"') + circle(286, 18, 9, "#FFF3C4")
    b += rect(0, 78, W, 24, "#244C36")
    b += rect(0, 78, W, 2, "#7FA36B")
    # palace
    b += rect(40, 44, 242, 36, "url(#icL)") + rect(40, 44, 242, 3, "#B68D4A")
    b += rect(136, 24, 50, 56, "#F7E8C4") + rect(136, 24, 50, 3, "#B68D4A")
    b += poly([(132, 25), (161, 4), (190, 25)], "url(#icR)")
    b += rect(159, 1.5, 4, 5, "#C9971F")
    for x in range(48, 132, 13):
        b += rect(x, 52, 7, 28, "#E7CD9C") + rect(x + 6, 52, 1.4, 28, "#B68D4A")
    for x in range(192, 276, 13):
        b += rect(x, 52, 7, 28, "#E7CD9C") + rect(x + 6, 52, 1.4, 28, "#B68D4A")
    b += windows(50, 58, 6, 3, 13, 8, 4, 4, "#6B4A28", 3, .7)
    b += windows(194, 58, 6, 3, 13, 8, 4, 4, "#6B4A28", 9, .7)
    b += windows(145, 34, 3, 3, 9, 8, 4, 4, "#6B4A28", 5, .8)
    b += rect(120, 80, 84, 5, "#C9A96C") + rect(110, 85, 104, 3, "#A9874F")
    # oversized gold scales, drawn in front of the palace
    g = "url(#icG)"
    b += rect(46, 82, 86, 6, "#8E2F39", 1, "#3A2412", .8)
    b += rect(86, 34, 5, 48, g, 0, "#3A2412", 1.2)
    b += circle(88.5, 31, 4.2, g, "#3A2412", 1.2)
    b += rect(40, 38, 98, 4, g, 1, "#3A2412", 1.2)
    for cx in (46, 132):
        b += line(cx, 42, cx - 12, 63, "#3A2412", 1.5) + line(cx, 42, cx + 12, 63, "#3A2412", 1.5)
        b += line(cx, 42, cx - 12, 63, "#C9971F", .8) + line(cx, 42, cx + 12, 63, "#C9971F", .8)
        b += path("M%d 62 Q%d 78 %d 62 Z" % (cx - 16, cx, cx + 16), g, "#3A2412", 1.2)
        b += line(cx - 13, 63, cx + 13, 63, "#3A2412", 1.0)
    b += rect(6, 4, 90, 15, "#0B2336", 1, "#FDFBF6", .6)
    b += t(51, 14.4, "THE HAGUE &#183; ICJ", 7.4, "#FDFBF6", 900, "middle", .9)
    b += rect(230, 5, 84, 44, "#9A1B1F", 2, "#FDFBF6", 1.1)
    b += t(272, 22, "GUILTY", 9.4, "#FFFFFF", 900, "middle", 1.2)
    b += t(272, 38, "9&#8211;6 VOTE", 9.4, "#F7E7C2", 900, "middle", .8)
    return svg(W, H, b)


ANT_SERIES = [
    (20, 83.0), (28, 83.0), (36, 99.0), (46, 104.2), (58, 102.6), (70, 108.4), (84, 110.2),
    (96, 111.53), (108, 108.6), (122, 109.4), (134, 105.4), (148, 107.0), (160, 103.1),
    (174, 104.8), (186, 101.4), (200, 103.0), (212, 99.6), (226, 101.2), (238, 98.4),
    (250, 100.0), (262, 97.2), (274, 98.9), (286, 96.5), (296, 98.0), (304, 97.17),
]


def art_anthropic():
    """New York: a bold emerald trading terminal with a crisp round-trip chart."""
    W, H = 322, 102

    def py(p):
        return 90 - (p - 80) / (114 - 80) * 72

    d = ("<defs>"
         + lingrad("anB", [("0", "#061A14", "1"), ("1", "#0C3325", "1")])
         + lingrad("anA", [("0", "#34D399", ".55"), ("1", "#34D399", ".04")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#anB)")
    for p in (85, 90, 95, 100, 105, 110):
        b += line(16, py(p), 306, py(p), "#1E5C44", .7, ' stroke-opacity=".75"')
    dl = "M" + " L".join("%s %s" % (n(x), n(py(p))) for x, p in ANT_SERIES)
    b += path(dl + " L304 92 L20 92 Z", "url(#anA)")
    b += line(16, py(83), 306, py(83), "#F5C542", 1.2, "4 3", ' stroke-opacity=".9"')
    b += path(dl, "none", "#065F46", 4.0, ' stroke-linejoin="round" stroke-linecap="round"')
    b += path(dl, "none", "#6EE7B7", 2.2, ' stroke-linejoin="round" stroke-linecap="round"')
    for x, p in ((20, 83), (96, 111.53), (304, 97.17)):
        b += circle(x, py(p), 4.4, "#052E22", "#6EE7B7", 1.8)
        b += circle(x, py(p), 1.8, "#D1FAE5")
    b += t(16, 14, "ANT &#183; NASDAQ", 9.2, "#ECFDF5", 900, "start", 1.0)
    b += t(16, 28, "+17% DAY ONE", 7.8, "#6EE7B7", 900, "start", .5)
    b += t(102, 16, "$111.53", 8.2, "#D1FAE5", 900, "start", .3)
    b += line(100, 18, 98, py(111.53) - 4, "#6EE7B7", .7)
    b += t(18, 96, "$83", 8.2, "#FDE68A", 900, "start", .2)
    b += line(24, 92, 23, py(83) + 4, "#F5C542", .8)
    b += t(304, 72, "$97.17", 8.2, "#ECFDF5", 900, "end", .2)
    b += line(302, 66, 304, py(97.17) + 5, "#6EE7B7", .8)
    b += rect(236, 2, 78, 32, "#047857", 2, "#D1FAE5", 1.0)
    b += t(275, 20, "$81BN", 12.4, "#FFFFFF", 900, "middle", -.2)
    b += t(275, 29.5, "RECORD IPO", 4.4, "#D1FAE5", 900, "middle", .7)
    return svg(W, H, b)


def art_cop():
    """Antalya: a split graphic - hot globe vs a clean draft that drops fossil fuels."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("cpL", [("0", "#0E7490", "1"), ("1", "#22B8CF", "1")])
         + lingrad("cpD", [("0", "#FFFDF7", "1"), ("1", "#F2E4C6", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cpL)")
    b += circle(38, 29, 19, "#0B4F62", extra=' fill-opacity=".35"')
    b += circle(38, 29, 17, "#5EEAD4", "#083344", 1.2)
    b += path("M22 24 Q30 18 40 21 Q50 24 54 30 Q47 34 39 32 Q30 30 22 24 Z", "#0F766E",
              extra=' fill-opacity=".85"')
    b += path("M28 38 Q36 34 46 37 Q50 40 44 43 Q35 45 28 38 Z", "#0F766E",
              extra=' fill-opacity=".85"')
    b += line(38, 12, 38, 46, "#083344", .6, ' stroke-opacity=".55"')
    b += line(21, 29, 55, 29, "#083344", .6, ' stroke-opacity=".55"')
    b += path("M31 18 Q38 26 45 18", "none", "#083344", .6, ' stroke-opacity=".55"')
    b += path("M31 40 Q38 32 45 40", "none", "#083344", .6, ' stroke-opacity=".55"')
    b += rect(74, 12, 8, 34, "#FDFBF6", 4, "#083344", 1.0)
    b += rect(72, 8, 12, 10, "#FDFBF6", 2, "#083344", 1.0)
    b += rect(75.5, 16, 5, 24, "#DC2626", 2)
    b += circle(78, 46, 5.2, "#DC2626", "#083344", 1.0)
    b += rect(72, 51, 12, 2, "#083344", 1)
    b += rect(94, 0, 96, 58, "#F6EBD2")
    b += rect(94, 0, 1.4, 58, "#1A1F2B")
    b += rect(100, 5, 84, 49, "url(#cpD)", 1, "#1A1F2B", .9)
    b += t(105, 15, "COP31 DRAFT", 6.2, "#9A1B1F", 900, "start", .8)
    b += t(105, 27, "FOSSIL FUELS", 8.2, "#1A1F2B", 900, "start", .4)
    b += line(104, 28.4, 170, 28.4, "#9A1B1F", 2.6)
    b += t(105, 43, "35% BY 2035", 10.4, "#9A1B1F", 900, "start", -.2)
    b += t(105, 52, "CLEAN ELECTRICITY", 4.6, "#2C313A", 700, "start", .5)
    return svg(W, H, b)


def art_cyclone():
    """Odisha: a bold teal coast, a big white Akvan spiral and a crimson track."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("cyO", [("0", "#0E5A73", "1"), ("1", "#083344", "1")])
         + lingrad("cyL", [("0", "#E8D9B5", "1"), ("1", "#B68D4A", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cyO)")
    for x, w in ((84, 22), (118, 16), (158, 20), (24, 12)):
        b += rect(x, 20 + (x % 7), w, .7, "#FFFFFF", extra=' fill-opacity=".4"')
    land = "M0 0 L54 0 Q50 10 43 16 Q35 22 29 30 Q23 38 15 46 Q9 52 5 58 L0 58 Z"
    b += path(land, "url(#cyL)")
    b += path(land, "none", "#FDFBF6", 2.2)
    b += path("M0 0 L42 0 Q38 8 32 13 Q24 19 20 27 Q14 36 10 46 Q7 52 3 58 L0 58 Z",
              "#5E7F3A", extra=' fill-opacity=".88"')
    b += path("M17 0 Q21 18 13 34 Q9 44 15 58", "none", "#2F4A1E", 1.1, ' stroke-opacity=".8"')
    cx, cy = 142, 35
    for rr in (17, 12, 7):
        b += circle(cx, cy, rr, "none", "#FFFFFF", 1.0, ' stroke-opacity=".6" stroke-dasharray="2 3"')
    arms = ""
    for k in range(4):
        a0 = k * math.pi / 2
        pts = [(cx + (2 + i * .9) * math.cos(a0 + i * .24),
                cy + (2 + i * .9) * math.sin(a0 + i * .24)) for i in range(15)]
        arms += path("M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts),
                     "none", "#FFFFFF", 3.0, ' stroke-linecap="round"')
    b += arms + circle(cx, cy, 3.2, "#9A1B1F", "#FFFFFF", 1.0)
    b += path("M184 54 Q166 47 148 44 Q128 40 108 38", "none", "#FDE68A", 2.0, ' stroke-dasharray="4 2"')
    b += poly([(102, 35), (112, 41), (104, 45)], "#9A1B1F", "#FFFFFF", .8)
    b += rect(5, 4, 52, 13, "#FDFBF6", 2, "#083344", .9)
    b += t(31, 13.6, "ODISHA", 7.4, "#083344", 900, "middle", 1.0)
    b += rect(112, 4, 74, 13, "#9A1B1F", 2, "#FDFBF6", .8)
    b += t(149, 13.6, "AKVAN &#183; 300K", 6.4, "#FFFFFF", 900, "middle", .5)
    return svg(W, H, b)


def art_kyiv():
    """Kyiv: gold cathedral domes, big Dutch and Austrian flags, one impact burst."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("kvS", [("0", "#123B5E", "1"), (".62", "#2E6E9E", "1"), ("1", "#D7E8F0", "1")])
         + lingrad("kvD", [("0", "#FFE08A", "1"), ("1", "#C9971F", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#kvS)")
    b += circle(164, 10, 7, "#FFE7A0", extra=' fill-opacity=".35"') + circle(164, 10, 4, "#FFF3C4")
    b += rect(0, 48, W, 10, "#244C36")
    # cathedral
    b += rect(69, 30, 52, 20, "#F7E8C4") + rect(84, 22, 22, 12, "#F7E8C4")
    for cx, cy, r in ((95, 17, 8), (76, 27, 5.5), (114, 27, 5.5)):
        b += rect(cx - r * .7, cy + r * .4, r * 1.4, 30 - cy, "#F7E8C4")
        b += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            n(cx - r), n(cy + r * .5), n(cx - r), n(cy - r), n(cx), n(cy - r * 1.55),
            n(cx + r), n(cy - r), n(cx + r), n(cy + r * .5)), "url(#kvD)", "#3A2412", 1.0)
        b += rect(cx - .5, cy - r * 1.55 - 4.2, 1, 4.2, "#FFE08A")
        b += rect(cx - 1.5, cy - r * 1.55 - 3.0, 3, .8, "#FFE08A")
    b += windows(74, 34, 6, 2, 7, 6, 3, 3, "#6B4A28", 3, .8)
    b += rect(70, 48, 50, 2, "#3A2412")
    # Dutch flag (left) and Austrian flag (right), oversized
    b += rect(11, 7, 2, 40, "#E8D9B5") + circle(12, 6.4, 1.8, "#E8B84B")
    b += rect(13, 8, 36, 7, "#AE1C28") + rect(13, 15, 36, 7, "#FDFBF6") + rect(13, 22, 36, 7, "#21468B")
    b += rect(146, 7, 2, 40, "#E8D9B5") + circle(147, 6.4, 1.8, "#E8B84B")
    b += rect(148, 8, 36, 7, "#C8102E") + rect(148, 15, 36, 7, "#FDFBF6") + rect(148, 22, 36, 7, "#C8102E")
    b += path(burst_d(128, 29, 8.5, .5, 11), "#EA580C", "#3A2412", .8)
    b += path(burst_d(128, 29, 4.6, .6, 9), "#FEF08A")
    b += rect(4, 42, 46, 14, "#9A1B1F", 2, "#FDFBF6", .7)
    b += t(27, 51.8, "KYIV", 7.4, "#FFFFFF", 900, "middle", 1.2)
    return svg(W, H, b)


def art_riyadh():
    """Riyadh: PIF Tower silhouette on a rich dusk-teal sky with a bright hit."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("ryS", [("0", "#082F3A", "1"), (".6", "#0F5C6B", "1"), ("1", "#E9B76B", "1")])
         + lingrad("ryT", [("0", "#16323C", "1"), ("1", "#0A1C24", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#ryS)")
    b += circle(24, 12, 5, "#FFE7A0", extra=' fill-opacity=".55"')
    for x, w, h in ((0, 14, 10), (14, 10, 16), (26, 14, 8), (44, 10, 13), (60, 14, 9),
                    (152, 12, 12), (166, 14, 8), (180, 10, 15)):
        b += rect(x, 50 - h, w, h, "#0A2630", extra=' fill-opacity=".8"')
    b += path("M0 48 Q48 45 96 48 Q146 51 190 47 L190 58 L0 58 Z", "#C98A4B")
    b += path("M0 52 Q48 49 96 52 Q146 55 190 51 L190 58 L0 58 Z", "#8A5A2B")
    # PIF tower
    b += path("M102 50 L105 14 L110 8 L120 6 L126 8 L130 14 L133 50 Z", "url(#ryT)", "#020C10", .9)
    for y in range(17, 48, 5):
        b += line(106, y, 129, y, "#F5C542", .7, ' stroke-opacity=".85"')
    b += line(117, 7, 117, 50, "#7FE3F0", .5, ' stroke-opacity=".55"')
    b += path(burst_d(118, 12, 9.5, .5, 12), "#F97316", "#3A1206", .8)
    b += path(burst_d(118, 12, 5.2, .55, 9), "#FEF08A")
    for cx, cy, r in ((102, 9, 3.6), (96, 6, 2.8), (92, 3, 2)):
        b += circle(cx, cy, r, "#9AA5A8", extra=' fill-opacity=".6"')
    b += path("M148 50 L150 27 Q158 15 166 27 L168 50 Z M153 31 Q158 21 163 31 L163 28 Q158 18 153 28 Z",
              "#16323C", extra=' fill-rule="evenodd"')
    b += rect(5, 4, 53, 13, "#9A1B1F", 2, "#FDFBF6", .8)
    b += t(31, 13.6, "RIYADH", 7.0, "#FFFFFF", 900, "middle", 1.0)
    b += t(6, 54, "PIF TOWER", 5.8, "#FDFBF6", 900, "start", .8)
    return svg(W, H, b)


def art_gta():
    """Worldwide: a saturated Vice sunset, a huge VI emblem and a 99 badge."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("gtS", [("0", "#241046", "1"), (".36", "#7A1F6E", "1"), (".66", "#D93A82", "1"),
                           (".86", "#FF8A4C", "1"), ("1", "#FFD08A", "1")])
         + lingrad("gtSea", [("0", "#5B2A6A", "1"), ("1", "#1A0730", "1")])
         + radgrad("gtSun", [("0", "#FFF4C2", "1"), (".55", "#FFC15E", "1"), ("1", "#FF5E8A", "1")], 112, 31, 17)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#gtS)")
    b += circle(112, 31, 17, "url(#gtSun)")
    for i, y in enumerate((28, 31, 34, 37)):
        b += rect(95, y, 34, 1 + i * .4, "#D93A82", extra=' fill-opacity=".82"')
    for x, w, h in ((0, 12, 10), (12, 9, 16), (22, 13, 8), (36, 8, 13), (46, 11, 9),
                    (146, 10, 14), (157, 13, 9), (171, 8, 16), (180, 9, 11)):
        b += rect(x, 39 - h, w, h, "#2A0C4A")
    b += line(42, 30, 51, 30, "#FF6FE0", .8) + line(154, 28, 163, 28, "#FF6FE0", .8)
    b += rect(0, 39, W, 5, "url(#gtSea)")
    for x, w in ((96, 22), (104, 30), (116, 16), (146, 18)):
        b += rect(x, 41.5, w, .7, "#FFC36B", extra=' fill-opacity=".7"')
    b += rect(0, 44, W, 14, "#12041F")
    b += path("M84 44 L66 58 L73 58 L89 44 Z", "#5B1B78", extra=' fill-opacity=".6"')
    b += path("M92 44 L114 58 L121 58 L98 44 Z", "#5B1B78", extra=' fill-opacity=".6"')
    b += line(88, 44, 74, 58, "#FF3FD8", 1.1) + line(94, 44, 108, 58, "#FF3FD8", 1.1)
    b += palm(24, 58, 40, -3, "#12041F", .75) + palm(34, 58, 27, 2, "#1D0734", .55)
    b += palm(162, 58, 36, 3, "#12041F", .65) + palm(176, 58, 24, 1, "#1D0734", .48)
    b += path("M66 53 L73 48 Q82 46 93 45 L102 42 Q113 39 124 42 L132 45 Q140 47 145 51 L146 53 Z",
              "#05010C")
    b += path("M73 48 Q82 46 93 45 L102 42 Q113 39 124 42 L132 45 Q140 47 145 51", "none", "#FF7BE8", 1.0)
    b += circle(79, 53, 4.0, "#05010C", "#A855F7", 1.0) + circle(79, 53, 1.6, "#A855F7")
    b += circle(135, 53, 4.0, "#05010C", "#A855F7", 1.0) + circle(135, 53, 1.6, "#A855F7")
    b += t(12, 32, "VI", 22, "#FFFFFF", 900, "start", -1.2,
           ' stroke="#FF2D95" stroke-width="1.6" paint-order="stroke"')
    b += rect(140, 3, 46, 26, "#15803D", 2, "#DCFCE7", 1.0)
    b += t(163, 17, "99", 11.6, "#FFFFFF", 900, "middle", -.2)
    b += t(163, 26, "METASCORE", 3.9, "#DCFCE7", 900, "middle", .5)
    return svg(W, H, b)


def art_berlin():
    """Berlin: a dark Brandenburg Gate, big EU/German flags and a two-tone banner."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("brS", [("0", "#A9CBE2", "1"), (".7", "#E8F4FA", "1"), ("1", "#F6EFE0", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#brS)")
    b += circle(164, 8, 5, "#FFE7A0", extra=' fill-opacity=".6"')
    # gate silhouette
    b += rect(56, 18, 78, 5, "#2C313A")
    for x in range(58, 132, 12):
        b += rect(x, 23, 7, 19, "#2C313A") + rect(x + 5, 23, 2, 19, "#56606E")
    b += rect(54, 39, 82, 4, "#2C313A")
    b += path("M70 18 L76 12 L82 15 L88 10 L94 14 L100 10 L106 14 L112 11 L118 16 L122 18 Z",
              "#2C313A")
    for cx in (76, 88, 100, 112):
        b += circle(cx, 10, 2.4, "#2C313A")
    # EU flag, twelve stars
    b += rect(8, 7, 44, 24, "#1B3F94", 1, "#FDFBF6", .8)
    for k in range(12):
        a = -math.pi / 2 + k * math.pi / 6
        b += path(star_d(30 + 8.2 * math.cos(a), 19 + 8.2 * math.sin(a), 2.0), "#F5C542")
    # German flag
    b += rect(138, 7, 44, 24, "#1A1A1A", 1, "#FDFBF6", .8)
    b += rect(138, 15, 44, 8, "#C8102E") + rect(138, 23, 44, 8, "#F5C542")
    # banner
    b += rect(0, 43, 102, 15, "#9A1B1F")
    b += rect(102, 43, 88, 15, "#1A1F2B")
    b += rect(0, 43, 190, 1.4, "#E8B84B")
    b += t(51, 54, "UNITED LINE", 8.0, "#FFFFFF", 900, "middle", .9)
    b += t(146, 54, "BERLIN", 8.8, "#FFFFFF", 900, "middle", 1.1)
    return svg(W, H, b)


def art_kenya():
    """Mrima Hill: bold emerald/terracotta ridges, a crystal and a $60BN+ badge."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("knS", [("0", "#0F3B35", "1"), (".6", "#2F7D5B", "1"), ("1", "#E8B76B", "1")])
         + lingrad("knX", [("0", "#5EEAD4", "1"), ("1", "#0E7490", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#knS)")
    b += circle(168, 10, 6, "#FFE7A0", extra=' fill-opacity=".45"')
    b += path("M0 36 Q30 24 58 32 Q90 41 118 29 Q148 18 190 33 L190 58 L0 58 Z", "#3E8E5A")
    b += path("M0 43 Q36 33 72 41 Q108 50 144 37 Q168 30 190 40 L190 58 L0 58 Z", "#1F5E3C")
    b += path("M0 51 Q44 43 92 49 Q140 56 190 47 L190 58 L0 58 Z", "#B4552F")
    b += path("M0 55 Q44 48 92 53 Q140 58 190 52 L190 58 L0 58 Z", "#8A3A1C")
    # crystal
    b += poly([(52, 15), (68, 27), (62, 49), (44, 49), (36, 27)], "url(#knX)", "#062E38", 1.2)
    b += poly([(52, 15), (52, 49), (44, 49), (36, 27)], "#99F6E4", "#062E38", .8)
    b += poly([(52, 15), (68, 27), (52, 33)], "#22D3EE", "#062E38", .7)
    b += line(52, 15, 52, 49, "#ECFEFF", 1.0, ' stroke-opacity=".9"')
    b += poly([(76, 29), (86, 36), (82, 49), (72, 49), (68, 36)], "#0E7490", "#062E38", 1.0)
    b += rect(4, 4, 72, 13, "#0B2A26", 2, "#FDFBF6", .5)
    b += t(40, 13.6, "MRIMA HILL", 6.8, "#FDFBF6", 900, "middle", .9)
    b += rect(116, 4, 70, 30, "#9A1B1F", 2, "#FDFBF6", 1.0)
    b += t(151, 20, "$60BN+", 11.2, "#FFFFFF", 900, "middle", -.2)
    b += t(151, 29, "NIOBIUM", 4.4, "#F7E7C2", 900, "middle", .7)
    return svg(W, H, b)


def art_tonga():
    """Nuku'alofa: a blazing amber El Nino sun, cracked coral and a Tongan flag."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("tnS", [("0", "#082F49", "1"), (".6", "#0E7490", "1"), ("1", "#67E8F9", "1")])
         + lingrad("tnC", [("0", "#F97316", "1"), ("1", "#9A3412", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#tnS)")
    for k in range(12):
        a = k * math.pi / 6
        b += line(150, 20, 150 + 17 * math.cos(a), 20 + 17 * math.sin(a), "#FCD34D", 1.6,
                  extra=' stroke-opacity=".8"')
    b += circle(150, 20, 14, "#F59E0B", extra=' fill-opacity=".35"')
    b += circle(150, 20, 11, "#FBBF24", "#7C2D12", 1.0)
    b += circle(150, 20, 6.5, "#FEF3C7")
    # cracked coral coast
    b += path("M0 42 Q30 36 62 41 Q96 47 128 42 Q158 38 190 44 L190 58 L0 58 Z", "url(#tnC)")
    b += path("M0 42 Q30 36 62 41 Q96 47 128 42 Q158 38 190 44", "none", "#FED7AA", 1.2)
    for dpath in ("M18 45 L26 50 L23 56", "M54 44 L62 49 L58 56", "M90 46 L98 51 L94 58",
                  "M126 44 L134 49 L130 56", "M160 43 L168 48 L164 56"):
        b += path(dpath, "none", "#7C2D12", 1.1, ' stroke-opacity=".9"')
    # Tongan flag
    b += rect(7, 7, 36, 26, "#C8102E", 1, "#FDFBF6", .8)
    b += rect(7, 7, 16, 13, "#FDFBF6")
    b += rect(13.8, 9, 2.4, 9, "#C8102E") + rect(10.5, 12.2, 9, 2.4, "#C8102E")
    b += t(46, 15, "TONGA", 7.4, "#FFFFFF", 900, "start", 1.0)
    b += t(150, 44, "EL NI&#209;O", 6.0, "#FEF3C7", 900, "middle", .8)
    b += rect(4, 44, 104, 12, "#9A1B1F", 2, "#FDFBF6", .8)
    b += t(56, 53, "27-DAY EMERGENCY", 6.2, "#FFFFFF", 900, "middle", .4)
    return svg(W, H, b)


def art_seoul():
    """Seoul: a bold Taegeukgi, a wooden gavel and an angled OVERTURNED stamp."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("seS", [("0", "#0C2438", "1"), (".6", "#17496B", "1"), ("1", "#2E6E9E", "1")])
         + lingrad("seG", [("0", "#D9A05B", "1"), ("1", "#8A5A2B", "1")])
         + radgrad("seGlow", [("0", "#F5C542", ".38"), ("1", "#F5C542", "0")], 132, 30, 42)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#seS)")
    b += rect(0, 0, W, H, "url(#seGlow)")
    b += circle(172, 8, 5, "#FFE7A0", extra=' fill-opacity=".55"')
    # Taegeukgi
    b += rect(6, 7, 48, 30, "#FDFBF6", 1, "#F5C542", .9)
    b += circle(30, 22, 7.2, "#FDFBF6")
    b += path("M22.8 22 A7.2 7.2 0 0 1 37.2 22 A3.6 3.6 0 0 1 30 22 A3.6 3.6 0 0 0 22.8 22 Z", "#C8102E")
    b += path("M22.8 22 A7.2 7.2 0 0 0 37.2 22 A3.6 3.6 0 0 0 30 22 A3.6 3.6 0 0 1 22.8 22 Z", "#1B3F94")
    for bx, by in ((10, 12), (40, 12), (10, 30), (40, 30)):
        b += rect(bx - 3.6, by - 3.2, 7.2, 1.2, "#1A1A1A")
        b += rect(bx - 3.6, by - 1.1, 7.2, 1.2, "#1A1A1A")
        b += rect(bx - 3.6, by + 1.0, 7.2, 1.2, "#1A1A1A")
    # gavel
    b += line(92, 52, 130, 24, "#5A3518", 6.0, ' stroke-linecap="round"')
    b += line(92, 52, 130, 24, "#C08A4A", 2.0, ' stroke-linecap="round"')
    b += '<g transform="rotate(-42 134 22)">'
    b += rect(119, 13, 30, 18, "url(#seG)", 2, "#3A2412", 1.2)
    b += rect(119, 13, 5, 18, "#E8B84B") + rect(144, 13, 5, 18, "#E8B84B")
    b += '</g>'
    # angled stamp
    b += '<g transform="rotate(-12 145 29)">'
    b += rect(107, 19, 76, 21, "#9A1B1F", 2, "#FDFBF6", 1.0)
    b += t(145, 32.8, "OVERTURNED", 7.2, "#FFFFFF", 900, "middle", .7)
    b += '</g>'
    b += t(6, 55, "SEOUL", 7.2, "#FDE68A", 900, "start", 1.2)
    return svg(W, H, b)


def art_paris():
    """Paris/IEA: a bold red-on-charcoal server-rack energy chart and a padded badge."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("prS", [("0", "#12161C", "1"), ("1", "#2A303A", "1")])
         + lingrad("prBar", [("0", "#F05252", "1"), ("1", "#B91C1C", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#prS)")
    b += line(10, 50, 108, 50, "#C9D1D9", 1.4)
    bars = ((14, 8), (32, 16), (50, 25), (68, 34), (86, 44))
    for i, (x, h) in enumerate(bars):
        y = 50 - h
        b += rect(x, y, 13, h, "url(#prBar)", 1, "#080B0F", 1.0)
        b += rect(x, y, 13, 3.4, "#1A1F2B", 1)
        for yy in range(y + 7, 49, 6):
            b += line(x + 2, yy, x + 11, yy, "#F5C542", .7, ' stroke-opacity=".9"')
        b += circle(x + 10.2, y + 5.2, .9, "#FDE68A")
    b += path("M18 46 L34 38 L52 29 L70 20 L96 8", "none", "#F5C542", 1.8,
              ' stroke-linecap="round" stroke-dasharray="3 2"')
    b += poly([(97, 7), (87, 8), (92, 15)], "#F5C542")
    b += t(21, 56, "2026", 5.2, "#E5E7EB", 900, "middle", .3)
    b += t(92, 56, "2030", 5.2, "#E5E7EB", 900, "middle", .3)
    b += rect(114, 4, 72, 24, "#B91C1C", 2, "#FDFBF6", 1.1)
    b += t(150, 20, "+70% CO&#8322;", 9.4, "#FFFFFF", 900, "middle", -.1)
    b += t(150, 36, "IEA &#183; DATA CENTRES", 5.0, "#E5E7EB", 700, "middle", .4)
    return svg(W, H, b)


# --------------------------------------------------------------- the stories

CARDS = [
    # row 1: three lead stories
    dict(n=1, reg="AP", place="SHENZHEN", beat="SUMMIT", art=art_apec, lon=114.06, lat=22.54, lead=True,
         h="Trump, Xi and Putin hold first three-way summit",
         p="First US&#8211;China&#8211;Russia trilateral at APEC issues a Declaration on Peace on nuclear "
           "risk; Ukraine and Iran omitted.",
         src="BBC &#183; Guardian"),
    dict(n=2, reg="GL", place="THE HAGUE", beat="JUSTICE", art=art_icj, lon=4.30, lat=52.08, lead=True,
         h="World Court convicts Myanmar of Rohingya genocide",
         p="In a landmark 9&#8211;6 verdict, the ICJ becomes the first court to hold a state liable for "
           "genocide, ordering reparations.",
         src="BBC &#183; UN News"),
    dict(n=3, reg="AM", place="NEW YORK", beat="MARKETS", art=art_anthropic, lon=-74.0, lat=40.71, lead=True,
         h="Anthropic jumps 17% in record $81bn Nasdaq debut",
         p="Priced at $83, ticker ANT peaks at $111.53 near a $2tn valuation before closing day one "
           "at $97.17.",
         src="BBC &#183; ABC &#183; DW"),
    # row 2
    dict(n=4, reg="GL", place="ANTALYA", beat="CLIMATE", art=art_cop, lon=30.71, lat=36.90,
         h="COP31 draft drops fossil-fuel phase-out",
         p="Second text strips fossil-fuel wording; 35% clean electricity by 2035.",
         src="Reuters &#183; UN News"),
    dict(n=5, reg="AP", place="ODISHA", beat="STORM", art=art_cyclone, lon=84.90, lat=19.27,
         h="300,000 evacuated ahead of Cyclone Akvan",
         p="India cancels 69 trains across coastal Odisha before Friday&#8217;s landfall.",
         src="TNIE &#183; DW"),
    dict(n=6, reg="EU", place="KYIV", beat="WAR", art=art_kyiv, lon=30.52, lat=50.45,
         h="Drone raid hits Dutch and Austrian embassies",
         p="Strike kills one in Kyiv; two embassies and a cathedral damaged.",
         src="Kyiv Ind. &#183; BBC"),
    dict(n=7, reg="ME", place="RIYADH", beat="GULF", art=art_riyadh, lon=46.68, lat=24.71,
         h="Houthi strike hits Riyadh; PIF tower damaged",
         p="Saudi authorities report damage to the PIF tower, Riyadh&#8217;s tallest, after missile and drone barrage.",
         src="Reuters &#183; Al Jazeera"),
    dict(n=8, reg="GL", place="WORLDWIDE", pin="MIAMI", beat="GAMES", art=art_gta, lon=-80.19, lat=25.76,
         h="GTA VI unlocks globally to 99 Metascore",
         p="After 13 years, launch beats Zelda&#8217;s record with $1.5bn+ in pre-sales.",
         src="BBC &#183; Guardian"),
    # row 3
    dict(n=9, reg="EU", place="BERLIN", beat="EUROPE", art=art_berlin, lon=13.40, lat=52.52,
         h="European allies set united Russia line",
         p="Leaders coordinate terms for talks; Macron urges reopening NATO&#8217;s role.",
         src="DW &#183; France 24"),
    dict(n=10, reg="AF", place="MRIMA HILL", beat="MINERALS", art=art_kenya, lon=39.25, lat=-4.48,
         h="Kenya picks US-led $60bn+ niobium bid",
         p="Frontier Minerals beats seven rivals for the coastal niobium deposit.",
         src="BBC"),
    dict(n=11, reg="OC", place="NUKU&#8216;ALOFA", beat="OCEANIA", art=art_tonga, lon=-175.20, lat=-21.14,
         h="Tonga declares 27-day drought emergency",
         p="Nationwide El Ni&#241;o order covers all islands and territorial waters.",
         src="RNZ Pacific"),
    dict(n=12, reg="AP", place="SEOUL", beat="JUSTICE", art=art_seoul, lon=126.98, lat=37.57,
         h="Korea top court clears ex-PM Han",
         p="Supreme Court overturns Han Duck-soo&#8217;s 15-year martial-law conviction.",
         src="DW"),
    dict(n=13, reg="GL", place="PARIS", beat="ENERGY", art=art_paris, lon=2.35, lat=48.86,
         h="IEA warns datacentre CO2 up 70% by 2030",
         p="Power demand to double on AI growth and fossil plants; IMF sees 4.7%.",
         src="Guardian &#183; Reuters"),
]

DISPATCHES = [
    # 14-23, left column
    ("AF", "SUDAN", "UN reports drone strikes killed 1,630 civilians.", "UN News"),
    ("AF", "SENEGAL", "Faye bypasses MPs on $2.2bn IMF deal.", "Africanews"),
    ("AF", "SOMALIA", "Mogadishu gives UAE envoy 72 hours to leave.", "Reuters"),
    ("AF", "PRETORIA", "South Africa holds policy rate at 7.25%.", "SABC"),
    ("OC", "COOK IS.", "Nassau on alert as Cyclone Xavier slows.", "RNZ"),
    ("OC", "WELLINGTON", "Court: pay-equity law breached rights.", "RNZ"),
    ("OC", "CANBERRA", "Jobless rate hits five-year high of 4.9%.", "ABC"),
    ("AM", "WASHINGTON", "Senate rejects Iran war-powers curb.", "Al Jazeera"),
    ("AM", "HAITI", "Port-au-Prince raid kills 34 gang members.", "Al Jazeera"),
    ("AM", "SACRAMENTO", "California subpoenas Nvidia on China chips.", "BBC"),
    # 24-33, right column
    ("AM", "BOSTON", "Judge blocks trans-care curbs on HIV funds.", "Reuters"),
    ("AM", "BOGOT&#193;", "Colombia unions launch nationwide strike.", "Reuters"),
    ("EU", "COPENHAGEN", "MPs ratify US&#8211;Greenland pact, 109&#8211;0.", "DW"),
    ("EU", "BRUSSELS", "First AI-driven cyberattack hits EU network.", "DW"),
    ("EU", "MOSCOW", "Putin vows &#8216;painful&#8217; reply to bridge strikes.", "BBC"),
    ("AP", "DHAKA", "Yunus home torched before Hasina return.", "DW"),
    ("AP", "PAKISTAN", "Bus hits LPG tanker: 10 dead, 27 hurt.", "Al Jazeera"),
    ("AP", "JAKARTA", "Indonesia passes asset-seizure law at last.", "Kompas"),
    ("ME", "LEBANON", "Israel strikes Hezbollah missile site.", "Al Jazeera"),
    ("GL", "ATHLETICS", "Jepchirchir banned three years.", "BBC"),
]

NUMBERS = [
    ("3", "presidents at one table", "AP"),
    ("9&#8211;6", "World Court genocide vote", "GL"),
    ("$81bn", "Anthropic record IPO", "AM"),
    ("300k", "evacuated in Odisha", "AP"),
    ("109&#8211;0", "Danish Arctic pact vote", "EU"),
    ("99", "GTA VI Metascore", "GL"),
]

DATE_CHECK_1 = (
    "<b>DATE CHECK &#10003;</b> Every story on this page happened, or was first reported, on "
    "<b>Thursday, 19 November 2026 (UTC)</b>."
)
DATE_CHECK_2 = (
    "<b>Left out as other days&#8217; news &#8212; WED 18 NOV:</b> Takaichi&#8211;Putin talks "
    "&#183; Mo&#239;se plot verdict &#183; Gaza &#8216;yellow line&#8217; crossing &#183; "
    "Jeffries 251&#8211;11 &#183; Van Gogh $190.4m &#183; Fed minutes. "
    "<b>FRI 20 NOV:</b> Akvan landfall &#183; UK&#8211;EU summit."
)
SOURCES = (
    "Disputed claims attributed, not stated as fact &#183; Original illustrations and Natural Earth "
    "map drawn in code &#183; Sources: BBC, Reuters, Guardian, DW, Al Jazeera, UN News, ABC, RNZ, "
    "SABC, Kompas, Africanews, Kyiv Independent, TNIE, France 24, IEA"
)

# map badge offsets (px in the 293-wide map) for the thirteen card pins
BADGES = {
    1: (241, 89), 2: (131, 24), 3: (76, 44), 4: (193, 51), 5: (228, 68),
    6: (183, 31), 7: (197, 80), 8: (68, 78), 9: (157, 23), 10: (166, 97),
    11: (16, 116), 12: (263, 66), 13: (136, 54),
}
MAP_W = 293
MAP_SCALE = MAP_W / 1000.0
MAP_H = round(486.99 * MAP_SCALE, 1)
PIN_R = 7.5


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
    b = rect(0, 0, MAP_W, MAP_H, "#DCE9F2")
    for lat in (60, 30, 0, -30):
        y = project(0, lat)[1]
        b += line(0, y, MAP_W, y, "#C4DCE8", .55, "2 3" if lat == 0 else None)
    for lon in (-120, -60, 0, 60, 120):
        x = project(lon, 0)[0]
        b += line(x, 0, x, MAP_H, "#C4DCE8", .45)
    b += ('<g transform="scale(%.5f)"><path d="%s" fill="#E6DCC5" stroke="#B9A883" '
          'stroke-width="2.2" stroke-linejoin="round"/></g>' % (MAP_SCALE, land))
    leaders, dots, badges = "", "", ""
    for c in CARDS:
        _l, fill, ink = REGIONS[c["reg"]]
        x, y = project(c["lon"], c["lat"])
        bx, by = BADGES[c["n"]]
        dx, dy = bx - x, by - y
        dist = math.hypot(dx, dy) or 1
        ex, ey = bx - dx / dist * (PIN_R + 1.8), by - dy / dist * (PIN_R + 1.8)
        leaders += line(x, y, ex, ey, ink, .9, extra=' stroke-opacity=".9"')
        dots += circle(x, y, 2.4, fill, "#FFFFFF", 1, ' class="pin-dot"')
        badges += ('<g class="pin-badge" data-n="%d">' % c["n"]
                   + circle(bx, by, PIN_R, ink, "#FFFFFF", 1.3)
                   + t(bx, by + 3.3, str(c["n"]), 9, "#FFFFFF", 900, "middle")
                   + "</g>")
    b += leaders + dots + badges
    return svg(MAP_W, MAP_H, b, "map-svg")


# --------------------------------------------------------------------- css

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:1024px;height:1024px;overflow:hidden;background:#F6F1E6;}
body{font-family:Lato,sans-serif;color:#141923;-webkit-font-smoothing:antialiased;}
.page{position:relative;width:1024px;height:1024px;overflow:hidden;background:#F6F1E6;}
.toprule{position:absolute;left:16px;right:16px;top:8px;height:2px;background:#9A1B1F;}
.kicker{position:absolute;left:16px;right:16px;top:12px;height:11px;display:flex;
 align-items:center;justify-content:space-between;white-space:nowrap;overflow:hidden;}
.kicker .kl{font-weight:900;font-size:7.5px;letter-spacing:1.7px;color:#9A1B1F;line-height:11px;}
.kicker .kr{font-weight:700;font-size:7.1px;letter-spacing:.7px;color:#4A4438;line-height:11px;}
.masthead{position:absolute;left:16px;right:16px;top:23px;height:59px;font-family:Liberation Serif,DejaVu Serif,Georgia,serif;
 font-weight:700;font-size:54px;line-height:59px;letter-spacing:-1.2px;color:#141923;white-space:nowrap;overflow:hidden;}
.deck{position:absolute;left:16px;right:16px;top:83px;height:16px;font-family:Liberation Serif,DejaVu Serif,Georgia,serif;
 font-style:italic;font-weight:400;font-size:13.3px;line-height:16px;letter-spacing:.05px;color:#9A1B1F;
 white-space:nowrap;overflow:hidden;}
.mastrule{position:absolute;left:16px;right:16px;top:101px;height:1.5px;background:#2C313A;}
.regionbar{position:absolute;left:16px;right:16px;top:105px;height:18px;display:flex;background:#EFE8D8;}
.seg{flex:1 1 0;height:18px;display:flex;align-items:center;justify-content:center;gap:5px;
 border-left:1px solid #C9BFA9;white-space:nowrap;overflow:hidden;}
.seg:first-child{border-left:none;}
.seg i{flex:none;width:6px;height:6px;background:var(--fill);}
.seg .lab{font-weight:700;font-size:7.2px;letter-spacing:.55px;color:#2C313A;line-height:10px;}
.seg .ct{font-weight:900;font-size:8.8px;color:var(--ink);line-height:10px;}
.stats{position:absolute;left:16px;right:16px;top:127px;height:32px;display:flex;background:#EFE8D8;
 border-top:1px solid #C9BFA9;border-bottom:1px solid #C9BFA9;}
.stats .cell{flex:1 1 0;display:flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap;
 border-left:1px solid #C9BFA9;overflow:hidden;}
.stats .cell:first-child{border-left:none;}
.stats .v{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;font-size:15.5px;
 color:var(--ink);line-height:17px;letter-spacing:-.2px;}
.stats .k{font-weight:700;font-size:6.8px;letter-spacing:.45px;text-transform:uppercase;color:#4A4438;line-height:9px;}
.row{position:absolute;left:16px;width:992px;display:grid;}
.r1{top:165px;height:214px;grid-template-columns:repeat(3,324px);column-gap:10px;}
.r2{top:387px;height:133px;grid-template-columns:repeat(5,192px);column-gap:8px;}
.r3{top:524px;height:133px;grid-template-columns:repeat(5,192px);column-gap:8px;}
.card{position:relative;background:#FDFBF6;border:1.25px solid #2C313A;
 display:flex;flex-direction:column;overflow:hidden;}
.art{flex:none;overflow:hidden;border-bottom:1.25px solid #2C313A;background:#FBF7EE;}
.art svg{display:block;width:100%;height:100%;}
.r1 .art{height:102px;}
.r2 .art,.r3 .art{height:58px;}
.body{flex:1;display:flex;flex-direction:column;min-height:0;}
.r1 .body{padding:3px 10px 4px;}
.r2 .body,.r3 .body{padding:2px 7px 2px;}
.kick{display:flex;align-items:center;gap:4px;white-space:nowrap;flex:none;overflow:hidden;}
.badge{flex:none;display:inline-block;background:var(--ink);color:#FFFFFF;font-weight:900;
 text-align:center;border-radius:1px;}
.kick .rgd{flex:none;width:4px;height:4px;background:var(--fill);}
.kick .pl{font-weight:900;color:var(--ink);}
.kick .sep{color:#8A8070;}
.kick .bt{font-weight:700;color:#3A342A;}
.r1 .kick{height:15px;margin-bottom:2px;}
.r1 .badge{width:15px;height:15px;line-height:15px;font-size:9px;}
.r1 .kick .pl,.r1 .kick .bt{font-size:8.2px;letter-spacing:.65px;}
.r1 .kick .sep{font-size:8px;}
.r2 .kick,.r3 .kick{height:11px;margin-bottom:1px;}
.r2 .badge,.r3 .badge{width:11px;height:11px;line-height:11px;font-size:7.4px;}
.r2 .kick .pl,.r2 .kick .bt,.r3 .kick .pl,.r3 .kick .bt{font-size:7.2px;letter-spacing:.35px;}
.r2 .kick .sep,.r3 .kick .sep{font-size:7px;}
.card h2{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;color:#141923;
 overflow:hidden;flex:none;}
.r1 h2{font-size:16.6px;line-height:18.4px;height:36.8px;letter-spacing:-.2px;}
.r2 h2,.r3 h2{font-size:11.7px;line-height:12.4px;height:24.8px;letter-spacing:-.1px;}
.card h2 sub{font-size:.7em;line-height:0;}
.card p{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:400;color:#2C313A;
 overflow:hidden;flex:none;}
.r1 p{margin-top:2px;font-size:9.8px;line-height:12.1px;height:36.3px;}
.r2 p,.r3 p{margin-top:1px;font-size:8.9px;line-height:10.2px;height:20.4px;}
.src{margin-top:auto;border-top:1px solid #E2D8C4;display:flex;justify-content:space-between;
 font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-style:italic;white-space:nowrap;
 flex:none;overflow:hidden;color:#6A6254;}
.r1 .src{font-size:8.2px;line-height:9px;padding-top:2px;}
.r2 .src,.r3 .src{font-size:7.1px;line-height:7.5px;padding-top:1px;}
.src .dt{font-family:Lato,Liberation Sans,sans-serif;font-style:normal;font-weight:700;font-size:6.6px;
 letter-spacing:.35px;color:#6A6254;}
.panel{position:absolute;top:661px;height:298px;background:#FDFBF6;border:1px solid #C9BFA9;
 overflow:hidden;}
.mappanel{left:16px;width:305px;padding:0 4px;display:flex;flex-direction:column;}
.digest{left:329px;width:679px;padding:0 10px;display:flex;flex-direction:column;}
.pcap{height:23px;display:flex;justify-content:space-between;align-items:center;white-space:nowrap;
 border-bottom:1.5px solid #2C313A;overflow:hidden;flex:none;}
.pcap .l{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;font-size:10px;
 letter-spacing:1.25px;color:#141923;}
.pcap .r{font-weight:700;font-size:6.8px;letter-spacing:.45px;color:#6A6254;}
.mapbox{margin-top:6px;width:295px;border:1px solid #B9C9D3;flex:none;}
.map-svg{display:block;width:293px;height:142.7px;}
.legend{margin-top:6px;display:grid;grid-template-columns:1fr 1fr;column-gap:8px;row-gap:0;flex:none;}
.lg{display:flex;align-items:center;gap:4px;height:13px;white-space:nowrap;overflow:hidden;}
.lg i{flex:none;width:5px;height:5px;background:var(--fill);}
.lg .nm{font-weight:700;font-size:7.1px;letter-spacing:.3px;color:#2C313A;line-height:9px;}
.lg .ct{margin-left:auto;font-weight:900;font-size:8px;color:#141923;line-height:9px;}
.mnote{margin-top:auto;border-top:1px solid #E2D8C4;padding-top:4px;font-weight:700;font-size:6.6px;
 letter-spacing:.3px;color:#4A4438;white-space:nowrap;overflow:hidden;flex:none;}
.cols{margin-top:3px;display:flex;gap:14px;flex:1;min-height:0;}
.col{flex:1 1 0;min-width:0;display:flex;flex-direction:column;}
.dl{flex:1 1 0;min-height:0;display:flex;align-items:center;gap:4px;padding:1px 0;
 border-bottom:1px dotted #D8CDB8;overflow:hidden;white-space:nowrap;}
.dl:last-child{border-bottom:none;}
.dl .nb{flex:none;width:16px;height:14px;line-height:14px;text-align:center;font-weight:900;
 font-size:8.6px;color:#FFFFFF;background:var(--ink);border-radius:1px;}
.dl .pl{flex:none;font-weight:900;font-size:9.0px;letter-spacing:.25px;color:var(--ink);line-height:12px;}
.dl .tx{flex:1 1 auto;min-width:0;font-weight:400;font-size:9.9px;line-height:12px;letter-spacing:.02px;
 color:#141923;white-space:nowrap;overflow:hidden;}
.dl .so{flex:none;font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-style:italic;
 font-weight:400;font-size:8.2px;color:#6A6254;line-height:11px;}
.datecheck{position:absolute;left:18px;width:988px;top:961px;height:46px;background:#FDFBF6;
 border:2px solid #9A1B1F;padding:4px 10px 3px;overflow:hidden;}
.datecheck div{white-space:nowrap;overflow:hidden;font-size:9.0px;line-height:14.5px;color:#2C313A;}
.datecheck b{font-weight:900;color:#9A1B1F;}
.footer{position:absolute;left:16px;right:16px;top:1009px;height:10px;font-weight:400;font-size:8px;
 line-height:10px;letter-spacing:.1px;color:#5A5449;white-space:nowrap;overflow:hidden;}
"""


def style_vars(reg):
    _l, fill, ink = REGIONS[reg]
    return "--fill:%s;--ink:%s;" % (fill, ink)


def card_html(c):
    label = REGIONS[c["reg"]][0]
    lead = " lead" if c.get("lead") else ""
    return (
        '<section class="card%s" data-story="c%02d" data-region="%s" style="%s">'
        % (lead, c["n"], c["reg"], style_vars(c["reg"]))
        + '<div class="art">%s</div>' % c["art"]()
        + '<div class="body"><div class="kick"><span class="badge">%d</span>' % c["n"]
        + '<span class="rgd"></span><span class="pl">%s</span><span class="sep">&#183;</span>'
          '<span class="bt">%s</span></div>' % (c["place"], c["beat"])
        + '<h2>%s</h2><p>%s</p>' % (c["h"], c["p"])
        + '<div class="src"><span>%s</span><span class="dt">THU 19 NOV</span></div></div>'
          '</section>' % c["src"]
    )


def dispatch_html(num, d):
    reg, tag, text, src = d
    return ('<div class="dl" data-story="d%02d" data-region="%s" style="%s">'
            '<span class="nb">%d</span><span class="pl">%s</span>'
            '<span class="tx">%s</span><span class="so">%s</span></div>'
            % (num, reg, style_vars(reg), num, tag, text, src))


def build_html():
    counts = region_counts()
    total = sum(counts.values())
    segs = "".join(
        '<div class="seg" data-region="%s" data-count="%d" style="%s"><i></i>'
        '<span class="lab">%s</span><span class="ct">%d</span></div>'
        % (k, counts[k], style_vars(k), REGIONS[k][0], counts[k]) for k in ORDER)
    nums = "".join(
        '<div class="cell" style="%s"><span class="v">%s</span><span class="k">%s</span></div>'
        % (style_vars(r), v, k) for v, k, r in NUMBERS)
    rows = [CARDS[0:3], CARDS[3:8], CARDS[8:13]]
    rows_html = "".join('<div class="row r%d">%s</div>' % (i + 1, "".join(card_html(c) for c in r))
                        for i, r in enumerate(rows))
    legend = "".join(
        '<div class="lg" style="%s"><i></i><span class="nm">%s</span><span class="ct">%d</span></div>'
        % (style_vars(k), REGIONS[k][0], counts[k]) for k in ORDER)
    legend += ('<div class="lg" style="--fill:#141923;--ink:#141923"><i></i>'
               '<span class="nm">ALL STORIES</span><span class="ct">%d</span></div>' % total)
    left = "".join(dispatch_html(14 + i, d) for i, d in enumerate(DISPATCHES[:10]))
    right = "".join(dispatch_html(24 + i, d) for i, d in enumerate(DISPATCHES[10:]))
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Thursday, 19 November 2026 &#183; The World Canvas</title>'
        '<style>' + CSS + '</style></head><body>'
        '<div class="page">'
        '<div class="toprule"></div>'
        '<div class="kicker"><span class="kl">THE WORLD CANVAS &#183; ONE-PAGE EDITION</span>'
        '<span class="kr">%d STORIES &#183; 7 REGIONS &#183; ALL VERIFIED THU 19 NOV 2026</span></div>' % total
        + '<h1 class="masthead">Thursday, 19 November 2026</h1>'
        '<div class="deck">Trump, Xi and Putin share one table at APEC &#183; World Court convicts '
        'Myanmar of Rohingya genocide &#183; Record $81bn Anthropic IPO debuts</div>'
        '<div class="mastrule"></div>'
        '<div class="regionbar">' + segs + '</div>'
        '<div class="stats">' + nums + '</div>'
        + rows_html
        + '<div class="panel mappanel"><div class="pcap"><span class="l">WHERE IT HAPPENED</span>'
          '<span class="r">PINS 1&#8211;13 &#183; ILLUSTRATED</span></div>'
          '<div class="mapbox">' + world_map_svg() + '</div>'
          '<div class="legend">' + legend + '</div>'
          '<div class="mnote">Miller projection &#183; Natural Earth 1:110m &#183; pins 1&#8211;13 = illustrated</div></div>'
        + '<div class="panel digest"><div class="pcap"><span class="l">ALSO ON THURSDAY 19 NOVEMBER 2026</span>'
          '<span class="r">20 VERIFIED DISPATCHES &#183; THU 19 NOV 2026</span></div>'
        + '<div class="cols"><div class="col">' + left + '</div><div class="col">' + right + '</div></div></div>'
        + '<div class="datecheck"><div>' + DATE_CHECK_1 + '</div><div>' + DATE_CHECK_2 + '</div></div>'
        + '<div class="footer">' + SOURCES + '</div>'
        '</div></body></html>'
    )


# --------------------------------------------------------------------- audit

AUDIT_JS = r"""() => {
  const out = {doc:[document.documentElement.scrollWidth, document.documentElement.scrollHeight],
               issues:[], notes:[]};
  const add = (m) => { if (out.issues.length < 160) out.issues.push(m); };
  if (out.doc[0] !== 1024 || out.doc[1] !== 1024) add('document ' + out.doc.join('x'));
  const lab = (el) => { const s = el.closest('[data-story]'); return (s ? s.dataset.story + ' ' : '') +
      el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className : '')
      + ' "' + (el.textContent || '').trim().slice(0, 28) + '"'; };
  const R = (el) => el.getBoundingClientRect();
  const inter = (a, b, tol) => !(a.right <= b.left + tol || b.right <= a.left + tol ||
      a.bottom <= b.top + tol || b.bottom <= a.top + tol);

  // census and exact region sums
  const stories = [...document.querySelectorAll('[data-story]')];
  const seen = {};
  stories.forEach(el => { seen[el.dataset.story] = (seen[el.dataset.story]||0)+1; });
  out.ids = Object.keys(seen).sort();
  Object.keys(seen).filter(k => seen[k] > 1).forEach(k => add('duplicate id ' + k));
  const counts = {};
  stories.forEach(el => {
    const r = el.dataset.region;
    if (!r) add('missing region ' + el.dataset.story);
    counts[r] = (counts[r]||0) + 1;
  });
  out.total = stories.length;
  let sum = 0; Object.values(counts).forEach(v => sum += v);
  if (sum !== 33) add('story total ' + sum);
  let barSum = 0;
  document.querySelectorAll('.seg').forEach(s => {
    const r = s.dataset.region, c = +s.dataset.count; barSum += c;
    if (counts[r] !== c) add('region ' + r + ' bar ' + c + ' actual ' + (counts[r]||0));
  });
  if (barSum !== 33) add('bar total ' + barSum);
  out.badges = document.querySelectorAll('.pin-badge').length;
  if (out.badges !== 13) add('map badges ' + out.badges);

  // overflow / clipped text on every text container
  document.querySelectorAll('.masthead,.deck,.kicker span,.seg,.stats .cell,.kick,.card h2,.card p,.src,' +
      '.pcap,.lg,.dl,.dl .pl,.dl .tx,.dl .so,.datecheck div,.footer,.panel,.card,.art,.mapbox,.mnote').forEach(el => {
    if (el.scrollWidth - el.clientWidth > 0.5) add('overflow-x ' + lab(el) + ' +' + (el.scrollWidth - el.clientWidth));
    if (el.scrollHeight - el.clientHeight > 0.5) add('overflow-y ' + lab(el) + ' +' + (el.scrollHeight - el.clientHeight));
  });
  const lines = (el) => { const r = document.createRange(); r.selectNodeContents(el);
      const ys = new Set(); [...r.getClientRects()].forEach(q => { if (q.width > 1) ys.add(Math.round(q.top)); });
      return ys.size; };
  document.querySelectorAll('.card').forEach(c => {
    const h = c.querySelector('h2'), p = c.querySelector('p');
    const lh = lines(h), lp = lines(p);
    const maxP = 2;
    out.notes.push(c.dataset.story + ' h' + lh + ' p' + lp);
    if (lh < 1 || lh > 2) add('headline lines ' + c.dataset.story + ' (' + lh + ')');
    if (lp > maxP) add('summary >' + maxP + ' lines ' + c.dataset.story + ' (' + lp + ')');
    if (lp < 1) add('summary empty ' + c.dataset.story);
  });
  document.querySelectorAll('.dl').forEach(d => {
    const tx = d.querySelector('.tx'), so = d.querySelector('.so'), pl = d.querySelector('.pl');
    if (lines(tx) !== 1) add('dispatch wraps ' + d.dataset.story);
    const tr = document.createRange(); tr.selectNodeContents(tx);
    const textR = tr.getBoundingClientRect(), boxR = R(tx);
    const slack = boxR.right - textR.right;
    if (slack < 15) add('dispatch slack ' + d.dataset.story + ' ' + slack.toFixed(1));
    if (textR.left < boxR.left - 0.5) add('dispatch text left ' + d.dataset.story);
    if (R(so).left - R(pl).right < 2) add('dispatch source touches place ' + d.dataset.story);
    out.notes.push(d.dataset.story + ' slack ' + Math.round(slack));
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
  sib('.row'); sib('.cols'); sib('.col'); sib('.legend'); sib('.regionbar'); sib('.stats');
  sib('.body'); sib('.kick'); sib('.dl'); sib('.kicker'); sib('.datecheck');
  const secs = ['.toprule','.kicker','.masthead','.deck','.mastrule','.regionbar','.stats','.r1','.r2','.r3',
                '.mappanel','.digest','.datecheck','.footer'].map(s => [s, R(document.querySelector(s))]);
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
    // coloured badge text must sit at least 1px inside its badge rectangle
    const badgeCols = new Set(['#9a1b1f', '#b91c1c', '#047857', '#15803d', '#0b5c3b']);
    const mapB = (b) => ({left: sb.left + b.x / vb.width * sb.width,
      right: sb.left + (b.x + b.width) / vb.width * sb.width,
      top: sb.top + b.y / vb.height * sb.height,
      bottom: sb.top + (b.y + b.height) / vb.height * sb.height});
    const badgeRects = [...s.querySelectorAll('rect')]
      .filter(r => badgeCols.has((r.getAttribute('fill') || '').toLowerCase()))
      .map(r => mapB(r.getBBox()));
    texts.forEach(tx => { const b = mapB(tx.getBBox());
      const cx = (b.left + b.right) / 2, cy = (b.top + b.bottom) / 2;
      badgeRects.forEach(r => {
        if (cx > r.left && cx < r.right && cy > r.top && cy < r.bottom) {
          const pad = Math.min(b.left - r.left, r.right - b.right, b.top - r.top, r.bottom - b.bottom);
          if (pad < 1) add('svg' + i + ' badge text clipped "' + tx.textContent + '" ' + pad.toFixed(1));
        }
      });
    });
  });
  // map badges: no two badges overlap, no badge covers a foreign pin dot
  const badges = [...document.querySelectorAll('.pin-badge')].map(g => [g.dataset.n, R(g.querySelector('circle'))]);
  const dots = [...document.querySelectorAll('.pin-dot')].map(d => R(d));
  for (let a = 0; a < badges.length; a++) {
    for (let b = a + 1; b < badges.length; b++) if (inter(badges[a][1], badges[b][1], -1.5))
      add('map badges crowd ' + badges[a][0] + ' x ' + badges[b][0]);
    dots.forEach((d, k) => { if (inter(badges[a][1], d, 0)) add('badge ' + badges[a][0] + ' covers dot ' + (k+1)); });
  }

  // contrast
  const parse = (s) => s.match(/[\d.]+/g).slice(0, 4).map(Number);
  const lum = (c) => { const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = Math.max(lum(a), lum(b)), y = Math.min(lum(a), lum(b)); return (x + .05) / (y + .05); };
  const bgOf = (el) => { let n = el; while (n) { const c = parse(getComputedStyle(n).backgroundColor);
      if (c.length < 4 || c[3] > 0) { if (c.length < 4 || c[3] === 1) return c.slice(0, 3); }
      n = n.parentElement; } return [246, 241, 230]; };
  const floor = (sel, min) => document.querySelectorAll(sel).forEach(el => {
    const r = ratio(parse(getComputedStyle(el).color).slice(0, 3), bgOf(el));
    if (r < min) add('contrast ' + lab(el) + ' ' + r.toFixed(2));
  });
  floor('.card h2,.card p,.dl .tx,.masthead,.deck,.seg .lab,.stats .k,.lg .ct,.lg .nm,.mnote,.footer', 6.5);
  floor('.kick .pl,.kick .bt,.src,.dl .pl,.dl .so,.stats .v,.pcap .l,.pcap .r,.badge,.dl .nb,.seg .ct,' +
        '.datecheck div,.datecheck b', 4.5);
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
    expect = {"c%02d" % c["n"] for c in CARDS} | {"d%02d" % (14 + i) for i in range(len(DISPATCHES))}
    assert len(expect) == 33, len(expect)
    counts = region_counts()
    assert sum(counts.values()) == 33, counts
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    audit = render(sorted(expect))

    missing = sorted(expect - set(audit["ids"]))
    extra = sorted(set(audit["ids"]) - expect)
    print("AUDIT doc=%s stories=%d/%d badges=%d region_sum=%d repeat_identical=%s"
          % (audit["doc"], len(audit["ids"]), len(expect), audit["badges"],
             sum(region_counts().values()), audit["repeat_identical"]))
    slack = [x for x in audit["notes"] if " slack " in x]
    tight = sorted(slack, key=lambda s: int(s.split()[-1]))[:5]
    print("  tightest dispatch slack (px):", ", ".join(tight))
    print("  card lines:", " | ".join(x for x in audit["notes"] if " slack " not in x))
    for issue in audit["issues"]:
        print("  ISSUE", issue)
    assert not missing and not extra, ("census", missing, extra)
    assert not audit["issues"], "layout audit reported %d issues" % len(audit["issues"])
    assert sum(region_counts().values()) == 33

    from PIL import Image
    raw1, raw2 = RAW_1X.read_bytes(), RAW_2X.read_bytes()
    assert png_size(raw1) == (1024, 1024) and png_size(raw2) == (2048, 2048)
    native = Image.open(io.BytesIO(raw1)).convert("RGB")
    down = Image.open(io.BytesIO(raw2)).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    box = (340, 684, 1000, 952)  # the two dispatch columns
    sn, sd = sharpness(native, box), sharpness(down, box)
    print("dispatch edge variance: native 1x %.1f | 2x->Lanczos %.1f" % (sn, sd))
    chosen, mode = (down, "2x supersampled -> Lanczos") if sd >= sn else (native, "native 1x")
    if chosen is native:
        boxes = [tuple(b) for b in audit["art_boxes"]]
        assert len(boxes) == 14, boxes
        for b in boxes:
            chosen.paste(down.crop(b), b[:2])
        mode += " text + 2x Lanczos in %d illustration/map boxes" % len(boxes)

    quality, data = encode_jpeg(chosen)
    assert data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
    assert len(data) < HARD_LIMIT
    ENTRY.write_bytes(data)
    final = Image.open(io.BytesIO(data)).convert("RGB")
    final.resize((300, 300), Image.LANCZOS).save(PREVIEW_300)
    final.resize((512, 512), Image.LANCZOS).save(PREVIEW_512)
    print("entry.png: 1024x1024 JPEG q%d 4:4:4 via %s, %d bytes (%.1f KiB)"
          % (quality, mode, len(data), len(data) / 1024))


if __name__ == "__main__":
    main()
