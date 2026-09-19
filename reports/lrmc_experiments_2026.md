# LRMC Experiments (2026): xG margin, graduated OT confidence, held-out calibration, self-consistent fitting

**Date:** 2026-09-07
**Status:** All four experiments run to completion. Two clean negatives (xG, self-consistent fitting), one inconclusive-by-design (graduated OT confidence — the test data structurally can't exercise it), one genuine partial win (held-out calibration). **All four ship OFF by default** — none is an unambiguous win on all three metrics, matching this project's established bar for flipping a default.

This follows the four ideas raised when the user (whose LRMC professors at Georgia Tech originated the method) asked what LRMC adaptations hadn't been tried yet, given the project's history: OT/SO fixed vote (`ot_confidence`) is the one adaptation that worked (`reports/lrmc_hockey_adaptation.md`); empty-net correction, conference-silo shrinkage, and naive in-sample Platt calibration were all tried and rejected (`reports/lrmc_hockey_adaptation.md`, `reports/lrmc_calibration.md`, `reports/lrmc_empty_net.md`).

All four backtests use the standard 5-year/20-split protocol (2021-22 through 2025-26, Jan1/Jan15/Feb1/Feb15 cutoffs, 8,371 pooled test games) established in `reports/five_year_backtest_and_di_filter.md`, with paired per-game significance tests (paired t-test on Brier/LogLoss, McNemar's on accuracy) against each feature's off-by-default baseline.

## 1. xG-based margin (`LRMC.use_xg`) — clean negative

Already wired in `src/rankings/lrmc.py` but never validated. **Real per-game xG coverage is 0% before 2024-25** (0/1173 games in 2023-24, etc.) and only 90%/46% for 2024-25/2025-26 — with `fallback_to_goals=True`, this mechanically dilutes any pooled effect, so results are reported both pooled (all 5 seasons) and restricted to the two xG-covered seasons.

| | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| LRMC_Classic (pooled) | 58.60% | 0.19393 | 0.71556 |
| LRMC_xG (pooled) | 58.38% | 0.19491 | 0.71793 |
| LRMC_Classic (xG-covered seasons only) | 57.96% | 0.18885 | 0.69537 |
| LRMC_xG (xG-covered seasons only) | 57.41% | 0.19130 | 0.70134 |

xG margin is **significantly worse** on Brier and LogLoss in both views (p<1e-11), and directionally worse on accuracy (not significant, p=0.09). Reproducible: `python -m analysis.exploratory.lrmc_xg_backtest`. **Shipped: `use_xg=False` remains the default** (unchanged — this was already the default; the finding is simply that turning it on has no basis).

## 2. Graduated OT confidence by period count (`HockeyLRMC.graduated_ot_confidence`) — inconclusive by design

New feature: decays the OT/SO fixed vote toward a coin flip as overtime periods increase (`conf(periods) = ot_confidence * decay^(periods-1)`), using the `OT_Info` column ('OT'/'2OT'/'3OT'/'5OT') already present in scraped data. `decay=1.0` is verified to reproduce the existing fixed-vote behavior exactly (a strict generalization).

**Result: no measurable effect in the standard backtest — but for a structural reason, not because the idea is wrong.** All 70 multi-OT games (2OT/3OT/5OT) in the 15-season archive fall between March 3 and April 10; only 2 fall before the earliest cutoff tested (Feb 15), and none before March 1. Multi-OT games essentially only occur in late-season/conference-tournament play, which is always in the TEST window under the Jan-Feb cutoff protocol this project uses — they're never in a training window, so this feature (which only affects how *training* games are weighted when fitting ratings) had zero games to act on in any of the 20 splits. The pooled comparison came back byte-identical across every decay value tested, confirming this exactly. Reproducible: `python -m analysis.exploratory.lrmc_graduated_ot_backtest`.

**This is not a negative result — it's an untested one.** Validating it would require either a late-season cutoff (March-ish, which this project has avoided for unrelated reasons — postseason/tournament games complicate the test set) or a different validation approach (e.g., directly measuring rating sensitivity to a multi-OT game via a leave-one-out-style perturbation, independent of the backtest protocol). **Shipped: `graduated_ot_confidence=False`** (default off — the mechanism is implemented and tested for correctness, but has no backtest evidence either way).

## 3. Held-out calibration (`HockeyLRMC.held_out_calibration`) — genuine partial win, still not a clean win

The naive in-sample calibration attempt (`reports/lrmc_calibration.md`) failed because it calibrated against the same games used to estimate the ratings. This version mirrors Massey's held-out beta fit (`massey.py`) exactly: fit ratings on the first ~80% of the training window (by date), calibrate the `[is_home_ice, log_ratio] → outcome` logistic only against the remaining ~20%'s actual outcomes — genuinely out-of-sample relative to those ratings.

**A real bug found and fixed while validating this:** the shared `_fit_logit_safe` helper rejects any fit with `|coefficient| > 5.0`, a threshold tuned for a different use case (`_learn_params_home_and_home`'s margin fit). The held-out calibration's raw log-ratio is independently known (from the original diagnosis) to need roughly a 4-5x scale correction — a fitted scale of ~5.17 was being rejected as "unstable" every time, silently falling back to the uncalibrated baseline with zero indication anything had gone wrong. Fixed by adding a `max_abs_param` parameter to `_fit_logit_safe` (default unchanged at 5.0 for existing callers; held-out calibration passes 15.0, with the reasoning documented inline). Caught via a regression test (`test_held_out_calibration_produces_nondegenerate_fit_on_real_data`) asserting the fit actually fires on real data, not just that it doesn't crash.

**Result (shrinkage sweep, pooled n=8,371, vs. shrink=0.0 baseline):**

| Shrinkage | Accuracy | McNemar p | Brier diff | Brier p | LogLoss diff | LogLoss p |
|---|---:|---:|---:|---:|---:|---:|
| 0.25 | 62.73% (+0.8pp) | **0.0012** | **−0.00157** | **1.5e-18** | +0.01303 | 3.9e-13 |
| 0.5 | 62.45% | 0.12 | **−0.00247** | **1.1e-12** | +0.02791 | 8.5e-15 |
| 0.75 | 62.41% | 0.21 | **−0.00268** | **1.3e-07** | +0.04444 | 1.8e-16 |
| 1.0 | 62.11% | 0.68 | **−0.00226** | 6.1e-4 | +0.06251 | 3.8e-18 |
| (baseline) | 61.93% | — | — | — | — | — |

At `shrinkage=0.25` specifically: accuracy improves significantly (+0.8pp, p=0.0012) AND Brier improves significantly (p<1e-17) — a genuinely better result than the in-sample attempt on two of three metrics. But **LogLoss degrades monotonically with any nonzero shrinkage**, the same qualitative failure mode as the in-sample version, just far less severe (0.705→0.771 at shrink=1.0, vs. the in-sample version's 0.704→0.851). Interpretation: the held-out fit is a real, generalizable correction on average, but occasionally produces a confidently wrong call that LogLoss's asymmetric penalty punishes heavily — the same accuracy/Brier-vs-LogLoss tension already documented elsewhere in this project (e.g. Dixon-Coles' kappa sweep). Reproducible: `python -m analysis.exploratory.lrmc_held_out_calibration_backtest`.

**Shipped: `held_out_calibration=False`** (default off, consistent with this project's "must not lose on any of the three metrics" bar) — but this is the one experiment worth revisiting if accuracy or Brier is ever prioritized over LogLoss for a specific purpose (e.g., bracket-style win/loss projections rather than probability-calibrated output).

## 4. Self-consistent iterative fitting (`HockeyLRMC.iterative_fit`) — clean, decisive negative

The most structural idea: base LRMC is a strict one-pass pipeline (fit alpha/beta once, build the transition matrix once, take its stationary distribution once) that never checks whether the resulting ratings agree with the probabilities used to build them — unlike KRACH, whose win-probability formula IS the model that was fit (self-consistent by construction). This experiment iteratively blends the original margin-based per-game probability with the Bradley-Terry-implied probability (`r_home / (r_home + r_away)`) from the *current* iteration's ratings, rebuilding the transition matrix each round until ratings converge. `iterative_blend=0.0` is verified to reproduce the non-iterative baseline exactly (ratings match to <1e-9); nonzero blends converge cleanly and geometrically (verified via direct iteration trace — no oscillation, ratio ≈ the blend factor per step).

**Result: unambiguous, severe negative, growing monotonically with blend:**

| Blend | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| 0.0 (baseline) | 61.93% | 0.1891 | 0.7050 |
| 0.25 | 61.51% | 0.1900 | 0.7068 |
| 0.5 | 60.33% | 0.1924 | 0.7116 |
| 0.75 | 58.09% | 0.2015 | 0.7317 |
| 1.0 | 53.78% | 0.3106 | 1.4247 |

Every nonzero blend is significantly worse on every metric (p<0.03 at blend=0.25, p<1e-10 elsewhere); blend=1.0 (fully self-consistent, margin evidence only informs the starting point) collapses to barely-better-than-a-coin-flip accuracy and a LogLoss of 1.42 — double the baseline. Reproducible: `python -m analysis.exploratory.lrmc_iterative_backtest`.

**Why this makes sense, not just "it didn't work":** KRACH's self-consistency is a genuine MLE fixed point — maximizing a well-defined likelihood has a unique, well-behaved optimum. This blend is not maximizing anything; it's a heuristic feedback loop where the "evidence" partially becomes the model's own current belief. Once an early-season rating drifts slightly (from a small sample or a single upset), each iteration partially reinforces that drift rather than correcting it against independent evidence — a genuine echo-chamber failure mode, distinct from and worse than the calibration-only decoupling this method was meant to fix structurally. **Shipped: `iterative_fit=False`.**

## Summary

| Experiment | Verdict | Shipped default |
|---|---|---|
| xG-based margin | Clean negative (worse Brier/LogLoss, p<1e-11) | Off (unchanged) |
| Graduated OT confidence | Inconclusive — test data structurally excludes it | Off |
| Held-out calibration | Partial win (accuracy+Brier up, LogLoss down) | Off |
| Self-consistent iterative fit | Clean, severe negative | Off |

None of the four is a new default. The one adaptation that has ever actually beaten `LRMC_Classic` remains the original OT/SO fixed-vote fix from `reports/lrmc_hockey_adaptation.md`. Held-out calibration is the one idea here worth revisiting for a specific, non-default use case (accuracy/Brier-optimized rather than probability-calibrated output). Graduated OT confidence would need a different validation approach (a late-season cutoff, or a targeted perturbation test) before it can be judged at all — it currently has neither positive nor negative evidence.

## Bugs found along the way

- `_fit_logit_safe`'s `max_abs_param=5.0` guard (tuned for the margin-fit use case) was silently rejecting held-out calibration's genuinely-diagnosed ~5x scale correction, making it a silent no-op. Fixed by parameterizing the threshold per caller.

## Regression testing

21 new/updated tests in `tests/unit/test_hockey_lrmc.py` (was 9, now 21) covering: graduated OT confidence (default-off, decay math, `decay=1.0` reproduces baseline, missing-column fallback), held-out calibration (default-off, `shrinkage=0.0` reproduces baseline, guard-rail fallback on tiny data, non-degenerate fit on real data), and iterative fitting (default-off, `blend=0.0` reproduces baseline exactly, convergence within `max_iter`, ratings actually change when `blend>0`). Full suite: 116/116 passing.
