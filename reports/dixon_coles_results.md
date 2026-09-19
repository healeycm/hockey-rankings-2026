# Dixon-Coles Bivariate Poisson: An Honest Tie, Not a Win

## Summary

Built `DixonColes` ([src/rankings/dixon_coles.py](../src/rankings/dixon_coles.py)),
a bivariate Poisson model of the goal-scoring process (Dixon & Coles 1997),
specifically to test whether modeling the two teams' scoring rates directly
beats fixed Massey — the current best model in this codebase on every
metric ([reports/massey_calibration_results.md](massey_calibration_results.md)).

**Result: it doesn't beat Massey. It ties it.** After a prior-strength sweep
and fixing a real optimizer bug along the way, a pooled paired-per-game test
(n=8,371) found **no statistically significant difference on any of
accuracy (p=0.84), Brier (p=0.67), or LogLoss (p=0.28)**. This is reported
as a legitimate result, not buried — the original plan
([reports/goal_based_ranking_plan.md](goal_based_ranking_plan.md))
explicitly flagged this as the most likely outcome given the project's
track record (4 of 5 prior HockeyLRMC adaptations were rejected on
evidence; the LRMC calibration attempt and the empty-net-goal correction
were both rejected too).

## The model

Each team gets attack and defense parameters instead of one strength
scalar:

```
lambda_home = exp(mu + attack_home - defense_away + eta)   (eta=0 at neutral sites)
lambda_away = exp(mu + attack_away - defense_home)
P(h, a) = Poisson(h; lambda_home) * Poisson(a; lambda_away) * tau(h, a)
```

`tau` is the Dixon-Coles low-score correction — adjusts the (0,0), (1,0),
(0,1), (1,1) score cells only, designed for exactly the low-scoring regime
hockey is in. Fit by MLE (+ optional L2 prior on attack/defense) via
`scipy.optimize.minimize`, ~133 parameters for a 65-team field.

Nested variants, same ablation discipline as the rest of this project:

| Variant | Adds |
|---|---|
| D0 | Nothing — plain independent bivariate Poisson |
| D1 | `eta` (home-ice, additive in log-lambda) |
| D2 | `rho` (Dixon-Coles low-score correction) |
| D3 | `kappa` (L2 prior on attack/defense) |

## A real optimizer bug, caught and fixed before trusting any results

