# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A bold one-page front page for **Thursday 19 November 2026**: **19 stories across 7 regions**, every one an event of that day. v15 drops the 33-story micro-text layout. Fewer stories, each with a large picture and text that stays readable when the page is shrunk to 300 pixels across. **No HTML text is smaller than 10px and no SVG label is smaller than 9px**, and the build enforces both limits.

- **Masthead**: a centred 66px serif `Thursday, 19 November 2026`, an italic crimson deck naming the three lead stories, and a seven-region colour strip with counts (Asia-Pacific 3 · Americas 3 · Europe 3 · Middle East 2 · Africa 2 · Oceania 2 · Global 4 = 19).
- **Three lead stories** with 322×150 illustrations, 21.5px headlines and two-line summaries:
  1. **Shenzhen**: Trump, Xi and Putin hold the first three-way summit at APEC (`Declaration Toward Peace` on nuclear risk). US, Chinese and Russian flags over the summit table.
  2. **The Hague**: the World Court rules 9–6 that Myanmar committed genocide against the Rohingya. Peace Palace, gold scales and a `GENOCIDE · RULING 9–6` stamp.
  3. **New York**: Anthropic jumps 17% in a record $81bn Nasdaq IPO. Price chart: `$83` IPO, `$111.50` open, `$97.17` close.
- **Ten illustrated cards** (190×96 art, 15.5px headlines): 4 COP31 draft drops fossil-fuel phase-out (Antalya) · 5 300,000 evacuated ahead of Cyclone Akvan (Odisha) · 6 Russian drones hit Dutch and Austrian embassies (Kyiv) · 7 missile strike damages Riyadh's PIF Tower, attributed by the coalition to the Houthis · 8 Kenya picks US-led bid for Mrima Hill niobium · 9 Tonga's 27-day drought emergency · 10 Korea's top court voids ex-PM Han's verdict 9–3 · 11 allies urge Russia to agree a winter energy truce (Berlin) · 12 IEA: data-centre CO₂ to rise 70% by 2030 (Paris) · 13 GTA VI launches to a record-tying 99 Metascore.
- **Where it happened**: a Natural Earth 1:110m map (stored offline in `world_land_110m.svgpath`) with 18 numbered region-coloured pins and leader lines. Story 13 is marked as worldwide.
- **Also on Thursday**: six two-line briefs in 14px bold serif: the US Senate rejects an Iran war-powers curb 48–51, Danish MPs back the US–Greenland pact 109–0, army jets strike RSF bases in Nyala, Israel says it struck a Hezbollah missile site, Colombian unions strike over a tax bill, and Cyclone Xavier (Category 4) hits the northern Cook Islands.
- **Footer**: `19 November 2026 (UTC) · All events verified for this date · Disputed claims attributed · Sources: …`.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs a DOM audit in the same pass. The audit checks an exact 1024×1024 page, a 19/19 story census, exact per-region sums, 18 map pins, zero overflow, overlaps or clipped text, at most two lines for each headline, summary and brief, minimum font sizes, padded badge labels, SVG ink inside every viewBox and a contrast floor. The build fails on any issue. Text comes from the native 1× render. The 2× Lanczos pixels are pasted into the fourteen illustration and map boxes. The page is encoded as a 4:4:4 baseline JPEG at quality 90: **438,553 bytes (428.3 KiB)**, under the 1 MiB gate. The build also writes a 300×300 preview to `/tmp/news_v15_300.png`.

`entry.png` is that JPEG. `main.py` uses only the standard library and no network. It re-validates every JPEG segment up to the EOI marker, then atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs give byte-identical output, and so do two full builds (sha256 `ddf9440a…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
