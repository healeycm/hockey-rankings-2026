# Fixed Massey: A New Best Model, By All Three Metrics

## Summary

The pre-fix `Massey` implementation had three hardcoded, never-validated
constants. The most consequential — `beta=0.15` in `predict()`'s
margin-to-probability sigmoid — never hurt accuracy at all (accuracy
depends only on the sign of the predicted margin) but badly hurt Brier and
LogLoss, which is exactly why Massey topped the model roster on accuracy
while looking mediocre on calibration. Fixing all three constants (fit, not
guessed) turns Massey into **the best model in the codebase on every
metric**, beating HockeyBT, ELO, and KRACH on accuracy, Brier, and LogLoss
simultaneously — all 9 comparisons statistically significant.

## Correcting an earlier claim in this project

Prior reports in this project asserted, based on the HockeyLRMC margin work
and the empty-net ablation, that "margin doesn't help in hockey." **That was
too broad a generalization from two negative results.** What those
experiments actually showed is narrower: margin doesn't help as a Markov-
chain vote weight, and empty-net correction of margins doesn't help. Goal
differential in a well-posed linear system (Massey) turns out to carry the
best signal of anything tested in this project. The lesson is really: *how*
margin is used matters enormously, not whether it's used at all.

## The three bugs

From [src/rankings/massey.py](../src/rankings/massey.py) as it shipped:

1. **`beta = 0.15`**, hardcoded in `predict()`, literal comment: "generic
   hockey slope beta ~ 0.15." A guess, never fit, never validated.
2. **`home_ice_advantage = 0.2`**, hardcoded in `fit()`, subtracted from
   home margin before the linear solve. Also never fit — the same class of
   gap identified in KRACH (`reports/hockey_bt_plan.md`) and in the base
   LRMC's alpha/beta.
