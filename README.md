# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A bold one-page front page for **Thursday 19 November 2026**: **23 stories across 7 regions**, every one an event of that day. v16 keeps v15's large illustrations and 300px-readable type, and brings back v11's stat strip, its wider brief list and its crimson DATE CHECK box. **No HTML text is smaller than 10px and no SVG label is smaller than 9px**, and the build enforces both limits.

- **Masthead**: a centred 66px serif `Thursday, 19 November 2026`, an italic crimson deck naming the three lead stories, and a seven-region colour strip with counts (Asia-Pacific 4 · Americas 3 · Europe 4 · Middle East 2 · Africa 3 · Oceania 2 · Global 5 = 23).
- **Stat strip**: six 19.5px serif figures: `3` presidents at one table · `9–6` World Court genocide vote · `$81bn` Anthropic record IPO · `300k` evacuated in Odisha · `109–0` Danish Arctic pact vote · `99` GTA VI Metascore.
- **Three lead stories** with 322×130 illustrations, 21.5px headlines and two-line summaries:
  1. **Shenzhen**: Trump, Xi and Putin hold the first three-way summit at APEC (`Declaration Toward Peace` on nuclear risk).
  2. **The Hague**: the World Court rules 9–6 that Myanmar committed genocide against the Rohingya.
  3. **New York**: Anthropic jumps 17% in a record $81bn Nasdaq IPO (`$83` IPO, `$111.50` open, `$97.17` close).
- **Ten illustrated cards** (190×84 art, 15.5px headlines): 4 COP31 draft drops fossil-fuel phase-out (Antalya) · 5 300,000 evacuated ahead of Cyclone Akvan (Odisha) · 6 Russian drones hit Dutch and Austrian embassies (Kyiv) · 7 missile strike damages Riyadh's PIF Tower, attributed by the coalition to the Houthis · 8 Kenya picks US-led bid for Mrima Hill niobium · 9 Tonga's 27-day drought emergency · 10 Korea's top court voids ex-PM Han's verdict 9–3 · 11 allies urge Russia to agree a winter energy truce (Berlin) · 12 IEA: data-centre CO₂ to rise 70% by 2030 (Paris) · 13 GTA VI launches to a record-tying 99 Metascore.
- The art is drawn on the v15 boards (322×150 and 190×96). It is compressed vertically to fit the new boxes, with every label counter-scaled and every circle kept round, so text and discs keep their true shape.
- **Where it happened**: a Natural Earth 1:110m map (stored offline in `world_land_110m.svgpath`) with 21 numbered region-coloured pins and leader lines. Stories 13 and 23 are marked as worldwide. Stories 10 and 17 share the Korea dot.
- **Also on Thursday**: ten one-line briefs (11px place, 13px bold serif text) in two columns: 14 Washington, Senate rejects an Iran war-powers curb 48–51 · 15 Copenhagen, Danish MPs back the US–Greenland pact 109–0 · 16 Kerch, Ukraine strike halts Crimea bridge rail traffic · 17 S. Korea, 551,864 sit the Suneung exam and flights are grounded · 18 Nyala, army jets pound RSF bases · 19 Somalia, Mogadishu gives the UAE envoy 72 hours to leave · 20 Bogotá, unions strike over a tax bill · 21 Lebanon, Israel says it hit a Hezbollah missile site · 22 Cook Islands, Category 4 Cyclone Xavier · 23 IMF/APEC, Georgieva warns the AI boom may force rate hikes.
- **DATE CHECK ✓**: a 2px crimson box: every story happened, or was first reported, on Thursday 19 November 2026 (UTC). It names what was left out as other days' news. WED 18 NOV: Takaichi–Putin talks · Moïse verdict · Gaza 'yellow line' · Jeffries 251–11 · Van Gogh $190.4m · Fed minutes. FRI 20 NOV: Akvan landfall · UK–EU summit.
- **Footer**: one attribution line with the sources.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs a DOM audit in the same pass. The audit checks an exact 1024×1024 page, a 23/23 story census, exact per-region sums, 21 map pins with no crowding and no badge covering a dot, and zero overflow, overlaps or clipped text. It also checks line limits (two lines for headlines and summaries, one for each brief, two for the date check), minimum font sizes, padded badge labels, SVG ink inside every viewBox and a contrast floor. The build fails on any issue. Text comes from the native 1× render. The 2× Lanczos pixels are pasted into the fourteen illustration and map boxes. The page is encoded as a 4:4:4 baseline JPEG at quality 87: **420,812 bytes (410.9 KiB)**, under the 1 MiB gate. The build also writes a 300×300 preview to `/tmp/news_v16_300.png`.

`entry.png` is that JPEG. `main.py` uses only the standard library and no network. It re-validates every JPEG segment up to the EOI marker, then atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs give byte-identical output, and so do two full builds (sha256 `3e1d30d8…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
