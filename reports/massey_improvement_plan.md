# Plan: Further Improvements to Massey

**Date:** 2026-09-07
**Status:** Plan only — nothing implemented yet.

Massey is the current best model (`reports/massey_calibration_results.md`), but three structural gaps remain: it treats every appearance by a team as if the same goalie were in net, it gives every game in the season equal weight regardless of recency, and it doesn't distinguish 5-on-5 play from special-teams situations. Below is a staged plan for the goalie idea (the one asked for) plus two other concrete possibilities, in order of how much new data each needs.

## 1. Starting vs. backup goalie adjustment

### Why this is plausible
Massey's team rating is, by construction, an average over whatever mix of goalies actually played. If a team's backup goalie (a meaningfully worse stopper) starts a specific game — common on the second night of a weekend back-to-back, or after a starter injury — the team's true expected performance that night is measurably different from its season-average rating, and Massey has no way to know that.

### Data (confirmed feasible — checked a live box score before writing this)
`collegehockeynews.com` box scores already carry a "Goalies" table (goalie name, saves, goals against, minutes played per goalie who appeared) below the team stats CHN scraper already parses (`src/data/advanced_metrics_scraper.py`). This is the same page `Home_xG`/`Away_xG`/`Home_ENG`/`Away_ENG` already come from — extending the existing per-game scrape to also pull the goalie table is additive, not a new scraper.

**Coverage caveat, same one that limited the xG experiment (`reports/lrmc_experiments_2026.md`):** `data/raw_advanced/` currently only has 2024-25 and 2025-26. Goalie/save tables are a more basic box-score element than xG (which needs shot-location data), so they may well exist further back in CHN's archive — worth checking coverage across more seasons *before* committing to a validation design, since 2 seasons may not give enough backtest power for a clean signal.

### Metric
Raw save% is confounded by team defense quality (a great defense makes any goalie's save% look better). Two options, in order of rigor:
1. **MVP — shrunk raet save%:** each goalie's saves/shots-faced, regressed toward the team (or league) average with a Bayesian prior weighted by shots faced (heavy shrinkage early season, light shrinkage once a goalie has played enough). Cheap, no new data beyond the goalie table itself.
2. **Better — Goals Saved Above Expected (GSAx):** per-game expected-goals-against (already scraped, since `Home_xG`/`Away_xG` model shot quality against each team) minus actual goals allowed, attributed to whichever goalie played, summed/averaged per goalie with the same shrinkage. This nets out defense quality and reuses infrastructure you already have — the more defensible metric, worth building once coverage is confirmed adequate.

### Integration into Massey
Massey is a linear system (`A @ ratings = margin`) that already fits home-ice as one extra column (`fit_home_ice`). The goalie adjustment slots in the same way: for each game, add a covariate `goalie_delta_home - goalie_delta_away` (each team's starting goalie's rate relative to that team's own season-average goalie performance), and fit one scalar `goalie_weight` jointly with team ratings and home-ice via the same ridge regression — architecturally identical to how home-ice was fit, not a new modeling paradigm.

### The hard part: future games don't have a confirmed starter
Backtesting uses the actual historical starter, but a live projection for next Friday doesn't know who's starting yet. Plan: default to each team's rolling (trailing-N-game) goalie-usage-weighted average delta when no starter is confirmed — which converges to ≈0 extra signal beyond what the team rating already captures — and only apply a meaningful adjustment when either (a) a clear, stable #1 vs #2 timeshare pattern exists, or (b) a starter is confirmed close to game day (would need a separate, lightweight "confirmed starters" data source, likely not available far in advance). **Be upfront that this feature's practical value is mostly in-hindsight (retrodiction/backtesting) and near-game-day, not in far-out season projections** — that's a real, permanent limitation of the idea, not an implementation gap to fix later.

### Validation
Standard project protocol: `use_goalie_adjustment` as an off-by-default, ablatable Massey config flag; 5-year/20-split backtest (or however many seasons coverage allows) against baseline Massey; paired significance tests on accuracy/Brier/LogLoss. Given the coverage caveat, this may need to run on 2 seasons only initially, clearly labeled as lower-powered than the project's usual 20-split standard (same disclosure pattern used for the xG experiment).

## 2. Two other possibilities

### A. Time-decay (recency) weighting — cheapest to try, no new data
Checked: **Massey currently has zero time-decay support** — every game in the training window gets equal weight regardless of how long ago it was played, unlike LRMC (which has a `time_decay_halflife` mechanism, though it's never been validated as beating `LRMC_Classic` either — see `reports/lrmc_experiments_2026.md`, item left open). A team that started poorly and has since improved gets an average rating that under-credits its current form. Plan: add the same weighted-ridge-regression treatment LRMC already has (`weight = 2^-(days_ago/halflife)` on each row of the design matrix), as an off-by-default `time_decay_halflife` config on Massey, backtested the same way LRMC's version should have been (a halflife sweep, not just one guess). Zero new data required — pure reuse of the `Date` column already in every game.

### B. Rest / back-to-back schedule fatigue — cheap, no new data
College hockey is scheduled heavily in Friday/Saturday weekend series; a team playing its second game in ~24 hours, or on the road with less rest than its opponent, plausibly performs a bit worse than its full-strength rating implies. Plan: compute `days_since_last_game` per team per game (pure `Date`/`Season` arithmetic, already available for all 15 seasons — no coverage caveat, unlike the goalie/special-teams ideas) and a `second_game_of_set` flag, then add them as one or two more fitted covariates in the same linear system, exactly like home-ice. This is the cheapest of the three to actually test, since it needs no new scraping at all — worth doing first as a quick, well-powered check before investing in the goalie data pipeline.

### C. 5-on-5 (score-effects-adjusted) margins — moderate, partially-available data
The empty-net scraper already parses each goal's situation tag (blank/PP/SH/3x3/EN) from CHN's goal-by-goal table (`extract_empty_net_goals`'s docstring in `src/data/advanced_metrics_scraper.py`) — it just doesn't keep anything except the EN count today. A team that wins 4-2 with 2 power-play goals is a different (weaker, at 5-on-5) team than one that wins 4-2 at even strength, and Massey currently can't tell the difference. Plan: extend the same parsing to tag every goal's manpower situation, compute each game's 5-on-5-only margin alongside the actual margin, and either (a) fit Massey on 5v5 margins directly as an alternative target, or (b) add net special-teams goal differential as a separate covariate the same way as home-ice/goalie/rest above. Same 2-season coverage caveat as the goalie idea, since it needs the CHN goal-by-goal table.

## Suggested order

1. **B (rest/fatigue)** first — cheapest, no coverage caveat, immediately backtestable on the full 5-year/20-split protocol.
2. **A (time decay)** next — also cheap, no new data, same full-protocol backtest.
3. Check CHN's actual historical goalie-table coverage before committing further; if it extends well past 2024-25, **goalie adjustment** and **C (5v5 margins)** become much better-powered and worth building in that order (goalie first, since it was explicitly asked for and has a clearer mechanism; 5v5 margins second).

Not attempted here: broader injury/roster-availability adjustments beyond goalies (data isn't reliably available), and anything requiring a real-time confirmed-starters feed (out of scope for this project's data sources).
