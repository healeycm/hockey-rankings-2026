# Ensembling: Two Real Bugs Found, One Honest Negative Result

## Summary

Built `Ensemble` ([src/rankings/ensemble.py](../src/rankings/ensemble.py)),
combining Massey/HockeyBT/KRACH/ELO/RPI via simple averaging or stacked
logistic regression. Checked error correlation first (0.94–0.99 across all
pairs — pre-registered modest expectations), then found and fixed two real
bugs in the stacking implementation along the way. **Final result: neither
combination method beats Massey.** Pooled paired test (n=8,371): no
significant difference from Massey on accuracy, Brier, or LogLoss
(p=0.30–0.52). Reported as the honest result it is.

## Step 0: is there any diversity to exploit?

Before building anything, checked pairwise correlation of each model's
prediction error on the pooled 5-year backtest
(`python -m analysis.exploratory.ensemble_backtest`):

|          | Massey | HockeyBT | KRACH  | ELO    | RPI    |
|----------|--------|----------|--------|--------|--------|
| Massey   | 1.0000 | 0.9891   | 0.9706 | 0.9822 | 0.9872 |
| HockeyBT | 0.9891 | 1.0000   | 0.9856 | 0.9780 | 0.9857 |
| KRACH    | 0.9706 | 0.9856   | 1.0000 | 0.9386 | 0.9674 |
| ELO      | 0.9822 | 0.9780   | 0.9386 | 1.0000 | 0.9780 |
| RPI      | 0.9872 | 0.9857   | 0.9674 | 0.9780 | 1.0000 |

**Every pair is above 0.93.** These models extract very similar signal from
the same games — they differ mainly in functional form (Bradley-Terry vs.
linear regression vs. iterative averaging), not in what information they
use (Massey is the only one using goal margin rather than win/loss/tie
alone). This set modest expectations before any backtest was run: with this
little diversity, classical ensembling headroom is small.

## Bug 1: unconstrained stacking is a multicollinearity disaster

First implementation: logistic regression of the outcome on each base
model's logit-transformed prediction (standard stacking), fit via
unconstrained MLE (`statsmodels.Logit`) on a genuinely held-out temporal
split — same discipline as Massey's beta and RPI's beta.

**Result: catastrophic.** 59.6% accuracy — worse than every individual base
model, including the weakest one (KRACH at 63.7%). The fitted weights
included a large **negative** coefficient on HockeyBT (a perfectly decent
model on its own). This is a textbook multicollinearity failure: with
inputs this correlated, an unconstrained regression can assign large
offsetting positive/negative weights that fit the small calibration-holdout
well but don't generalize at all.

**Fix:** L2-regularized fit via `scipy.optimize`, with weights constrained
non-negative (a negative weight on a reasonably-good model is itself a
symptom of overfitting to holdout noise, not a real correction — excluded
from the search space entirely).

## Bug 2: regularizing toward the wrong target

First regularization attempt penalized `sum(weights^2)` (standard ridge —
shrink toward zero). Swept the ridge strength:

| kappa | Accuracy | Brier | LogLoss |
|---|---|---|---|
| 0.5 | 63.5% | 0.176 | 0.645 |
| 1.0 | 61.9% | 0.181 | 0.658 |
| 2.0 | 60.4% | 0.185 | 0.667 |
| 5.0 | 58.2% | 0.190 | 0.677 |
| 10.0 | 57.7% | 0.191 | 0.681 |

**Monotonically worse with more regularization** — the opposite of what
ridge is supposed to do. Root cause: penalizing weights toward zero, on
*standardized* features, drives predictions toward the intercept alone — a
near-constant, uninformative prediction. That's not the "safe fallback";
simple averaging (equal weight `1/n` on each model) is. Standard ridge
shrinks toward the wrong point entirely for a stacking ensemble.

**Fix:** penalize `sum((weights - 1/n_models)^2)` instead — shrinks toward
the simple-average ensemble as `kappa → ∞`, not toward nothing. Re-swept:

| kappa | Accuracy | Brier | LogLoss |
|---|---|---|---|
| 0.5 | 63.9% | 0.177 | 0.643 |
| 1.0 | 63.9% | 0.177 | 0.644 |
| 2.0 | 64.0% | 0.177 | 0.644 |
| 5.0 | 64.0% | 0.177 | 0.645 |
| 10.0 | 64.0% | 0.177 | 0.645 |

Stable now (not degenerating), but **plateaus below both Massey (64.9%) and
simple averaging (64.7%) at every kappa tested** — properly regularized
stacking still doesn't help here, for the reason established in Step 0:
there just isn't enough diversity among these models for a learned
weighting to beat an unweighted one.

## Final result: ensembling doesn't help, at all

Pooled, paired per-game test (8,371 test games, simple-average method vs.
Massey):

| | Accuracy | Brier | LogLoss |
|---|---|---|---|
| Ensemble (average) | 64.40% | 0.17377 | 0.63479 |
| Massey | 64.59% | 0.17338 | 0.63417 |
| **p-value** | 0.52 (McNemar) | 0.30 | 0.52 |

**No comparison reaches significance**, and Massey is nominally better on
all three — averaging in four weaker-but-correlated models doesn't hurt
much, but it doesn't help either. It's a dead heat with the top individual
model, not an improvement.

## Interpretation

This isn't a failure to find something — it's the expected consequence of
Step 0's diagnostic, confirmed. Ensembling earns its keep when base models
make different *kinds* of mistakes; here, every model is fundamentally
estimating the same latent "team strength" from the same win/loss/tie/goal
data, so their mistakes are highly correlated by construction. The one
model with genuinely different input information (Massey, via goal margin)
is also simply the best individual model — there's no "diverse-but-weaker"
model left over whose errors would meaningfully cancel Massey's.

## Shipped

- `config.yaml`: `ensemble:` config block added, default `method: "average"`
  (the fitting-overfit-free option). **Not added to `active_models`** — no
  predictive benefit over Massey alone.
- `run_system.py`: dispatches `Ensemble` if added to `active_models`.
- `src/rankings/ensemble.py` ships with `method='average'`,
  `base_models=['Massey','HockeyBT','KRACH','ELO','RPI']`.
- Tests: [tests/unit/test_ensemble.py](../tests/unit/test_ensemble.py)
  (7 tests) — including explicit regression guards for both bugs found
  (non-negative weight constraint, and the standardization stats being
  stored and re-applied identically at prediction time).
- Reproducible: [tests/ensemble_backtest.py](../tests/ensemble_backtest.py)
  (`python -m analysis.exploratory.ensemble_backtest`).

## Open items

1. **Only 5 of the project's ~13 models were included as ensemble
   candidates** (the strongest ones). A wider net (including NPI,
   DixonColes, Colley, Markov) wasn't tried — given the correlation
   diagnostic, weaker/more-correlated additions seem unlikely to help, but
   this wasn't tested directly.
2. **The stacking holdout fraction (20%) and its temporal-split design**
   weren't swept independently of the ridge parameter — plausible that a
   different split fraction changes the calibration-noise/data-volume
   tradeoff, though unlikely to overturn the core finding (lack of
   diversity, not lack of data, is the limiting factor here).
3. **A genuinely different ensembling target** — e.g. combining models at
   the *rating* level (before any model's own sigmoid) rather than the
   probability level — wasn't tried, though it's unclear this would
   introduce new diversity rather than just reformulating the same
   correlated signal.
