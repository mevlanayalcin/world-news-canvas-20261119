#!/usr/bin/env python3
"""Build the 1024x1024 editorial news poster (entry.png) and 300px audit preview.

Rendering uses Playwright driving the system Chrome. Build-time tooling only.
The shipped runtime (main.py) is standard library only.
"""

import base64
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "entry.png"
HTML_PATH = Path("/tmp/world_news_canvas.html")
PREVIEW_300 = Path("/tmp/preview_300.png")
PREVIEW_600 = Path("/tmp/preview_600.png")
CHROME = "/usr/bin/google-chrome"


def star(cx, cy, r):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append("%.2f,%.2f" % (cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return "M" + " L".join(pts) + " Z"


def art_summit():
    us_stars = "".join(
        '<circle cx="%d" cy="%d" r="0.9" fill="#f4f1e8"/>' % (49 + c * 5, 24 + r * 5)
        for r in range(3) for c in range(3)
    )
    stripes = "".join(
        '<rect x="45" y="%.2f" width="36" height="5.15" fill="%s"/>'
        % (20 + i * 5.14, "#b3261e" if i % 2 == 0 else "#f4f1e8")
        for i in range(7)
    )
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<defs>'
        '<clipPath id="clipUS"><circle cx="63" cy="38" r="18"/></clipPath>'
        '<clipPath id="clipCN"><circle cx="145" cy="38" r="18"/></clipPath>'
        '<clipPath id="clipRU"><circle cx="227" cy="38" r="18"/></clipPath>'
        '</defs>'
        '<g stroke="#ffffff" stroke-opacity=".09" fill="none">'
        '<circle cx="145" cy="40" r="74"/>'
        '<ellipse cx="145" cy="40" rx="74" ry="27"/>'
        '<ellipse cx="145" cy="40" rx="26" ry="74"/>'
        '</g>'
        '<line x1="82" y1="38" x2="126" y2="38" stroke="#d9a441" stroke-width="1" stroke-dasharray="2 3"/>'
        '<line x1="164" y1="38" x2="208" y2="38" stroke="#d9a441" stroke-width="1" stroke-dasharray="2 3"/>'
        '<g clip-path="url(#clipUS)">'
        '<rect x="45" y="20" width="36" height="36" fill="#f4f1e8"/>'
        + stripes +
        '<rect x="45" y="20" width="18" height="15.4" fill="#1f3a6e"/>'
        + us_stars +
        '</g>'
        '<circle cx="63" cy="38" r="18" fill="none" stroke="#d9a441" stroke-width="1.6"/>'
        '<g clip-path="url(#clipCN)">'
        '<rect x="127" y="20" width="36" height="36" fill="#c8322b"/>'
        '<path d="%s" fill="#f2c94c"/>' % star(137, 31, 6.2) +
        '<path d="%s" fill="#f2c94c"/>' % star(148, 24, 2.0) +
        '<path d="%s" fill="#f2c94c"/>' % star(153, 30, 2.0) +
        '<path d="%s" fill="#f2c94c"/>' % star(153, 37, 2.0) +
        '<path d="%s" fill="#f2c94c"/>' % star(148, 43, 2.0) +
        '</g>'
        '<circle cx="145" cy="38" r="18" fill="none" stroke="#d9a441" stroke-width="1.6"/>'
        '<g clip-path="url(#clipRU)">'
        '<rect x="209" y="20" width="36" height="12" fill="#f4f1e8"/>'
        '<rect x="209" y="32" width="36" height="12" fill="#2b4c8c"/>'
        '<rect x="209" y="44" width="36" height="12" fill="#c8322b"/>'
        '</g>'
        '<circle cx="227" cy="38" r="18" fill="none" stroke="#d9a441" stroke-width="1.6"/>'
        '<text x="63" y="75" text-anchor="middle" font-family="Lato" font-size="8.5" font-weight="700" letter-spacing="1.2" fill="#cbb27a">USA</text>'
        '<text x="145" y="75" text-anchor="middle" font-family="Lato" font-size="8.5" font-weight="700" letter-spacing="1.2" fill="#cbb27a">CHINA</text>'
        '<text x="227" y="75" text-anchor="middle" font-family="Lato" font-size="8.5" font-weight="700" letter-spacing="1.2" fill="#cbb27a">RUSSIA</text>'
        '</svg>'
    )


def art_ipo():
    candles = []
    data = [(158, 58, 16, "#1f8a5b"), (174, 54, 22, "#1f8a5b"),
            (190, 50, 26, "#1f4e8c"), (206, 46, 32, "#1f8a5b"),
            (222, 40, 36, "#1f4e8c"), (238, 34, 42, "#1f8a5b"),
            (254, 26, 50, "#1f4e8c")]
    for x, top, h, col in data:
        candles.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.4"/>'
                       % (x, top - 6, x, top + h + 6, col))
        candles.append('<rect x="%d" y="%d" width="8" height="%d" fill="%s"/>'
                       % (x - 4, top, h, col))
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<g stroke="#c9d6e6" stroke-width="1">'
        '<line x1="8" y1="24" x2="282" y2="24"/><line x1="8" y1="38" x2="282" y2="38"/>'
        '<line x1="8" y1="52" x2="282" y2="52"/><line x1="8" y1="66" x2="282" y2="66"/>'
        '</g>'
        '<text x="10" y="40" font-family="Lato" font-size="35" font-weight="900" letter-spacing="-1" fill="#173d6b">$1.5T</text>'
        '<text x="12" y="54" font-family="Lato" font-size="7.4" font-weight="700" letter-spacing="1.3" fill="#476582">RECORD LISTING</text>'
        '<text x="12" y="66" font-family="Lato" font-size="7.4" font-weight="700" letter-spacing="1.3" fill="#476582">NASDAQ &#183; ANT</text>'
        + "".join(candles) +
        '<line x1="150" y1="70" x2="276" y2="16" stroke="#1f4e8c" stroke-width="2.2"/>'
        '<path d="M276 16 L266 18 L270 26 Z" fill="#1f4e8c"/>'
        '</svg>'
    )


