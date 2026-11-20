#!/usr/bin/env python3
"""Build the 1024x1024 visual front page for Thursday 19 November 2026 (entry.png), v15.

A bold one-day front page on warm cream newsprint: a centred serif masthead
naming the date, an italic deck with the three lead stories, a seven-region
colour strip, three large lead illustrations, ten illustrated secondary cards
(two rows of five), a Natural Earth locator with numbered pins, and six short
two-line briefs. Nineteen stories in all, every one an event of that Thursday.
No micro-text: HTML text is at least 10px and SVG labels at least 9px.

The page is rendered in headless Chromium at 1x and 2x device scale. The same
pass runs a strict DOM audit (exact size, 19/19 story census, exact region
sums, 18 map pins, no overflow, no overlaps, no clipped text, line limits,
minimum font sizes, SVG ink inside every viewBox and an ink-contrast floor);
the build fails on any issue. Text comes from native 1x text; the 2x Lanczos
pixels are pasted into the fourteen integer-aligned illustration and map
boxes. The result is a 4:4:4 baseline JPEG.

Build-time tooling only (Playwright + Pillow). The shipped runtime (main.py) is
standard library only. Everything rendered is local: system Liberation Serif /
Lato, inline SVG and the Natural Earth 1:110m outline in world_land_110m.svgpath.
"""

