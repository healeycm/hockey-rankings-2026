# Colley: Validated for the First Time

## Summary

`Colley` ([src/rankings/colley.py](../src/rankings/colley.py)) has been
implemented in this codebase since early on but was never run through a
validated backtest or given its own report -- it appears only in passing
mentions elsewhere (`reports/five_year_backtest_and_di_filter.md`,
`reports/ensemble_results.md`'s list of untried ensemble candidates). This
report closes that gap, prompted by the paper (`paper/draft.md`) needing a
complete, validated model roster rather than one with a silent exception.

## Result

Standard 5-year/20-split protocol (`python -m
analysis.exploratory.paper_table1_backtest`, which also filled in
split-averaged figures for ELO/DixonColes/Glicko2 for the same paper):

**Split-averaged:**

| Model | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| Massey | 64.78% | 0.1718 | 0.6317 |
| Colley | 63.58% | 0.1770 | 0.6451 |

**Pooled, paired per-game test (n=8,371):**

| | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| Massey | 64.50% | 0.17311 | 0.63361 |
| Colley | 63.51% | 0.17864 | 0.64874 |
| **p-value** | **0.0067 (McNemar)** | **1.7e-15** | **2.2e-12** |

Colley loses to Massey significantly on all three metrics, but the
interesting part is *how* it loses: its accuracy (63.58% split-averaged)
is squarely in the middle of the validated model roster -- better than
KRACH, NPI, HockeyLRMC, Keener -- while its calibration (Brier, LogLoss)
is among the worst.

## Why: the same failure mode pre-fix Massey had

`Colley.predict()` uses a fixed, unfit linear mapping from rating
difference to win probability (`0.5 + (r_home - r_away)`, clamped to
[0.01, 0.99]) -- never calibrated against actual outcomes, exactly the
class of bug `reports/massey_calibration_results.md` diagnosed and fixed
in Massey itself (`beta=0.15` hardcoded, never fit). Since accuracy
depends only on the sign of the predicted margin, an uncalibrated linear
map can still pick winners reasonably well while being badly wrong about
*how confident* to be -- precisely Massey's pre-fix symptom, now confirmed
in a second, independently-implemented least-squares method. This is
useful corroborating evidence for this project's central finding: it is
not "least-squares methods are good" or "Colley/Massey's specific formula
is good," it is specifically "a properly fit probability mapping matters
enormously, independent of which underlying rating produces the input to
it."

## Not fixed here

Colley's rating itself is unmodified -- this report only characterizes the
existing implementation's predictive performance, the same held-out
protocol as everything else in this project. Applying the same
held-out-temporal-split beta-fitting treatment already validated for
Massey and RPI to Colley's prediction step would be the natural next
step if Colley's calibration specifically becomes of interest, but
Colley is not a candidate to replace Massey/Dixon-Coles regardless (its
accuracy still trails both), so this wasn't pursued.

## Shipped

- No config or default changes -- `Colley` was already fully implemented
  and configured (`config.yaml`'s `colley:` block, empty since it has no
  tunable parameters), just never benchmarked.
- New script: [analysis/exploratory/paper_table1_backtest.py](../analysis/exploratory/paper_table1_backtest.py).
- Not added to `active_models` -- loses to Massey/Dixon-Coles/RPI on
  accuracy and to most of the roster on calibration.
