# P0.2 — Paired significance testing for the women's backtest

**Status:** Done. Unblocks the "Open Items" gap in `reports/womens_hockey_import.md`
("paired significance tests... not computed here").

## What changed

1. `src/backtesting/backtest_engine.py`: added `BacktestEngine.save_predictions()`,
   writing every held-out per-game prediction already collected in
   `self.all_predictions` to `<output_dir>/backtest_predictions.csv`. The
   engine was already collecting this (`run()`); it just never persisted
   it. `save_results()` (split-level aggregates) was untouched.
2. `analysis/exploratory/womens_hockey_backtest.py`: added a `paired_tests()`
   function — the same paired t-test (Brier, LogLoss) and McNemar's test
   (accuracy) that `analysis/exploratory/hockey_bt_backtest.py` already runs
   for men's data, generalized from one hardcoded pair to N models compared
   against a reference model (`BEST_MODEL = 'Massey'`). Results are printed
   and saved to `womens_hockey_backtest_significance.csv`.

No production behavior changed for any existing consumer of `BacktestEngine`
(`save_predictions()` is new and additive; nothing calls it automatically).

## Result (5-year/20-split women's backtest, men's-tuned hyperparameters, pooled 4,841 held-out games)

Split-averaged means (matches `reports/womens_hockey_import.md` exactly —
this re-run is deterministic):

| Model    | Accuracy | Brier  | LogLoss | ECE    |
|----------|---------:|-------:|--------:|-------:|
| Massey   | 0.7544   | 0.1339 | 0.5244  | 0.0747 |
| HockeyBT | 0.7473   | 0.1342 | 0.5275  | 0.0568 |
| KRACH    | 0.7450   | 0.1414 | 0.5587  | 0.0993 |
| ELO      | 0.7428   | 0.1409 | 0.5520  | 0.0706 |
| RPI      | 0.7279   | 0.1418 | 0.5467  | 0.0825 |

Pooled paired tests, Massey vs. each other model (n=4,841 paired games,
4,550 decisive for accuracy/McNemar):

| Comparison | Accuracy (McNemar p) | Brier (paired-t p) | LogLoss (paired-t p) |
|---|---|---|---|
| Massey vs. KRACH | 0.7510 vs. 0.7413, **p=0.022** | diff −0.0079, **p=2.2e-13** | diff −0.038, **p=1.3e-13** |
| Massey vs. ELO | 0.7510 vs. 0.7371, **p=0.004** | diff −0.0081, **p=8.3e-09** | diff −0.031, **p=1.2e-11** |
| Massey vs. RPI | 0.7510 vs. 0.7281, **p<0.0001** | diff −0.0074, **p=5.6e-11** | diff −0.021, **p=1.6e-11** |
| Massey vs. HockeyBT | 0.7510 vs. 0.7420, **p=0.017** | diff −0.0003, p=0.71 (n.s.) | diff −0.003, p=0.26 (n.s.) |

## Interpretation

**The models paper's headline finding (P1 in PLAN.md) now has the same kind
of evidence for women's hockey as for men's**, not just a split-averaged
mean: Massey is the single most accurate model, and it beats KRACH, ELO,
and RPI on all three primary metrics with real statistical significance —
not merely "ahead." This closes P1 as **confirmed**, upgraded from
"prediction" to "evidenced."

**Massey vs. HockeyBT is the interesting case**, and it sharpens rather
than contradicts the existing calibration finding
(`reports/womens_hockey_import.md`: "HockeyBT... has the best calibration...
a genuine difference from the men's-hockey calibration ranking"). Massey
wins on accuracy with significance (p=0.017) but the Brier/LogLoss
differences are not significant (p=0.71, p=0.26) — i.e., **the two models
are statistically indistinguishable on calibrated probabilistic scoring**,
even though Massey is significantly more often exactly right. This is
consistent with, not contradictory to, HockeyBT's separately-measured edge
in calibration (lowest ECE): a model can score comparably on Brier/LogLoss
while genuinely differing in reliability, which is exactly what the
Brier-decomposition table already showed and this paired test doesn't
re-litigate.

## What this does not yet do

- Does not include NPI (deliberately — see P0.3, not yet run).
- Does not stratify by conference (blocked on P0.1).
- Is not yet corrected for multiple comparisons (4 pairwise tests here; the
  full W2/W3 study will run more and should apply a correction — see
  PLAN.md's reporting discipline).
- Does not yet report a minimum detectable effect (see P0.4, next).
