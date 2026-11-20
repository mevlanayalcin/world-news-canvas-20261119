# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A classic archival editorial broadsheet for **Thursday 19 November 2026**: **33 stories across 7 regions**, every one first reported on that day. The page is set on warm cream newsprint (`#F6F1E6`) with charcoal ink and deep crimson accents: a giant **Title-Case serif masthead**, an italic crimson deck, a seven-region balance bar, a parchment *Day in Numbers* strip, thirteen bold high-contrast editorial graphics, a Natural Earth locator and twenty numbered one-line briefs. No all-caps dashboard cards, no dark night-scene grid.

- **13 illustrated stories** in a 3 + 5 + 5 broadsheet grid, each an original inline SVG drawn in code. Every art box is now a single, instant-read editorial graphic with a strong focal object and a crisp, padded callout:
  1. **Shenzhen · Summit** — a bold APEC summit table under large US, Chinese and Russian flags, with `TRUMP`, `XI` and `PUTIN` podium tags and an `APEC 2026 · SHENZHEN` top bar.
  2. **The Hague · Justice** — crisp Peace Palace limestone, oversized golden scales and an unclipped crimson `GUILTY` / `9–6 VOTE` stamp.
  3. **New York · Markets** — a dark emerald trading terminal: `ANT · NASDAQ`, a thick rising chart with `$83`, `$111.53` and `$97.17` tags and an emerald `$81BN RECORD IPO` badge.
  4. **Antalya · Climate** — a bold split graphic: turquoise globe and thermometer on the left, cream COP31 draft on the right with struck-through `FOSSIL FUELS` and `35% BY 2035`.
  5. **Odisha · Storm** — a high-contrast teal coastal map with a thick white Akvan spiral, crimson track arrow and a clean `AKVAN · 300K` pill.
  6. **Kyiv · War** — gold cathedral domes, oversized Dutch and Austrian flags, an impact burst and a padded `KYIV` chip.
  7. **Riyadh · Gulf** — a bold PIF Tower silhouette against a dusk-teal sky, bright impact burst and a `RIYADH` pill.
  8. **Worldwide · Games** — the single Vice-sunset card: magenta/orange sky, palms, a huge `VI` emblem and an emerald `99 METASCORE` badge.
  9. **Berlin · Europe** — the Brandenburg Gate with a 12-star EU flag, German flag and a two-tone `UNITED LINE` / `BERLIN` banner.
  10. **Mrima Hill · Minerals** — rich terracotta/emerald ridges, a bold mineral crystal and a high-contrast `$60BN+ NIOBIUM` badge.
  11. **Nuku‘alofa · Oceania** — a blazing amber El Niño sun, cracked coral coastline, Tongan flag and a `27-DAY EMERGENCY` pill.
  12. **Seoul · Justice** — a crisp Taegeukgi, bold wooden gavel and an angled crimson `OVERTURNED` stamp on deep navy.
  13. **Paris · Energy** — a red-on-charcoal server-rack energy chart rising `2026 → 2030`, with a cleanly padded `+70% CO₂` badge.
- **Region balance**: Asia-Pacific 6 · Americas 6 · Europe 5 · Middle East 2 · Africa 5 · Oceania 4 · Global/Science 5 = **33** exactly, matching the 13 cards plus 20 dispatches.
- **Two-column numbered briefs (14–33)**: ten per column, each a single **9.9px Lato** line with a numbered region badge, bold place, one concrete verified fact and an italic source. The tightest measured slack is **22px**, so nothing wraps, clips or truncates. The four v10 replacements are hard-dated Thursday stories: Australia’s 4.9% jobless rate, Colombia’s nationwide union strike, Indonesia’s asset-seizure law and South Africa’s 7.25% policy hold.
- **World locator**: a Natural Earth 1:110m coastline (stored offline in `world_land_110m.svgpath`) on pale archival ocean with warm tan continents, numbered pins 1–13 and short leader lines for the crowded European pins. A compact seven-region legend sits below the map.
- **Header**: a crimson kicker strip (`THE WORLD CANVAS · ONE-PAGE EDITION`), a 54px Title-Case `Thursday, 19 November 2026` masthead, an italic crimson summary deck, the region balance bar and six parchment stats (`3`, `9–6`, `$81bn`, `300k`, `109–0`, `99`).
- **Footer**: a prominent full-width `DATE CHECK ✓` callout with a 2px crimson border and exactly two crisp lines, naming only the Wednesday 18 and Friday 20 stories left out on purpose (Takaichi–Putin talks, Moïse verdict, Gaza ‘yellow line’, Jeffries 251–11, Van Gogh $190.4m, Fed minutes; Akvan landfall, UK–EU summit), followed by a one-line attribution/sources micro-footer.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs the DOM geometry audit in the same pass. The audit enforces an exact 1024×1024 page, a **33/33** story census, **13** map badges, exact per-region sums against the balance bar, zero overflow, zero overlaps, zero clipped text, every card headline at most two lines, every summary at most two lines, one-line briefs with **≥15px** slack, SVG ink inside every viewBox, at least 1px of padding for every coloured badge label, and an ink-contrast floor. The build fails on any issue.

Text is taken from the native 1× render (edge variance **6785.9** against 6163.1 for the Lanczos-downsampled 2× on the brief columns). The 2× Lanczos pixels are pasted into all **fourteen** integer-aligned boxes (13 story illustrations plus the map), which keeps flags, spirals, skylines and charts smooth while the body text stays pin-sharp. The page is encoded as a 4:4:4 baseline JPEG at quality 91: **434,746 bytes (424.6 KiB)**, well under the 1 MiB gate.

`entry.png` is that JPEG. `main.py` uses only the standard library and no network: it re-validates every JPEG segment up to the EOI marker and atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs are byte-identical, and two full builds are byte-identical too (sha256 `71657f83…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
