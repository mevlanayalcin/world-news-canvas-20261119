# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A classic archival editorial broadsheet for **Thursday 19 November 2026**: **33 stories across 7 regions**, every one first reported on that day. The page is set on warm cream newsprint (`#F6F1E6`) with charcoal ink and deep crimson accents: a giant **Title-Case serif masthead**, an italic crimson deck, a seven-region balance bar, a parchment *Day in Numbers* strip, thirteen bright daylight illustrations, a Natural Earth locator and twenty numbered briefs. No all-caps dashboard cards, no dark night-scene grid.

- **13 illustrated stories** in a 3 + 5 + 5 broadsheet grid, each an original inline SVG drawn in code:
  1. **Shenzhen · Summit** — a sunlit harbour terrace, APEC table and waving US, Chinese and Russian flags.
  2. **The Hague · Justice** — the limestone Peace Palace, gold scales of justice and a `GUILTY 9–6` crimson verdict badge.
  3. **New York · Markets** — a crisp emerald Nasdaq chart from the $83 IPO price to the $111.53 peak and $97.17 close, with a `$81BN RECORD IPO` badge.
  4. **Antalya · Climate** — a bright Mediterranean COP31 dome, wind turbines and a solar field.
  5. **Odisha · Storm** — a pale-blue coastal cyclone chart with a white Akvan spiral and crimson warning pin.
  6. **Kyiv · War** — a daylight cathedral, Dutch and Austrian embassy flags and one bright blast.
  7. **Riyadh · Gulf** — a warm desert-day PIF Tower hit beside the Kingdom Centre.
  8. **Worldwide · Games** — the single twilight card: a neon Vice-coast sunset, palms and a `99` Metascore badge, so it pops uniquely.
  9. **Berlin · Europe** — the Brandenburg Gate with EU and German flags on a green lawn.
  10. **Mrima Hill · Minerals** — emerald Kenyan hills, red earth, a headframe and a small truck.
  11. **Nuku‘alofa · Oceania** — a turquoise Pacific coast, white beach, palms and the Tongan flag.
  12. **Seoul · Justice** — a bright court, gold gavel, crimson block and the Korean flag.
  13. **Paris · Energy** — a cream data centre, solar panels, a turbine, the Eiffel Tower and a `+70%` badge.
- **Region balance**: Asia-Pacific 5 · Americas 5 · Europe 5 · Middle East 4 · Africa 5 · Oceania 4 · Global/Science 5 = **33** exactly, matching the 13 cards plus 20 dispatches.
- **Two-column numbered briefs (14–33)**: ten per column at 9.7px Lato on a 27px pitch — a numbered region badge, bold place, one concrete verified fact and an italic source. The tightest measured slack is 37px, so nothing wraps or truncates.
- **World locator**: a Natural Earth 1:110m coastline (stored offline in `world_land_110m.svgpath`) on pale archival ocean with warm tan continents, numbered pins 1–13 and short leader lines for the crowded European pins. A compact seven-region legend sits below the map; there is no redundant 13-row vertical key.
- **Header**: a crimson kicker strip (`THE WORLD CANVAS · ONE-PAGE EDITION`), a 54px Title-Case `Thursday, 19 November 2026` masthead, an italic crimson summary deck, the region balance bar and six parchment stats (`3`, `9–6`, `$81bn`, `300k`, `109–0`, `99`).
- **Footer**: a full-width `DATE CHECK ✓` callout with a 1.5px crimson border, naming only the Wednesday 18 and Friday 20 stories left out on purpose (Takaichi–Putin talks, Moïse verdict, Gaza ‘yellow line’, Jeffries 251–11, Van Gogh $190.4m, Fed minutes; Akvan landfall, UK–EU summit), followed by a one-line attribution/sources micro-footer.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs the DOM geometry audit in the same pass. The audit enforces an exact 1024×1024 page, a **33/33** story census, **13** map badges, exact per-region sums against the balance bar, zero overflow, zero overlaps, zero clipped or truncated text, every card headline at most two lines, every summary at most two lines (three for the leads), one-line briefs with positive slack, SVG ink inside every viewBox, and an ink-contrast floor. The build fails on any issue.

Text is taken from the native 1× render (edge variance 7222 against 6630 for the Lanczos-downsampled 2× on the brief columns). The 2× Lanczos pixels are pasted into all **fourteen** integer-aligned boxes (13 story illustrations plus the map), which keeps flags, stripes, spirals and skylines smooth. The page is encoded as a 4:4:4 baseline JPEG at quality 92: **427,325 bytes (417.3 KiB)**, well under the 1 MiB gate.

`entry.png` is that JPEG. `main.py` uses only the standard library and no network: it re-validates every JPEG segment up to the EOI marker and atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs are byte-identical, and two full builds are byte-identical too (sha256 `fbfe4f3e…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
