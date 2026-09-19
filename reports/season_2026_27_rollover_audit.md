# 2026-27 Season Rollover: Current-Season-Only Audit

**Date:** 2026-09-08

## Ask
Update the site for the 2026-27 season (uscho.com's division-i-men/20262027 composite schedule), move toward weekly updates, and verify records/rankings/projections are scoped to the current season only.

## Bug found and fixed: `DataLoader.get_schedule()` had zero season filtering

`get_schedule()` (the function behind `data/processed/upcoming_schedule.csv`) returned every `Is_Final=False` row across **all 15 seasons** of raw data, with no season filter at all. Any game that never got marked final for any reason — a scraper miss, a postponement, or a Frozen Four bracket slot left as a placeholder ("Clarkson/Dartmouth") once the real matchup was decided — stayed in "upcoming" forever, regardless of season.

**Confirmed on disk before fixing anything:** `upcoming_schedule.csv` had 6 stray rows mixed in with the real 2026-27 schedule — a 2014-01-10 Cornell/Massachusetts game, a 2014-12-13 Minnesota State/Princeton game, a 2024-02-13 Stonehill/Saint Anselm game, and 4 leftover 2025-26 NCAA tournament bracket placeholders dated into April 2026.

**Fix:** `get_schedule()` now filters to one season — the newest season present in the raw archive by default, or an explicit `target_season` if passed. `process_data()` (its only caller anywhere in the codebase — checked) needed no changes. Verified: regenerating `upcoming_schedule.csv` now produces exactly 922 rows, 100% tagged `20262027`, zero stray rows.

## What was already correctly scoped (verified, not assumed)

- **Records** (`load_records()`): already filters `games_archive.csv` by `config.yaml`'s `system.season` for men's hockey — confirmed correct.
- **Rankings/projections generation** (`run_system.py`): already filters `season_df = full_history[full_history['Season'] == target_season]` before fitting any model — confirmed correct, no cross-season leakage into the ratings themselves. (LRMC-family models' `fit_source: 'history'` deliberately uses multi-season data for the alpha/beta margin-calibration curve only, not for which games/teams determine ratings — an established, already-validated design choice, not a leak.)
- **`MonteCarloSimulator`**: never reads `upcoming_schedule.csv` directly — it only receives an already-filtered DataFrame from `run_system.py`, so it inherited the same protection automatically once the schedule-loader fix landed.

## Live verification

Ran the real pipeline end-to-end against the actual USCHO 2026-27 page:
```
Navigating to: https://www.uscho.com/scoreboard/division-i-men/20262027/composite-schedule/
  - Found 965 rows for 20262027.
Validation OK: 964 games look consistent.
SUCCESS: Saved 964 games to games_2026_2027.csv
```
This is the exact URL and season you asked about. Processed cleanly into `upcoming_schedule.csv` (922 games post-exhibition-filter, all `20262027`).

**Rankings did not regenerate — correctly.** `run_system.py` reported "No data found for season 20262027" and produced 0 new rankings, because **zero 2026-27 games are marked final yet** (the season hasn't started — USCHO D-I men's play typically opens in early October). This is expected, not a bug: there's nothing to rank yet.

## Current state you should know about

`output/rankings/*` and `output/projections/*` still hold **2025-26 season data** (last dated 2026-03-31) — the website, if visited right now, shows last season's KRACH/Massey/etc. numbers with **blank W-L records** next to them (since records correctly returned 0 rows for the new season). Nothing on the site currently indicates these rankings are stale/from a prior season. This isn't a bug I can code around — there's genuinely no 2026-27 data to rank yet — but it's worth deciding how you want the site to look during this pre-season gap (leave last season's numbers up as-is, or add some "preseason / season starts October" indicator). Your call, not something I changed unprompted.

## Changes made to support weekly updates

- `config.yaml`: `data.scrape_latest` flipped from `false` to `true` — without this, a scheduled run would just reprocess whatever's already in `data/raw/` instead of pulling fresh USCHO scores, so weekly automation would silently never actually update.
- The automation built earlier this project (`scripts/daily_update.py`, `scripts/register_task.ps1`) is unchanged and ready — running `register_task.ps1` (elevated PowerShell, one-time) registers a daily 6 AM Windows Task Scheduler job. Not run automatically; that's your call to opt into whenever you're ready.

## Regression testing
Added `tests/unit/test_data_loader.py` (4 tests: stray older-season rows excluded, defaults to the newest season present, accepts an explicit `target_season`, still respects the pre-existing `Is_Final` filter alongside the new season filter). Full unit suite: 133/133 passing (was 129 before this fix).