def art_voyager():
    stars = [(12, 11, 1.1), (25, 20, 0.8), (41, 9, 1.2), (56, 17, 0.9), (72, 10, 1.0),
             (90, 21, 0.8), (106, 9, 1.1), (121, 17, 0.9), (140, 8, 1.2), (156, 15, 0.8),
             (170, 21, 1.0), (186, 10, 0.9), (202, 18, 1.1), (219, 8, 0.8), (234, 17, 1.0),
             (270, 12, 1.1), (282, 24, 0.8), (18, 32, 0.9), (262, 62, 1.0), (272, 47, 0.8),
             (10, 59, 1.0), (97, 69, 0.8), (182, 64, 0.9), (206, 57, 0.8), (44, 67, 0.7)]
    dots = "".join(
        '<circle cx="%d" cy="%d" r="%.1f" fill="#cfe6f5" opacity=".75"/>' % (x, y, r)
        for x, y, r in stars
    )
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="290" height="84" fill="#0a1020"/>'
        + dots +
        '<circle cx="30" cy="49" r="13" fill="none" stroke="#7fd1e8" stroke-opacity=".25"/>'
        '<circle cx="30" cy="49" r="9" fill="#1f6f9e"/>'
        '<path d="M24 46 Q28 41 31 45 Q34 42 36 47 Q35 53 30 54 Q25 53 24 46 Z" fill="#2f8a5c"/>'
        '<path d="M42 51 Q150 8 244 29" fill="none" stroke="#7fd1e8" stroke-width="1.2" stroke-dasharray="2 4" opacity=".85"/>'
        '<g transform="translate(250,28) rotate(-18)">'
        '<ellipse cx="0" cy="0" rx="9" ry="5" fill="#d9c9a0" stroke="#f2e6c8" stroke-width="0.8"/>'
        '<line x1="-2" y1="0" x2="-13" y2="0" stroke="#d9c9a0" stroke-width="1"/>'
        '<line x1="0" y1="4" x2="0" y2="12" stroke="#d9c9a0" stroke-width="1"/>'
        '<rect x="-3.5" y="4" width="7" height="5" fill="#bfae86"/>'
        '<line x1="6" y1="-2" x2="14" y2="-8" stroke="#d9c9a0" stroke-width="1"/>'
        '</g>'
        '<text x="86" y="25" font-family="Lato" font-size="18" font-weight="900" letter-spacing=".2" fill="#f2e6c8">1 LIGHT-DAY</text>'
        '<text x="87" y="36" font-family="Lato" font-size="6.8" font-weight="700" letter-spacing="1.1" fill="#8fa6bd">25.9 BILLION KM FROM EARTH</text>'
        '<line x1="20" y1="70" x2="268" y2="70" stroke="#3b4a5e" stroke-width="1"/>'
        '<g stroke="#3b4a5e" stroke-width="1">'
        '<line x1="20" y1="66" x2="20" y2="74"/><line x1="82" y1="67" x2="82" y2="73"/>'
        '<line x1="144" y1="67" x2="144" y2="73"/><line x1="206" y1="67" x2="206" y2="73"/>'
        '<line x1="268" y1="66" x2="268" y2="74"/>'
        '</g>'
        '<text x="20" y="81" font-family="Lato" font-size="6.4" font-weight="700" letter-spacing="1" fill="#8fa6bd">EARTH</text>'
        '<text x="145" y="81" text-anchor="middle" font-family="Lato" font-size="6.4" font-weight="700" letter-spacing="1" fill="#8fa6bd">49 YEARS</text>'
        '<text x="268" y="81" text-anchor="end" font-family="Lato" font-size="6.4" font-weight="700" letter-spacing="1" fill="#8fa6bd">VOYAGER 1</text>'
        '</svg>'
    )


