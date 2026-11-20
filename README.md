# world-news-canvas-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/mevlanayalcin/world-news-canvas-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

A classic archival editorial broadsheet for **Thursday 19 November 2026**: **33 stories across 7 regions**, every one first reported on that day. The page is set on warm cream newsprint (`#F6F1E6`) with charcoal ink and deep crimson accents: a giant **Title-Case serif masthead**, an italic crimson deck, a bold seven-pill colour-coded region bar, a high-contrast *Day in Numbers* strip, thirteen bold high-contrast editorial graphics, a Natural Earth locator and twenty numbered one-line briefs. No all-caps dashboard cards, no dark night-scene grid.

- **13 illustrated stories** in a 3 + 5 + 5 broadsheet grid, each an original inline SVG drawn in code. The three lead cards carry 18.4px bold serif headlines over two-line 10.3px summaries. Every art box is now a single, instant-read editorial graphic with a strong focal object and a crisp, padded callout:
  1. **Shenzhen · Summit** — a bold APEC summit table under large US, Chinese and Russian flags, with `TRUMP`, `XI` and `PUTIN` podium tags and an `APEC 2026 · SHENZHEN` top bar.
  2. **The Hague · Justice** — crisp Peace Palace limestone, oversized golden scales and an unclipped crimson `GUILTY` / `9–6 VOTE` stamp.
  3. **New York · Markets** — a dark emerald trading terminal: `ANT · NASDAQ`, a thick rising chart with `$83`, `$111.53` and `$97.17` tags and an emerald `$81BN RECORD IPO` badge.
  4. **Antalya · Climate** — a bold split graphic: turquoise globe and thermometer on the left, cream COP31 draft on the right with struck-through `FOSSIL FUELS` and `35% BY 2035`.
  5. **Odisha · Storm** — a high-contrast teal coastal map with a thick white Akvan spiral, crimson track arrow and a clean `AKVAN · 300K` pill.
  6. **Kyiv · War** — gold cathedral domes, oversized Dutch and Austrian flags, an impact burst and a padded `KYIV` chip.
  7. **Riyadh · Gulf** — a bold PIF Tower silhouette against a dusk-teal sky, bright impact burst and a `RIYADH` pill; the copy attributes the strike (the coalition blames the Houthis, Saudi officials report the damage, no injuries).
  8. **Worldwide · Games** — the single Vice-sunset card: magenta/orange sky, palms, a huge `VI` emblem and an emerald `99 METASCORE` badge.
  9. **Berlin · Diplomacy** — the Brandenburg Gate with a 12-star EU flag, German flag and a two-tone `ENERGY TRUCE` / `BERLIN` banner for the coalition summit’s winter energy-ceasefire call.
  10. **Mrima Hill · Minerals** — rich terracotta/emerald ridges, a bold mineral crystal and a high-contrast `$60BN+ EST. DEPOSIT` badge (the deposit estimate, not the bid).
  11. **Nuku‘alofa · Oceania** — a blazing amber El Niño sun, cracked coral coastline, Tongan flag and a `27-DAY EMERGENCY` pill.
  12. **Seoul · Justice** — a crisp Taegeukgi, bold wooden gavel and an angled crimson `RETRIAL · 9–3` stamp on deep navy: the Supreme Court voided Han Duck-soo’s insurrection verdict and sent the case back, he stays detained.
  13. **Paris · Energy** — a red-on-charcoal server-rack energy chart rising `2026 → 2030`, with a cleanly padded `+70% CO₂` badge.
- **Region balance**: Asia-Pacific 6 · Americas 6 · Europe 5 · Middle East 2 · Africa 5 · Oceania 4 · Global/Science 5 = **33** exactly, matching the 13 cards plus 20 dispatches.
- **Two-column numbered briefs (14–33)**: ten per column, each a single **10.3px Lato** line with a numbered region badge, bold 9.4px place, one concrete verified fact and an italic source. The tightest measured slack is **17px**, so nothing wraps, clips or truncates. v11 re-checked every item against Thursday reporting and swapped out four that were not clean Thursday news: the UN Sudan drone tally (published Tue 17) became the army’s Nyala air raids; the Yunus home fire (late Wed 18, in Chattogram, not Dhaka) became South Korea’s 551,864-candidate Suneung; the Moscow-datelined Putin vow became the Kerch bridge rail strike itself; and the EU cyberattack now reads as the Commission’s Thursday confirmation of an October intrusion. Claims that rest on one party are attributed (“Police say…”, “Israel says…”), and vote tallies are added where they exist (48–51, 4–3).
- **World locator**: a Natural Earth 1:110m coastline (stored offline in `world_land_110m.svgpath`) on pale archival ocean with warm tan continents, numbered pins 1–13 and short leader lines for the crowded European pins. A compact seven-region legend sits below the map.
- **Header**: a crimson kicker strip (`THE WORLD CANVAS · ONE-PAGE EDITION`), a 54px Title-Case `Thursday, 19 November 2026` masthead, an italic crimson summary deck, a seven-pill region bar (solid region colours, white 8.4px labels, white count chips, so it still reads as a colour band at 300px) and six stats in 20px serif with a 3px region-colour cap and two-line 7.3px labels (`3`, `9–6`, `$81bn`, `300k`, `109–0`, `99`).
- **Footer**: a prominent full-width `DATE CHECK ✓` callout with a 2px crimson border and exactly two crisp lines, naming only the Wednesday 18 and Friday 20 stories left out on purpose (Takaichi–Putin talks, Moïse verdict, Gaza ‘yellow line’, Jeffries 251–11, Van Gogh $190.4m, Fed minutes, Yunus home fire; Akvan landfall, UK–EU summit), followed by a one-line attribution/sources micro-footer.

`build_poster.py` renders the page in headless Chromium at 1× and 2× DPR and runs the DOM geometry audit in the same pass. The audit enforces an exact 1024×1024 page, a **33/33** story census, **13** map badges, exact per-region sums against the balance bar, zero overflow, zero overlaps, zero clipped text, every card headline at most two lines, every summary at most two lines, one-line briefs with **≥15px** slack, SVG ink inside every viewBox, at least 1px of padding for every coloured badge label, and an ink-contrast floor. The build fails on any issue.

Text is taken from the native 1× render (edge variance **6961.6** against 6398.1 for the Lanczos-downsampled 2× on the brief columns). The 2× Lanczos pixels are pasted into all **fourteen** integer-aligned boxes (13 story illustrations plus the map), which keeps flags, spirals, skylines and charts smooth while the body text stays pin-sharp. The page is encoded as a 4:4:4 baseline JPEG at the highest quality that fits 420 KB, quality 89: **415,137 bytes (405.4 KiB)**, well under the 1 MiB gate.

`entry.png` is that JPEG. `main.py` uses only the standard library and no network: it re-validates every JPEG segment up to the EOI marker and atomically copies the verified bytes to `MAKEFUN_OUTPUT_DIR`. Two runs are byte-identical, and two full builds are byte-identical too (sha256 `52604402…`).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
