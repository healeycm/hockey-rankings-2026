# Plan: A Rigorous Goal-Based Ranking Model (non-Bradley-Terry)

> Results of executing this plan are in
> [reports/dixon_coles_results.md](dixon_coles_results.md). Note: the
> "quick win" half of this plan (fixing Massey's calibration) turned out to
> raise the bar substantially — see
> [reports/massey_calibration_results.md](massey_calibration_results.md).

## Correction to an earlier claim

Prior work in this project asserted "margin doesn't help in hockey," based
on the HockeyLRMC margin experiments and the empty-net ablation. That was
too broad a generalization from two negative results — narrower ones about
*how* margin was used (Markov-chain vote weighting; empty-net subtraction),
not whether margin carries signal at all.

## The measured baseline (5-year, 20 splits) — most of this was never benchmarked

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| Massey (pre-fix) | **64.82%** | 0.1850 | 0.6672 |
| HockeyBT | 64.10% | 0.1753 | 0.6387 |
| KRACH | 63.80% | 0.1840 | 0.6682 |
| ELO | 63.74% | **0.1739** | **0.6382** |
| Colley | 63.58% | 0.1770 | 0.6451 |
| Markov | 62.85% | 0.1872 | 1.1567 |
| NPI | 62.44% | 0.1764 | 0.6452 |

No model dominated at the time this plan was written. The frontier:
accuracy → Massey; calibration → ELO. HockeyBT was the best all-rounder but
best at nothing specifically.

## Diagnosis: the best signal was being wasted by a bad probability mapping

Massey's flaws were fixable-by-construction, and none were about the
*signal*: arbitrary hardcoded `beta=0.15` (accuracy-blind, since accuracy
depends only on the sign of predicted margin); Gaussian least-squares on
discrete low-count data; hardcoded `home_ice_advantage=0.2`, never fit; no
regularization.

## Primary recommendation: Dixon-Coles bivariate Poisson

Model the scoring process rather than the comparison outcome:

```
λ_home = exp(μ + attack_i − defense_j + η)      (η = home effect, fit)
λ_away = exp(μ + attack_j − defense_i)
P(scoreline h,a) = Poisson(h; λ_home) · Poisson(a; λ_away) · τ(h,a)
```

- Two parameters per team (attack, defense) vs. one strength scalar
- Probabilities come from the model itself, not a bolted-on sigmoid
- Correct likelihood for count data
- η fit by MLE
- τ (Dixon-Coles low-score correction) designed precisely for low-scoring
  sports — hockey's regime
- Regularization/priors drop in naturally
- Natively predicts ties/OT, like HockeyBT

**Honest caveat:** the extra expressiveness (2n parameters vs. n) might
overfit a ~1,000-game season. Massey says goals help; the LRMC/ENG work
says naive goal handling doesn't. This is the best-specified test of the
question either way.

## Do the cheap thing first: fix Massey's calibration properly

Fit `beta` and `home_ice_advantage` on training data (not hardcode them),
add regularization, validate out-of-sample. Establishes the true bar before
investing in Dixon-Coles — if a properly calibrated Massey already beats
everything, that's the headline, and Dixon-Coles has to beat *that*.

⚠️ Critical trap: any calibration fit must use a genuinely held-out split,
not the same games used to fit the underlying ratings — the LRMC
calibration work already showed in-sample Platt scaling overfits and makes
LogLoss worse, not better.

## Secondary tracks (not pursued in this pass, noted for future work)

- **Hierarchical/GLMM shrinkage** — estimate the shrinkage variance from
  data instead of a hand-tuned kappa, plus conference partial pooling.
- **Dynamic state-space (Glicko/Kalman-style)** — ELO's calibration
  strength is suggestive; a proper state-space model estimates the drift
  variance rather than assuming a halflife, and yields per-team rating
  uncertainty that nothing else in this codebase provides.

## Pre-registered success criteria (as originally written)

- Accuracy > 64.82% (Massey pre-fix)
- Brier < 0.1739 and LogLoss < 0.6382 (ELO)
- Paired per-game significance tests, not just split means
- Component ablation; anything that doesn't earn its keep ships disabled

**Note:** the Massey fix (executed alongside this plan) moved the real bar
to 64.59% pooled accuracy / 0.1734 Brier / 0.634 LogLoss — see
`reports/massey_calibration_results.md`. Dixon-Coles is evaluated against
that revised, higher bar in `reports/dixon_coles_results.md`, not the
numbers above.

**Honest expectation going in:** given the project's track record (4 of 5
HockeyLRMC adaptations rejected on evidence; calibration and empty-net both
rejected), Dixon-Coles beating the frontier on all three metrics looked like
well under even odds.