def art_climate():
    lines = "".join(
        '<rect x="8" y="%d" width="%d" height="2.6" fill="#d8cbb4"/>'
        % (18 + i * 6, [36, 30, 34, 24, 32][i])
        for i in range(5)
    )
    smoke = "".join(
        '<circle cx="%d" cy="%d" r="%d" fill="#c9b89c" opacity=".65"/>' % (x, y, r)
        for x, y, r in [(5, 17, 4), (9, 10, 5), (14, 3, 4), (24, 6, 4), (29, 1, 3)]
    )
    ticks = "".join(
        '<line x1="22" y1="%d" x2="26" y2="%d" stroke="#b9a98c" stroke-width="1"/>'
        % (12 + i * 8, 12 + i * 8)
        for i in range(5)
    )
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<g transform="translate(12,5)">'
        '<path d="M0 0 H50 L62 12 V74 H0 Z" fill="#fffdf7" stroke="#c2b49a" stroke-width="1"/>'
        '<path d="M50 0 V12 H62" fill="#ece1cb" stroke="#c2b49a" stroke-width="1"/>'
        + lines +
        '<rect x="8" y="46" width="28" height="8" fill="#b3261e" opacity=".9"/>'
        '<rect x="8" y="59" width="32" height="2.6" fill="#d8cbb4"/>'
        '<text x="8" y="70" font-family="Lato" font-size="6.2" font-weight="900" letter-spacing="1.4" fill="#9a8a74">DRAFT</text>'
        '</g>'
        '<g transform="translate(110,17)">'
        + smoke +
        '<rect x="0" y="26" width="13" height="34" fill="#9a8a74"/>'
        '<rect x="18" y="16" width="16" height="44" fill="#8a7a64"/>'
        '<rect x="-1" y="24" width="15" height="3" fill="#c9b89c"/>'
        '<rect x="17" y="14" width="18" height="3" fill="#c9b89c"/>'
        '<circle cx="17" cy="40" r="27" fill="none" stroke="#b3261e" stroke-width="3"/>'
        '<line x1="-2" y1="21" x2="36" y2="59" stroke="#b3261e" stroke-width="3"/>'
        '</g>'
        '<text x="171" y="47" font-family="Lato" font-size="29" font-weight="900" fill="#a8621a">9</text>'
        '<text x="172" y="57" font-family="Lato" font-size="6.2" font-weight="900" letter-spacing="1.2" fill="#8a6a3a">PAGE DRAFT</text>'
        '<g transform="translate(235,9)">'
        '<rect x="6" y="4" width="12" height="54" rx="6" fill="#fffdf7" stroke="#c2b49a" stroke-width="1"/>'
        '<rect x="9" y="31" width="6" height="24" rx="3" fill="#b3261e"/>'
        '<circle cx="12" cy="62" r="9" fill="#b3261e" stroke="#8a1a14" stroke-width="1"/>'
        + ticks +
        '</g>'
        '</svg>'
    )


