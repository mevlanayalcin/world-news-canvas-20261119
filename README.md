# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A crisp light-newsprint broadsheet for Thursday 19 November 2026: **45 verified stories, 7 regions, 26 cited wires** — gathered the same day with a threaded sweep of 70+ feeds (1,840 unique items, date-filtered) and curated against every headline.

- **Hero Deck (top 10):** the first Trump–Xi–Putin trilateral and its Shenzhen "peace declaration"; Anthropic's record Nasdaq debut — $83 to $97.17, $81bn raised, a $2tn intraday value; Voyager 1 at one light-day; the ICJ's first-ever genocide finding against Myanmar; COP31's fossil-fuel-free Antalya draft; JWST catching a star eating its companion; Israel's "Yellow Line" operation in Gaza; Berlin's "no Yalta 2.0" allies summit; GTA VI's ~$2bn day one; the IMF's 4.7% AI-inflation warning — each with a bespoke inline SVG map, chart or editorial graphic.
- **World Digest Matrix (35 more):** five to six dated briefs per column across Middle East & Gulf, Asia-Pacific, Europe, Americas, Africa, Markets/Tech and Science/Space/Health — from the $48bn Iran war bill and the Hormuz tanker mines to Africa's #1 cyber-target ranking, Kenya's minerals award, the 31.5m-acre Pacific seabed auction and J&J's first US OTTAVA robot. Every brief carries names, numbers and bracketed sources (`[Reuters]`, `[BBC]`, `[AP]`, `[UN NEWS]`, `[DARK READING]` …).

The palette is warm archival newsprint `#FBF8F1` with white story panels, `#111827` ink on hairline rules and seven accent-flagged regional bands; every story-bearing line clears **17:1** measured ink contrast. `build_poster.py` renders in headless Chromium at both 1× and 2× DPR, picks the sharper small-text candidate by edge-variance metric (1× won: 8481 vs 7271), and encodes a 4:4:4 baseline JPEG at quality 93 (~486 kB). The same pass runs a DOM geometry audit: 1024×1024 exactly, zero clipped containers, zero overlapping cards, a 45/45 story census keyed by `data-story`, SVG ink confined to every viewBox, and per-element contrast ≥ 7:1 — the build fails on any issue.

`entry.png` is that committed JPEG; `main.py` (standard library only, no network) re-validates every JPEG segment to the EOI marker and atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR` — two runs are byte-identical (sha256 `7a9a6be5…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
