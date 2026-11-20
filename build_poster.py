#!/usr/bin/env python3
"""Build the 1024x1024 visual broadsheet for Thursday 19 November 2026 (entry.png), v9.

A classic archival editorial broadsheet: warm cream newsprint, a giant Title-Case
serif masthead, an italic crimson deck, a seven-region balance bar, a parchment
Day-in-Numbers strip, thirteen bright daylight editorial illustrations in three
rows (3 + 5 + 5), a Natural Earth locator with numbered pins 1-13, and twenty
numbered dispatches (14-33) in two balanced columns. A crimson-boxed DATE CHECK
names the Wednesday and Friday stories that were deliberately left out.

The page is rendered in headless Chromium at 1x and 2x device scale. The same
pass runs a strict DOM geometry audit (exact size, 33/33 story census, 13 map
badges, exact region sums, no overflow, no overlaps, no clipped text, headline
and summary line limits, positive dispatch slack, SVG ink inside every viewBox
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
HTML_PATH = Path("/tmp/world_news_canvas_v9.html")
RAW_1X = Path("/tmp/world_news_canvas_v9_1x.png")
RAW_2X = Path("/tmp/world_news_canvas_v9_2x.png")
PREVIEW_300 = Path("/tmp/news_v9_300.png")
PREVIEW_512 = Path("/tmp/news_v9_512.png")
CHROME = "/usr/bin/google-chrome"

JPEG_QUALITIES = (92, 91, 90)
JPEG_MAX = 450 * 1024
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


# ------------------------------------------------------- row 1 art (322x102)

def art_apec():
    """Shenzhen: a bright harbour terrace, APEC table, three large flags."""
    W, H = 322, 102
    d = ("<defs>"
         + lingrad("apS", [("0", "#9FD3EE", "1"), (".55", "#D6EEF8", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("apW", [("0", "#8FD0E6", "1"), ("1", "#4FA8C6", "1")])
         + lingrad("apT", [("0", "#FBF4E3", "1"), ("1", "#E3D2AE", "1")])
         + fold_shade("FUF") + fold_shade("FCF") + fold_shade("FRF")
         + "</defs>")
    b = d + rect(0, 0, W, 76, "url(#apS)")
    b += circle(262, 16, 15, "#FFE7A0", extra=' fill-opacity=".35"') + circle(262, 16, 9, "#FFF3C4")
    for x, y, s in ((32, 16, 1.0), (62, 24, .7), (196, 20, .8), (292, 30, .55)):
        b += (circle(x, y, 4 * s, "#FFFFFF", extra=' fill-opacity=".85"')
              + circle(x + 5 * s, y + 1, 3.2 * s, "#FFFFFF", extra=' fill-opacity=".85"')
              + circle(x - 4 * s, y + 1.5, 2.6 * s, "#FFFFFF", extra=' fill-opacity=".85"'))
    far = "#B9CFDA"
    for x, w, h in ((0, 20, 18), (18, 14, 27), (32, 18, 16), (50, 12, 24), (62, 16, 19),
                    (196, 18, 22), (214, 12, 30), (226, 16, 18), (286, 20, 24), (306, 14, 17)):
        b += rect(x, 76 - h, w, h, far)
    b += path("M236 76 L237 34 L241 30 L245 34 L246 76 Z", far)
    near = "#8FAFBE"
    for x, w, h in ((0, 16, 12), (16, 12, 20), (28, 18, 14), (46, 10, 18), (56, 14, 22),
                    (70, 12, 13), (206, 16, 18), (222, 10, 24), (232, 14, 15), (294, 14, 20), (308, 14, 13)):
        b += rect(x, 76 - h, w, h, near)
        b += windows(x + 2, 78 - h, max(1, int((w - 3) // 3)), max(1, int((h - 3) // 4)),
                     3, 4, 1.2, 1.2, "#F4FBFF", x, 0.45)
    b += path("M176 76 L176 50 L180 46 L184 50 L184 76 Z", "#7FA0B2")
    b += rect(0, 76, W, 10, "url(#apW)")
    for x, w in ((18, 26), (52, 16), (102, 38), (150, 20), (214, 26), (252, 18), (292, 22)):
        b += rect(x, 78 + (x % 3), w, .9, "#FFFFFF", extra=' fill-opacity=".5"')
    b += rect(0, 86, W, 16, "#EFE2C6") + line(0, 86, W, 86, "#CBB88F", 1)
    b += poly([(62, 86), (260, 86), (272, 94), (50, 94)], "url(#apT)")
    b += rect(50, 94, 222, 4, "#D8C39B") + rect(56, 91, 210, 2.2, "#9A1B1F")
    for x in (96, 161, 226):
        b += rect(x - 11, 70, 22, 16, "#F8F0DE", 2, "#B9A57C", .7)
        b += rect(x - 8, 72, 16, 7, "#E8D7B4", 1)
    for px, fn, cid in ((64, flag_us, "FU"), (140, flag_cn, "FC"), (216, flag_ru, "FR")):
        b += rect(px - .8, 16, 1.6, 68, "#8A6A3A") + circle(px, 15.5, 1.8, "#C9971F")
        b += pole_flag(px, 16, 38, 24, fn, cid, 1.3)
    for x in (110, 161, 212):
        b += rect(x - 6, 83, 12, 2.6, "#FDFBF6", 1, "#8A8272", .5)
        b += rect(x - .5, 78, 1, 5, "#3A342A") + circle(x, 77.5, 1.2, "#3A342A")
    b += rect(8, 7, 118, 14, "#FDFBF6", 1, "#9A1B1F", .9)
    b += t(67, 16.6, "SHENZHEN &#183; APEC", 7.4, "#9A1B1F", 900, "middle", 1.1)
    b += t(161, 99.2, "DECLARATION ON PEACE", 6.2, "#FDFBF6", 900, "middle", 1.2)
    return svg(W, H, b)


def art_icj():
    """The Hague: sunlit Peace Palace limestone and gold scales of justice."""
    W, H = 322, 102
    d = ("<defs>"
         + lingrad("icS", [("0", "#BFDDF0", "1"), (".6", "#E4F1F9", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("icL", [("0", "#EFDDB6", "1"), ("1", "#D8C193", "1")])
         + lingrad("icR", [("0", "#7FA07F", "1"), ("1", "#54745A", "1")])
         + lingrad("icG", [("0", "#E8C25C", "1"), ("1", "#B8861E", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#icS)")
    b += circle(280, 18, 16, "#FFE7A0", extra=' fill-opacity=".35"') + circle(280, 18, 9, "#FFF3C4")
    b += rect(0, 88, W, 14, "#7FA36B")
    b += rect(26, 52, 270, 38, "url(#icL)") + rect(26, 52, 270, 3, "#C9B183")
    b += rect(128, 34, 66, 56, "#F0DEB8") + rect(128, 34, 66, 3, "#C9B183")
    b += rect(150, 16, 22, 20, "#EAD6AC") + poly([(146, 17), (161, 2), (176, 17)], "url(#icR)")
    b += rect(159.5, .5, 3, 4, "#C9971F")
    b += circle(161, 10, 3.2, "#FDFBF6", "#2C313A", .6) + line(161, 10, 161, 8, "#2C313A", .7)
    for x in range(34, 128, 12):
        b += rect(x, 58, 5, 30, "#E2CDA2") + rect(x + 4, 58, 1, 30, "#C9B183")
    for x in range(198, 292, 12):
        b += rect(x, 58, 5, 30, "#E2CDA2") + rect(x + 4, 58, 1, 30, "#C9B183")
    for x in (134, 142, 180, 188):
        b += rect(x, 56, 5, 34, "#E2CDA2") + rect(x + 4, 56, 1, 34, "#C9B183")
    b += windows(38, 66, 7, 4, 12, 7, 4, 4, "#7A6646", 3, .6)
    b += windows(202, 66, 7, 4, 12, 7, 4, 4, "#7A6646", 9, .6)
    b += windows(150, 38, 2, 2, 8, 7, 4, 4, "#7A6646", 5, .7)
    b += rect(120, 86, 82, 4, "#DCC79C") + rect(112, 90, 98, 3, "#D2BB8D")
    g = "url(#icG)"
    b += rect(58, 84, 44, 5, "#9A1B1F", 1)
    b += rect(78, 40, 4, 44, g) + circle(80, 37, 3.4, g)
    b += rect(42, 44, 76, 3.4, g, 1.6)
    for cx in (48, 112):
        b += line(cx, 47, cx - 10, 64, "#B8861E", 1) + line(cx, 47, cx + 10, 64, "#B8861E", 1)
        b += path("M%d 64 Q%d 74 %d 64 Z" % (cx - 12, cx, cx + 12), g)
    b += t(10, 14, "GAMBIA v. MYANMAR", 7, "#2C313A", 900, "start", 1.0)
    b += rect(238, 8, 76, 22, "#9A1B1F", 1, "#FDFBF6", .8)
    b += t(276, 18, "GUILTY", 8.6, "#FDFBF6", 900, "middle", 1.4)
    b += t(276, 26.5, "9&#8211;6 VOTE", 6.4, "#F7E7C2", 900, "middle", .9)
    return svg(W, H, b)


ANT_SERIES = [
    (20, 83.0), (28, 83.0), (36, 99.0), (46, 104.2), (58, 102.6), (70, 108.4), (84, 110.2),
    (96, 111.53), (108, 108.6), (122, 109.4), (134, 105.4), (148, 107.0), (160, 103.1),
    (174, 104.8), (186, 101.4), (200, 103.0), (212, 99.6), (226, 101.2), (238, 98.4),
    (250, 100.0), (262, 97.2), (274, 98.9), (286, 96.5), (296, 98.0), (304, 97.17),
]


def art_anthropic():
    """New York: a crisp emerald Nasdaq chart on warm paper."""
    W, H = 322, 102

    def py(p):
        return 88 - (p - 80) / (114 - 80) * 76

    d = ("<defs>"
         + lingrad("anB", [("0", "#FDFAF1", "1"), ("1", "#F3EBD9", "1")])
         + lingrad("anA", [("0", "#8FD9B8", ".85"), ("1", "#E8F6EE", ".15")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#anB)")
    for p in (85, 90, 95, 100, 105, 110):
        b += line(16, py(p), 306, py(p), "#DDD2BC", .6)
    dl = "M" + " L".join("%s %s" % (n(x), n(py(p))) for x, p in ANT_SERIES)
    b += path(dl + " L304 92 L20 92 Z", "url(#anA)")
    b += line(16, py(83), 306, py(83), "#C9971F", 1.1, "4 3")
    b += path(dl, "none", "#0E7A4E", 2.6, ' stroke-linejoin="round" stroke-linecap="round"')
    for x, p in ((20, 83), (96, 111.53), (304, 97.17)):
        b += circle(x, py(p), 4, "#FFFFFF", "#0E7A4E", 1.6)
    b += t(18, 15, "ANT &#183; NASDAQ", 7.6, "#2C313A", 900, "start", 1.2)
    b += t(158, 13, "PEAK $111.53", 7.4, "#0E7A4E", 900, "start", .4)
    b += rect(232, 8, 78, 30, "#0E7A4E", 2, "#FDFBF6", .8)
    b += t(271, 24, "$81BN", 12.6, "#FDFBF6", 900, "middle", -.2)
    b += t(271, 35, "RECORD IPO", 5.2, "#CFEBDD", 900, "middle", .9)
    b += t(304, 97.5, "CLOSE $97.17", 7.4, "#2C313A", 900, "end", .4)
    return svg(W, H, b)


# ---------------------------------------------------- small feature art (190x58)

def art_cop():
    """Antalya: bright Mediterranean COP31 dome, wind and solar power."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("cpS", [("0", "#BFE4F5", "1"), (".65", "#E8F7FC", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("cpSea", [("0", "#3FAFCB", "1"), ("1", "#237E9E", "1")])
         + lingrad("cpD", [("0", "#FDFBF6", "1"), ("1", "#E4D6B8", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cpS)")
    b += circle(160, 11, 7, "#FFE7A0", extra=' fill-opacity=".55"') + circle(160, 11, 5, "#FFF3C4")
    for x, y, s in ((26, 10, .6), (78, 8, .5), (122, 14, .45)):
        b += (circle(x, y, 3 * s, "#FFFFFF", extra=' fill-opacity=".9"')
              + circle(x + 3 * s, y + .5, 2.4 * s, "#FFFFFF", extra=' fill-opacity=".9"'))
    b += rect(0, 30, W, 16, "url(#cpSea)")
    for x, w in ((14, 18), (44, 12), (92, 20), (136, 14), (162, 10)):
        b += rect(x, 33 + (x % 3), w, .7, "#FFFFFF", extra=' fill-opacity=".55"')
    b += path("M0 44 Q48 40 96 43 Q146 46 190 42 L190 58 L0 58 Z", "#E8D9B5")
    b += path("M0 44 Q48 40 96 43 Q146 46 190 42", "none", "#C7AE7F", .8)
    b += path("M38 44 A18 18 0 0 1 74 44 Z", "url(#cpD)", "#2C313A", .7)
    b += path("M41 44 A15 15 0 0 1 71 44", "none", "#3E7F5E", 4, ' stroke-opacity=".9"')
    b += rect(50, 37, 12, 7, "#9A1B1F", 1)
    b += line(56, 37, 56, 44, "#5B3A12", .6)
    b += rect(34, 44, 44, 3, "#D8C193") + rect(30, 47, 52, 2, "#CBB88F")
    for x, h in ((90, 20), (112, 15)):
        b += line(x, 44, x, 44 - h, "#FDFBF6", 1.2)
        for ang in (-90, 30, 150):
            a = math.radians(ang)
            b += line(x, 44 - h, x + h * .36 * math.cos(a), 44 - h + h * .36 * math.sin(a), "#FDFBF6", 1.1)
    for r, (y, bw) in enumerate(((46, 22), (50, 32), (54, 42))):
        for k in range(2):
            x0 = 128 + k * 26 - r * 3
            b += poly([(x0, y), (x0 + bw, y), (x0 + bw - 3, y + 3), (x0 - 3, y + 3)],
                      "#2C6FA6", "#FDFBF6", .4)
            b += line(x0 + 1, y + 1.2, x0 + bw - 2, y + 1.2, "#9ED0EA", .35)
    b += t(9, 13, "ANTALYA", 7, "#2C313A", 900, "start", 1.0)
    b += t(55, 34, "COP31", 5.8, "#2C313A", 900, "middle", .8)
    return svg(W, H, b)


def art_cyclone():
    """Odisha: a bright coastal cyclone chart with a crimson warning pin."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("cyO", [("0", "#8FD3E8", "1"), ("1", "#4FA8C6", "1")])
         + lingrad("cyL", [("0", "#E8D9B5", "1"), ("1", "#D8C193", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#cyO)")
    land = "M0 0 L58 0 Q52 10 44 16 Q36 22 30 30 Q24 38 16 46 Q10 52 6 58 L0 58 Z"
    b += path(land, "url(#cyL)") + path(land, "none", "#FDFBF6", 1.2)
    b += path("M0 0 L44 0 Q40 8 34 12 Q26 18 22 26 Q16 34 12 44 Q8 50 4 58 L0 58 Z",
              "#7FA35B", extra=' fill-opacity=".55"')
    b += path("M18 0 Q22 18 14 34 Q10 44 16 58", "none", "#4E6B36", .8, ' stroke-opacity=".6"')
    cx, cy = 146, 28
    for rr in (17, 12, 7):
        b += circle(cx, cy, rr, "none", "#FFFFFF", .8, ' stroke-opacity=".55" stroke-dasharray="2 3"')
    arms = ""
    for k in range(4):
        a0 = k * math.pi / 2
        pts = [(cx + (2 + i * .85) * math.cos(a0 + i * .22),
                cy + (2 + i * .85) * math.sin(a0 + i * .22)) for i in range(16)]
        arms += path("M" + " L".join("%s %s" % (n(x), n(y)) for x, y in pts),
                     "none", "#FFFFFF", 2.4, ' stroke-linecap="round"')
    b += arms + circle(cx, cy, 2.8, "#9A1B1F", "#FFFFFF", .8)
    b += path("M186 52 Q170 40 156 34 Q138 27 118 24", "none", "#FDE68A", 1.4, ' stroke-dasharray="3 2"')
    b += circle(114, 23, 4.2, "#9A1B1F", "#FFFFFF", 1.2)
    b += t(10, 14, "ODISHA", 7.4, "#2C313A", 900, "start", 1.2)
    b += t(184, 10, "AKVAN", 7.4, "#9A1B1F", 900, "end", 1.2)
    return svg(W, H, b)


def art_kyiv():
    """Kyiv: daylight cathedral, Dutch and Austrian embassy flags, one blast."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("kvS", [("0", "#C7DFEF", "1"), (".7", "#E8F3FA", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("kvD", [("0", "#7FA07F", "1"), ("1", "#4E7358", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#kvS)")
    b += circle(164, 10, 6, "#FFE7A0", extra=' fill-opacity=".6"') + circle(164, 10, 4, "#FFF3C4")
    for x, r in ((8, 5), (20, 6), (36, 5), (58, 4), (120, 5), (136, 4), (178, 5)):
        b += circle(x, 50, r, "#5E8F62", extra=' fill-opacity=".8"')
    b += rect(54, 32, 64, 20, "#F3E4C4") + rect(72, 24, 28, 10, "#F3E4C4")
    for cx, cy, r in ((88, 18, 6.5), (62, 29, 4), (78, 24, 4.4), (98, 24, 4.4), (114, 29, 4)):
        b += rect(cx - r * .8, cy + r * .4, r * 1.6, 52 - cy - r * .4, "#F3E4C4")
        b += path("M%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            n(cx - r), n(cy + r * .6), n(cx - r), n(cy - r), n(cx), n(cy - r * 1.5),
            n(cx + r), n(cy - r), n(cx + r), n(cy + r * .6)), "url(#kvD)")
        b += rect(cx - .4, cy - r * 1.5 - 3.4, .8, 3.4, "#C9971F")
        b += rect(cx - 1.3, cy - r * 1.5 - 2.4, 2.6, .7, "#C9971F")
    b += rect(2, 40, 38, 14, "#F7EDD8", 1, "#C9B183", .6)
    b += rect(150, 40, 38, 14, "#F7EDD8", 1, "#C9B183", .6)
    b += windows(5, 43, 7, 2, 5, 5, 2, 2.2, "#8A7856", 3, .7)
    b += windows(153, 43, 7, 2, 5, 5, 2, 2.2, "#8A7856", 7, .7)
    b += rect(18, 28, .8, 12, "#8A8272") + rect(19, 28, 10, 2.4, "#AE1C28")
    b += rect(19, 30.4, 10, 2.4, "#FFFFFF") + rect(19, 32.8, 10, 2.4, "#21468B")
    b += rect(168, 28, .8, 12, "#8A8272") + rect(169, 28, 10, 2.4, "#C8102E")
    b += rect(169, 30.4, 10, 2.4, "#FFFFFF") + rect(169, 32.8, 10, 2.4, "#C8102E")
    b += path(burst_d(146, 36, 6.5, .5, 11), "#EA580C") + path(burst_d(146, 36, 3.6, .6, 9), "#FEF08A")
    b += t(8, 12, "KYIV", 7.4, "#2C313A", 900, "start", 1.4)
    return svg(W, H, b)


def art_riyadh():
    """Riyadh: bright desert daylight, PIF tower hit, Kingdom Centre behind."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("ryS", [("0", "#C7E4F4", "1"), (".65", "#E8F3F8", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("ryT", [("0", "#8FC3DD", "1"), ("1", "#4E8FB0", "1")], x2="1", y2="0")
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#ryS)")
    b += circle(22, 11, 6, "#FFE7A0", extra=' fill-opacity=".65"') + circle(22, 11, 4, "#FFF3C4")
    for x, w, h in ((0, 14, 10), (14, 10, 16), (26, 14, 8), (44, 10, 13), (60, 14, 9),
                    (150, 12, 12), (164, 14, 8), (180, 10, 15)):
        b += rect(x, 50 - h, w, h, "#C3D5DF")
    b += path("M0 48 Q48 45 96 48 Q146 51 190 47 L190 58 L0 58 Z", "#E8D5A9")
    b += path("M108 48 L110 14 L114 8 L122 6 L126 8 L128 14 L130 48 Z", "url(#ryT)", "#2C313A", .7)
    b += line(119, 7, 119, 48, "#FDFBF6", .5, ' stroke-opacity=".7"')
    for y in range(16, 46, 5):
        b += line(111, y, 127, y, "#FDFBF6", .4, ' stroke-opacity=".65"')
    b += path(burst_d(119, 15, 8, .5, 11), "#EA580C") + path(burst_d(119, 15, 4.6, .55, 9), "#FEF08A")
    for cx, cy, r in ((104, 10, 4), (98, 7, 3), (94, 4, 2)):
        b += circle(cx, cy, r, "#9AA5A8", extra=' fill-opacity=".55"')
    b += path("M148 48 L150 26 Q158 14 166 26 L168 48 Z M153 30 Q158 20 163 30 L163 27 Q158 17 153 27 Z",
              "#C3D5DF", extra=' fill-rule="evenodd"')
    b += windows(112, 20, 4, 5, 4, 5, 1.4, 1.6, "#FDFBF6", 4, .55)
    b += t(8, 12, "RIYADH", 7.4, "#2C313A", 900, "start", 1.2)
    b += t(8, 54, "PIF TOWER", 6.2, "#2C313A", 900, "start", 1.0)
    return svg(W, H, b)


def art_gta():
    """Worldwide: the one twilight card, a neon Vice-coast sunset."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("gtS", [("0", "#2A1450", "1"), (".38", "#6B2A68", "1"), (".68", "#C2417A", "1"),
                           (".88", "#FF9E5E", "1"), ("1", "#FFD08A", "1")])
         + lingrad("gtSea", [("0", "#5B2A6A", "1"), ("1", "#240B3A", "1")])
         + radgrad("gtSun", [("0", "#FFF4C2", "1"), (".55", "#FFC15E", "1"), ("1", "#FF7A6A", "1")], 120, 30, 15)
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#gtS)")
    b += circle(120, 30, 15, "url(#gtSun)")
    for i, y in enumerate((27, 30, 33, 36)):
        b += rect(105, y, 30, 1 + i * .35, "#C2417A", extra=' fill-opacity=".8"')
    for x, w, h in ((0, 12, 10), (12, 9, 16), (22, 13, 8), (36, 8, 13), (46, 11, 9),
                    (140, 10, 14), (151, 13, 9), (165, 8, 16), (174, 9, 11)):
        b += rect(x, 38 - h, w, h, "#3A1454")
    b += line(44, 29, 52, 29, "#FF6FE0", .7) + line(150, 27, 158, 27, "#FF6FE0", .7)
    b += rect(0, 38, W, 5, "url(#gtSea)")
    for x, w in ((104, 18), (112, 26), (120, 14), (150, 16)):
        b += rect(x, 40.5, w, .6, "#FFC36B", extra=' fill-opacity=".55"')
    b += rect(0, 43, W, 15, "#1C0838")
    b += path("M86 43 L70 58 L76 58 L90 43 Z", "#5B1B78", extra=' fill-opacity=".55"')
    b += path("M92 43 L112 58 L118 58 L96 43 Z", "#5B1B78", extra=' fill-opacity=".55"')
    b += line(90, 43, 78, 58, "#FF3FD8", .9) + line(92, 43, 104, 58, "#FF3FD8", .9)
    b += palm(18, 58, 40, -4, "#1A0730", .75) + palm(30, 58, 26, 3, "#240A3E", .55)
    b += palm(168, 58, 36, 5, "#1A0730", .7) + palm(180, 58, 24, 2, "#240A3E", .5)
    b += path("M70 52 L76 48 Q84 46 94 45 L102 42 Q112 39 122 42 L130 45 Q138 47 142 50 L143 52 Z",
              "#12041F")
    b += path("M76 48 Q84 46 94 45 L102 42 Q112 39 122 42 L130 45 Q138 47 142 50", "none", "#FF7BE8", .9)
    b += circle(82, 52, 3.6, "#05010C", "#A855F7", .9) + circle(82, 52, 1.5, "#A855F7")
    b += circle(132, 52, 3.6, "#05010C", "#A855F7", .9) + circle(132, 52, 1.5, "#A855F7")
    b += rect(71, 49, 4, 1.4, "#FF2D55", 1)
    b += rect(150, 7, 34, 20, "#15803D", 2, "#BBF7D0", .8)
    b += t(167, 19, "99", 10.4, "#FFFFFF", 900, "middle", -.2)
    b += t(167, 26.2, "SCORE", 4.3, "#DCFCE7", 900, "middle", .7)
    return svg(W, H, b)