def art_icj():
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<g>'
        '<rect x="44" y="67" width="62" height="4" rx="1" fill="#1f3f6e"/>'
        '<rect x="72" y="18" width="4" height="50" fill="#1f3f6e"/>'
        '<circle cx="74" cy="15" r="3" fill="#c8a24a"/>'
        '<rect x="24" y="18" width="100" height="3" fill="#1f3f6e"/>'
        '<line x1="28" y1="21" x2="28" y2="36" stroke="#1f3f6e" stroke-width="1"/>'
        '<line x1="33" y1="21" x2="33" y2="36" stroke="#1f3f6e" stroke-width="1"/>'
        '<line x1="115" y1="21" x2="115" y2="36" stroke="#1f3f6e" stroke-width="1"/>'
        '<line x1="120" y1="21" x2="120" y2="36" stroke="#1f3f6e" stroke-width="1"/>'
        '<path d="M14 36 Q30 52 46 36 Z" fill="#1f3f6e"/>'
        '<path d="M102 36 Q118 52 134 36 Z" fill="#1f3f6e"/>'
        '<rect x="24" y="14" width="10" height="3" fill="#c8a24a"/>'
        '<rect x="114" y="14" width="10" height="3" fill="#c8a24a"/>'
        '</g>'
        '<g transform="translate(216,14) rotate(-28)">'
        '<rect x="0" y="0" width="36" height="12" rx="2" fill="#8a6a3a"/>'
        '<rect x="-7" y="-2" width="7" height="16" rx="2" fill="#c8a24a"/>'
        '<rect x="36" y="-2" width="7" height="16" rx="2" fill="#c8a24a"/>'
        '<rect x="14" y="12" width="7" height="26" rx="2" fill="#8a6a3a"/>'
        '</g>'
        '<rect x="214" y="58" width="38" height="6" rx="2" fill="#1f3f6e"/>'
        '<g transform="translate(184,62) rotate(-5)">'
        '<rect x="0" y="0" width="92" height="20" fill="none" stroke="#b3261e" stroke-width="2"/>'
        '<text x="46" y="15" text-anchor="middle" font-family="Lato" font-size="12.5" font-weight="900" letter-spacing="1.4" fill="#b3261e">GUILTY</text>'
        '</g>'
        '</svg>'
    )


def art_mideast():
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<g stroke="#d8b9a2" fill="none" opacity=".75">'
        '<path d="M6 76 Q50 64 96 74"/>'
        '<path d="M18 70 Q58 60 104 68"/>'
        '<path d="M150 78 Q196 66 240 74"/>'
        '</g>'
        '<g transform="translate(58,42)">'
        '<circle r="27" fill="none" stroke="#a8421f" stroke-opacity=".35"/>'
        '<circle r="19" fill="none" stroke="#a8421f" stroke-opacity=".45"/>'
        '<circle r="11" fill="none" stroke="#a8421f" stroke-opacity=".6"/>'
        '<path d="M0 0 L27 -12 A30 30 0 0 1 28 11 Z" fill="#b3261e" opacity=".13"/>'
        '<line x1="0" y1="0" x2="27" y2="-12" stroke="#b3261e" stroke-width="1.4" opacity=".8"/>'
        '<circle r="2.4" fill="#b3261e"/>'
        '</g>'
        '<g transform="translate(128,7)">'
        '<path d="M16 0 L33 30 H-1 Z" fill="#f2c94c" stroke="#8a5a12" stroke-width="1"/>'
        '<text x="16" y="24" text-anchor="middle" font-family="Lato" font-size="15" font-weight="900" fill="#5a3a08">!</text>'
        '</g>'
        '<line x1="210" y1="30" x2="242" y2="44" stroke="#a8421f" stroke-width="1" stroke-dasharray="2 3"/>'
        '<g transform="translate(206,20)">'
        '<path d="M0 0 C-8 -10 -10 -16 -10 -22 A10 10 0 1 1 10 -22 C10 -16 8 -10 0 0 Z" fill="#b3261e"/>'
        '<circle cx="0" cy="-22" r="3.4" fill="#fff5e8"/>'
        '</g>'
        '<text x="221" y="19" font-family="Lato" font-size="8" font-weight="900" letter-spacing="1.2" fill="#8f3418">IRAN</text>'
        '<g transform="translate(244,50)">'
        '<path d="M0 0 C-8 -10 -10 -16 -10 -22 A10 10 0 1 1 10 -22 C10 -16 8 -10 0 0 Z" fill="#a8621a"/>'
        '<circle cx="0" cy="-22" r="3.4" fill="#fff5e8"/>'
        '</g>'
        '<text x="259" y="55" font-family="Lato" font-size="8" font-weight="900" letter-spacing="1.2" fill="#8a5a12">GAZA</text>'
        '</svg>'
    )


