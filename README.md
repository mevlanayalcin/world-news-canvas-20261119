# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A visual broadsheet for **Thursday 19 November 2026**: **20 stories across 7 regions**, every one first reported on that day. Each story's timestamp was checked against the BBC, Guardian, Al Jazeera, DW, Reuters, UN News, ABC, Africanews and RNZ feeds, and the primary articles were read for the numbers. The page is deliberately a **spacious twenty-story front page**, not a wire dump: eight big illustrated features, generous type, a locator map and twelve roomy one-line dispatches.

- **8 illustrated features** in a 3 + 5 broadsheet grid, each an original inline SVG scene:
  1. Shenzhen at dusk: Kingkey 100 and Ping An skyline, harbour, spotlit APEC summit table with waving US, Chinese and Russian flags (first-ever Trump–Xi–Putin trilateral, peace declaration).
  2. A navy Nasdaq chart with a glowing emerald price line: $83 IPO price → $111.53 peak (almost $2tn) → $97.17 close, +17%, and a gold `$81BN RECORD IPO` badge.
  3. The Peace Palace at night under gold scales of justice, `GAMBIA v. MYANMAR · GUILTY` (first state found guilty of genocide by an international court).
  4. A twilight COP31 Antalya scene: a lit conference dome and crescent over the Mediterranean, oil derricks fading into shadow against wind turbines and a solar field, `COP31 ANTALYA · DRAFT 2` and `35% ELECTRIC BY 2035`.
  5. Kyiv: St Volodymyr's Cathedral, Dutch and Austrian embassy flags, drones and a blast.
  6. Riyadh at night: the PIF tower hit, the Kingdom Centre, a missile streak and smoke.
  7. A satellite view of Cyclone Akvan nearing Odisha (~300,000 moved, 69 trains cancelled).
  8. A neon Vice-coastline sunset: a magenta-gold dusk, palm-lined art-deco skyline, a sleek sports-car silhouette, a `99 METASCORE` badge and a `$1.5BN+ PRE-SALES` ribbon (no logos or trademarks).
- **World locator**: a Natural Earth 1:110m coastline (stored offline in `world_land_110m.svgpath`) with large numbered, colour-coded pins 1–8 for the features, a 7-region legend with exact counts (Asia-Pacific 3, Americas 3, Europe 3, Middle East 1, Africa 4, Oceania 2, Global/Science 4) and a full pin key.
- **12 spacious one-line dispatches** (9–20) in a single column at 12.3px on a 36px pitch, each with a numbered region badge, a region · place tag, one concrete fact and its source.
- **Header**: a 52px `THURSDAY, 19 NOVEMBER 2026` banner, an edition block, a seven-segment region balance bar and a five-stat *Day in numbers* strip.
- **Footer**: a single-line `DATE CHECK` / `SOURCES` bar naming only Wednesday 18 stories left out on purpose (the Moïse plot verdict, the Fed minutes, the Van Gogh sale) and the source list. No Friday forecast or event is presented as a Thursday headline.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs a DOM geometry audit in the same pass. The audit checks for an exact 1024×1024 page, no overflow, one-line headlines, at most two lines per summary, no wrapped dispatches, nothing escaping a card or the page, no overlapping cards, labels, SVG text or map badges, SVG ink inside every viewBox, a 20/20 story census and an ink-contrast floor. The build fails on any issue.

The script then compares the two renders on the dispatch column. Native 1× text is sharper (edge variance 5419 against 5098 for the Lanczos-downsampled 2×), so the page keeps 1× text and pastes the 2× Lanczos pixels into the nine integer-aligned illustration boxes (8 features and the map), which gives smoother flags, stripes, spirals and skylines. The result is encoded as a 4:4:4 baseline JPEG at quality 91 (432,057 bytes, 421.9 KiB).

`entry.png` is that JPEG. `main.py` uses only the standard library and no network: it re-validates every JPEG segment up to the EOI marker and atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs are byte-identical (sha256 `b2e3cedc…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