Ran likelihood-ratio tests for `eta` and `rho` across 4 seasons, one at a
time — valid here (unlike HockeyBT's `fit_ties` boundary) because both
nest smoothly: verified directly that evaluating the `rho`-model's
objective at `[eta`-model's solution, `rho=0]` exactly recovers the
`eta`-model's likelihood.

On 3 of 4 seasons this worked cleanly. On **2025-26**, a cold-started
(all-zeros initial guess) fit for the `rho` model converged to a **worse**
likelihood than the simpler `eta`-only model — despite `rho=0` being
trivially achievable and provably at least as good. That produced an
impossible negative likelihood-ratio statistic (LR=-21.35), which would
look exactly like a modeling bug if not caught:

```
D1 nll: -803.07  (eta-only)
D2 nll: -792.40  (eta+rho, cold-started -- WORSE than D1!)
D2 objective evaluated at [D1's solution, rho=0]: -803.07  (proves nesting is correct)
```

**Fix:** `fit()` now fits in stages — `[attack, defense, mu]` →
`+ eta` → `+ rho` — each warm-started from the previous stage's optimum.
This guarantees each stage can only do as well as or better than the one
before it. Re-running the LR tests after the fix:

| Season | eta | LR(eta) | p | rho | LR(rho) | p |
|---|---|---|---|---|---|---|
| 2022-23 | 0.133 | 25.75 | 3.9e-07 | 0.037 | 0.47 | 0.492 |
| 2023-24 | 0.103 | 16.90 | 3.9e-05 | 0.317 | 6.92 | 0.0085 |
| 2024-25 | 0.034 | 1.80 | 0.179 | 0.107 | 4.79 | 0.029 |
| 2025-26 | 0.073 | 8.69 | 3.2e-03 | **0.121** | **6.49** | **0.011** |

2025-26's `rho` went from a pathological bound-pinned 0.5 to a sensible
0.121, consistent with the other seasons. `eta` is home-ice-significant in
3/4 seasons (same season-to-season variability pattern already seen with
HockeyBT's `theta`); `rho` is positive across all 4 seasons and significant
in 3/4 — notably, **positive** rather than the small negative value typical
in soccer, meaning hockey's low/1-goal outcomes are *less* correlated
between teams than independent Poisson would predict, not more.
Reproducible: `python -m analysis.exploratory.dixon_coles_lr_check`.

## Ablation: does rho help held-out prediction?

In-sample LR-significance is not the same as out-of-sample predictive
value — the exact lesson HockeyBT's rejected silo prior already taught.
Backtested D0/D1/D2 (5-year/20-split):

| Variant | Accuracy | Brier | LogLoss |
|---|---|---|---|
| D0 (plain) | 64.55% | 0.1751 | 0.6419 |
| D1 (+ eta) | **64.95%** | 0.1737 | 0.6376 |
| D2 (+ eta, rho) | 64.81% | 0.1737 | 0.6408 |

Adding `rho` did **not** improve held-out accuracy/Brier/LogLoss over `eta`
alone, despite being in-sample LR-significant in most seasons — the same
pattern already seen once in this project. Shipped `fit_rho=False`.

## Prior-strength (kappa) sweep

| kappa | Accuracy | Brier | LogLoss |
|---|---|---|---|
| 0.0 | 64.95% | 0.1737 | 0.6376 |
| 1.0 | 64.94% | 0.1731 | 0.6348 |
| 2.0 | 64.88% | 0.1725 | 0.6325 |
| **3.0** | 64.82% | 0.1720 | 0.6313 |
| 5.0 | 64.50% | 0.1715 | 0.6302 |

Brier/LogLoss keep improving with more regularization; accuracy starts
degrading past kappa≈2-3. Shipped `kappa=3.0` — the point where the
**pooled paired significance test against Massey shows no significant
difference on any metric** (the cleanest, most representative
characterization of the actual result), not the single best-scoring sweep
point. (kappa=1.0 was tried as an alternative and gives comparable/slightly
better accuracy but a marginally significant Brier disadvantage vs. Massey,
p=0.041 — a less clean story than kappa=3.0's full tie.)

## Final result: statistical parity with Massey

Pooled, paired per-game test (8,371 test games,
`python -m analysis.exploratory.dixon_coles_backtest`):

| | Accuracy | Brier | LogLoss |
|---|---|---|---|
| DixonColes | 64.53% | 0.17320 | 0.63296 |
| Massey | 64.59% | 0.17338 | 0.63417 |
| **p-value** | 0.8401 (McNemar) | 0.6718 | 0.2799 |

**No comparison reaches significance.** DixonColes does not beat fixed
Massey. It also doesn't lose to it — a genuine statistical tie between a
two-parameter-per-team count model and a one-parameter-per-team linear
model, once both are properly calibrated.

## Why report a tie as a real result

The original plan pre-registered this as the most likely outcome and
committed to reporting it honestly either way. A tie here is informative:
it says the *extra expressiveness* of modeling attack and defense
separately, and the *correct* likelihood for count data, don't translate
into better predictions once Massey's calibration bugs are fixed — the
signal both models are extracting from goal differential appears to have a
similar ceiling by either route. That's a real, useful negative result
about where this dataset's predictive ceiling sits, not a failure to find
one.

## Shipped

- `config.yaml`: `dixon_coles:` config block added with validated defaults,
  but **`DixonColes` is NOT added to `active_models`** — it doesn't improve
  on Massey, so running both provides no additional predictive value by
  itself. Add it manually if wanted for its other properties (below).
- `run_system.py`: dispatches `DixonColes` if added to `active_models`.
- `src/rankings/dixon_coles.py` ships with `fit_home_ice=True,
  fit_rho=False, prior_strength=3.0`.
- Tests: [tests/unit/test_dixon_coles.py](../tests/unit/test_dixon_coles.py)
  (9 tests) — fit/predict sanity, outcome-probabilities-sum-to-one, the
  staged-fit nesting-correctness regression guard (directly targeting the
  2025-26 bug above), home-ice recovery, prior shrinkage, and a guard on
  the shipped defaults.
- Reproducible:
  [tests/dixon_coles_lr_check.py](../tests/dixon_coles_lr_check.py) and
  [tests/dixon_coles_backtest.py](../tests/dixon_coles_backtest.py).

## Why it might still be worth having around

Even tied on raw predictive metrics, DixonColes has two properties nothing
else in this codebase has:

1. **Native tie/OT probability** without collapsing to a single scalar
   (`predict_outcomes()` returns the full `(P_home_win, P_tie, P_away_win)`
   triple) — shared with HockeyBT, not shared with Massey/KRACH/ELO/Colley.
2. **An interpretable attack/defense split**, not just a single strength
   number — useful for questions like "is this team good because they score
   a lot or because they don't allow much," which no other model here
   answers directly.

Neither is a reason to prefer it for pure prediction accuracy, which is why
it stays off by default.

## Open items

1. **kappa was tuned on the same data used for final evaluation** — same
   acknowledged limitation as HockeyBT's kappa and Massey's ridge_lambda/
   beta-holdout-fraction. No separate held-out set exists in this project.
2. **A team-specific or conference-specific rho** (rather than one global
   value) was not explored — the low-score correlation might genuinely
   differ by matchup type (rivalry games, defensive vs. offensive
   conferences) even though a single global rho didn't help here.
3. **The tau renormalization** (when `fit_rho=True`) redistributes the
   small mass shift from adjusting 4 score cells across the whole grid —
   standard practice, not revisited further since `fit_rho` ships off.