import io
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "entry.png"
WORLD_PATH = ROOT / "world_land_110m.svgpath"
HTML_PATH = Path("/tmp/world_news_canvas_v15.html")
RAW_1X = Path("/tmp/world_news_canvas_v15_1x.png")
RAW_2X = Path("/tmp/world_news_canvas_v15_2x.png")
PREVIEW_300 = Path("/tmp/news_v15_300.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITIES = (91, 90, 89, 88, 87)
JPEG_MAX = 440 * 1000
HARD_LIMIT = 1048576

N_STORIES = 19

# key: (label, fill, ink) - muted archival region inks, used for chips and pins
REGIONS = {
    "AP": ("ASIA-PACIFIC", "#5B3F80", "#4F366F"),
    "AM": ("AMERICAS", "#8C2F39", "#7A2730"),
    "EU": ("EUROPE", "#1F4E79", "#1B4467"),
    "ME": ("MIDDLE EAST", "#12606F", "#0F5360"),
    "AF": ("AFRICA", "#8A4A12", "#783F0F"),
    "OC": ("OCEANIA", "#8F2F55", "#7C2849"),
    "GL": ("GLOBAL", "#2A5F45", "#24523B"),
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




# ------------------------------------------------------- v15 large editorial art
# Lead boxes are 322x150, secondary boxes 190x96, both drawn 1:1 in user units.
# Every picture has one focal object, one or two padded labels at 10px or more,
# and nothing that needs reading at small size to make sense.

LW, LH = 322, 150
SW, SH = 190, 96


def chip(x, y, w, h, label, size, fill="#9A1B1F", ink="#FFFFFF", ls=1.0, border="#FDFBF6"):
    return (rect(x, y, w, h, fill, 2, border, .9)
            + t(x + w / 2.0, y + h / 2.0 + size * 0.36, label, size, ink, 900, "middle", ls))


def art_apec():
    """Shenzhen: the summit table under large US, Chinese and Russian flags."""
    W, H = LW, LH
    d = ("<defs>"
         + lingrad("apSky", [("0", "#082743", "1"), (".6", "#14507E", "1"), ("1", "#3A8FBE", "1")])
         + lingrad("apSea", [("0", "#1D6E92", "1"), ("1", "#0B3B55", "1")])
         + lingrad("apT", [("0", "#F8E9C8", "1"), ("1", "#D9BE8A", "1")])
         + fold_shade("FUF") + fold_shade("FCF") + fold_shade("FRF")
         + "</defs>")
    b = d + rect(0, 0, W, 110, "url(#apSky)")
    b += circle(296, 56, 22, "#FFD36B", extra=' fill-opacity=".25"') + circle(296, 56, 11, "#FFE7A0")
    for x, w, h in ((0, 20, 26), (20, 14, 44), (34, 18, 30), (112, 12, 36), (124, 10, 50),
                    (196, 18, 34), (212, 12, 52), (224, 18, 28), (246, 12, 40), (300, 12, 30), (312, 10, 22)):
        b += rect(x, 110 - h, w, h, "#082743", extra=' fill-opacity=".85"')
    b += rect(0, 110, W, 9, "url(#apSea)")
    for x, w in ((14, 22), (60, 16), (100, 30), (160, 18), (210, 24), (264, 16), (296, 20)):
        b += rect(x, 112 + (x % 3), w, 1, "#FFFFFF", extra=' fill-opacity=".5"')
    b += rect(0, 119, W, 31, "#E8D2A8")
    b += poly([(28, 119), (294, 119), (310, 133), (12, 133)], "url(#apT)")
    b += rect(12, 133, 298, 17, "#6E4A2C")
    b += rect(22, 137, 278, 6, "#9A1B1F")
    for px, fn, cid in ((38, flag_us, "FU"), (138, flag_cn, "FC"), (238, flag_ru, "FR")):
        b += rect(px - 1.2, 30, 2.4, 90, "#D8C7A2")
        b += circle(px, 29.5, 3, "#E8B84B", "#3A2A16", .6)
        b += pole_flag(px, 30, 66, 40, fn, cid, 1.6)
    for cx, lab in ((72, "TRUMP"), (172, "XI"), (272, "PUTIN")):
        b += rect(cx - 38, 86, 76, 21, "#FDFBF6", 2, "#1A1F2B", 1.0)
        b += t(cx, 101, lab, 12.5, "#1A1F2B", 900, "middle", 1.2)
    b += rect(0, 0, W, 24, "#9A1B1F") + rect(0, 24, W, 2, "#E8B84B")
    b += t(10, 16.5, "APEC &#183; SHENZHEN", 11.5, "#FFFFFF", 900, "start", 1.1)
    b += t(312, 16.5, "FIRST 3-WAY SUMMIT", 10.5, "#F7E7C2", 900, "end", .8)
    return svg(W, H, b)


def art_icj():
    """The Hague: Peace Palace, oversized gold scales and a GENOCIDE 9-6 stamp."""
    W, H = LW, LH
    d = ("<defs>"
         + lingrad("icS", [("0", "#0D304C", "1"), (".55", "#2A658E", "1"), ("1", "#C8E1ED", "1")])
         + lingrad("icL", [("0", "#F7E8C4", "1"), ("1", "#D6B87F", "1")])
         + lingrad("icR", [("0", "#8E3A28", "1"), ("1", "#5E2418", "1")])
         + lingrad("icG", [("0", "#FFE08A", "1"), ("1", "#B8861E", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#icS)")
    b += circle(150, 24, 16, "#FFE7A0", extra=' fill-opacity=".22"') + circle(150, 24, 8, "#FFF3C4")
    b += rect(0, 122, W, 28, "#244C36") + rect(0, 122, W, 2.5, "#7FA36B")
    # palace: long limestone wing with a red-roofed clock tower
    b += rect(112, 76, 200, 48, "url(#icL)") + rect(112, 76, 200, 4, "#B68D4A")
    b += poly([(108, 77), (210, 60), (316, 77)], "url(#icR)")
    b += rect(176, 34, 40, 90, "#F7E8C4") + rect(176, 34, 40, 4, "#B68D4A")
    b += poly([(172, 35), (196, 8), (220, 35)], "url(#icR)")
    b += rect(194, 3, 4, 7, "#C9971F")
    b += circle(196, 48, 7, "#FDFBF6", "#6B4A28", 1.2) + line(196, 48, 196, 43.5, "#3A2412", 1.2) \
        + line(196, 48, 199.5, 49.5, "#3A2412", 1.2)
    for x in range(120, 172, 13):
        b += rect(x, 86, 7, 36, "#E7CD9C") + rect(x + 6, 86, 1.6, 36, "#B68D4A")
    for x in range(224, 306, 13):
        b += rect(x, 86, 7, 36, "#E7CD9C") + rect(x + 6, 86, 1.6, 36, "#B68D4A")
    b += windows(122, 92, 4, 3, 13, 10, 4, 5, "#6B4A28", 3, .75)
    b += windows(226, 92, 6, 3, 13, 10, 4, 5, "#6B4A28", 9, .75)
    b += windows(183, 62, 3, 5, 10, 11, 4, 5, "#6B4A28", 5, .8)
    # oversized gold scales in front
    g = "url(#icG)"
    b += rect(28, 128, 90, 8, "#8E2F39", 1, "#3A2412", .9)
    b += rect(70, 54, 6, 74, g, 0, "#3A2412", 1.2)
    b += circle(73, 50, 6, g, "#3A2412", 1.2)
    b += rect(16, 58, 114, 6, g, 1, "#3A2412", 1.2)
    for cx in (24, 122):
        for sx in (-16, 16):
            b += line(cx, 64, cx + sx, 96, "#3A2412", 1.8) + line(cx, 64, cx + sx, 96, "#C9971F", .9)
        b += path("M%d 95 Q%d 116 %d 95 Z" % (cx - 21, cx, cx + 21), g, "#3A2412", 1.3)
    b += chip(8, 8, 122, 21, "ICJ &#183; THE HAGUE", 10.5, "#0B2336", "#FDFBF6", 1.0)
    b += '<g transform="rotate(-3 262 112)">'
    b += rect(206, 89, 112, 47, "#9A1B1F", 2, "#FDFBF6", 1.4)
    b += t(262, 108, "GENOCIDE", 15, "#FFFFFF", 900, "middle", 1.4)
    b += t(262, 130, "RULING 9&#8211;6", 11, "#F7E7C2", 900, "middle", .9)
    b += '</g>'
    return svg(W, H, b)


ANT_SERIES = [
    (20, 83.0), (92, 83.0), (96, 111.5), (110, 108.0), (122, 109.4), (136, 106.2),
    (148, 107.6), (162, 104.4), (174, 105.7), (188, 102.2), (200, 103.5), (214, 100.6),
    (226, 101.9), (240, 99.2), (252, 100.4), (266, 97.8), (278, 99.0), (290, 96.7),
    (298, 97.8), (304, 97.17),
]


def art_anthropic():
    """New York: an emerald terminal - $83 IPO, a $111.50 open and a $97.17 close."""
    W, H = LW, LH

    def py(p):
        return 136 - (p - 80) / (116 - 80) * 100

    base = py(83)
    d = ("<defs>"
         + lingrad("anB", [("0", "#061A14", "1"), ("1", "#0C3325", "1")])
         + lingrad("anA", [("0", "#34D399", ".55"), ("1", "#34D399", ".04")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#anB)")
    for p in (85, 90, 95, 100, 105, 110, 115):
        b += line(14, py(p), 308, py(p), "#1E5C44", .8, extra=' stroke-opacity=".75"')
    dl = "M" + " L".join("%s %s" % (n(x), n(py(p))) for x, p in ANT_SERIES)
    b += path(dl + " L304 %s L96 %s Z" % (n(base), n(base)), "url(#anA)")
    b += line(14, base, 308, base, "#F5C542", 1.4, "5 3", ' stroke-opacity=".9"')
    b += path(dl, "none", "#065F46", 5.0, ' stroke-linejoin="round" stroke-linecap="round"')
    b += path(dl, "none", "#6EE7B7", 2.8, ' stroke-linejoin="round" stroke-linecap="round"')
    for x, p in ((20, 83), (96, 111.5), (304, 97.17)):
        b += circle(x, py(p), 5.2, "#052E22", "#6EE7B7", 2.0) + circle(x, py(p), 2.1, "#D1FAE5")
    b += t(14, 20, "ANT &#183; NASDAQ", 13, "#ECFDF5", 900, "start", 1.0)
    b += t(14, 37, "+17% DAY ONE", 12, "#6EE7B7", 900, "start", .5)
    b += t(108, 52, "OPEN $111.50", 11, "#D1FAE5", 900, "start", .3)
    b += t(14, 146, "IPO PRICE $83", 11, "#FDE68A", 900, "start", .3)
    b += t(310, 75, "CLOSE $97.17", 11, "#ECFDF5", 900, "end", .3)
    b += rect(220, 6, 96, 44, "#047857", 2, "#D1FAE5", 1.1)
    b += t(268, 30, "$81BN", 20, "#FFFFFF", 900, "middle", -.2)
    b += t(268, 44, "RECORD IPO", 9.5, "#D1FAE5", 900, "middle", .8)
    return svg(W, H, b)


def art_cop():
    """Antalya: a warming globe and a COP31 draft with fossil fuels struck out."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("cpL", [("0", "#0E7490", "1"), ("1", "#22B8CF", "1")])
         + lingrad("cpD", [("0", "#FFFDF7", "1"), ("1", "#F2E4C6", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cpL)")
    cx, cy, r = 32, 50, 24
    b += circle(cx, cy, r + 3, "#0B4F62", extra=' fill-opacity=".35"')
    b += circle(cx, cy, r, "#5EEAD4", "#083344", 1.3)
    b += path("M12 42 Q22 33 34 37 Q46 41 52 50 Q42 55 32 52 Q20 49 12 42 Z", "#0F766E")
    b += path("M18 62 Q28 57 40 61 Q46 65 38 69 Q27 71 18 62 Z", "#0F766E")
    b += line(cx, cy - r, cx, cy + r, "#083344", .7, extra=' stroke-opacity=".5"')
    b += line(cx - r, cy, cx + r, cy, "#083344", .7, extra=' stroke-opacity=".5"')
    b += rect(62, 18, 10, 56, "#FDFBF6", 5, "#083344", 1.1)
    b += rect(64.5, 34, 5, 38, "#DC2626", 2)
    b += circle(67, 76, 8, "#DC2626", "#083344", 1.1)
    b += rect(80, 0, 110, 96, "#F6EBD2") + rect(80, 0, 1.5, 96, "#1A1F2B")
    b += rect(86, 6, 98, 84, "url(#cpD)", 1, "#1A1F2B", 1.0)
    b += t(92, 22, "COP31 DRAFT", 10, "#9A1B1F", 900, "start", .8)
    b += t(92, 41, "FOSSIL FUELS", 12, "#1A1F2B", 900, "start", .2)
    b += t(92, 58, "PHASE-OUT", 12, "#1A1F2B", 900, "start", .4)
    b += line(90, 37, 180, 37, "#9A1B1F", 2.6) + line(90, 54, 160, 54, "#9A1B1F", 2.6)
    b += t(92, 81, "35% BY 2035", 13, "#9A1B1F", 900, "start", -.2)
    return svg(W, H, b)


def art_cyclone():
    """Odisha: the coast, a big white Akvan spiral and a crimson track."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("cyO", [("0", "#0E5A73", "1"), ("1", "#083344", "1")])
         + lingrad("cyL", [("0", "#E8D9B5", "1"), ("1", "#B68D4A", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cyO)")
    for x, y, w in ((84, 30, 22), (150, 78, 16), (70, 60, 20), (166, 20, 12)):
        b += rect(x, y, w, .8, "#FFFFFF", extra=' fill-opacity=".4"')
    land = "M0 0 L60 0 Q56 16 48 26 Q38 38 31 50 Q24 64 15 78 Q9 88 6 96 L0 96 Z"
    b += path(land, "url(#cyL)") + path(land, "none", "#FDFBF6", 2.4)
    b += path("M0 0 L47 0 Q43 13 36 22 Q27 32 22 45 Q15 60 10 76 Q6 88 3 96 L0 96 Z", "#5E7F3A")
    cx, cy = 128, 42
    for rr in (27, 19, 11):
        b += circle(cx, cy, rr, "none", "#FFFFFF", 1.1, ' stroke-opacity=".55" stroke-dasharray="2 3"')
    for k in range(4):
        a0 = k * math.pi / 2
        pts = [(cx + (3 + i * 1.45) * math.cos(a0 + i * .24),
                cy + (3 + i * 1.45) * math.sin(a0 + i * .24)) for i in range(15)]
        b += path("M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts),
                  "none", "#FFFFFF", 4.2, ' stroke-linecap="round"')
    b += circle(cx, cy, 4.5, "#9A1B1F", "#FFFFFF", 1.2)
    b += path("M186 66 Q160 62 138 58 Q100 50 74 44", "none", "#FDE68A", 2.2, ' stroke-dasharray="5 3"')
    b += poly([(66, 41), (78, 39), (74, 50)], "#FDE68A", "#083344", .8)
    b += chip(4, 4, 62, 19, "ODISHA", 11, "#FDFBF6", "#083344", 1.0, "#083344")
    b += chip(72, 74, 114, 18, "300,000 EVACUATED", 10, "#9A1B1F", "#FFFFFF", .3)
    return svg(W, H, b)


def art_kyiv():
    """Kyiv: gold domes, the Dutch and Austrian flags and one impact burst."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("kvS", [("0", "#123B5E", "1"), (".62", "#2E6E9E", "1"), ("1", "#D7E8F0", "1")])
         + lingrad("kvD", [("0", "#FFE08A", "1"), ("1", "#C9971F", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#kvS)")
    b += rect(0, 82, W, 14, "#244C36")
    b += rect(66, 52, 56, 32, "#F7E8C4") + rect(82, 40, 24, 16, "#F7E8C4")
    for cx, cy, r in ((94, 32, 11), (72, 48, 7), (116, 48, 7)):
        b += rect(cx - r * .7, cy + r * .4, r * 1.4, 54 - cy, "#F7E8C4")
        b += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            n(cx - r), n(cy + r * .5), n(cx - r), n(cy - r), n(cx), n(cy - r * 1.55),
            n(cx + r), n(cy - r), n(cx + r), n(cy + r * .5)), "url(#kvD)", "#3A2412", 1.0)
        b += rect(cx - .6, cy - r * 1.55 - 5, 1.2, 5, "#FFE08A")
        b += rect(cx - 2, cy - r * 1.55 - 3.6, 4, 1, "#FFE08A")
    b += windows(71, 60, 6, 2, 8, 9, 3.5, 5, "#6B4A28", 3, .85)
    b += rect(66, 82, 56, 2, "#3A2412")
    b += rect(8, 8, 2.4, 76, "#E8D9B5") + circle(9.2, 7.5, 2.2, "#E8B84B")
    b += rect(10.4, 9, 44, 10, "#AE1C28") + rect(10.4, 19, 44, 10, "#FDFBF6") + rect(10.4, 29, 44, 10, "#21468B")
    b += rect(134, 8, 2.4, 76, "#E8D9B5") + circle(135.2, 7.5, 2.2, "#E8B84B")
    b += rect(136.4, 9, 44, 10, "#C8102E") + rect(136.4, 19, 44, 10, "#FDFBF6") + rect(136.4, 29, 44, 10, "#C8102E")
    b += chip(13, 43, 38, 15, "NL", 9.5, "#1A1F2B", "#FFFFFF", .8)
    b += chip(139, 43, 38, 15, "AT", 9.5, "#1A1F2B", "#FFFFFF", .8)
    b += path(burst_d(158, 70, 13, .5, 11), "#EA580C", "#3A2412", .9)
    b += path(burst_d(158, 70, 7, .6, 9), "#FEF08A")
    b += chip(14, 66, 46, 18, "KYIV", 11, "#9A1B1F", "#FFFFFF", 1.2)
    return svg(W, H, b)


def art_riyadh():
    """Riyadh: the PIF Tower on a dusk sky with a bright hit near the top."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("ryS", [("0", "#082F3A", "1"), (".6", "#0F5C6B", "1"), ("1", "#E9B76B", "1")])
         + lingrad("ryT", [("0", "#16323C", "1"), ("1", "#0A1C24", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#ryS)")
    for x, w, h in ((0, 14, 14), (14, 10, 24), (26, 14, 12), (44, 12, 20), (62, 14, 14),
                    (178, 12, 18)):
        b += rect(x, 84 - h, w, h, "#0A2630", extra=' fill-opacity=".85"')
    b += path("M0 82 Q48 78 96 82 Q146 86 190 80 L190 96 L0 96 Z", "#C98A4B")
    b += path("M0 88 Q48 84 96 88 Q146 92 190 86 L190 96 L0 96 Z", "#8A5A2B")
    b += path("M100 84 L104 26 L110 16 L122 13 L128 16 L134 26 L138 84 Z", "url(#ryT)", "#020C10", 1.0)
    for y in range(30, 82, 6):
        b += line(105, y, 133, y, "#F5C542", .8, extra=' stroke-opacity=".85"')
    b += path(burst_d(119, 22, 15, .5, 12), "#F97316", "#3A1206", .9)
    b += path(burst_d(119, 22, 8, .55, 9), "#FEF08A")
    for cx, cy, r in ((100, 14, 5), (92, 9, 4), (86, 5, 3)):
        b += circle(cx, cy, r, "#9AA5A8", extra=' fill-opacity=".6"')
    b += path("M150 84 L153 46 Q164 28 175 46 L178 84 Z M157 52 Q164 38 171 52 L171 48 Q164 34 157 48 Z",
              "#16323C", extra=' fill-rule="evenodd"')
    b += chip(4, 4, 70, 19, "RIYADH", 11, "#9A1B1F", "#FFFFFF", 1.0)
    b += t(6, 92, "PIF TOWER", 10, "#FDFBF6", 900, "start", .8)
    return svg(W, H, b)


def art_gta():
    """Worldwide: a Vice-sunset skyline, a large VI and a 99 Metascore badge."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("gtS", [("0", "#241046", "1"), (".36", "#7A1F6E", "1"), (".66", "#D93A82", "1"),
                           (".86", "#FF8A4C", "1"), ("1", "#FFD08A", "1")])
         + lingrad("gtSea", [("0", "#5B2A6A", "1"), ("1", "#1A0730", "1")])
         + radgrad("gtSun", [("0", "#FFF4C2", "1"), (".55", "#FFC15E", "1"), ("1", "#FF5E8A", "1")], 108, 50, 24)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#gtS)")
    b += circle(108, 50, 24, "url(#gtSun)")
    for i, y in enumerate((46, 51, 56, 61)):
        b += rect(84, y, 48, 1.2 + i * .5, "#D93A82", extra=' fill-opacity=".82"')
    for x, w, h in ((0, 12, 14), (12, 9, 24), (22, 13, 12), (36, 8, 18), (148, 10, 20),
                    (158, 13, 12), (172, 8, 24), (180, 10, 16)):
        b += rect(x, 64 - h, w, h, "#2A0C4A")
    b += rect(0, 64, W, 8, "url(#gtSea)")
    b += rect(0, 72, W, 24, "#12041F")
    b += line(92, 72, 70, 96, "#FF3FD8", 1.3) + line(100, 72, 122, 96, "#FF3FD8", 1.3)
    b += palm(30, 96, 56, -3, "#12041F", 1.0) + palm(162, 96, 52, 3, "#12041F", .95)
    b += path("M66 90 L74 84 Q84 81 95 80 L104 77 Q115 74 126 77 L134 80 Q142 82 147 87 L148 90 Z", "#05010C")
    b += path("M74 84 Q84 81 95 80 L104 77 Q115 74 126 77 L134 80 Q142 82 147 87", "none", "#FF7BE8", 1.1)
    b += circle(81, 90, 4.4, "#05010C", "#A855F7", 1.1) + circle(137, 90, 4.4, "#05010C", "#A855F7", 1.1)
    b += t(8, 48, "VI", 38, "#FFFFFF", 900, "start", -1.5,
           ' stroke="#FF2D95" stroke-width="2" paint-order="stroke"')
    b += rect(126, 4, 60, 40, "#15803D", 2, "#DCFCE7", 1.1)
    b += t(156, 24.5, "99", 19, "#FFFFFF", 900, "middle", -.2)
    b += t(156, 40, "METASCORE", 9, "#DCFCE7", 900, "middle", .3)
    return svg(W, H, b)


def art_berlin():
    """Berlin: the Brandenburg Gate between EU and German flags, a truce banner."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("brS", [("0", "#A9CBE2", "1"), (".7", "#E8F4FA", "1"), ("1", "#F6EFE0", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#brS)")
    b += rect(50, 30, 90, 7, "#2C313A")
    for x in range(53, 136, 14):
        b += rect(x, 37, 8, 32, "#2C313A") + rect(x + 6, 37, 2, 32, "#56606E")
    b += rect(48, 66, 94, 6, "#2C313A")
    b += path("M64 30 L72 21 L80 25 L88 17 L95 22 L102 17 L110 25 L118 21 L126 30 Z", "#2C313A")
    for cx in (72, 88, 102, 118):
        b += circle(cx, 18, 3.2, "#2C313A")
    b += rect(4, 8, 42, 28, "#1B3F94", 1, "#FDFBF6", .8)
    for k in range(12):
        a = -math.pi / 2 + k * math.pi / 6
        b += path(star_d(25 + 9.5 * math.cos(a), 22 + 9.5 * math.sin(a), 2.3), "#F5C542")
    b += rect(144, 8, 42, 28, "#1A1A1A", 1, "#FDFBF6", .8)
    b += rect(144, 17.3, 42, 9.4, "#C8102E") + rect(144, 26.7, 42, 9.3, "#F5C542")
    b += rect(0, 74, W, 22, "#9A1B1F") + rect(0, 74, W, 1.6, "#E8B84B")
    b += t(95, 89, "WINTER ENERGY TRUCE", 11, "#FFFFFF", 900, "middle", .8)
    return svg(W, H, b)


def art_kenya():
    """Mrima Hill: emerald and terracotta ridges, a niobium crystal and a $60bn+ badge."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("knS", [("0", "#0F3B35", "1"), (".6", "#2F7D5B", "1"), ("1", "#E8B76B", "1")])
         + lingrad("knX", [("0", "#5EEAD4", "1"), ("1", "#0E7490", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#knS)")
    b += path("M0 56 Q30 42 58 52 Q90 64 118 48 Q148 34 190 52 L190 96 L0 96 Z", "#3E8E5A")
    b += path("M0 68 Q36 56 72 64 Q108 76 144 60 Q168 52 190 62 L190 96 L0 96 Z", "#1F5E3C")
    b += path("M0 80 Q44 70 92 78 Q140 86 190 74 L190 96 L0 96 Z", "#B4552F")
    b += poly([(46, 12), (68, 30), (60, 66), (34, 66), (24, 30)], "url(#knX)", "#062E38", 1.3)
    b += poly([(46, 12), (46, 66), (34, 66), (24, 30)], "#99F6E4", "#062E38", .9)
    b += poly([(46, 12), (68, 30), (46, 38)], "#22D3EE", "#062E38", .8)
    b += line(46, 12, 46, 66, "#ECFEFF", 1.1, extra=' stroke-opacity=".9"')
    b += poly([(80, 36), (93, 45), (88, 66), (74, 66), (68, 45)], "#0E7490", "#062E38", 1.1)
    b += rect(108, 6, 78, 44, "#9A1B1F", 2, "#FDFBF6", 1.1)
    b += t(147, 29, "$60BN+", 18, "#FFFFFF", 900, "middle", -.2)
    b += t(147, 43, "EST. DEPOSIT", 9, "#F7E7C2", 900, "middle", .4)
    b += chip(4, 74, 104, 18, "MRIMA HILL, KENYA", 9.5, "#0B2A26", "#FDFBF6", .4)
    return svg(W, H, b)


def art_tonga():
    """Nuku'alofa: a blazing El Nino sun over cracked, dry coral and the Tongan flag."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("tnS", [("0", "#082F49", "1"), (".6", "#0E7490", "1"), ("1", "#67E8F9", "1")])
         + lingrad("tnC", [("0", "#F97316", "1"), ("1", "#9A3412", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#tnS)")
    for k in range(12):
        a = k * math.pi / 6
        b += line(146, 32, 146 + 27 * math.cos(a), 32 + 27 * math.sin(a), "#FCD34D", 2.0,
                  extra=' stroke-opacity=".8"')
    b += circle(146, 32, 20, "#F59E0B", extra=' fill-opacity=".35"')
    b += circle(146, 32, 16, "#FBBF24", "#7C2D12", 1.1) + circle(146, 32, 9, "#FEF3C7")
    b += path("M0 64 Q30 58 62 63 Q96 69 128 64 Q158 60 190 66 L190 96 L0 96 Z", "url(#tnC)")
    b += path("M0 64 Q30 58 62 63 Q96 69 128 64 Q158 60 190 66", "none", "#FED7AA", 1.3)
    for dp in ("M120 68 L130 74 L126 80", "M150 66 L160 72 L156 78", "M176 68 L184 72"):
        b += path(dp, "none", "#7C2D12", 1.3, ' stroke-opacity=".9"')
    b += rect(6, 8, 48, 32, "#C8102E", 1, "#FDFBF6", .9)
    b += rect(6, 8, 22, 16, "#FDFBF6")
    b += rect(15.6, 10.5, 3, 11, "#C8102E") + rect(11.5, 14.5, 11, 3, "#C8102E")
    b += t(60, 29, "TONGA", 12, "#FFFFFF", 900, "start", 1.2)
    b += t(146, 66, "EL NI&#209;O", 10, "#FEF3C7", 900, "middle", .8,
           ' stroke="#7C2D12" stroke-width="2" paint-order="stroke"')
    b += chip(4, 74, 114, 18, "27-DAY EMERGENCY", 10, "#9A1B1F", "#FFFFFF", .4)
    return svg(W, H, b)


def art_seoul():
    """Seoul: the Taegeukgi, a gavel and an angled RETRIAL 9-3 stamp."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("seS", [("0", "#0C2438", "1"), (".6", "#17496B", "1"), ("1", "#2E6E9E", "1")])
         + lingrad("seG", [("0", "#D9A05B", "1"), ("1", "#8A5A2B", "1")])
         + radgrad("seGlow", [("0", "#F5C542", ".35"), ("1", "#F5C542", "0")], 128, 64, 50)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#seS)") + rect(0, 0, W, H, "url(#seGlow)")
    b += rect(6, 8, 60, 40, "#FDFBF6", 1, "#F5C542", 1.0)
    cx, cy, r = 36, 28, 9.5
    b += path("M%s %s A%s %s 0 0 1 %s %s A%s %s 0 0 1 %s %s A%s %s 0 0 0 %s %s Z" % (
        n(cx - r), n(cy), n(r), n(r), n(cx + r), n(cy), n(r / 2), n(r / 2), n(cx), n(cy),
        n(r / 2), n(r / 2), n(cx - r), n(cy)), "#C8102E")
    b += path("M%s %s A%s %s 0 0 0 %s %s A%s %s 0 0 0 %s %s A%s %s 0 0 1 %s %s Z" % (
        n(cx - r), n(cy), n(r), n(r), n(cx + r), n(cy), n(r / 2), n(r / 2), n(cx), n(cy),
        n(r / 2), n(r / 2), n(cx - r), n(cy)), "#1B3F94")
    for bx, by in ((14, 15), (58, 15), (14, 41), (58, 41)):
        for dy in (-3.4, -.6, 2.2):
            b += rect(bx - 4.5, by + dy, 9, 1.5, "#1A1A1A")
    b += rect(62, 84, 54, 8, "#8A5A2B", 1, "#3A2412", .9)
    b += line(86, 82, 126, 58, "#5A3518", 7.0, ' stroke-linecap="round"')
    b += line(86, 82, 126, 58, "#C08A4A", 2.4, ' stroke-linecap="round"')
    b += '<g transform="rotate(-31 132 54)">'
    b += rect(114, 43, 36, 22, "url(#seG)", 2, "#3A2412", 1.3)
    b += rect(114, 43, 6, 22, "#E8B84B") + rect(144, 43, 6, 22, "#E8B84B")
    b += '</g>'
    b += '<g transform="rotate(-8 140 22)">'
    b += rect(96, 10, 88, 26, "#9A1B1F", 2, "#FDFBF6", 1.2)
    b += t(140, 27.5, "RETRIAL 9&#8211;3", 12, "#FFFFFF", 900, "middle", .6)
    b += '</g>'
    b += t(8, 70, "SEOUL", 12, "#FDE68A", 900, "start", 1.4)
    return svg(W, H, b)


def art_paris():
    """Paris/IEA: rising server-rack bars 2026 to 2030 and a +70% CO2 badge."""
    W, H = SW, SH
    d = ("<defs>"
         + lingrad("prS", [("0", "#12161C", "1"), ("1", "#2A303A", "1")])
         + lingrad("prBar", [("0", "#F05252", "1"), ("1", "#B91C1C", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#prS)")
    b += line(8, 80, 110, 80, "#C9D1D9", 1.5)
    for x, h in ((12, 16), (32, 28), (52, 40), (72, 53), (92, 66)):
        y = 80 - h
        b += rect(x, y, 15, h, "url(#prBar)", 1, "#080B0F", 1.0) + rect(x, y, 15, 4, "#1A1F2B", 1)
        for yy in range(y + 9, 79, 7):
            b += line(x + 2.5, yy, x + 12.5, yy, "#F5C542", .8, extra=' stroke-opacity=".9"')
    b += path("M16 60 L38 48 L58 36 L78 24 L100 10", "none", "#F5C542", 2.0,
              ' stroke-linecap="round" stroke-dasharray="4 2.5"')
    b += poly([(104, 7), (92, 8), (98, 16)], "#F5C542")
    b += t(19.5, 92, "2026", 9.5, "#E5E7EB", 900, "middle", .3)
    b += t(99.5, 92, "2030", 9.5, "#E5E7EB", 900, "middle", .3)
    b += rect(114, 6, 72, 30, "#B91C1C", 2, "#FDFBF6", 1.1)
    b += t(150, 26, "+70% CO&#8322;", 13, "#FFFFFF", 900, "middle", -.2)
    b += t(150, 52, "DATA CENTRES", 9, "#E5E7EB", 900, "middle", .3)
    b += t(150, 66, "IEA &#183; PARIS", 9, "#F5C542", 900, "middle", .6)
    return svg(W, H, b)


# --------------------------------------------------------------- the stories

CARDS = [
    # row 1: three lead stories
    dict(n=1, reg="AP", place="SHENZHEN", beat="SUMMIT", art=art_apec, lon=114.06, lat=22.54,
         h="Trump, Xi and Putin hold first <span style=\"white-space:nowrap\">three-way</span> summit",
         p="The first US&#8211;China&#8211;Russia talks, at APEC, issue a &#8216;Declaration Toward "
           "Peace&#8217; on nuclear risk."),
    dict(n=2, reg="GL", place="THE HAGUE", beat="JUSTICE", art=art_icj, lon=4.30, lat=52.08,
         h="World Court rules Myanmar committed Rohingya genocide",
         p="By 9&#8211;6, the UN&#8217;s top court finds a state responsible for genocide for the first "
           "time and orders redress."),
    dict(n=3, reg="AM", place="NEW YORK", beat="MARKETS", art=art_anthropic, lon=-74.0, lat=40.71,
         h="Anthropic jumps 17% in record $81bn Nasdaq debut",
         p="Priced at $83, ticker ANT opens at $111.50 and closes its first day at $97.17."),
    # row 2
    dict(n=4, reg="GL", place="ANTALYA", beat="CLIMATE", art=art_cop, lon=30.71, lat=36.90,
         h="COP31 draft drops <span style=\"white-space:nowrap\">fossil-fuel</span> phase-out",
         p="Phase-out wording is cut; a 35% electrification goal for 2035 stays."),
    dict(n=5, reg="AP", place="ODISHA", beat="STORM", art=art_cyclone, lon=84.90, lat=19.27,
         h="300,000 evacuated ahead of Cyclone Akvan",
         p="Coastal trains cancelled before Friday&#8217;s expected landfall."),
    dict(n=6, reg="EU", place="KYIV", beat="WAR", art=art_kyiv, lon=30.52, lat=50.45,
         h="Russian drones hit Dutch and Austrian embassies",
         p="One killed in Kyiv; a cathedral is also damaged."),
    dict(n=7, reg="ME", place="RIYADH", beat="GULF", art=art_riyadh, lon=46.68, lat=24.71,
         h="Missile strike damages Riyadh&#8217;s PIF Tower",
         p="Coalition blames the Houthis; Saudi officials report no injuries."),
    dict(n=8, reg="AF", place="MRIMA HILL", beat="MINERALS", art=art_kenya, lon=39.25, lat=-4.48,
         h="Kenya picks US-led bid for Mrima Hill niobium",
         p="Frontier Minerals is preferred bidder for a deposit put at $60bn+."),
    # row 3
    dict(n=9, reg="OC", place="NUKU&#8216;ALOFA", beat="DROUGHT", art=art_tonga, lon=-175.20, lat=-21.14,
         h="Tonga declares 27-day drought emergency",
         p="The nationwide El Ni&#241;o order covers all islands and waters."),
    dict(n=10, reg="AP", place="SEOUL", beat="JUSTICE", art=art_seoul, lon=126.98, lat=37.57,
         h="Korea top court voids <span style=\"white-space:nowrap\">ex-PM</span> Han verdict",
         p="A 9&#8211;3 ruling sends Han Duck-soo&#8217;s martial-law case to retrial."),
    dict(n=11, reg="EU", place="BERLIN", beat="DIPLOMACY", art=art_berlin, lon=13.40, lat=52.52,
         h="Allies urge Russia to agree winter energy truce",
         p="The Berlin summit also seeks a Black Sea ceasefire."),
    dict(n=12, reg="GL", place="PARIS", beat="ENERGY", art=art_paris, lon=2.35, lat=48.86,
         h="IEA: data-centre CO<sub>2</sub> to jump 70% by 2030",
         p="AI doubles power demand; the US leans on gas, China on coal."),
    dict(n=13, reg="GL", place="WORLDWIDE", beat="GAMES", art=art_gta, lon=None, lat=None,
         h="GTA VI launches to a record-tying 99 Metascore",
         p="Trackers put pre-sales above $1.5bn, 13 years after GTA V."),
]

BRIEFS = [
    dict(n=14, reg="AM", place="WASHINGTON", lon=-77.04, lat=38.90,
         tx="US Senate rejects a curb on Iran war powers, 48&#8211;51."),
    dict(n=15, reg="EU", place="COPENHAGEN", lon=12.57, lat=55.68,
         tx="Danish MPs back the US&#8211;Greenland pact, 109&#8211;0."),
    dict(n=16, reg="AF", place="NYALA, SUDAN", lon=24.88, lat=12.05,
         tx="Army jets pound RSF bases in South Darfur."),
    dict(n=17, reg="ME", place="LEBANON", lon=35.50, lat=33.90,
         tx="Israel says it struck a Hezbollah missile site."),
    dict(n=18, reg="AM", place="BOGOT&#193;", lon=-74.07, lat=4.71,
         tx="Colombian unions strike nationwide over a tax bill."),
    dict(n=19, reg="OC", place="COOK ISLANDS", lon=-159.80, lat=-21.20,
         tx="Category 4 Cyclone Xavier lashes the northern atolls."),
]

DECK = ("Trump, Xi and Putin meet at APEC &#183; World Court rules Myanmar committed Rohingya genocide "
        "&#183; Anthropic&#8217;s record $81bn IPO")
FOOTER = ("19 November 2026 (UTC) &#183; All events verified for this date &#183; Disputed claims "
          "attributed &#183; Sources: BBC, Reuters, Guardian, AP, DW, Al Jazeera, UN News, RNZ, Kyiv Independent")

# map badge centres (px in the 348-wide map) for every pinned story
BADGES = {
    1: (302, 98), 2: (158, 36), 3: (121, 51), 4: (186, 73), 5: (258, 105), 6: (222, 41),
    7: (237, 91), 8: (229, 120), 9: (13, 145), 10: (316, 56), 11: (197, 29), 12: (157, 62),
    14: (81, 58), 15: (177, 22), 16: (181, 101), 17: (227, 65), 18: (86, 110), 19: (35, 141),
}
MAP_W = 348
MAP_SCALE = MAP_W / 1000.0
MAP_H = round(486.99 * MAP_SCALE, 1)
PIN_R = 7.2


def miller(lat):
    p = math.radians(lat)
    return 1.25 * math.log(math.tan(math.pi / 4 + 0.4 * p))


def project(lon, lat):
    k = 1000.0 / (2 * math.pi)
    x = (lon + 180.0) / 360.0 * 1000.0
    y = (miller(82.0) - miller(lat)) * k
    return x * MAP_SCALE, y * MAP_SCALE


def all_stories():
    return CARDS + BRIEFS


def region_counts():
    counts = {k: 0 for k in ORDER}
    for s in all_stories():
        counts[s["reg"]] += 1
    return counts


def world_map_svg():
    land = WORLD_PATH.read_text().strip()
    b = rect(0, 0, MAP_W, MAP_H, "#DCE9F2")
    for lat in (60, 30, 0, -30):
        y = project(0, lat)[1]
        b += line(0, y, MAP_W, y, "#C4DCE8", .6, "2 3" if lat == 0 else None)
    for lon in (-120, -60, 0, 60, 120):
        x = project(lon, 0)[0]
        b += line(x, 0, x, MAP_H, "#C4DCE8", .5)
    b += ('<g transform="scale(%.5f)"><path d="%s" fill="#E6DCC5" stroke="#B9A883" '
          'stroke-width="2.2" stroke-linejoin="round"/></g>' % (MAP_SCALE, land))
    leaders, dots, badges = "", "", ""
    for s in all_stories():
        if s["lon"] is None:
            continue
        _l, fill, ink = REGIONS[s["reg"]]
        x, y = project(s["lon"], s["lat"])
        bx, by = BADGES[s["n"]]
        dx, dy = bx - x, by - y
        dist = math.hypot(dx, dy) or 1
        ex, ey = bx - dx / dist * (PIN_R + 1.5), by - dy / dist * (PIN_R + 1.5)
        leaders += line(x, y, ex, ey, ink, 1.0, extra=' stroke-opacity=".9"')
        dots += circle(x, y, 2.6, fill, "#FFFFFF", 1, ' class="pin-dot"')
        badges += ('<g class="pin-badge" data-n="%d">' % s["n"]
                   + circle(bx, by, PIN_R, ink, "#FFFFFF", 1.3)
                   + t(bx, by + 3.4, str(s["n"]), 9.5 if s["n"] < 10 else 9, "#FFFFFF", 900, "middle",
                       -.3 if s["n"] >= 10 else 0)
                   + "</g>")
    b += leaders + dots + badges
    return svg(MAP_W, MAP_H, b, "map-svg")


# --------------------------------------------------------------------- css

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:1024px;height:1024px;overflow:hidden;background:#F6F1E6;}
body{font-family:Lato,sans-serif;color:#141923;-webkit-font-smoothing:antialiased;}
.page{position:relative;width:1024px;height:1024px;overflow:hidden;background:#F6F1E6;}
.toprule{position:absolute;left:16px;right:16px;top:8px;height:2.5px;background:#9A1B1F;}
.kicker{position:absolute;left:16px;right:16px;top:12px;height:12px;display:flex;
 align-items:center;justify-content:space-between;white-space:nowrap;overflow:hidden;}
.kicker span{font-weight:900;font-size:10px;letter-spacing:1.4px;line-height:12px;}
.kicker .kl{color:#9A1B1F;}
.kicker .kr{color:#4A4438;letter-spacing:.9px;}
.masthead{position:absolute;left:16px;right:16px;top:24px;height:72px;text-align:center;
 font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;font-size:66px;line-height:72px;
 letter-spacing:-1.4px;color:#141923;white-space:nowrap;overflow:hidden;}
.deck{position:absolute;left:16px;right:16px;top:96px;height:20px;text-align:center;
 font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-style:italic;font-weight:400;font-size:16px;
 line-height:20px;color:#9A1B1F;white-space:nowrap;overflow:hidden;}
.mastrule{position:absolute;left:16px;right:16px;top:119px;height:1.5px;background:#2C313A;}
.regionbar{position:absolute;left:16px;right:16px;top:124px;height:22px;display:flex;gap:4px;}
.seg{flex:1 1 0;height:22px;display:flex;align-items:center;justify-content:center;gap:7px;
 background:var(--fill);border-radius:3px;white-space:nowrap;overflow:hidden;}
.seg .lab{font-weight:900;font-size:10.5px;letter-spacing:.9px;color:#FFFFFF;line-height:13px;}
.seg .ct{font-weight:900;font-size:11px;color:var(--ink);background:#FFFFFF;border-radius:8px;
 min-width:18px;padding:0 4px;text-align:center;line-height:15px;}
.row{position:absolute;left:16px;width:992px;display:grid;}
.r1{top:152px;height:258px;grid-template-columns:repeat(3,324px);column-gap:10px;}
.r2{top:418px;height:184px;grid-template-columns:repeat(5,192px);column-gap:8px;}
.r3{top:610px;height:184px;grid-template-columns:repeat(5,192px);column-gap:8px;}
.card{position:relative;background:#FDFBF6;border:1.25px solid #2C313A;
 display:flex;flex-direction:column;overflow:hidden;}
.art{flex:none;overflow:hidden;border-bottom:1.25px solid #2C313A;background:#FBF7EE;}
.art svg{display:block;width:100%;height:100%;}
.r1 .art{height:150px;}
.r2 .art,.r3 .art{height:96px;}
.body{flex:1;display:flex;flex-direction:column;min-height:0;overflow:hidden;}
.r1 .body{padding:5px 10px 0;}
.r2 .body,.r3 .body{padding:5px 8px 0;}
.kick{display:flex;align-items:center;gap:5px;white-space:nowrap;flex:none;overflow:hidden;}
.badge{flex:none;display:inline-block;background:var(--ink);color:#FFFFFF;font-weight:900;
 text-align:center;border-radius:2px;}
.kick .pl{font-weight:900;color:var(--ink);}
.kick .sep{color:#8A8070;}
.kick .bt{font-weight:700;color:#3A342A;}
.r1 .kick{height:16px;margin-bottom:2px;}
.r1 .badge{width:17px;height:16px;line-height:16px;font-size:11px;}
.r1 .kick .pl,.r1 .kick .bt,.r1 .kick .sep{font-size:11px;letter-spacing:.8px;}
.r2 .kick,.r3 .kick{height:14px;margin-bottom:2px;}
.r2 .badge,.r3 .badge{width:16px;height:14px;line-height:14px;font-size:10px;}
.r2 .kick .pl,.r2 .kick .bt,.r2 .kick .sep,.r3 .kick .pl,.r3 .kick .bt,.r3 .kick .sep{font-size:10px;letter-spacing:.5px;}
.card h2{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;color:#141923;
 overflow:hidden;flex:none;}
.r1 h2{font-size:21.5px;line-height:23.5px;height:47px;letter-spacing:-.3px;}
.r2 h2,.r3 h2{font-size:15.5px;line-height:16.5px;height:33px;letter-spacing:-.2px;}
.card h2 sub{font-size:.65em;line-height:0;}
.card p{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:400;color:#2C313A;
 overflow:hidden;flex:none;}
.r1 p{margin-top:3px;font-size:13px;line-height:14.5px;height:29px;}
.r2 p,.r3 p{margin-top:3px;font-size:11.5px;line-height:13px;height:26px;}
.panel{position:absolute;top:802px;height:196px;background:#FDFBF6;border:1px solid #B9AE95;
 overflow:hidden;}
.mappanel{left:16px;width:364px;padding:0 6px;display:flex;flex-direction:column;}
.digest{left:388px;width:620px;padding:0 12px;display:flex;flex-direction:column;}
.pcap{height:19px;display:flex;justify-content:space-between;align-items:center;white-space:nowrap;
 border-bottom:1.5px solid #2C313A;overflow:hidden;flex:none;}
.pcap .l{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;font-size:12px;
 letter-spacing:1.3px;color:#141923;}
.pcap .r{font-weight:700;font-size:10px;letter-spacing:.4px;color:#5A5449;}
.mapbox{margin-top:2px;width:350px;border:1px solid #B9C9D3;flex:none;}
.map-svg{display:block;width:348px;height:%MAPH%px;}
.briefs{margin-top:6px;flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;
 grid-template-rows:repeat(3,1fr);column-gap:18px;row-gap:0;}
.bf{display:flex;gap:8px;align-items:flex-start;padding-top:6px;border-top:1px dotted #CDBFA5;
 overflow:hidden;min-width:0;}
.bf:nth-child(1),.bf:nth-child(2){border-top:none;padding-top:2px;}
.bf .nb{flex:none;width:21px;height:20px;line-height:20px;text-align:center;font-weight:900;
 font-size:11px;color:#FFFFFF;background:var(--ink);border-radius:2px;margin-top:1px;}
.bf .bx{flex:1;min-width:0;display:flex;flex-direction:column;}
.bf .pl{font-weight:900;font-size:10.5px;letter-spacing:.8px;color:var(--ink);line-height:13px;
 white-space:nowrap;overflow:hidden;}
.bf .tx{font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-weight:700;font-size:14px;
 line-height:16px;color:#141923;overflow:hidden;max-height:32px;}
.footer{position:absolute;left:16px;right:16px;top:1003px;height:14px;text-align:center;font-weight:700;
 font-size:10px;line-height:14px;letter-spacing:.15px;color:#4A4438;white-space:nowrap;overflow:hidden;}
""".replace("%MAPH%", n(MAP_H))


def style_vars(reg):
    _l, fill, ink = REGIONS[reg]
    return "--fill:%s;--ink:%s;" % (fill, ink)


def card_html(c):
    return (
        '<section class="card" data-story="s%02d" data-region="%s" style="%s">'
        % (c["n"], c["reg"], style_vars(c["reg"]))
        + '<div class="art">%s</div>' % c["art"]()
        + '<div class="body"><div class="kick"><span class="badge">%d</span>' % c["n"]
        + '<span class="pl">%s</span><span class="sep">&#183;</span>'
          '<span class="bt">%s</span></div>' % (c["place"], c["beat"])
        + '<h2>%s</h2><p>%s</p></div></section>' % (c["h"], c["p"])
    )


def brief_html(s):
    return ('<div class="bf" data-story="s%02d" data-region="%s" style="%s">'
            '<span class="nb">%d</span><div class="bx"><span class="pl">%s</span>'
            '<span class="tx">%s</span></div></div>'
            % (s["n"], s["reg"], style_vars(s["reg"]), s["n"], s["place"], s["tx"]))


def build_html():
    counts = region_counts()
    total = sum(counts.values())
    segs = "".join(
        '<div class="seg" data-region="%s" data-count="%d" style="%s">'
        '<span class="lab">%s</span><span class="ct">%d</span></div>'
        % (k, counts[k], style_vars(k), REGIONS[k][0], counts[k]) for k in ORDER)
    rows = [CARDS[0:3], CARDS[3:8], CARDS[8:13]]
    rows_html = "".join('<div class="row r%d">%s</div>' % (i + 1, "".join(card_html(c) for c in r))
                        for i, r in enumerate(rows))
    pins = sum(1 for s in all_stories() if s["lon"] is not None)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Thursday, 19 November 2026 &#183; The World Canvas</title>'
        '<style>' + CSS + '</style></head><body><div class="page">'
        '<div class="toprule"></div>'
        '<div class="kicker"><span class="kl">THE WORLD CANVAS &#183; ONE DAY&#8217;S WORLD NEWS</span>'
        '<span class="kr">%d STORIES &#183; 7 REGIONS &#183; ALL FROM THURSDAY 19 NOVEMBER 2026</span></div>'
        % total
        + '<h1 class="masthead">Thursday, 19 November 2026</h1>'
        '<div class="deck">' + DECK + '</div>'
        '<div class="mastrule"></div>'
        '<div class="regionbar">' + segs + '</div>'
        + rows_html
        + '<div class="panel mappanel"><div class="pcap"><span class="l">WHERE IT HAPPENED</span>'
          '<span class="r">%d PINS &#183; 13 IS WORLDWIDE</span></div>' % pins
        + '<div class="mapbox">' + world_map_svg() + '</div></div>'
        + '<div class="panel digest"><div class="pcap"><span class="l">ALSO ON THURSDAY</span>'
          '<span class="r">19 NOVEMBER 2026</span></div>'
          '<div class="briefs">' + "".join(brief_html(s) for s in BRIEFS) + '</div></div>'
        + '<div class="footer">' + FOOTER + '</div>'
        '</div></body></html>'
    )


# --------------------------------------------------------------------- audit

AUDIT_JS = r"""(want) => {
  const out = {doc:[document.documentElement.scrollWidth, document.documentElement.scrollHeight],
               issues:[], notes:[], minHtml:99, minSvg:99};
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
  stories.forEach(el => { const r = el.dataset.region; if (!r) add('missing region ' + el.dataset.story);
    counts[r] = (counts[r]||0) + 1; });
  if (stories.length !== want.total) add('story total ' + stories.length);
  let barSum = 0;
  document.querySelectorAll('.seg').forEach(s => {
    const r = s.dataset.region, c = +s.dataset.count; barSum += c;
    if (counts[r] !== c) add('region ' + r + ' bar ' + c + ' actual ' + (counts[r]||0));
  });
  if (barSum !== want.total) add('bar total ' + barSum);
  out.badges = document.querySelectorAll('.pin-badge').length;
  if (out.badges !== want.pins) add('map badges ' + out.badges);

  // overflow / clipped text
  document.querySelectorAll('.masthead,.deck,.kicker span,.seg,.kick,.card h2,.card p,.pcap,.bf,.bf .pl,' +
      '.bf .tx,.footer,.panel,.card,.art,.mapbox,.body').forEach(el => {
    if (el.scrollWidth - el.clientWidth > 0.5) add('overflow-x ' + lab(el) + ' +' + (el.scrollWidth - el.clientWidth));
    if (el.scrollHeight - el.clientHeight > 0.5) add('overflow-y ' + lab(el) + ' +' + (el.scrollHeight - el.clientHeight));
  });
  const lines = (el) => { const r = document.createRange(); r.selectNodeContents(el);
      const ys = []; [...r.getClientRects()].forEach(q => { if (q.width > 1 && !ys.some(y => Math.abs(y - q.bottom) < 4)) ys.push(q.bottom); });
      return ys.length; };
  document.querySelectorAll('.card').forEach(c => {
    const lh = lines(c.querySelector('h2')), lp = lines(c.querySelector('p'));
    out.notes.push(c.dataset.story + ' h' + lh + ' p' + lp);
    if (lh < 1 || lh > 2) add('headline lines ' + c.dataset.story + ' (' + lh + ')');
    if (lp < 1 || lp > 2) add('summary lines ' + c.dataset.story + ' (' + lp + ')');
    const body = R(c.querySelector('.body')), p = R(c.querySelector('p'));
    if (body.bottom - p.bottom < 2) add('summary crowds card bottom ' + c.dataset.story);
  });
  document.querySelectorAll('.bf').forEach(b => {
    const lt = lines(b.querySelector('.tx'));
    out.notes.push(b.dataset.story + ' t' + lt);
    if (lt < 1 || lt > 2) add('brief lines ' + b.dataset.story + ' (' + lt + ')');
  });
  // headline text must not end in a lone short word (widow) on line two
  // every HTML text node at least 10px
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const el = node.parentElement;
    if (el.closest('svg') || el.closest('title')) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    out.minHtml = Math.min(out.minHtml, fs);
    if (fs < 10 && el.tagName !== 'SUB') add('small html text ' + fs + ' ' + lab(el));
  }
  document.querySelectorAll('svg text').forEach(tx => {
    const s = tx.ownerSVGElement, k = R(s).width / s.viewBox.baseVal.width;
    const fs = parseFloat(tx.getAttribute('font-size')) * k;
    out.minSvg = Math.min(out.minSvg, fs);
    if (fs < 8.9) add('small svg text ' + fs.toFixed(2) + ' "' + tx.textContent + '"');
  });

  // everything inside the page, every child inside its card / panel
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
  const sib = (sel) => document.querySelectorAll(sel).forEach(par => {
    const kids = [...par.children];
    for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++)
      if (inter(R(kids[i]), R(kids[j]), 0.5)) add('overlap ' + lab(kids[i]) + ' x ' + lab(kids[j]));
  });
  sib('.row'); sib('.regionbar'); sib('.body'); sib('.kick'); sib('.kicker'); sib('.briefs'); sib('.bf');
  sib('.bx'); sib('.mappanel'); sib('.digest');
  const secs = ['.toprule','.kicker','.masthead','.deck','.mastrule','.regionbar','.r1','.r2','.r3',
                '.mappanel','.digest','.footer'].map(s => [s, R(document.querySelector(s))]);
  for (let i = 0; i < secs.length; i++) for (let j = i + 1; j < secs.length; j++)
    if (inter(secs[i][1], secs[j][1], 0.5)) add('section overlap ' + secs[i][0] + ' x ' + secs[j][0]);

  // svg: ink inside the viewBox, labels inside the box and never touching each other
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
    // text drawn on a coloured badge keeps at least 1.5px of padding
    const badgeRects = [...s.querySelectorAll('rect')].filter(r => {
        const w = +r.getAttribute('width'), h = +r.getAttribute('height');
        return r.getAttribute('stroke') && w >= 30 && h >= 14 && w < vb.width - 4; })
      .map(r => R(r));
    texts.forEach(tx => {
      const g = tx.getBBox(), m = tx.getScreenCTM();
      const b = {left: m.e + g.x * m.a, right: m.e + (g.x + g.width) * m.a, top: m.f + g.y * m.d,
                 bottom: m.f + (g.y + g.height) * m.d};
      if (tx.closest('g[transform]')) return;
      const cx = (b.left + b.right) / 2, cy = (b.top + b.bottom) / 2;
      badgeRects.forEach(r => {
        if (cx > r.left && cx < r.right && cy > r.top && cy < r.bottom) {
          const pad = Math.min(b.left - r.left, r.right - b.right);
          if (pad < 1.5) add('svg' + i + ' badge text tight "' + tx.textContent + '" ' + pad.toFixed(1));
        }
      });
    });
  });
  // map badges: no two crowd, no badge covers a pin dot
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
      if (c.length < 4 || c[3] === 1) return c.slice(0, 3); n = n.parentElement; } return [246, 241, 230]; };
  const floor = (sel, min) => document.querySelectorAll(sel).forEach(el => {
    const r = ratio(parse(getComputedStyle(el).color).slice(0, 3), bgOf(el));
    if (r < min) add('contrast ' + lab(el) + ' ' + r.toFixed(2));
  });
  floor('.card h2,.card p,.bf .tx,.masthead,.deck,.seg .lab,.footer', 6.5);
  floor('.kick .pl,.kick .bt,.bf .pl,.pcap .l,.pcap .r,.badge,.bf .nb,.seg .ct,.kicker span', 4.5);
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


def render(want):
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
                audit = page.evaluate(AUDIT_JS, want)
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


def encode_jpeg(image):
    best = None
    for q in JPEG_QUALITIES:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=q, subsampling=0, optimize=True, progressive=False)
        best = (q, buf.getvalue())
        if len(best[1]) <= JPEG_MAX:
            break
    return best


def main():
    stories = all_stories()
    expect = {"s%02d" % s["n"] for s in stories}
    assert len(expect) == N_STORIES and sorted(s["n"] for s in stories) == list(range(1, N_STORIES + 1))
    pins = sum(1 for s in stories if s["lon"] is not None)
    assert set(BADGES) == {s["n"] for s in stories if s["lon"] is not None}
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    audit = render({"total": N_STORIES, "pins": pins})

    missing = sorted(expect - set(audit["ids"]))
    extra = sorted(set(audit["ids"]) - expect)
    print("AUDIT doc=%s stories=%d/%d pins=%d/%d regions=%s repeat_identical=%s"
          % (audit["doc"], len(audit["ids"]), N_STORIES, audit["badges"], pins,
             region_counts(), audit["repeat_identical"]))
    print("  min font: html %.1fpx | svg %.2fpx" % (audit["minHtml"], audit["minSvg"]))
    print("  lines:", " ".join(audit["notes"]))
    for issue in audit["issues"]:
        print("  ISSUE", issue)
    assert not missing and not extra, ("census", missing, extra)
    assert not audit["issues"], "layout audit reported %d issues" % len(audit["issues"])
    assert audit["repeat_identical"]

    from PIL import Image
    raw1, raw2 = RAW_1X.read_bytes(), RAW_2X.read_bytes()
    assert png_size(raw1) == (1024, 1024) and png_size(raw2) == (2048, 2048)
    native = Image.open(io.BytesIO(raw1)).convert("RGB")
    down = Image.open(io.BytesIO(raw2)).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    boxes = [tuple(b) for b in audit["art_boxes"]]
    assert len(boxes) == 14, boxes
    for b in boxes:
        native.paste(down.crop(b), b[:2])

    quality, data = encode_jpeg(native)
    assert data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
    assert len(data) < HARD_LIMIT
    ENTRY.write_bytes(data)
    final = Image.open(io.BytesIO(data)).convert("RGB")
    final.resize((300, 300), Image.LANCZOS).save(PREVIEW_300)
    for p in (HTML_PATH, RAW_1X, RAW_2X):
        p.unlink()
    print("entry.png: 1024x1024 JPEG q%d 4:4:4, native 1x text + 2x Lanczos in %d art/map boxes, "
          "%d bytes (%.1f KiB)" % (quality, len(boxes), len(data), len(data) / 1024))


if __name__ == "__main__":
    main()