def art_africa():
    pulses = "".join(
        '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="#b3261e" stroke-opacity=".55"/>'
        % (x, y, r)
        for x, y, r in [(68, 26, 7), (84, 50, 7), (110, 33, 7)]
    )
    dots = "".join(
        '<circle cx="%d" cy="%d" r="2.4" fill="#b3261e"/>' % (x, y)
        for x, y in [(68, 26), (84, 50), (110, 33)]
    )
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M70 9 L86 6 L103 7 L117 11 L126 19 L122 27 L112 29 L110 37 L105 47 L101 59 L95 71 L89 67 L85 55 L82 45 L77 38 L68 35 L62 27 L64 17 Z" fill="#1f6b4a"/>'
        '<ellipse cx="112" cy="55" rx="4" ry="8" fill="#1f6b4a" opacity=".85"/>'
        '<g stroke="#2b7a56" stroke-width="1" fill="none">'
        '<path d="M70 26 H146 L160 34"/>'
        '<path d="M86 50 H140 L158 44"/>'
        '<path d="M112 33 H158"/>'
        '</g>'
        '<g fill="#2b7a56">'
        '<circle cx="146" cy="26" r="1.8"/><circle cx="140" cy="50" r="1.8"/><circle cx="158" cy="33" r="1.8"/>'
        '</g>'
        + pulses + dots +
        '<g transform="translate(160,32)">'
        '<rect x="0" y="8" width="22" height="18" rx="2" fill="#175e46"/>'
        '<path d="M5 8 V2 A6 6 0 0 1 17 2 V8" fill="none" stroke="#175e46" stroke-width="2.4"/>'
        '<circle cx="11" cy="16" r="2.2" fill="#e8f3ea"/>'
        '<rect x="10" y="17" width="2" height="5" fill="#e8f3ea"/>'
        '</g>'
        '<text x="196" y="37" font-family="Lato" font-size="24" font-weight="900" letter-spacing="-.8" fill="#b3261e">NO.1</text>'
        '<text x="197" y="47" font-family="Lato" font-size="6.2" font-weight="900" letter-spacing="1.2" fill="#1f6b4a">MOST-TARGETED</text>'
        '<text x="197" y="56" font-family="Lato" font-size="6.2" font-weight="900" letter-spacing="1.2" fill="#1f6b4a">REGION</text>'
        '</svg>'
    )


def art_gta():
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<g transform="translate(14,12)">'
        '<path d="M20 4 H84 C94 4 102 12 102 22 L104 38 C105 48 96 52 90 45 L80 36 H24 L14 45 C8 52 -1 48 0 38 L2 22 C2 12 10 4 20 4 Z" fill="#2c2444" stroke="#6b4a94" stroke-width="1.4"/>'
        '<rect x="22" y="16" width="16" height="5" rx="2" fill="#cfc6e8"/>'
        '<rect x="27.5" y="10.5" width="5" height="16" rx="2" fill="#cfc6e8"/>'
        '<circle cx="76" cy="13" r="2.6" fill="#cfc6e8"/><circle cx="84" cy="19" r="2.6" fill="#cfc6e8"/>'
        '<circle cx="72" cy="22" r="2.6" fill="#cfc6e8"/><circle cx="80" cy="28" r="2.6" fill="#cfc6e8"/>'
        '<circle cx="47" cy="27" r="5" fill="none" stroke="#cfc6e8" stroke-width="2"/>'
        '<circle cx="63" cy="31" r="5" fill="none" stroke="#cfc6e8" stroke-width="2"/>'
        '</g>'
        '<text x="180" y="53" font-family="Lato" font-size="42" font-weight="900" letter-spacing="-2" fill="#5b3a7e">VI</text>'
        '<circle cx="252" cy="22" r="18" fill="#b3261e"/>'
        '<text x="252" y="28" text-anchor="middle" font-family="Lato" font-size="17" font-weight="900" fill="#ffffff">99</text>'
        '<text x="252" y="48" text-anchor="middle" font-family="Lato" font-size="6.2" font-weight="900" letter-spacing="1" fill="#6b5a8a">METACRITIC</text>'
        '<text x="180" y="71" font-family="Lato" font-size="6.6" font-weight="700" letter-spacing="1.1" fill="#6b5a8a">PS5 &#183; XBOX SERIES X/S</text>'
        '</svg>'
    )


def art_imf():
    return (
        '<svg viewBox="0 0 290 84" xmlns="http://www.w3.org/2000/svg">'
        '<defs><clipPath id="clipGlobe"><circle cx="52" cy="40" r="27"/></clipPath></defs>'
        '<circle cx="52" cy="40" r="27" fill="#d9ece8" stroke="#175e63" stroke-width="1.6"/>'
        '<g clip-path="url(#clipGlobe)" stroke="#5a9b95" fill="none">'
        '<ellipse cx="52" cy="40" rx="10" ry="27"/><ellipse cx="52" cy="40" rx="19" ry="27"/>'
        '<line x1="25" y1="28" x2="79" y2="28"/><line x1="25" y1="40" x2="79" y2="40"/>'
        '<line x1="25" y1="52" x2="79" y2="52"/>'
        '</g>'
        '<text x="140" y="41" font-family="Lato" font-size="34" font-weight="900" letter-spacing="-1" fill="#175e63">4.7%</text>'
        '<text x="142" y="52" font-family="Lato" font-size="7" font-weight="900" letter-spacing="1.3" fill="#3f6f6c">GLOBAL INFLATION</text>'
        '<line x1="96" y1="72" x2="272" y2="58" stroke="#b3261e" stroke-width="2.2"/>'
        '<path d="M272 58 L261 56 L264 65 Z" fill="#b3261e"/>'
        '</svg>'
    )


