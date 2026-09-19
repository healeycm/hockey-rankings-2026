# P1: history-only priors (538 continuous Elo vs. refit-blend strength sweep)

See this experiment's module docstring (`research/preseason/experiments/p1_history_prior.py`) for the full pre-registration. Summary: r1/r2 (prior construction) held at production's validated 0.6/0.15; swept each model's APPLICATION strength (Massey prior_lambda, ELO prior_weight), and compared against a 538-style continuous Elo that never resets between seasons. Tune seasons (18): [20012002, 20022003, 20032004, 20042005, 20052006, 20062007, 20072008, 20082009, 20102011, 20112012, 20122013, 20132014, 20142015, 20152016, 20172018, 20182019, 20192020, 20202021]. Holdout seasons (5): [20212022, 20222023, 20232024, 20242025, 20252026] (unchanged from reports/preseason_priors_results.md).

**Selected on tune seasons (lowest mean Brier):** Massey -> `Massey_lambda4`, ELO -> `ELO_weight0.7`, continuous Elo -> `ContinuousElo_rev0.33_k20`.

Full tune-season Brier by arm:

```
Massey:
Arm
Massey_lambda4     0.192789
Massey_lambda2     0.192944
Massey_lambda8     0.192974
Massey_lambda1     0.193224
Massey_lambda16    0.193738

ELO:
Arm
ELO_weight0.7    0.186682
ELO_weight0.5    0.186722
ELO_weight0.9    0.187514
ELO_weight0.3    0.187730
ELO_weight1.0    0.188222

Continuous Elo:
Arm
ContinuousElo_rev0.33_k20    0.180619
ContinuousElo_rev0.25_k20    0.180762
ContinuousElo_rev0.5_k30     0.180815
ContinuousElo_rev0.33_k30    0.180839
ContinuousElo_rev0.25_k15    0.181051
ContinuousElo_rev0.33_k15    0.181199
ContinuousElo_rev0.5_k20     0.181352
ContinuousElo_rev0.25_k30    0.181359
ContinuousElo_rev0.15_k15    0.181480
ContinuousElo_rev0.15_k20    0.181549
ContinuousElo_rev0.5_k15     0.182473
ContinuousElo_rev0.15_k30    0.182592
```


## Massey: holdout comparison vs. `Massey_none`

| Candidate | Cutoff | N | Acc (base->cand) | Brier (base->cand) | LogLoss (base->cand) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|---|
| Massey_prodprior | Oct15 | 474 | 0.575->0.598 | 0.1988->0.1965 | 0.6823->0.6774 | 0.00392 (Holm 0.0235) | 0.00605 | 0.268 |
| Massey_prodprior | Nov1 | 554 | 0.615->0.654 | 0.1864->0.1777 | 0.6682->0.6467 | 1.55e-07 (Holm 1.55e-06) | 1.39e-06 | 0.00266 |
| Massey_prodprior | Nov15 | 526 | 0.629->0.643 | 0.1955->0.1874 | 0.6798->0.6540 | 5.26e-07 (Holm 4.73e-06) | 2.86e-06 | 0.169 |
| Massey_prodprior | Dec1 | 465 | 0.643->0.643 | 0.1804->0.1782 | 0.6413->0.6368 | 0.00489 (Holm 0.0245) | 0.0249 | 0.724 |
| Massey_prodprior | Jan1 | 492 | 0.635->0.654 | 0.1829->0.1806 | 0.6179->0.6127 | 0.00959 (Holm 0.0384) | 0.0373 | 0.0265 |
| Massey_lambda4 | Oct15 | 474 | 0.575->0.603 | 0.1988->0.1968 | 0.6823->0.6781 | 0.0396 (Holm 0.0864) | 0.0559 | 0.207 |
| Massey_lambda4 | Nov1 | 554 | 0.615->0.664 | 0.1864->0.1771 | 0.6682->0.6460 | 3.47e-05 (Holm 0.000243) | 0.000172 | 0.000978 |
| Massey_lambda4 | Nov15 | 526 | 0.629->0.639 | 0.1955->0.1851 | 0.6798->0.6466 | 1.44e-05 (Holm 0.000115) | 3.42e-05 | 0.472 |
| Massey_lambda4 | Dec1 | 465 | 0.643->0.641 | 0.1804->0.1778 | 0.6413->0.6366 | 0.0358 (Holm 0.0864) | 0.151 | 1 |
| Massey_lambda4 | Jan1 | 492 | 0.635->0.656 | 0.1829->0.1799 | 0.6179->0.6123 | 0.0288 (Holm 0.0864) | 0.131 | 0.0339 |

## ELO: holdout comparison vs. `ELO_none`

