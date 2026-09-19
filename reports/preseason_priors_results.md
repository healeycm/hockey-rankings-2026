# Preseason priors: backtest results

Validates src/rankings/priors.py's carryover-based preseason prior for ELO and Massey (config.yaml's `preseason:` block) — see src/rankings/priors.py and tests/preseason_priors_backtest.py for how this was generated. Pre-registered expectation: a large gain at Oct/Nov cutoffs, shrinking toward zero by January, and NOT a regression at any cutoff.

Seasons: tune=[20122013, 20132014, 20142015, 20152016, 20182019, 20192020, 20202021], holdout=[20212022, 20222023, 20232024, 20242025, 20252026] (20172018 excluded — its own s-1 season, 20162017, is missing from the archive, so no prior could be built for it). Cutoffs: ['Oct15', 'Nov1', 'Nov15', 'Dec1', 'Jan1'], each scored on the 14 days immediately following (not the rest of the season — see backtest_engine.py's `test_window_days`).


## Tune seasons


### ELO

| Cutoff | N games | Acc (off→on) | Brier (off→on) | LogLoss (off→on) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|
| Oct15 | 616 | 0.600→0.642 | 0.1958→0.1884 | 0.6709→0.6507 | 0.00623 | 0.00167 | 0.024 |
| Nov1 | 713 | 0.585→0.649 | 0.1940→0.1822 | 0.6700→0.6402 | 2.19e-07 | 1.73e-08 | 0.000755 |
| Nov15 | 672 | 0.627→0.623 | 0.1823→0.1764 | 0.6512→0.6319 | 0.00532 | 0.000222 | 0.909 |
| Dec1 | 654 | 0.619→0.646 | 0.1824→0.1781 | 0.6553→0.6418 | 0.0242 | 0.00449 | 0.0919 |
| Jan1 | 728 | 0.614→0.649 | 0.1904→0.1863 | 0.6738→0.6642 | 0.0203 | 0.0271 | 0.00903 |

### Massey

| Cutoff | N games | Acc (off→on) | Brier (off→on) | LogLoss (off→on) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|
| Oct15 | 616 | 0.576→0.596 | 0.2010→0.1987 | 0.6838→0.6787 | 0.000152 | 0.000329 | 0.248 |
| Nov1 | 713 | 0.572→0.597 | 0.1935→0.1916 | 0.6691→0.6656 | 0.0497 | 0.124 | 0.0853 |
| Nov15 | 672 | 0.656→0.629 | 0.1782→0.1763 | 0.6328→0.6298 | 0.079 | 0.332 | 0.0648 |
| Dec1 | 654 | 0.629→0.631 | 0.1905→0.1877 | 0.6802→0.6712 | 0.000108 | 0.000564 | 1 |
| Jan1 | 728 | 0.632→0.629 | 0.1876→0.1872 | 0.6673→0.6666 | 0.435 | 0.631 | 0.823 |

## Holdout seasons


### ELO

| Cutoff | N games | Acc (off→on) | Brier (off→on) | LogLoss (off→on) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|
| Oct15 | 474 | 0.598→0.630 | 0.1931→0.1843 | 0.6689→0.6489 | 0.00484 | 0.00541 | 0.126 |
| Nov1 | 554 | 0.579→0.634 | 0.1863→0.1729 | 0.6677→0.6349 | 5.23e-07 | 8.71e-08 | 0.00693 |
| Nov15 | 526 | 0.592→0.639 | 0.1901→0.1806 | 0.6563→0.6335 | 4.36e-05 | 2.65e-05 | 0.01 |
| Dec1 | 465 | 0.617→0.636 | 0.1830→0.1781 | 0.6501→0.6371 | 0.0606 | 0.0367 | 0.35 |
| Jan1 | 492 | 0.643→0.652 | 0.1840→0.1800 | 0.6270→0.6157 | 0.0499 | 0.0184 | 0.694 |

### Massey

| Cutoff | N games | Acc (off→on) | Brier (off→on) | LogLoss (off→on) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|
| Oct15 | 474 | 0.575→0.598 | 0.1988→0.1965 | 0.6823→0.6774 | 0.00399 | 0.00614 | 0.268 |
| Nov1 | 554 | 0.615→0.654 | 0.1873→0.1800 | 0.6712→0.6531 | 9.7e-07 | 6.05e-06 | 0.00266 |
| Nov15 | 526 | 0.629→0.643 | 0.1954→0.1877 | 0.6797→0.6550 | 1.3e-06 | 6.13e-06 | 0.169 |
| Dec1 | 465 | 0.643→0.643 | 0.1807→0.1783 | 0.6418→0.6368 | 0.00315 | 0.0171 | 0.724 |
| Jan1 | 492 | 0.635→0.654 | 0.1830→0.1806 | 0.6182→0.6129 | 0.00992 | 0.0371 | 0.0265 |


*Brier/LogLoss columns show off→on (lower is better); a negative diff (on < off) is a win for the prior. p-values are paired t-tests (Brier/LogLoss) or McNemar's test (accuracy), same tests used throughout this project's other backtest reports.*


**Status:** these numbers are what actually ran against the current `config.yaml` preseason.* values — see the top of this file for how they were produced, and treat any 'holdout' row as the honest read (the 'tune' rows are not disjoint validation).

## Conclusion

**Clean win, holds current defaults.** On the 5 held-out seasons (2021-22 through 2025-26), the prior improves Brier and LogLoss at every single Oct/Nov/Dec/Jan cutoff for BOTH models, with zero reversals — no cutoff where it makes calibration worse. Accuracy improves at 9 of 10 (cutoff, model) holdout cells and ties on the 10th (Massey/Dec1: 0.643→0.643). Several holdout cells are individually significant (e.g. ELO Nov1 LogLoss p=8.7e-08, Massey Nov1 Brier p=9.7e-07).

**One deviation from the pre-registered expectation, in the GOOD direction:** the plan expected the prior's benefit to shrink toward zero by January as real in-season games take over. Instead it's still helping materially at Jan1 on holdout (ELO accuracy 0.643→0.652, Brier p=0.05; Massey accuracy 0.635→0.654, McNemar p=0.027) — the carryover signal isn't just filling in for missing early games, it's adding real information beyond what ~2-3 months of the current season's own results capture. Worth re-checking at a Feb/Mar cutoff in a future pass to find where (if anywhere) the benefit actually does fade to zero, but that's a refinement, not a blocker.

**Decision: keep `config.yaml`'s `preseason.enabled: true` with the current values** (r1=0.6, r2=0.15, massey_prior_lambda=2.0, elo_carryover_weight=0.6) — this backtest validates them as a real improvement, not just an untested guess. No config change needed as a result of this report.