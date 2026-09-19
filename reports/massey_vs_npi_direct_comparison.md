# Filling a Gap: A Direct Massey-vs-NPI Comparison

## Summary

Every prior report in this project pairs fixed Massey against
HockeyBT/ELO/KRACH ([reports/massey_calibration_results.md](massey_calibration_results.md))
or pairs NPI against HockeyBT/RPI ([reports/hockey_bt_results.md](hockey_bt_results.md),
[reports/rpi_results.md](rpi_results.md)) — but no report ever ran Massey
and NPI against each other directly on the same held-out games. Their
accuracy figures were consistent to two decimal places across those other
reports by coincidence of using the same protocol (NPI: 62.00% in both
`hockey_bt_results.md` and `rpi_results.md`; Massey: 64.59% in three
separate reports), which is reassuring, but this project's own standard —
and the paper this project's results are being written up into — call for
a directly-computed pairwise test rather than one assembled by
transitivity across reports.

## Result

Pooled, paired per-game test, standard 5-year/20-split protocol (8,371
test games, `python -m analysis.exploratory.massey_vs_npi_backtest`):

| | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| Massey | 64.50% | 0.17311 | 0.63361 |
| NPI | 62.00% | 0.17732 | 0.64623 |
| **p-value** | **<0.0001 (McNemar)** | **1.74e-06** | **6.53e-09** |

All three comparisons favor Massey and all three are significant at
p<0.0001 or better. This directly confirms — rather than merely being
consistent with — the transitive inference from other reports' NPI and
Massey figures.

(Massey's pooled accuracy here, 64.50%, is a hair below the 64.59%
reported in `massey_calibration_results.md` — expected, since this run
includes `fit_rest_advantage=True`, shipped as the default only after
`massey_calibration_results.md` was written; see
[reports/massey_experiments_2026.md](massey_experiments_2026.md). NPI's
62.00% matches both prior reports that measured it exactly.)

## Shipped

New script: [analysis/exploratory/massey_vs_npi_backtest.py](../analysis/exploratory/massey_vs_npi_backtest.py),
following the same pattern as `massey_backtest.py`/`rpi_backtest.py`. No
model or config changes — this is a pure evaluation gap-fill, not a new
model or default.