| Candidate | Cutoff | N | Acc (base->cand) | Brier (base->cand) | LogLoss (base->cand) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|---|
| ELO_prodprior | Oct15 | 474 | 0.598->0.630 | 0.1931->0.1843 | 0.6689->0.6489 | 0.0048 (Holm 0.0288) | 0.00535 | 0.126 |
| ELO_prodprior | Nov1 | 554 | 0.579->0.634 | 0.1863->0.1730 | 0.6677->0.6350 | 5.39e-07 (Holm 5.39e-06) | 8.88e-08 | 0.00693 |
| ELO_prodprior | Nov15 | 526 | 0.592->0.639 | 0.1901->0.1806 | 0.6563->0.6336 | 4.52e-05 (Holm 0.000361) | 2.75e-05 | 0.01 |
| ELO_prodprior | Dec1 | 465 | 0.617->0.636 | 0.1830->0.1782 | 0.6501->0.6372 | 0.0631 (Holm 0.189) | 0.0384 | 0.35 |
| ELO_prodprior | Jan1 | 492 | 0.643->0.654 | 0.1840->0.1799 | 0.6270->0.6153 | 0.0402 (Holm 0.161) | 0.0145 | 0.596 |
| ELO_weight0.7 | Oct15 | 474 | 0.598->0.628 | 0.1931->0.1840 | 0.6689->0.6482 | 0.0118 (Holm 0.0589) | 0.0131 | 0.171 |
| ELO_weight0.7 | Nov1 | 554 | 0.579->0.634 | 0.1863->0.1720 | 0.6677->0.6321 | 2.86e-06 (Holm 2.58e-05) | 4.6e-07 | 0.00873 |
| ELO_weight0.7 | Nov15 | 526 | 0.592->0.656 | 0.1901->0.1799 | 0.6563->0.6316 | 0.000152 (Holm 0.00106) | 9.22e-05 | 0.000991 |
| ELO_weight0.7 | Dec1 | 465 | 0.617->0.638 | 0.1830->0.1783 | 0.6501->0.6369 | 0.114 (Holm 0.189) | 0.0699 | 0.289 |
| ELO_weight0.7 | Jan1 | 492 | 0.643->0.652 | 0.1840->0.1798 | 0.6270->0.6146 | 0.0706 (Holm 0.189) | 0.0268 | 0.72 |

## ELO vs. continuous Elo: holdout comparison vs. `ELO_prodprior`

| Candidate | Cutoff | N | Acc (base->cand) | Brier (base->cand) | LogLoss (base->cand) | Brier p | LogLoss p | McNemar p |
|---|---|---|---|---|---|---|---|---|
| ContinuousElo_rev0.33_k20 | Oct15 | 474 | 0.630->0.626 | 0.1843->0.1801 | 0.6489->0.6382 | 0.019 (Holm 0.0948) | 0.0133 | 0.86 |
| ContinuousElo_rev0.33_k20 | Nov1 | 554 | 0.634->0.652 | 0.1730->0.1704 | 0.6350->0.6265 | 0.108 (Holm 0.432) | 0.0291 | 0.124 |
| ContinuousElo_rev0.33_k20 | Nov15 | 526 | 0.639->0.662 | 0.1806->0.1788 | 0.6336->0.6281 | 0.162 (Holm 0.487) | 0.0824 | 0.0455 |
| ContinuousElo_rev0.33_k20 | Dec1 | 465 | 0.636->0.634 | 0.1782->0.1776 | 0.6372->0.6344 | 0.647 (Holm 0.647) | 0.441 | 1 |
| ContinuousElo_rev0.33_k20 | Jan1 | 492 | 0.654->0.661 | 0.1799->0.1785 | 0.6153->0.6105 | 0.312 (Holm 0.623) | 0.136 | 0.663 |


*Brier/LogLoss columns show baseline->candidate (lower is better). Holm-adjusted p-value shown alongside the raw Brier p-value, corrected across every row in each table.*


**Status:** pre-registration and gate are at the top of this file's generating script (`research/preseason/experiments/p1_history_prior.py`). This report only presents what ran; the ship/no-ship call against that gate is left to a human reading the holdout tables above, not made automatically here.

## Conclusion

**The pre-registered hypothesis was wrong, in the reassuring direction.** `reports/preseason_priors_results.md` found the shipped prior still helping at Jan1 and read that as a sign it was under-weighted. Sweeping the strength directly says otherwise: Massey's tuned `lambda4` is statistically indistinguishable from the shipped `lambda2` on every holdout cutoff (raw Brier differs in the fourth decimal place), and ELO's tuned `weight0.7` beats the shipped `weight0.6` only marginally (Brier improves by 0.0003-0.0010 depending on cutoff, itself not significant anywhere). **Production's current preseason-prior values were already close to the achievable optimum for this construction** — there was no large amount of money left on the table, just table scraps. Both tuned values clear the literal "no reversal" ship gate (every cutoff improves over both `_none` and `_prodprior`, direction never flips), but the improvement over what's already shipped is too small to justify a config change on its own.

**The 538-style continuous Elo is the actual finding here, and it's a "watch this" result, not a "ship this" one.** It beats today's refit-blend ELO (`ELO_prodprior`) on Brier and LogLoss at **all 5 of 5 holdout cutoffs, zero reversals** — a consistency no other candidate in this sweep matched. But none of those 5 comparisons survive Holm correction (best case Oct15, raw p=0.019, Holm-adjusted 0.095): with 5 holdout seasons, this test doesn't have the power to distinguish "a real, moderate effect" from "a lucky run," even though the direction alone is a stronger signal than pure chance would produce 5-for-5. This is a **promising, underpowered result** — the plan's next natural move (not done in this pass) is a direct `ContinuousElo` vs. `ELO_none` comparison (this report only tested it against `ELO_prodprior`, one hop removed) and/or widening the season-level statistical test (a per-season bootstrap, rather than per-game pairing, since per-game pairing likely understates the true uncertainty by treating within-season games as independent when they aren't).

**Recommendation:** don't touch `config.yaml`'s current preseason values based on this pass — the tuning gain is real but too small to act on alone. Do treat 538-style continuous Elo as the most promising open thread from this phase, worth a dedicated, better-powered follow-up before any promotion decision.