PANELS = [
    {
        "region": "ASIA-PACIFIC &#183; GLOBAL", "beat": "DIPLOMACY",
        "headline": 'THREE POWERS,<br><span class="hl">ONE TABLE</span>',
        "sub": "First trilateral in Shenzhen: Trump, Xi, Putin pledge nuclear-risk talks.",
        "art": art_summit, "accent": "#d9a441", "reg": "#e2bb6a",
        "artbg": "#111a2e", "dark": True,
    },
    {
        "region": "AMERICAS", "beat": "MARKETS &#183; TECH",
        "headline": "ANTHROPIC'S<br>$1.5TN IPO",
        "sub": "The AI firm's record listing raises $81bn on Nasdaq at $83 a share.",
        "art": art_ipo, "accent": "#1f4e8c", "reg": "#1f4e8c",
        "artbg": "#e7eef7", "dark": False,
    },
    {
        "region": "SPACE", "beat": "SCIENCE",
        "headline": "VOYAGER 1:<br>ONE LIGHT-DAY",
        "sub": "NASA confirms the probe is 25.9bn km from Earth after 49 years.",
        "art": art_voyager, "accent": "#2b6f74", "reg": "#2b6f74",
        "artbg": "#0a1020", "dark": False,
    },
    {
        "region": "EUROPE", "beat": "CLIMATE",
        "headline": "CLIMATE DRAFT<br>DROPS FOSSIL FUELS",
        "sub": "COP31 draft in Antalya omits any shift away from fossil fuels.",
        "art": art_climate, "accent": "#6b4494", "reg": "#6b4494",
        "artbg": "#f6ecda", "dark": False, "tight": True,
    },
    {
        "region": "ASIA-PACIFIC", "beat": "INTERNATIONAL LAW",
        "headline": "ICJ FINDS<br>GENOCIDE",
        "sub": "World Court: Myanmar committed genocide against the Rohingya.",
        "art": art_icj, "accent": "#b3261e", "reg": "#b3261e",
        "artbg": "#e8edf3", "dark": False,
    },
    {
        "region": "MIDDLE EAST", "beat": "SECURITY",
        "headline": "IRAN STRIKE<br>OPTION WEIGHED",
        "sub": "Trump weighs military options on Iran; Israel raids central Gaza.",
        "art": art_mideast, "accent": "#a8621a", "reg": "#a8621a",
        "artbg": "#f7e7dc", "dark": False,
    },
    {
        "region": "AFRICA", "beat": "CYBERSECURITY",
        "headline": "AFRICA: TOP<br>CYBER TARGET",
        "sub": "Nigeria, Angola and Kenya lead a surge in attacks, analysts say.",
        "art": art_africa, "accent": "#1f6b4a", "reg": "#1f6b4a",
        "artbg": "#e6efe7", "dark": False,
    },
    {
        "region": "GLOBAL", "beat": "CULTURE &#183; GAMING",
        "headline": "GTA VI<br>ARRIVES AT LAST",
        "sub": "After 13 years, GTA VI hits PS5 and Xbox with a 99 score.",
        "art": art_gta, "accent": "#5b3a7e", "reg": "#5b3a7e",
        "artbg": "#ece7f5", "dark": False,
    },
    {
        "region": "GLOBAL", "beat": "ECONOMY",
        "headline": "AI BOOM KEEPS<br>INFLATION HIGH",
        "sub": "IMF warns AI demand and energy shocks keep inflation near 4.7%.",
        "art": art_imf, "accent": "#2b6f74", "reg": "#2b6f74",
        "artbg": "#e3efee", "dark": False,
    },
]

KEY = [
    ("ASIA-PACIFIC", "#b3261e"),
    ("AMERICAS", "#1f4e8c"),
    ("EUROPE", "#6b4494"),
    ("MIDDLE EAST", "#a8621a"),
    ("AFRICA", "#1f6b4a"),
    ("SPACE &#183; GLOBAL", "#2b6f74"),
]

