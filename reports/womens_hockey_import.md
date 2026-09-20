# Women's Hockey Import — Data, Analysis, and Website Integration

**Date:** 2026-09-07
**Status:** Phases 1–3 complete and verified as scoped below. Several follow-on items are explicitly deferred (see "Open Items").

## 1. Summary

This adds NCAA women's D-I hockey (2021-22 through 2025-26) to the ranking system alongside the existing men's pipeline, using **physical separation** (`data/raw/women/`, `data/processed/women/`, `output/women/`) rather than a shared file with a `Division` column. That choice was made deliberately: this project has hit three separate silent-data-mixing bugs in the past from shared paths / missing filters, and a fourth was in fact found and fixed during this work (see §4). Every division-aware code change defaults to `division='men'` and was verified not to change men's behavior.

## 2. Phase 1 — Import

- **Source verified live, not assumed:** USCHO publishes a structurally identical composite schedule for women's hockey at `https://www.uscho.com/scoreboard/division-i-women/{season}/composite-schedule/` (mirroring the men's URL pattern with `women` substituted for `men`). No new scraper logic was needed — [`scraper.py`](../src/data/scraper.py) was parameterized with a `division` argument that threads through the URL, the raw-data output directory, and season-size validation bounds.
- `EXPECTED_FULL_SEASON_GAMES` is now a dict keyed by division; women's bounds (600–1000 games/season) were set from the 5 seasons actually scraped (717, 776, 808, 811, 829 games).
- **Data scraped:** `data/raw/women/games_2021_2022.csv` through `games_2025_2026.csv` — 5 real seasons. One transient scrape failure (2022-23, a marionette/geckodriver hiccup) resolved on retry; not a data-availability issue.
- **Team roster built (`data/teams/team_info_women.csv`, 45 teams):** union of non-exhibition teams appearing across all 5 seasons (52 raw), minus 7 teams that appeared only in 2021-22 as one-off scheduling fillers and are not genuine D-I-for-hockey programs (Anna Maria, Castleton, Hamilton, Johnson & Wales, Lake Forest, Potsdam, Wesleyan). Cross-checked against external sources: the 45-team count and NEWHA's status as an NCAA-granted D-I-for-hockey-only conference (its members are otherwise D-II schools) were both confirmed via web search rather than assumed — this is a genuinely different situation from the men's "non-DI opponent" exclusion pattern and was not handled by blindly reusing that logic.
- **Team metadata (`data/teams/college_hockey_teams_women.csv`, 45 rows):** logos populated for 38/45 teams by reusing existing men's-program logo assets (36 by exact name match, plus 2 manual fixes for men's/women's USCHO naming variants: "Minnesota Duluth"→`minnesota-duluth.png`, "LIU"→`long_island.png`). The remaining 7 women's-only programs (Assumption, Delaware, Franklin Pierce, Post, Saint Anselm, St. Michael's, Syracuse) fall back to the site default logo. **Conference field was deliberately left blank** — an initial assumption about Penn State's women's-hockey conference turned out to be wrong, so rather than guess for all 45 teams, the field is left empty pending a verified source.

## 3. Phase 2 — Analysis

- Processed via [`processor.py`](../src/data/processor.py) (now `division`-aware) into `data/processed/women/games_archive.csv` (3,866 games) and `upcoming_schedule.csv` (0 rows — the 2026-27 women's schedule has not been scraped yet).
- **5-year / 20-split backtest** ([`analysis/exploratory/womens_hockey_backtest.py`](../analysis/exploratory/womens_hockey_backtest.py)) run on the validated 5-model roster (Massey, HockeyBT, KRACH, ELO, RPI), reusing the men's-tuned hyperparameters as a first pass rather than re-sweeping (explicitly scoped out — see Open Items). Split-averaged results:

| Model    | Accuracy | Brier  | LogLoss | ECE    | Reliability | Resolution |
|----------|---------:|-------:|--------:|-------:|------------:|-----------:|
| Massey   | 0.7544   | 0.1339 | 0.5244  | 0.0747 | 0.0094      | 0.0640     |
| HockeyBT | 0.7473   | 0.1342 | 0.5275  | 0.0568 | 0.0056      | 0.0596     |
| KRACH    | 0.7450   | 0.1414 | 0.5587  | 0.0993 | 0.0149      | 0.0619     |
| ELO      | 0.7428   | 0.1409 | 0.5520  | 0.0706 | 0.0082      | 0.0550     |
| RPI      | 0.7279   | 0.1418 | 0.5467  | 0.0824 | 0.0112      | 0.0574     |

**Findings:**
- Massey remains the best model by Accuracy, Brier, and LogLoss — the core "Massey is the best model" finding from men's hockey transfers to women's hockey.
- Overall accuracy is noticeably higher than men's hockey's typical ~68-70% range in this project's men's backtests, consistent with women's D-I hockey's flatter/smaller field producing more predictable outcomes.
- HockeyBT, not Massey or ELO, has the best calibration (lowest ECE/Reliability) for women's hockey — a genuine difference from the men's-hockey calibration ranking, worth investigating further before treating Massey as the calibration-optimal choice as well as the accuracy-optimal one.
- **Update (2026-09-20):** the paired-significance gap flagged below is closed — see `research/womens_comparison/reports/p0_2_paired_significance.md`. `BacktestEngine` now has `save_predictions()`, and the same paired t-test (Brier/LogLoss)/McNemar's (Accuracy) tests the men's-hockey scripts already run are wired into this backtest. Result: Massey beats KRACH, ELO, and RPI on all three metrics with real significance (McNemar p=0.004–<0.0001, paired-t p<1e-8 on Brier/LogLoss); Massey vs. HockeyBT is significant on accuracy (p=0.017) but NOT on Brier/LogLoss (p=0.71, p=0.26) — consistent with, not contradicting, HockeyBT's separately-measured calibration edge noted above.

- **Rankings generated** ([`src/generate_womens_rankings.py`](../src/generate_womens_rankings.py), standalone — not yet wired into `run_system.py`'s orchestrator) for the most recently completed season (2025-26) across all 5 models, written to `output/women/rankings/{Model}/rankings_{Model}_{date}.csv` in the exact format the website expects. Passed a domain sanity check: Massey ranked Ohio State #1, Wisconsin #2.

## 4. Critical bug found and fixed during this work

`BaseRanker`'s DI-team filter uses a ≥50%-overlap heuristic to decide whether a supplied team list looks like real production data (its original purpose: catching e.g. unit-test fixtures with unrelated names). **This heuristic cannot distinguish "wrong division" from "right division"**, because men's and women's programs mostly share school names. Verified directly: instantiating a women's-data model without explicitly overriding the team-list path applied the **men's** `team_info.csv` by default and silently dropped 175 of 797 games (622 kept); wrapping the same instantiation in `using_di_team_path(WOMENS_TEAM_INFO)` kept all 797 games, 0 dropped.

**Fix:** [`base_ranker.py`](../src/rankings/base_ranker.py) gained a `using_di_team_path(path)` context manager plus module-level `_ACTIVE_DI_TEAM_PATH` state, letting all ~13 existing model classes become division-aware without touching their constructors (none of them forward `**kwargs` to `super().__init__()`, so changing signatures wasn't an option). `using_di_team_path()` is now **mandatory**, not optional, for every women's-data script — every one written in this phase (backtest, ranking generator) wraps model instantiation in it. Regression tests for this mechanism were added in [`tests/unit/test_division_support.py`](../tests/unit/test_division_support.py) (context-manager scoping/reset, explicit-kwarg precedence, and a same-name-in-both-divisions scenario that specifically reproduces the failure mode above).

## 5. Phase 3 — Website

- [`webpage/utils/data_loader.py`](../webpage/utils/data_loader.py): added division-aware path resolution (`_data_dir`, `_output_dir`, `_team_info_path`, `_college_teams_path`, all defaulting to `'men'` = original unnamespaced path) and threaded a `division='men'` parameter through `get_available_models`, `get_logo_url`, `load_records`, `load_rankings`. `ensure_logos_in_assets()` now loops over both divisions' team files. **Not touched (scoped out):** `get_current_season`, `load_projections`, `load_team_analysis`, `get_team_schedule`, `load_rank_distribution`.
- [`webpage/pages/home.py`](../webpage/pages/home.py): added a Men's/Women's `RadioItems` toggle. Selecting a division refreshes the model dropdown (the two divisions have different validated model rosters — women's only has the 5-model set above, not the full ~13-model men's roster) and reloads the rankings table, logos, and team links accordingly.
- [`webpage/pages/team_detail.py`](../webpage/pages/team_detail.py): **explicitly guarded**, not wired. Since team-detail data loading (`get_team_schedule`, `load_team_analysis`, `load_rank_distribution`, `load_rankings`) is not yet division-aware, and many schools field both a men's and a women's program under the identical name (e.g. "Wisconsin"), silently proceeding for `division="women"` would render the men's team's page under a women's-hockey link — a correctness bug, not a cosmetic one. The page now returns an explicit "not available yet" message for `division="women"` instead.
- Verified via direct Python-level invocation of `layout()` and the `@callback` functions (after importing `app` first, since `dash.register_page()` requires prior app instantiation) — raw HTTP testing of `/_dash-layout` was tried first and abandoned, since for a Pages-based Dash app that endpoint only returns the app shell, not per-page content (client-side routing renders it).

## 6. Regression testing

- Full backend suite: **83/83 passing** (79 pre-existing + 4 new in [`test_division_support.py`](../tests/unit/test_division_support.py) covering the `using_di_team_path` mechanism specifically), confirming zero behavior change for men's hockey from any of the `base_ranker.py` / `data_loader.py` / `processor.py` / `scraper.py` changes.

## 7. Open items (explicitly deferred, not oversights)

- Hyperparameter re-sweeping for Massey/HockeyBT/RPI/KRACH specifically on women's hockey, rather than reusing men's-tuned defaults.
- ~~Conference assignments for `college_hockey_teams_women.csv`~~ — done 2026-09-20, see `research/womens_comparison/reports/p0_1_conference_data.md` (45/45, cross-checked against 2+ independent sources per team, current-season only — not backfilled for realignment within the 5-year backtest window).
- Team-detail, projection, schedule, and rank-distribution pages for women's hockey — currently explicitly blocked with a placeholder message rather than wired incompletely.
- A `config.yaml` `system.division` key — division-awareness is currently all explicit-parameter/context-manager driven, not config-driven.
- Integrating `generate_womens_rankings.py` into `run_system.py`'s full orchestrator (currently a standalone script).
- Scraping the 2026-27 women's season once it becomes available (currently 0 upcoming games).
