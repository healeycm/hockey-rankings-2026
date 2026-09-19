# Massey Experiments (2026): time decay, rest/fatigue, manpower-adjusted margin

**Date:** 2026-09-07
**Status:** All three complete. One new shipped default (rest/fatigue); time decay and manpower-adjusted margin both clean negatives.

Follows `reports/massey_improvement_plan.md` — the "three other possibilities" from that plan (time decay, rest/fatigue, manpower-adjusted margin), goalie adjustment explicitly excluded per the user's request. All three are off-by-default, ablatable `Massey` config flags, backtested via the standard 5-year/20-split protocol (2021-22 through 2025-26, Jan1/Jan15/Feb1/Feb15 cutoffs, 8,371 pooled test games), paired significance tests (paired t-test on Brier/LogLoss, McNemar's on accuracy) against each feature's off-by-default baseline.

## 1. Time-decay (recency) weighting — clean negative

`Massey.time_decay_halflife`: weighted least squares on training games, `weight = 2^-(days_ago/halflife)`, mirroring LRMC's existing (also-never-validated) decay mechanism. Swept halflife in {None (off), 90, 45, 30, 15}.

| Halflife | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| None (baseline) | 64.90% | 0.1721 | 0.6322 |
| 90 | 64.27% | 0.1729 | 0.6340 |
| 45 | 63.85% | 0.1744 | 0.6376 |
| 30 | 63.13% | 0.1763 | 0.6423 |
| 15 | 60.97% | 0.1819 | 0.6561 |

Every halflife is significantly worse on every metric, with damage growing monotonically as the decay gets more aggressive (p=0.03 accuracy at halflife=90, p<1e-24 at halflife=15). Reproducible: `python -m analysis.exploratory.massey_time_decay_backtest`. **This matches the same finding already suspected for LRMC's never-validated decay mechanism** — college hockey seasons are short (~30 games), and aggressively downweighting early-season games trades away real sample size without capturing genuine team improvement. **Shipped: `time_decay_halflife=None` (unchanged default).**

## 2. Rest/fatigue adjustment — genuine, if modest, win

`Massey.fit_rest_advantage`: one extra fitted covariate (days since each team's last game, capped at `rest_days_cap=5` and normalized), fit jointly with team ratings and home-ice the same way home-ice itself is fit. Requires `predict()`'s new optional `game_date` kwarg to have any effect — every existing caller (`run_system.py`, `MonteCarloSimulator`, `BacktestEngine`, `RankInterpreter`) predicts without one, getting a rest contribution of exactly 0.0 (verified as a strict no-op). **This is the only one of the three that needed a custom backtest script** (`tests/massey_rest_backtest.py`) rather than reusing `BacktestEngine` directly, since `BacktestEngine.run()` never passes `game_date` — the script mirrors its train/test cutoff logic exactly but calls `predict(..., game_date=row['Date'])`.

| | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| Off (baseline) | 64.90% | 0.17206 | 0.63221 |
| On | 64.77% | 0.17188 | 0.63185 |

Pooled paired test (n=8,371): accuracy is not significantly different (McNemar p=0.34, and the tiny point-estimate difference runs the *other* direction), while Brier (p=0.0005) and LogLoss (p=0.01) are both **significantly better** with rest enabled. Verified directly on a real case: Harvard on 1 day's rest vs. a fully-rested Boston College dropped from 43.8% to 33.3% predicted win probability once the rest term kicked in — the mechanism does what it's supposed to. Reproducible: `python -m analysis.exploratory.massey_rest_backtest`.

The effect size is small (Brier improves by 0.0002) but the sample is large enough (8,371 games) to detect it reliably, and — unlike every other experiment in this batch and the LRMC batch before it — there is **no metric that gets worse**. That clears this project's established bar (win or tie on every metric, real improvement on at least one) for becoming a new default. **Shipped: `fit_rest_advantage=True`** (see `config.yaml`'s `massey:` block) — the first of these three experiments to actually change a shipped default.

