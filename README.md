# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A visual broadsheet for **Thursday 19 November 2026**: **44 stories across 7 regions**, every one first reported on that day. Each story's timestamp was checked against the BBC, Guardian, Al Jazeera, DW, France 24, UN News, CBC, NPR, Africanews, RNZ, ABC and TNIE feeds (plus Bing News RSS for wire copy), and the primary articles were read for the numbers. A story is kept only if the event itself happened on Thursday local time and was first reported on 19 November.

- **12 illustrated cards** in rows of 3 / 4 / 5, each an original inline SVG scene:
  1. Shenzhen at dusk: Kingkey 100 and Ping An skyline, harbour, spotlit summit table with waving US, Chinese and Russian flags (first Trump–Xi–Putin trilateral, peace declaration).
  2. A navy Nasdaq chart with a glowing emerald price line: $83 IPO price → $111.53 peak (almost $2tn) → $97.17 close, +17%, and a gold `$81BN RECORD IPO` badge.
  3. The Peace Palace at night under gold scales of justice, `GAMBIA v. MYANMAR · GUILTY` (first state found guilty of genocide by an international court).
  4. A Vice City sunset with palms and a neon `VI`, a `99 METASCORE` chip and `$1.5BN+ PRE-SALES`.
  5. A split COP31 scene: smokestacks and a derrick crossed out in crimson against wind turbines and solar, `COP31 ANTALYA · DRAFT 2` and `35% ELECTRIC BY 2035`.
  6. A satellite view of Cyclone Akvan nearing Odisha (~300,000 moved, 69 trains cancelled).
  7. Riyadh at night: the PIF tower hit, the Kingdom Centre, a missile streak and smoke.
  8. Kyiv: St Volodymyr's Cathedral, Dutch and Austrian embassy flags, drones and a blast.
  9. Berlin: the Brandenburg Gate beside the EU star ring.
  10. Mrima Hill: forested ridge, red laterite and the Kenyan coast, with a glowing `41 Nb` tile and `$60BN+` chip.
  11. Tonga: cracked earth, a dead palm and a near-empty water tank, `27-DAY EMERGENCY`.
  12. Datacentre racks, a CO₂ plume and bars marked `+70%` and `2× POWER` (IEA).
- **World locator**: a Natural Earth 1:110m coastline (stored offline in `world_land_110m.svgpath`) with numbered, colour-coded pins 1–12 for the cards, a 7-region legend with exact counts (Europe 7, Americas 7, Asia-Pacific 6, Africa 6, Middle East 6, Oceania 5, Global/Science 7) and a pin key.
- **32 one-line dispatches** (13–44) in two columns, each with a numbered region badge, a bold place tag, one concrete fact and its source.
- **Header**: a 47px `THURSDAY, 19 NOVEMBER 2026` banner, an edition block, a region bar sized by story count and a *Day in numbers* strip.
- **Footer**: a `DATE CHECK` line naming the Wednesday 18 stories left out on purpose (Takaichi–Putin talks, the Moïse plot verdict, the Venezuela TPS ruling, the Pew religion study, the Egypt–IMF deal, the Gaza "yellow line" crossing, Jeffries 251–11, the Van Gogh sale) and the Friday 20 ones (Speakman's resignation, the UK–EU summit, Akvan's landfall), plus the source list.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs a DOM geometry audit in the same pass. The audit checks for an exact 1024×1024 page, no overflow, one-line headlines, at most two lines per summary, no wrapped dispatches, nothing escaping a card or the page, no overlapping cards, labels, SVG text or map badges, SVG ink inside every viewBox, a 44/44 story census and an ink-contrast floor. The build fails on any issue.

The script then compares the two renders on the dispatch columns. Native 1× text is sharper (edge variance 9717 against 8722 for the Lanczos-downsampled 2×), so the page keeps 1× text and pastes the 2× Lanczos pixels into the 13 integer-aligned illustration boxes (12 cards and the map), which gives smoother flags, stripes, spirals and skylines. The result is encoded as a 4:4:4 baseline JPEG at quality 94 (665,069 bytes, ~650 KiB).

`entry.png` is that JPEG. `main.py` uses only the standard library and no network: it re-validates every JPEG segment up to the EOI marker and atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs in a network namespace with only loopback are byte-identical (sha256 `8cbcd07d…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