CSS = """
html,body{margin:0;padding:0;width:1024px;height:1024px;overflow:hidden;background:#efe8d7;}
body{font-family:Lato,Arial,sans-serif;-webkit-font-smoothing:antialiased;color:#15171b;}
.page{position:relative;width:1024px;height:1024px;background:radial-gradient(1200px 900px at 50% 35%,#f4eee1 0%,#efe8d7 55%,#e8dfca 100%);}
.rule-top{position:absolute;top:18px;left:24px;right:24px;height:5px;background:#15171b;}
.kicker{position:absolute;top:30px;left:24px;font-family:Lato;font-weight:900;font-size:14px;letter-spacing:3.4px;color:#b3261e;}
.meta{position:absolute;top:32px;right:24px;font-family:Lato;font-weight:700;font-size:11.5px;letter-spacing:2px;color:#6d6352;}
.masthead{position:absolute;top:52px;left:24px;width:976px;margin:0;font-family:Lato;font-weight:900;font-size:62px;line-height:1;letter-spacing:-1.2px;white-space:nowrap;display:flex;align-items:baseline;gap:14px;}
.masthead .day{color:#b3261e;}
.masthead .dot{color:#b3261e;font-size:42px;line-height:1;}
.masthead .date{color:#15171b;}
.regionkey{position:absolute;top:126px;left:24px;width:976px;height:24px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #cabfa9;border-bottom:1px solid #cabfa9;box-sizing:border-box;padding:0 2px;}
.keyitem{display:flex;align-items:center;gap:6px;font-family:Lato;font-weight:900;font-size:11.5px;letter-spacing:1.6px;color:#3d4046;}
.keydot{width:8px;height:8px;display:inline-block;}
.rule-bottom{position:absolute;top:156px;left:24px;right:24px;height:3px;background:#15171b;}
.grid{position:absolute;top:168px;left:24px;width:976px;height:786px;display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(3,1fr);gap:12px;}
.panel{position:relative;box-sizing:border-box;padding:11px 13px;background:#fbf7ec;border:1px solid #201f1c;border-top:3px solid var(--accent);overflow:hidden;}
.ptop{height:16px;display:flex;justify-content:space-between;align-items:center;}
.region{display:flex;align-items:center;gap:5px;font-family:Lato;font-weight:900;font-size:10.5px;letter-spacing:1.4px;color:var(--reg);white-space:nowrap;}
.region:before{content:"";width:6px;height:6px;background:var(--reg);display:inline-block;}
.beat{font-family:Lato;font-weight:900;font-size:9px;letter-spacing:1.1px;color:#8a7f6a;white-space:nowrap;}
.art{margin-top:5px;height:84px;width:100%;background:var(--artbg);overflow:hidden;}
.art svg{display:block;width:100%;height:84px;}
.panel h2{margin:6px 0 0;font-family:Lato;font-weight:900;font-size:28px;line-height:1;letter-spacing:-.4px;color:#15171b;white-space:nowrap;}
.panel h2 .hl{color:#d9a441;}
.panel p{margin:5px 0 0;font-family:Lato;font-weight:400;font-size:18px;line-height:1.24;color:#393b40;}
.panel.dark{background:#111a2e;border-color:#0a101d;}
.panel.dark h2{color:#f6efdc;font-size:30px;}
.panel.tight h2{font-size:27px;}
.panel.dark h2 .hl{color:#d9a441;}
.panel.dark p{color:#c7cfdb;}
.panel.dark .beat{color:#8fa0b8;}
.footer{position:absolute;top:966px;left:24px;width:976px;height:34px;background:#15171b;color:#f3ecdb;display:flex;justify-content:space-between;align-items:center;box-sizing:border-box;padding:0 14px;}
.footer .left{font-family:Lato;font-weight:700;font-size:10.5px;letter-spacing:1.2px;}
.footer .right{font-family:Lato;font-weight:900;font-size:10.5px;letter-spacing:1.2px;color:#d9a441;}
.grain{position:absolute;left:0;top:0;width:1024px;height:1024px;pointer-events:none;opacity:.06;mix-blend-mode:multiply;}
"""


def panel_html(p):
    cls = "panel dark" if p["dark"] else ("panel tight" if p.get("tight") else "panel")
    style = "--accent:%s;--reg:%s;--artbg:%s;" % (p["accent"], p["reg"], p["artbg"])
    return (
        '<section class="%s" style="%s">' % (cls, style) +
        '<div class="ptop"><span class="region">%s</span><span class="beat">%s</span></div>' % (p["region"], p["beat"]) +
        '<div class="art">%s</div>' % p["art"]() +
        '<h2>%s</h2>' % p["headline"] +
        '<p>%s</p>' % p["sub"] +
        '</section>'
    )


