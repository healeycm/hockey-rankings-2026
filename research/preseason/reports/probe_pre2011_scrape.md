# Probe: does USCHO's archive scrape cleanly before 2011-12?

**Pre-registered question:** `games_archive.csv` currently starts at 2011-12. Does `src/data/scraper.py`'s existing URL pattern (`.../scoreboard/division-i-men/{season_code}/composite-schedule/`) resolve to real, distinct, full seasons further back, and if so, how far?

**Method:** `research/preseason/experiments/probe_pre2011_scrape.py` — read-only, reuses production's `get_data_for_season()`/`validate_scraped_season()` unmodified, writes only to `research/preseason/data/pre2011_probe/`. Probed 13 seasons, 1998-99 through 2010-11, in ~1-year steps working backward. See that script's docstring for the full isolation guarantee.

## Result: works 2001-02 through 2008-09, plus 2010-11. 2009-10 is a trap. 2000-01 and earlier hard-fail.

| Season | Rows | Verdict |
|---|---|---|
| 2010-11 | 1204 (40 look duplicated) | Usable |
| **2009-10** | 1204 (40 look duplicated) | **NOT usable — see below** |
| 2008-09 | 1202 (36 look duplicated) | Usable |
| 2007-08 | 1218 (34 look duplicated) | Usable |
| 2006-07 | 1212 (34 look duplicated) | Usable |
| 2005-06 | 1220 (35 look duplicated) | Usable |
| 2004-05 | 1193 (37 look duplicated) | Usable |
| 2003-04 | 1197 (37 look duplicated) | Usable |
| 2002-03 | 1233 (37 look duplicated) | Usable |
| 2001-02 | 1190 (37 look duplicated) | Usable |
| 2000-01 | 0 rows, `NoSuchElementError` (no `#app` div) | Hard fail |
| 1999-2000 | same | Hard fail |
| 1998-99 | same | Hard fail |

**2000-01 and earlier are a genuine wall**, not a formatting quirk — the page simply doesn't have the expected content structure. USCHO's composite-schedule archive doesn't go back that far in a scrapeable form.

**2009-10 is not a clean miss, it's a silent wrong answer.** Fetching `.../20092010/composite-schedule/` returns a page that parses to **byte-for-byte identical content** to `.../20102011/composite-schedule/` (verified: same 1204 rows, same 40 "duplicates," `.equals()` is `True` after dropping the `Season` column). USCHO's site is aliasing the 2009-10 URL to the 2010-11 schedule. `validate_scraped_season()`'s date-range check caught this automatically (it flagged all 1204 rows as outside the expected 2009-08-01–2010-06-01 window, because the dates are actually 2010-11 dates) — **that check is the reason to trust "usable" above for the other 9 seasons**: a pairwise identical-content check across every adjacent probed season confirms 2009-10/2010-11 is the *only* aliased pair.

**Net gain if adopted:** 9 more usable seasons (2001-02 through 2008-09, plus 2010-11), extending the archive from 14 to 23 usable seasons, with a mandatory exclusion/skip for 2009-10.

## A second, unplanned finding: production data (2011-12 through 2020-21) has the same duplicate-row pattern this probe was watching for

While checking whether the pre-2011 seasons' "~35-40 duplicate rows per season" was itself a red flag, I checked the currently-used raw files for comparison. It isn't specific to old data:

| Season | Rows | Duplicate rows (same Date/Home/Visitor) |
|---|---|---|
| 2011-12 → 2020-21 (9 currently-used seasons) | ~600-1260 each | **34-41 per full season** (18 for the shortened 2020-21), a consistent ~3% |
| 2021-22 → 2026-27 (6 currently-used seasons) | ~960-1235 each | **0** |

This is a **real, previously unflagged production data-quality fact**, not a research-only artifact: 9 of the 14 seasons `games_archive.csv` already uses for every ranking model and every backtest report in this project (`reports/*_backtest*`, `reports/*_results.md`) contain low-single-digit-percent duplicate game rows. The likely mechanism is the same one caught above — USCHO's composite-schedule page appears to have listed some games twice in a way that changed (was fixed, or the scraper's parsing of it changed) somewhere around the 2020-21/2021-22 boundary. This wasn't found by this probe's actual object of study; it's a byproduct of double-checking the probe's own suspicious duplicate counts against known-good data.

**This is left unfixed, per the research-isolation rule** (research reads `src/`/`data/`, never edits them). It's flagged here for your decision, not patched. If you want it fixed, that's a small, separate, production-side task (likely a `.drop_duplicates(subset=['Date','Home_Team','Visitor_Team'])` in `src/data/processor.py`'s archive-building step, plus checking whether any past report's numbers move meaningfully once ~35 duplicate games/season are removed) — not part of this research workspace's scope.

## Recommendation
- **Adopt for research use:** 2001-02 through 2008-09 and 2010-11 (9 seasons), added to `research/preseason/data/` as extended history for P1 (history prior) and P2 (O/D split) tuning-season backtests only — more tuning-season data, doesn't touch the holdout seasons (2021-22 → 2025-26) at all.
- **Exclude 2009-10 permanently** from any future collection attempt — it doesn't have a distinguishable identity via this URL pattern.
- **Don't pursue pre-2001** — confirmed hard wall.
- **Decide whether to fix the production duplicate-row issue** (2011-12 → 2020-21) — separate from this probe's scope, but worth a decision since it affects every historical report in `reports/`.
