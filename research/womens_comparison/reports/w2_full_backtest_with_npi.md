# W2 — Full 6-model women's backtest, now including NPI

**Status:** Done. This is the update that actually closes the gap the
site's methodology page flags in every "Men's vs. women's" note: NPI has
never been in a women's-hockey backtest before. It now has, with the
corrected dials from P0.3.

## What changed

`analysis/exploratory/womens_hockey_backtest.py` now includes NPI in the
5-year/20-split backtest, using `config.yaml`'s `npi_women` block (not
NPI's men's-defaulting constructor) — the first time NPI has been
evaluated on women's data at all, anywhere in this project.

## Split-averaged means, all 6 models

| Model | Accuracy | Brier | LogLoss | ECE |
|---|---:|---:|---:|---:|
| Massey | 0.7544 | 0.1339 | 0.5244 | 0.0747 |
| HockeyBT | 0.7473 | 0.1342 | 0.5275 | 0.0568 |
| KRACH | 0.7450 | 0.1414 | 0.5587 | 0.0993 |
| ELO | 0.7428 | 0.1409 | 0.5520 | 0.0706 |
| **NPI** | **0.7400** | **0.1508** | **0.5800** | **0.1015** |
| RPI | 0.7279 | 0.1418 | 0.5467 | 0.0825 |

**NPI is the worst-calibrated model of all 6 for women's hockey** (highest
Brier, LogLoss, and ECE), and second-worst on accuracy (ahead of only
RPI). This mirrors the men's-hockey finding qualitatively (NPI underperforms
the field there too) but is now, for the first time, an actual women's
measurement rather than an assumption carried over from men's.

## The three comparisons the methodology page specifically flagged as untested

| Comparison | Accuracy (McNemar p) | Brier (paired-t p) | LogLoss (paired-t p) |
|---|---|---|---|
| Massey vs. NPI | 0.7510 vs. 0.7338, **p=0.0026** | diff −0.0171, **p=3.7e-23** | diff −0.056, **p=5.8e-26** |
| HockeyBT vs. NPI | 0.7420 vs. 0.7338, p=0.139 (n.s.) | diff −0.0168, **p=1.3e-37** | diff −0.053, **p=2.5e-52** |
| RPI vs. NPI | 0.7281 vs. 0.7338, p=0.413 (n.s., NPI numerically *ahead*) | diff −0.0097, **p=2.4e-08** | diff −0.034, **p=5.8e-13** |

## Interpretation: a mixed, genuinely informative result

**Calibration: fully replicates.** Every model beats NPI on Brier and
LogLoss with overwhelming significance (p < 1e-7 in all three
comparisons). NPI's men's-hockey reputation as poorly calibrated relative
to the field transfers cleanly to women's.

**Accuracy: does NOT fully replicate, and this matters.** The men's paper's
two headline accuracy claims against NPI were:
- *"HockeyBT beats NPI on accuracy"* — for women's, HockeyBT is
  numerically ahead (0.742 vs. 0.734) but **not significantly** (p=0.14).
- *"RPI beats NPI on accuracy... the second independent confirmation"* —
  for women's, this **reverses**: NPI is numerically (not significantly)
  *more* accurate than RPI (0.734 vs. 0.728, p=0.41).

Massey is the one model that does significantly beat NPI on accuracy too
(p=0.0026), so "the best model beats NPI on accuracy" still holds — but
the specific comparisons the men's paper used to build its case
(HockeyBT-vs-NPI, RPI-vs-NPI) do not carry the same evidentiary weight on
women's data. Where men's hockey has three independent accuracy
confirmations against NPI (HockeyBT, RPI, and Massey/the calibration
paper), women's hockey currently has one (Massey).

This is precisely the kind of finding PLAN.md's publication decision rule
anticipated as the likeliest and most useful outcome: not a clean
replication, not a clean reversal, but a real divergence in *which*
comparisons hold — worth reporting as its own contribution rather than
forcing it into either "replicates" or "doesn't."