3. **No regularization.** The classic Massey rank-deficiency (uniform
   rating shift doesn't change any prediction) was handled by overwriting
   the system's last row with a sum-to-zero constraint — a valid but
   inflexible fix that leaves no room for shrinkage.

Since (1) only rescales the logit and never flips its sign, it was
invisible to accuracy — exactly the pattern that made Massey look like a
free lunch on accuracy and a laggard on calibration.

## The fix

Rewrote `fit()`/`predict()` to jointly fit what used to be guessed:

- **Home-ice** is now an extra column in the least-squares design matrix,
  solved jointly with team ratings (one ridge-regularized linear system,
  via `np.linalg.lstsq`'s minimum-norm solution — which also replaces the
  old manual sum-to-zero constraint row with something that generalizes
  cleanly to `ridge_lambda > 0`).
- **Beta** is fit via a **genuinely held-out temporal split within the
  training window**: fit ratings on the first ~80% of training games by
  date, then fit beta by 1-D MLE against those ratings' *out-of-sample*
  predictions on the remaining ~20%. This is deliberately not a naive
  in-sample refit — `reports/lrmc_calibration.md` already showed that
  fitting a probability-scale parameter on the same games used to fit the
  ratings can overfit and make LogLoss *worse*. Guard rails fall back to
  the old fixed constant when there's too little data for a clean split.
- **Ridge regularization** (`ridge_lambda`) on team ratings, swept and
  tuned like HockeyBT's MAP prior.

Setting `fit_home_ice=False, ridge_lambda=0.0, fit_beta=False` reproduces
the original implementation **exactly** (own correctness gate, verified to
machine precision — see `tests/unit/test_massey.py`).

## Ridge sweep (5-year/20-split backtest)

| Config | Accuracy | Brier | LogLoss |
|---|---|---|---|
| Original (unfixed) | 64.82% | 0.1850 | 0.6672 |
| Fixed, λ=0.0 | 64.91% | 0.1721 | 0.6330 |
| Fixed, λ=0.5 | 64.89% | 0.1720 | 0.6323 |
| **Fixed, λ=1.0** | **64.90%** | **0.1721** | **0.6322** |
| Fixed, λ=2.0 | 64.85% | 0.1722 | 0.6324 |
| Fixed, λ=4.0 | 64.77% | 0.1725 | 0.6332 |
| Fixed, λ=8.0 | 64.68% | 0.1731 | 0.6348 |

Brier/LogLoss improve dramatically from the beta/HIA fit alone (even at
λ=0); ridge adds a further small, flat improvement in the 0.5–2.0 range.
Shipped `λ=1.0` — round number, in the flat optimum, not the single
best-scoring sweep point (avoiding over-fitting the choice of λ to this
exact sweep, the same reasoning used for HockeyBT's κ).

## Definitive test: fixed Massey vs. the rest of the roster

Pooled, paired per-game test (8,371 test games,
`python -m analysis.exploratory.massey_backtest`):

| vs. | Accuracy | Brier | LogLoss |
|---|---|---|---|
| **vs HockeyBT** | 64.59% vs 63.91% (McNemar p=0.041) | **0.1734 vs 0.1768 (p=2.9e-9)** | **0.634 vs 0.641 (p=2.5e-6)** |
| **vs ELO** | 64.59% vs 63.44% (McNemar p=0.006) | **0.1734 vs 0.1751 (p=0.021)** | **0.634 vs 0.640 (p=0.0017)** |
| **vs KRACH** | 64.59% vs 63.73% (McNemar p=0.021) | **0.1734 vs 0.1865 (p=2.5e-38)** | **0.634 vs 0.675 (p=5.0e-32)** |

**All 9 comparisons favor Massey, and all 9 reach statistical
significance** (p<0.05 at minimum, most far below that). This is a stronger
result than HockeyBT's earlier "wins on the two biggest gaps, ties on the
rest" — fixed Massey wins outright across the board, against the full
roster, not just the previous two top models.

## Why the linear-regression approach works this well

Massey directly regresses observed goal differential onto team-strength
differences — the natural quantity for a rate/count signal like scoring —
whereas Bradley-Terry-family models (KRACH, HockeyBT) only ever see win/loss
(or win/tie/loss). Once the probability *mapping* from that margin is
properly calibrated (the actual bug that was suppressing this model's real
performance), the extra information in the margin comes through cleanly.
This doesn't contradict the LRMC/empty-net findings — those were about
specific ways of *processing* margin (Markov-chain vote transfer;
empty-net-goal subtraction) that turned out not to help. A direct linear
regression of margin onto strength, properly calibrated, is a different and
evidently better way to use the same underlying signal.

## Shipped

- `config.yaml`: `massey:` config block updated to the validated defaults
  (`fit_home_ice: true, ridge_lambda: 1.0, fit_beta: true`). No
  `run_system.py` changes needed — `Massey` was already dispatched.
- `src/rankings/massey.py` ships with the validated defaults built in; pass
  `fit_home_ice=False, ridge_lambda=0.0, fit_beta=False` explicitly to
  reproduce the original (buggy) behavior.
- Tests: [tests/unit/test_massey.py](../tests/unit/test_massey.py) (9 tests)
  — the correctness gate, home-ice fit/recovery, beta fit/fallback
  behavior, ridge shrinkage, and a guard on the shipped defaults.
- Reproducible: [tests/massey_backtest.py](../tests/massey_backtest.py)
  (`python -m analysis.exploratory.massey_backtest`) — ridge sweep + the paired
  significance tests above.

## Open items

1. **This raises the bar for the Dixon-Coles work** (see
   `reports/goal_based_ranking_plan.md`) — it now needs to beat fixed
   Massey's numbers (64.59% pooled accuracy / 0.1734 Brier / 0.634 LogLoss),
   not the pre-fix per-metric leaders that motivated that plan.
2. **beta/HIA are still tuned on the same historical data used for final
   evaluation** (same acknowledged limitation as HockeyBT's kappa) — no
   separate held-out set exists in this project yet.
3. **The 80/20 temporal split fraction for beta calibration** was not
   itself swept — a reasonable default, not a tuned hyperparameter. Worth
   revisiting if beta's stability across splits becomes a concern.