def build_html():
    key_html = "".join(
        '<span class="keyitem"><span class="keydot" style="background:%s"></span>%s</span>' % (col, label)
        for label, col in KEY
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>19 November 2026</title>'
        '<style>' + CSS + '</style></head><body><div class="page">'
        '<div class="rule-top"></div>'
        '<div class="kicker">THE WORLD IN ONE DAY</div>'
        '<div class="meta">VOL. I &#183; NO. 19 &#183; NINE VERIFIED STORIES</div>'
        '<h1 class="masthead"><span class="day">THURSDAY</span><span class="dot">&#183;</span><span class="date">19 NOVEMBER 2026</span></h1>'
        '<div class="regionkey">' + key_html + '</div>'
        '<div class="rule-bottom"></div>'
        '<div class="grid">' + "".join(panel_html(p) for p in PANELS) + '</div>'
        '<div class="footer"><span class="left">SOURCES: AP &#183; REUTERS &#183; NASA &#183; IMF &#183; ICJ &#183; THE HAGUE</span>'
        '<span class="right">NINE STORIES &#183; SIX REGIONS &#183; ONE DAY</span></div>'
        '<svg class="grain" width="1024" height="1024" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">'
        '<filter id="grainfilter"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" seed="17" stitchTiles="stitch"/>'
        '<feColorMatrix type="saturate" values="0"/></filter>'
        '<rect width="1024" height="1024" filter="url(#grainfilter)"/></svg>'
        '</div></body></html>'
    )


AUDIT_JS = """() => {
  const out = {doc:[document.documentElement.scrollWidth, document.documentElement.scrollHeight], panels:[]};
  document.querySelectorAll('.panel').forEach((p, i) => {
    const h = p.querySelector('h2'), s = p.querySelector('p'), a = p.querySelector('.art');
    out.panels.push({
      i: i+1,
      ph: p.clientHeight, psh: p.scrollHeight,
      hh: h.clientHeight, hsh: h.scrollHeight,
      hw: h.clientWidth, hsw: h.scrollWidth,
      sh: s.clientHeight, ssh: s.scrollHeight,
      ah: a.clientHeight, ash: a.scrollHeight
    });
  });
  const m = document.querySelector('.masthead');
  out.masthead = [m.clientWidth, m.scrollWidth, m.clientHeight, m.scrollHeight];
  const k = document.querySelector('.regionkey');
  out.key = [k.clientWidth, k.scrollWidth];
  return out;
}"""

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def png_size(data):
    if data[:8] != PNG_SIG:
        raise SystemExit("entry.png is not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    return w, h


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
        page.wait_for_timeout(350)
        audit = page.evaluate(AUDIT_JS)
        print("AUDIT", audit)
        page.screenshot(path=str(ENTRY), clip={"x": 0, "y": 0, "width": 1024, "height": 1024})

        data = ENTRY.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        for size, dest in ((300, PREVIEW_300), (600, PREVIEW_600)):
            p = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
            p.set_content(
                '<html><body style="margin:0;padding:0;overflow:hidden;background:#000">'
                '<img src="data:image/png;base64,' + b64 + '" width="' + str(size) +
                '" height="' + str(size) + '" style="display:block">'
                '</body></html>'
            )
            p.wait_for_timeout(120)
            p.screenshot(path=str(dest))
            p.close()
        browser.close()


def render_with_chrome():
    import subprocess

    subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--window-size=1024,1024",
         "--screenshot=" + str(ENTRY), HTML_PATH.as_uri()],
        check=True,
    )


def main():
    html = build_html()
    HTML_PATH.write_text(html, encoding="utf-8")
    try:
        render_with_playwright()
    except ImportError:
        print("Playwright unavailable; falling back to Chrome CLI.")
        render_with_chrome()

    data = ENTRY.read_bytes()
    w, h = png_size(data)
    print("entry.png: %dx%d, %d bytes (%.1f KiB)" % (w, h, len(data), len(data) / 1024))
    assert (w, h) == (1024, 1024), "wrong dimensions"
    assert len(data) <= 1048576, "entry.png exceeds 1 MiB"
    for preview in (PREVIEW_300, PREVIEW_600):
        pw, ph = png_size(preview.read_bytes())
        print("%s: %dx%d, %d bytes" % (preview, pw, ph, preview.stat().st_size))


if __name__ == "__main__":
    main()