def art_berlin():
    """Berlin: sunlit Brandenburg Gate, EU and German flags, green lawn."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("brS", [("0", "#BFDFF2", "1"), (".7", "#E8F4FA", "1"), ("1", "#FBF3E2", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#brS)")
    b += circle(160, 10, 6, "#FFE7A0", extra=' fill-opacity=".6"') + circle(160, 10, 4, "#FFF3C4")
    b += rect(0, 50, W, 8, "#7FA36B")
    b += rect(36, 44, 120, 6, "#D8C193")
    for x in range(42, 150, 14):
        b += rect(x, 26, 7, 18, "#F0DEB8") + rect(x + 6, 26, 1, 18, "#C9B183")
    b += rect(38, 20, 116, 7, "#E8D6B0") + rect(38, 20, 116, 1.6, "#C9B183")
    b += rect(64, 12, 64, 8, "#5C5548")
    b += path("M72 12 L70 6 L74 4 L78 8 L82 5 L86 9 L90 5 L94 9 L98 4 L102 8 L106 5 L110 9 L114 6 L118 10 L120 12 Z",
              "#3A342A")
    for cx in (76, 86, 96, 106):
        b += circle(cx, 10, 2.2, "#3A342A")
    b += rect(6, 36, 24, 14, "#1B3F94", 1, "#FDFBF6", .6)
    for x, y in ((11, 40), (18, 39), (24, 40), (13, 45), (21, 45)):
        b += path(star_d(x, y, 1.6), "#F5C542")
    b += rect(160, 36, 24, 4.7, "#1A1A1A") + rect(160, 40.7, 24, 4.7, "#C8102E")
    b += rect(160, 45.4, 24, 4.6, "#F5C542")
    b += t(8, 12, "BERLIN", 7.4, "#2C313A", 900, "start", 1.4)
    return svg(W, H, b)


def art_kenya():
    """Mrima Hill: emerald hills, red earth, a small headframe and truck."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("knS", [("0", "#BFE6F3", "1"), (".65", "#E8F7F0", "1"), ("1", "#FBF3E2", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#knS)")
    b += circle(160, 11, 6, "#FFE7A0", extra=' fill-opacity=".65"') + circle(160, 11, 4, "#FFF3C4")
    b += path("M0 38 Q30 26 58 34 Q90 42 118 30 Q148 20 190 34 L190 58 L0 58 Z", "#8FC79A")
    b += path("M0 44 Q36 34 72 42 Q108 50 144 38 Q168 31 190 40 L190 58 L0 58 Z", "#4E9A68")
    b += path("M0 52 Q44 44 92 50 Q140 56 190 48 L190 58 L0 58 Z", "#2F7348")
    b += path("M98 58 Q96 52 88 48 Q80 44 82 40 L88 40 Q88 44 96 48 Q106 52 108 58 Z", "#B4552F")
    b += path("M98 58 Q96 52 88 48 Q80 44 82 40", "none", "#D98A5E", .7, ' stroke-opacity=".8"')
    b += line(64, 50, 70, 26, "#3A342A", 1.6) + line(82, 50, 76, 26, "#3A342A", 1.6)
    b += line(70, 26, 76, 26, "#3A342A", 1.4) + line(64, 50, 82, 50, "#3A342A", 1.2)
    for y in (32, 38, 44):
        b += line(66 + (50 - y) * .18, y, 80 - (50 - y) * .18, y, "#3A342A", .7)
    b += line(73, 26, 73, 20, "#3A342A", 1) + circle(73, 19, 2, "#C9971F", "#3A342A", .5)
    b += line(73, 19, 92, 27, "#3A342A", .7)
    b += rect(118, 46, 18, 6, "#E07A3A", 1) + rect(124, 42, 8, 5, "#F0C27A", 1)
    b += circle(122, 53, 2, "#2C313A") + circle(132, 53, 2, "#2C313A")
    b += t(8, 12, "MRIMA HILL", 7.2, "#2C313A", 900, "start", 1.0)
    return svg(W, H, b)