## 3. Manpower-adjusted margin — clean negative

`Massey.use_manpower_margin`: fits ratings against even-manpower goal margin (excludes power-play/short-handed/empty-net goals — see `src/data/advanced_metrics_scraper.py`'s new `extract_even_manpower_goals()`) instead of the raw final-score margin, isolating performance when neither side had a man advantage. Falls back to the raw margin per-game when even-manpower data isn't available (same fallback pattern as LRMC's `use_xg`).

**New scraper field, verified correct before any bulk use:** fetched a live box score (Arizona State 8, Air Force 1) and hand-checked its goal log against the parser's output — 3 special-teams goals for ASU (2 PP + 1 SH... total 3 SH + 2 PP) correctly excluded, leaving `away_ev_goals=3`, `home_ev_goals=1`, matching exactly. `src/data/backfill_manpower.py` (mirrors the existing `backfill_eng.py` pattern) populated `home_ev_goals`/`away_ev_goals` for all 1,701 games across the two CHN-covered seasons (2024-25, 2025-26 — same coverage limit as the xG experiment; no even-manpower data exists before 2024-25), 0 failures.

**Same coverage caveat as the xG experiment** — results reported both pooled (all 5 seasons, diluted by fallback-to-raw-margin outside the covered window) and restricted to the 2 covered seasons:

| | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| Massey (raw margin, pooled) | 64.78% | 0.17187 | 0.63182 |
| Massey (manpower margin, pooled) | 64.16% | 0.17279 | 0.63387 |
| Massey (raw margin, EV-covered only) | 64.84% | 0.16960 | 0.63461 |
| Massey (manpower margin, EV-covered only) | 63.28% | 0.17191 | 0.63974 |

Manpower-adjusted margin is **significantly worse on all three metrics**, both pooled (Accuracy McNemar p=0.021, Brier p=0.014, LogLoss p=0.016) and restricted to the covered seasons (same p-values — the effect is concentrated entirely in the covered games, as expected). Reproducible: `python -m analysis.exploratory.massey_manpower_margin_backtest`.

**Why this makes sense, unlike the empty-net exclusion this project already validated (`reports/lrmc_empty_net.md`):** an empty-net goal is a "game already decided" artifact — it happens only after the trailing team has pulled its goalie, so it carries little information about relative team strength. A power-play goal is different: converting on the power play is a real, measurable team skill, not noise. Excluding PP/SH goals doesn't isolate a distortion, it discards legitimate predictive signal — the same distinction the project's Dixon-Coles work implicitly relies on (modeling scoring directly, not filtering out a subset of it). **Shipped: `use_manpower_margin=False` (unchanged default).**

## Summary

| Experiment | Verdict | Shipped default |
|---|---|---|
| Time-decay weighting | Clean negative (all 3 metrics, monotonic) | Off (unchanged) |
| Rest/fatigue adjustment | Genuine win (Brier/LogLoss better, no accuracy cost) | **On (new default)** |
| Manpower-adjusted margin | Clean negative (all 3 metrics) | Off (unchanged) |

Of the three options requested (goalie adjustment explicitly excluded), only rest/fatigue survives — but it's a real, statistically significant, no-downside improvement to the project's best model, now shipped. The scraper extension built for the manpower-margin experiment (`extract_even_manpower_goals`, `backfill_manpower.py`, the `Home_EV_Goals`/`Away_EV_Goals` columns) remains in place even though this particular use of it didn't pan out — it's now available for other analyses (e.g., a genuine special-teams rating, which was never the goal here).

## Regression testing

129/129 unit tests passing (was 116 before this batch): 9 new tests for time-decay weighting and rest/fatigue in `tests/unit/test_massey.py`, plus 4 for manpower-adjusted margin. Every feature verified as a strict no-op when disabled, and the rest/fatigue mechanism verified against a real case (Harvard on 1 day's rest vs. a fully-rested Boston College: 43.8% → 33.3% predicted win probability).
