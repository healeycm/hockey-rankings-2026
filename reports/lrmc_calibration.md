# Calibrating HockeyLRMC's Predictions

## Summary

Attempted to fix the calibration gap identified in
`reports/five_year_backtest_and_di_filter.md` §3 (HockeyLRMC's accuracy
matches KRACH/NPI but its Brier/LogLoss don't). Built a Platt-scaling-style
calibration step, backtested it, and **the fix doesn't work as a default** —
LogLoss gets monotonically worse with any amount of it applied. The
diagnosis behind it is confirmed correct; the specific remedy tried isn't.
Shipped disabled (`calibrate_predictions=False`), documented, and left
available/tunable rather than deleted.

## The diagnosis (recap)

KRACH's win-probability formula, `K_i/(K_i+K_j)`, *is* the Bradley-Terry
model whose likelihood was maximized to produce the ratings — fitting and
prediction share one self-consistent functional form. LRMC's rating
estimation (a margin-fit logistic feeding a Markov chain's stationary
distribution) and its prediction formula
(`sigmoid(hia + log(r_home/r_away))`) are two unrelated steps that were
never jointly validated — nothing guarantees the raw log-ratio is on the
right scale to use directly as a logit.

## What was built

`HockeyLRMC._calibrate_predictions()`, called at the end of `fit()`: fits a
2-parameter logistic regression of actual game outcomes on
`[is_non_neutral, raw_log_ratio]`, using the same games used to estimate the
ratings (in-sample Platt scaling). No separate intercept term — a neutral
matchup between equally-rated teams is constrained to predict exactly
50/50, which is the correct no-information default, not something worth
estimating away.

A single-slice check (2024-25 season, Jan-15 cutoff) confirmed the
diagnosis directly: the fitted scale came out to **4.66x** — the raw
log-ratio needed to be multiplied by nearly 5x to match KRACH's spread of
predicted probabilities (std 0.24 vs. HockeyLRMC's uncalibrated 0.10). The
fitted home-ice term (0.206) barely moved from the existing `|alpha|`
(0.204) — confirming the problem really was the scale, not the intercept.

## Why it doesn't work anyway: overfitting

Ran the unshrunk fit through the 5-year/20-split backtest, then added
`calibration_shrinkage` (0 = ignore the fit, 1 = trust it fully) to fight
likely overfitting and swept it.

> Numbers below are the post-fix re-run after a later session found that
> `BacktestEngine` never passed `history_df` (see
> reports/lrmc_empty_net.md § "Bug found along the way"). The conclusion was
> identical before and after the fix.

| Shrinkage | Accuracy | Brier | LogLoss |
|---|---|---|---|
| 0.0 (off) | 62.39% | 0.1891 | **0.7050** |
| 0.1 | 62.78% | 0.1877 | 0.7174 |
| 0.2 | 62.71% | 0.1868 | 0.7311 |
| 0.3 | 62.80% | **0.1864** | 0.7460 |
| 0.5 | 62.74% | 0.1867 | 0.7788 |
| 0.75 | 62.46% | 0.1890 | 0.8251 |
| 1.0 (full fit) | 62.34% | 0.1926 | **0.8764** |

LogLoss got dramatically *worse*, not better — despite the diagnosis being
right.

LogLoss degrades **monotonically** from the very first unit of shrinkage —
even 0.1 already costs more than the entire Brier gain is worth. Brier does
improve slightly (~1% relative) up to shrink≈0.2-0.3 before also reversing,
but not enough to offset the LogLoss cost.

**Root cause:** the calibration data and the rating-estimation data are the
same games. This isn't genuine Platt scaling on held-out predictions — it's
mostly re-fitting whatever noise is already baked into that specific
training window's ratings, which then doesn't generalize to the test games.
A correct version would calibrate on a genuinely held-out split (temporal
holdout within the training window, or k-fold), which wasn't attempted here
— bigger lift than this pass covered.

## Where this leaves it

- `HockeyLRMC.conf['calibrate_predictions']` defaults to `False`.
  `calibration_shrinkage` defaults to `1.0` (irrelevant while calibration is
  off, but set to the "trust the fit fully" value so anyone who flips
  calibration on without also setting shrinkage gets the worst-tested
  configuration rather than a silently-better-than-tested one).
- Both are left in place and documented (in `hockey_lrmc.py`'s config
  comments and `_calibrate_predictions()`'s docstring) rather than deleted —
  someone optimizing specifically for Brier over LogLoss could reasonably
  choose shrink≈0.2-0.3; the code doesn't have to relitigate this if they
  do.
- Regression tests
  ([tests/unit/test_hockey_lrmc.py](../tests/unit/test_hockey_lrmc.py)):
  confirms the default matches the pre-calibration baseline, and that
  `calibration_shrinkage=0.0` discards the fit exactly.
- Reproducible sweep:
  [tests/lrmc_calibration_sweep.py](../tests/lrmc_calibration_sweep.py)
  (`python -m analysis.exploratory.lrmc_calibration_sweep`).

## Open item

A genuinely held-out calibration (temporal split: estimate ratings on the
first ~80% of the training window by date, fit the Platt-scaling step only
on predictions for the remaining ~20%, using ratings that didn't see those
specific games) is the textbook fix for exactly this overfitting failure
mode and hasn't been tried. Worth doing if the Brier/LogLoss gap to
KRACH/NPI becomes a priority — but it requires re-fitting ratings on a
sub-window rather than a single extra logistic regression, a meaningfully
bigger change than this pass.