def art_tonga():
    """Nuku'alofa: turquoise Pacific, white beach, palms, Tongan flag."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("tnS", [("0", "#BFE8F7", "1"), (".7", "#E8F9FD", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("tnSea", [("0", "#6FD3DF", "1"), ("1", "#2FB6C9", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#tnS)")
    b += circle(152, 12, 9, "#FFE7A0", extra=' fill-opacity=".55"') + circle(152, 12, 6, "#FFF3C4")
    b += circle(152, 12, 11.5, "none", "#F5C542", .7, ' stroke-dasharray="1.5 3" stroke-opacity=".65"')
    b += rect(0, 34, W, 16, "url(#tnSea)")
    for x, w in ((12, 16), (42, 12), (86, 18), (128, 14), (160, 10)):
        b += rect(x, 37 + (x % 3), w, .7, "#FFFFFF", extra=' fill-opacity=".6"')
    b += path("M0 48 Q36 42 76 46 Q120 50 156 46 L156 58 L0 58 Z", "#F7F0DD")
    b += path("M0 50 Q36 44 76 48 Q120 52 156 48", "none", "#E0D2B4", .8)
    b += palm(28, 50, 26, -3, "#2F7348", .8) + palm(44, 50, 20, 2, "#3E8E5A", .6)
    b += palm(70, 50, 23, 3, "#2F7348", .7)
    b += rect(118, 22, .8, 26, "#8A8272") + rect(119, 22, 18, 11, "#C8102E")
    b += rect(119, 22, 8, 6, "#FDFBF6")
    b += rect(121, 23.5, 4, 1, "#C8102E") + rect(122.5, 22, 1, 4, "#C8102E")
    b += t(8, 12, "NUKU&#8216;ALOFA", 7, "#2C313A", 900, "start", .9)
    return svg(W, H, b)


def art_seoul():
    """Seoul: a bright court, gold gavel, crimson block, Korean flag."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("seS", [("0", "#BFDDF2", "1"), (".7", "#E8F4FA", "1"), ("1", "#FBF3E2", "1")])
         + lingrad("seG", [("0", "#E8C25C", "1"), ("1", "#B8861E", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#seS)")
    b += circle(168, 9, 6, "#FFE7A0", extra=' fill-opacity=".55"') + circle(168, 9, 4, "#FFF3C4")
    b += rect(48, 24, 100, 24, "#FDFBF6", 1, "#C9B183", .6)
    b += rect(84, 28, 28, 20, "#7FB2CF", 1, "#2C313A", .5)
    b += rect(48, 22, 100, 4, "#E8D6B0")
    for x in range(54, 84, 10):
        b += rect(x, 30, 5, 16, "#F0DEB8") + rect(x + 4, 30, 1, 16, "#C9B183")
    for x in range(116, 146, 10):
        b += rect(x, 30, 5, 16, "#F0DEB8") + rect(x + 4, 30, 1, 16, "#C9B183")
    b += rect(44, 48, 108, 3, "#D8C193") + rect(40, 51, 116, 3, "#CBB88F")
    b += rect(150, 42, 24, 5, "#9A1B1F", 1)
    b += rect(160, 28, 5, 14, "url(#seG)") + rect(154, 24, 17, 7, "url(#seG)", 1, "#8A6A1A", .5)
    b += rect(6, 20, 26, 17, "#FDFBF6", 1, "#C9B183", .6)
    b += circle(19, 28.5, 5, "#C8102E")
    b += path("M14 28.5 A5 5 0 0 0 24 28.5 Z", "#1B3F94")
    for x, y in ((9, 23), (29, 23), (9, 34), (29, 34)):
        b += rect(x - 2, y - .6, 4, 1.2, "#1A1A1A")
    b += t(8, 12, "SEOUL", 7.4, "#2C313A", 900, "start", 1.4)
    return svg(W, H, b)


def art_paris():
    """Paris: cream data centre, solar panels, turbine, Eiffel, +70% badge."""
    W, H = 190, 58
    d = ("<defs>"
         + lingrad("prS", [("0", "#D6EAF5", "1"), (".7", "#EEF7FB", "1"), ("1", "#FBF3E2", "1")])
         + "</defs>")
    b = d + rect(0, 0, W, H, "url(#prS)")
    b += circle(170, 10, 6, "#FFE7A0", extra=' fill-opacity=".55"') + circle(170, 10, 4, "#FFF3C4")
    b += path("M30 52 L37 28 L39 12 L41 28 L48 52 L44 52 L40 34 L36 52 Z", "#8C8273")
    b += line(39, 16, 39, 30, "#8C8273", 1.2) + line(35, 24, 43, 24, "#8C8273", .9)
    b += line(33, 38, 45, 38, "#8C8273", .9)
    b += rect(62, 26, 84, 26, "#FDFBF6", 1, "#C9B183", .6)
    b += rect(62, 23, 84, 4, "#3E8E5A")
    for x in range(68, 142, 10):
        b += rect(x, 30, 6, 10, "#7FB2CF", 1, "#2C313A", .3)
    b += rect(92, 40, 12, 12, "#E8D6B0", 1, "#C9B183", .4)
    b += poly([(64, 52), (84, 52), (88, 56), (68, 56)], "#2C6FA6", "#FDFBF6", .4)
    b += poly([(88, 52), (108, 52), (112, 56), (92, 56)], "#2C6FA6", "#FDFBF6", .4)
    b += line(154, 52, 154, 32, "#FDFBF6", 1.2)
    for ang in (-90, 30, 150):
        a = math.radians(ang)
        b += line(154, 32, 154 + 10 * math.cos(a), 32 + 10 * math.sin(a), "#FDFBF6", 1)
    b += rect(144, 6, 40, 20, "#9A1B1F", 2, "#FDFBF6", .7)
    b += t(164, 17, "+70%", 8.8, "#FDFBF6", 900, "middle", .2)
    b += t(164, 26, "CO2 BY 2030", 4.5, "#F7E7C2", 900, "middle", .5)
    b += t(8, 12, "PARIS", 7.4, "#2C313A", 900, "start", 1.4)
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
         h="Houthi strike damages Riyadh&#8217;s PIF Tower",
         p="Officials report damage to the capital&#8217;s tallest tower, the PIF headquarters.",
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
    ("AF", "SUDAN", "UN reports drone strikes have killed 1,630 civilians", "UN News &#183; Reuters"),
    ("AF", "SENEGAL", "Faye bypasses parliament to salvage $2.2bn IMF deal", "Africanews"),
    ("AF", "SOMALIA", "Mogadishu gives UAE envoy 72 hours to leave", "Reuters"),
    ("AF", "ZIMBABWE", "250,000 landmines destroyed in Zimbabwe since 2013", "Africanews"),
    ("OC", "COOK ISLANDS", "Nassau placed on alert as Cyclone Xavier slows", "RNZ"),
    ("OC", "WELLINGTON", "Court rules pay-equity law breached women&#8217;s rights", "RNZ"),
    ("OC", "NORTHLAND", "Sperm whales die in Ninety Mile Beach stranding", "RNZ"),
    ("AM", "WASHINGTON", "Senate rejects Iran war-powers curb in 51&#8211;48 vote", "Al Jazeera"),
    ("AM", "HAITI", "Police raid in Port-au-Prince kills 34 gang members", "Al Jazeera"),
    ("AM", "SACRAMENTO", "California subpoenas Nvidia in China-chip probe", "BBC"),
    # 24-33, right column
    ("AM", "BOSTON", "Judge blocks Trump&#8217;s trans-care curbs on HIV funds", "Reuters"),
    ("EU", "COPENHAGEN", "MPs unanimously ratify US&#8211;Greenland security pact, 109&#8211;0", "DW"),
    ("EU", "BRUSSELS", "Commission reports first AI-driven cyberattack on its network", "DW"),
    ("EU", "MOSCOW", "Putin vows &#8216;far more painful&#8217; reply to bridge strikes", "BBC"),
    ("AP", "DHAKA", "Yunus&#8217;s ancestral home torched before Hasina return", "DW"),
    ("AP", "PAKISTAN", "Bus hits LPG tanker: 10 dead, 27 hurt", "Al Jazeera"),
    ("ME", "GAZA", "1/3 of global child violations in Palestinian territory", "Al Jazeera"),
    ("ME", "LEBANON", "Israel strikes Hezbollah missile site in Bekaa", "Al Jazeera"),
    ("ME", "IRAN / US", "Trump: &#8216;no rush&#8217; on Iran, will decide in new year", "Reuters"),
    ("GL", "ATHLETICS", "World marathon champion Jepchirchir banned 3 years", "BBC"),
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
    "Africanews, Kyiv Independent, TNIE, France 24, IEA"
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
.card{position:relative;background:#FDFBF6;border:1px solid #C9BFA9;border-top:2px solid var(--ink);
 display:flex;flex-direction:column;overflow:hidden;}
.art{flex:none;overflow:hidden;border-bottom:1px solid #DED3BE;background:#FBF7EE;}
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
.cols{margin-top:3px;display:flex;gap:12px;flex:1;min-height:0;}
.col{flex:1 1 0;min-width:0;display:flex;flex-direction:column;}
.dl{flex:1 1 0;min-height:0;display:flex;gap:5px;padding:2px 0 1px;border-bottom:1px dotted #D8CDB8;
 overflow:hidden;}
.dl:last-child{border-bottom:none;}
.dl .nb{flex:none;width:16px;height:13px;line-height:13px;text-align:center;font-weight:900;
 font-size:8.2px;color:#FFFFFF;background:var(--ink);border-radius:1px;margin-top:1px;}
.dl .dx{flex:1 1 auto;min-width:0;}
.dl .dh{height:12px;display:flex;align-items:center;gap:4px;white-space:nowrap;overflow:hidden;}
.dl .dh .rgd{flex:none;width:4px;height:4px;background:var(--fill);}
.dl .dh .pl{font-weight:900;font-size:8.5px;letter-spacing:.5px;color:var(--ink);line-height:11px;}
.dl .dh .so{margin-left:auto;font-family:Liberation Serif,DejaVu Serif,Georgia,serif;font-style:italic;
 font-weight:400;font-size:7.1px;color:#6A6254;line-height:10px;}
.dl .tx{font-weight:400;font-size:9.7px;line-height:11px;letter-spacing:.05px;color:#141923;
 white-space:nowrap;overflow:hidden;height:11px;}
.datecheck{position:absolute;left:18px;width:988px;top:963px;height:43px;background:#FDFBF6;
 border:1.5px solid #9A1B1F;padding:5px 10px 4px;overflow:hidden;}
.datecheck div{white-space:nowrap;overflow:hidden;font-size:8.6px;line-height:13.5px;color:#2C313A;}
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
            '<span class="nb">%d</span><div class="dx">'
            '<div class="dh"><span class="rgd"></span><span class="pl">%s</span>'
            '<span class="so">%s</span></div>'
            '<div class="tx">%s</div></div></div>'
            % (num, reg, style_vars(reg), num, tag, src, text))


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
      '.pcap,.lg,.dl,.dl .dh,.dl .tx,.datecheck div,.footer,.panel,.card,.art,.mapbox,.mnote').forEach(el => {
    if (el.scrollWidth - el.clientWidth > 0.5) add('overflow-x ' + lab(el) + ' +' + (el.scrollWidth - el.clientWidth));
    if (el.scrollHeight - el.clientHeight > 0.5) add('overflow-y ' + lab(el) + ' +' + (el.scrollHeight - el.clientHeight));
  });
  const lines = (el) => { const r = document.createRange(); r.selectNodeContents(el);
      const ys = new Set(); [...r.getClientRects()].forEach(q => { if (q.width > 1) ys.add(Math.round(q.top)); });
      return ys.size; };
  document.querySelectorAll('.card').forEach(c => {
    const h = c.querySelector('h2'), p = c.querySelector('p');
    const lh = lines(h), lp = lines(p);
    const maxP = c.classList.contains('lead') ? 3 : 2;
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
    if (slack < 1) add('dispatch slack ' + d.dataset.story + ' ' + slack.toFixed(1));
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
  sib('.body'); sib('.kick'); sib('.dl'); sib('.dh'); sib('.kicker'); sib('.datecheck');
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
  floor('.kick .pl,.kick .bt,.src,.dl .dh .pl,.dl .dh .so,.stats .v,.pcap .l,.pcap .r,.badge,.dl .nb,.seg .ct,' +
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
