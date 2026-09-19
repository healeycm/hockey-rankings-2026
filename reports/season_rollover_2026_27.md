# 2026-27 Season Rollover

## Summary

Rolled the system from the 2025-26 to the 2026-27 season: centralized every
season-dependent literal that was previously hardcoded per-year, scraped and
ingested the 2026-27 schedule, updated the DI team roster, and refreshed the
backtest/critique report. The whole pipeline (`run_system.py`) runs cleanly
end-to-end against the new season config.

## 1. Centralized season handling

Previously the season appeared as hardcoded literals in nine different
places, two of which (`npi.py`'s conference-tournament cutoff, `simulator.py`'s
simulated-game date stamp) would have failed *silently* if left at their
2025-26 values — no error, just quietly wrong output once real 2026-27 games
existed.

New: [src/utils/season.py](../src/utils/season.py) — single source of truth
for season-derived values (`season_start_year`, `season_end_year`,
`conf_tourney_cutoff`, `default_season_end_date`, `get_current_season_code`).
Everything below now derives from a season code instead of a literal date:

| File | Before | After |
|---|---|---|
| [config.yaml](../config.yaml) `system.season` | `20252026` | `20262027` (blank `""` now auto-derives from today's date) |
| [src/run_system.py](../src/run_system.py) | required `system.season` | falls back to `get_current_season_code()` if blank |
| [src/rankings/npi.py](../src/rankings/npi.py) conf-tourney cutoff | `Timestamp('2026-03-01')` | `conf_tourney_cutoff(season)`, derived per-season from the games' own `Season` column |
| [src/analysis/simulator.py](../src/analysis/simulator.py) sim-game date | fixed `Timestamp('2026-03-30')` for every simulated game | uses each game's **real scheduled date** from `upcoming_schedule_df`; falls back to `default_season_end_date()` only if a row lacks one. (This is also a correctness fix independent of the rollover — time-decay LRMC variants were weighting every simulated game as if played on the same day.) |
| [src/analysis/npi_vs_krach.py](../src/analysis/npi_vs_krach.py) | `CURRENT_SEASON = 20252026` hardcoded | `resolve_current_season(games_df)` — picks the most recent season with ≥50 games, so it advances automatically once 2026-27 has real results instead of pointing at an empty season |
| [src/data/advanced_metrics_scraper.py](../src/data/advanced_metrics_scraper.py) `SEASONS` | `["20242025", "20252026"]` | derived as (previous, current) via `get_current_season_code()` |
| [src/data/krach_validation.py](../src/data/krach_validation.py) `current_end_year` | `2026` | `season_end_year(get_current_season_code())` |
| [src/data/generate_team_mapping.py](../src/data/generate_team_mapping.py) input filenames | `games_2025_2026.csv` / `chn_krach_2026.csv` | derived from current season; also now defaults to writing a **draft** file instead of silently overwriting the hand-curated `team_info.csv` (see below) |
| [webpage/app.py](../webpage/app.py) footer | `© 2026` | `© {current year}` |

Also fixed: `BACKTEST_SEASONS` in `npi_vs_krach.py` included `20162017`, for
which `data/raw/games_2016_2017.csv` does not exist — `filter_season` was
silently returning an empty frame for it every run, so the report's "21
season-cutoff pairs" was actually only 21 out of an intended 24. Removed the
missing season and added `20252026` (now complete). The report now correctly
covers 24 season-cutoff pairs — see the regenerated `reports/npi_critique.md`.

## 2. `generate_team_mapping.py` overwrite guard

This script regenerates `team_info.csv` — the live, hand-curated DI team
list used by NPI's and KRACH's DI filters, conference-code logic, and the
logo pipeline. It previously wrote directly over that file on every run with
a pure fuzzy-match, discarding any manual corrections (team name fixes,
mismatches the fuzzy matcher got wrong, etc.). It now defaults to writing
`data/teams/team_info_draft_<year>.csv` instead; overwriting the live file
requires an explicit `--write` flag.

## 3. Data acquisition

Ran the scraper against USCHO's 2026-27 composite schedule
(`python -m src.data.scraper --season 20262027`) — this succeeded; Selenium's
built-in driver management pulled geckodriver automatically, no manual setup
needed. Result: 964 rows, saved to `data/raw/games_2026_2027.csv`.

Added a validation pass (`validate_scraped_season()` in
[src/data/scraper.py](../src/data/scraper.py)) that now runs automatically
after every scrape: checks game count against an expected full-season range
(skipped for the season currently in progress), missing/blank team names,
duplicate games, unparseable dates, and dates falling outside the expected
season window. The 2026-27 scrape passed cleanly.

Ran `python -m src.data.processor` to fold this into the pipeline:
- `games_archive.csv` (completed games only) — **unchanged**, 0 rows for
  20262027, since every scraped row is `Is_Final=False` (season hasn't
  started — today is 2026-09-07, opening games are late September).
- `upcoming_schedule.csv` — 929 new future games added.

Ran `python -m src.run_system` end-to-end against the new config: it
correctly reports "No data found for season 20262027" and exits cleanly
rather than crashing — expected, since no games have been played yet. This
will start producing real rankings automatically once games are played and
the archive is refreshed (no code changes needed).

## 4. Roster / conference changes for 2026-27

Verified via web search (USCHO/CHN/NCAA sources), then cross-checked against
the actual scraped schedule data:

- **Mercyhurst dropped its D-I men's program** after 2025-26 (budget-driven).
  Confirmed absent from the scraped 2026-27 schedule. **No action needed** —
  `team_info.csv` intentionally still lists Mercyhurst (it's used to
  DI-filter *historical* seasons too; removing it would have silently
  dropped all of Mercyhurst's games from every past-season backtest back to
  2011-12). Since Mercyhurst simply has no 2026-27 games, it will not appear
  in that season's rankings without any list changes.
- **Tennessee State launches its inaugural D-I program** in 2026-27, as an
  independent (first HBCU D-I men's hockey program). Added to
  `data/teams/team_info.csv`. **However, TSU does not yet appear anywhere in
  the scraped 2026-27 schedule** — their games may not be posted to USCHO's
  composite schedule yet this early in September. Re-scrape closer to their
  season opener and re-check.
- **Maryville University** will field a partial "transition/hybrid" D-I
  schedule (~20 games) in 2026-27 ahead of full D-I membership in 2027-28.
  **Deliberately NOT added** to `team_info.csv` — not confirmed whether the
  NCAA counts transition-period games toward opponents' official NPI, and
  including them would risk polluting other teams' SOS with games that don't
  officially count. **Flagging for your decision**, not resolved
  automatically. Also absent from the current scrape.
- **St. Thomas moves from CCHA to NCHC**, effective 2026-27. **No code
  change needed** — confirmed directly in the scraped data: St. Thomas's
  games are already tagged `Type=nt` (NCHC's code) rather than `cc2`. The
  conference map in `npi.py` is built fresh from each season's own game
  `Type` codes, so this realignment (and any future one) is picked up
  automatically.

`team_info.csv` team count: 63 → 64 (added Tennessee State; Mercyhurst not
removed per above).

## Open items

1. **Tennessee State's schedule isn't in USCHO's composite feed yet.**
   Re-scrape periodically as the season approaches; if it's still missing by
   October, check USCHO directly rather than assuming the team stays absent.
2. **Maryville's DI/NPI-counting status is unconfirmed.** Revisit once the
   NCAA's official stance on transition-period games is clear, or once real
   games start showing results.
3. **`data/teams/team_info_draft_2027.csv` was not generated in this pass**
   (didn't re-run `generate_team_mapping.py` — the manual additions above
   covered the known changes). Worth running once real CHN 2026-27 data
   exists, to catch any team-name-format drift between USCHO and CHN for the
   new season, then diff against the live file rather than overwrite it.
