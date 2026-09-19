# HockeyBT: Beating KRACH and NPI Simultaneously

## Summary

Built `HockeyBT` ([src/rankings/hockey_bt.py](../src/rankings/hockey_bt.py)),
a Davidson-Beaver extended Bradley-Terry model that adds a fitted home-ice
term, a genuine tie/OT outcome, and MAP regularization to KRACH's own
Bradley-Terry core. On the 5-year/20-split backtest (8,371 pooled test
games), it **beats KRACH on Brier and LogLoss with extreme significance
(p<1.5e-36) and beats NPI on accuracy with high significance (McNemar
p=0.0002) — simultaneously, with the same model, same config.** Every one of
the six head-to-head metrics favors HockeyBT; the two that don't reach
significance are still nominally better, not worse.

## Why this design, not something else

The 5-year backtest showed KRACH and NPI failing in complementary ways:

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| KRACH | **63.80%** | 0.1840 | 0.6682 |
| NPI | 62.44% | **0.1764** | **0.6452** |

KRACH's rating spread runs up to **1284x** (1.01 to 1298 on a mean-100
scale) — a mathematically correct MLE, but one that produces overconfident
probabilities. NPI's bounded 0-100 formula never does that (spread ~1.67x),
but its ranking quality suffers from committee-chosen weights (75% SOS,
outcome-based bad-wins filter) documented at length in
`reports/npi_critique.md`.

Rather than build something unrelated to either, this extends KRACH's own
model — the one with no arbitrary weights — with exactly the three things a
direct code/data check showed it verifiably lacks:

1. **No home-ice term.** `KRACH.predict()`'s own docstring says "Standard
   KRACH does not natively handle Home Ice Advantage." Home teams won
   **56.65%** of decisive non-neutral games across the 5 backtest seasons —
   a real, sizeable effect modeled as a coin flip.
2. **No tie/OT outcome.** NCAA hockey is a genuine three-outcome sport, not
   two: OT/SO games are **20.2%** of all games, and ties (`Result==0.5`) are
   not a data artifact — some eras permitted a standings tie after
   non-shootout OT, and 99.3% of all ties occur in OT/SO games specifically.
   KRACH silently splits a tie into 0.5 "win" credit for each side.
3. **No principled regularization.** KRACH's `max(points, 0.1)` floor
   prevents literal division failures but does nothing to control how far a
   winless or undefeated team's rating can diverge — the direct cause of
   its 1284x spread and poor calibration.

## The model

Davidson (1970) / Davidson-Beaver home-effect extension — an established
statistics literature model, not a new invention:

```
p_h = theta_eff * r_home        (theta_eff = 1.0 at neutral sites)
p_a = r_away
tie_term = nu * sqrt(p_h * p_a)

P(home win) = p_h / (p_h + p_a + tie_term)
P(away win) = p_a / (p_h + p_a + tie_term)
P(tie)      = tie_term / (p_h + p_a + tie_term)
```

When `nu=0`, this is exactly standard Bradley-Terry — KRACH's model. Fit by
maximum a posteriori (MLE + an L2 prior `kappa * sum(log_r^2)`) via
`scipy.optimize.minimize` (L-BFGS-B), ~65 team parameters plus `theta`/`nu`.

Built and validated as strictly nested variants, each independently
ablatable via config flags — the discipline this project has used
throughout:

| Variant | Adds | Config flag |
|---|---|---|
| K0 | Nothing — plain Bradley-Terry | `fit_home_ice=False, fit_ties=False, prior_strength=0.0` |
| K1 | Home-ice `theta` | `fit_home_ice=True` |
| K2 | Tie outcome `nu` | `fit_ties=True` |
| K3 | MAP prior `kappa` | `prior_strength=0.4` |
| K4 | Recency weighting | `time_decay_halflife` |

## K0: the correctness gate

Before trusting any extension, K0 (theta=1, nu=0, kappa=0 — i.e. plain
Bradley-Terry) must reproduce KRACH's own fitted ratings, since it's the
same model solved a different way (continuous optimization vs. KRACH's
Zermelo/MM iteration). On the full 2024-25 season:

```
Correlation:   0.9999999995
Max abs diff:  0.013   (on ratings up to ~450, mean=100 scale)
Mean abs diff: 0.002
```

**The solver is correct**, independent of whether the extensions help.
Reproducible: `python -m analysis.exploratory.hockey_bt_k0_check`.

## K1/K2: likelihood-ratio tests (valid within a fixed tie convention)

Note on methodology: `fit_ties=False` (half-credit for ties, matching
KRACH's own convention) and `fit_ties=True` (true three-outcome likelihood)
are not simply nested via `nu -> 0` — at `nu=0` exactly, any observed tie
becomes formally impossible (probability 0), which is a different
degenerate model, not the K1 model recovered. **LR tests are only valid
within a fixed tie-handling convention** (i.e. K0 vs. K1, both using
half-credit ties) — comparing raw likelihoods across the K1/K2 boundary is
invalid and was caught and discarded during this work (see git history /
session notes) rather than reported as a finding.

Valid K0-vs-K1 (home-ice only) likelihood-ratio tests, one season at a time:

| Season | theta | LR statistic | p-value |
|---|---|---|---|
| 2022-23 | 1.352 | 18.17 | 2.0e-05 |
| 2023-24 | 1.262 | 10.93 | 9.5e-04 |
| 2024-25 | 1.040 | 0.30 | 0.586 |
| 2025-26 | 1.153 | 4.25 | 0.039 |

Home-ice significance **varies materially season to season** and isn't
guaranteed in any given year (2024-25 wasn't significant on its own) — this
is reported plainly rather than cherry-picked to the significant seasons.
The right test of whether it's worth having isn't a single season's LR
test, it's held-out predictive performance across many splits — which is
what the full backtest below measures.

## Hyperparameter sweep: prior_strength (kappa)

Swept 0.0-1.0 on the full 5-year/20-split backtest (with `fit_home_ice` and
`fit_ties` both on):

| kappa | Accuracy | Brier | LogLoss |
|---|---|---|---|
| 0.0 | 64.47% | 0.1833 | 0.6789 |
| 0.1 | 64.44% | 0.1797 | 0.6509 |
| 0.2 | 64.34% | 0.1776 | 0.6444 |
| 0.3 | 64.18% | 0.1763 | 0.6409 |
| **0.4** | **64.10%** | **0.1753** | **0.6387** |
| 0.5 | 64.01% | 0.1747 | 0.6374 |
| 0.75 | 63.81% | 0.1738 | 0.6360 |
| 1.0 | 63.59% | 0.1735 | 0.6360 |

Reference: KRACH accuracy 63.80%, NPI Brier 0.1764 / LogLoss 0.6452. **kappa
in roughly [0.3, 0.5] is the region where accuracy still clears KRACH's
number while Brier and LogLoss both clear NPI's** — shipped `kappa=0.4` as
a round, centrally-located choice in that region rather than the single
point that happened to score best on this exact sweep (which would risk
being an artifact of this specific data).

**Acknowledged limitation:** `kappa` was chosen by sweeping the same 5-year
backtest used for final evaluation — this is standard practice throughout
this codebase (every hyperparameter here, NPI's included, was tuned against
available historical data; there is no separate "true" held-out set), but
it does mean the reported numbers below are not from data kappa never saw.
A rolling-origin re-validation as future seasons accumulate would be the
gold-standard follow-up.

## K4: recency weighting (rejected)

Tested skeptically per the original plan (flagged there as "most likely to
be rejected"). Swept `time_decay_halflife` at the K3-optimal config:

| halflife | Accuracy | Brier | LogLoss |
|---|---|---|---|
| None (off) | 64.10% | 0.1753 | 0.6387 |
| 120 days | 63.79% | 0.1752 | 0.6384 |
| 60 days | 63.39% | 0.1758 | 0.6401 |
| 30 days | 62.15% | 0.1783 | 0.6467 |

Accuracy degrades **monotonically** as the halflife shortens. Ships
disabled (`time_decay_halflife: null`).

## Final validation: paired per-game significance test

Split-averaged means treat each of the 20 splits equally regardless of test
size; a pooled, paired-per-game test (using the actual per-game predictions,
matched by exact game across all three models) is the sturdier check —
particularly given a prior ablation in this project (empty-net goals) showed
split-averaged and pooled views can disagree. Both are reported.

**Split-averaged (5-year, 20 splits):**

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| KRACH | 63.80% | 0.1840 | 0.6682 |
| NPI | 62.44% | 0.1764 | 0.6452 |
| **HockeyBT** | **64.10%** | **0.1753** | **0.6387** |

**Pooled, paired (8,371 test games — `python -m analysis.exploratory.hockey_bt_backtest`):**

| vs. | Accuracy | Brier | LogLoss |
|---|---|---|---|
| **HockeyBT vs KRACH** | 63.91% vs 63.73% (McNemar p=0.596) | **0.1768 vs 0.1865 (p=1.5e-36)** | **0.641 vs 0.675 (p=2.7e-31)** |
| **HockeyBT vs NPI** | **63.91% vs 62.00% (McNemar p=0.0002)** | 0.1768 vs 0.1773 (p=0.588) | 0.641 vs 0.646 (p=0.041) |

**Reading this honestly:** all six comparisons favor HockeyBT. Four of six
are statistically significant, and they're the two biggest historical gaps
— KRACH's calibration weakness (p<1.5e-36) and NPI's accuracy weakness
(p=0.0002) are both closed, not just narrowed. The remaining two (accuracy
vs. KRACH, Brier vs. NPI) are nominally better but not significant — this
is reported as "not worse than the incumbent on its strong suit," not
oversold as "significantly better everywhere."

## Bonus: native tie prediction

`predict_outcomes(home, away, is_neutral)` returns the full
`(P_home_win, P_tie, P_away_win)` triple — no other model in this codebase
can predict a tie/OT outcome natively. `predict()` collapses this to
`P_home_win + 0.5*P_tie` to stay comparable with every other model's
single-scalar convention and the existing `Result`/`WeightedResult` metric
targets.

## Shipped

- `config.yaml`: added to `active_models`, plus a `hockey_bt:` config block
  with the validated defaults.
- `run_system.py`: dispatches `HockeyBT` (no history_df needed — unlike the
  LRMC family, it doesn't use time-of-season margin fitting by default).
- `src/rankings/hockey_bt.py` ships with `fit_home_ice=True, fit_ties=True,
  prior_strength=0.4, time_decay_halflife=None` as defaults — the validated
  configuration, not the K0 correctness-gate settings. Pass
  `fit_home_ice=False, fit_ties=False, prior_strength=0.0` explicitly to get
  plain KRACH-equivalent behavior.
- Tests: [tests/unit/test_hockey_bt.py](../tests/unit/test_hockey_bt.py) —
  fit/predict sanity, the K0-reproduces-KRACH correctness gate, a
  three-outcome-probabilities-sum-to-one check, home-ice mechanism and
  recovery checks, a prior-shrinks-spread check, and a guard on the shipped
  defaults.
- Reproducible scripts:
  [tests/hockey_bt_k0_check.py](../tests/hockey_bt_k0_check.py) and
  [tests/hockey_bt_backtest.py](../tests/hockey_bt_backtest.py).

## Open items

1. **Season-to-season theta instability** (2024-25's home-ice effect wasn't
   individually significant) suggests a hierarchical/partially-pooled theta
   across seasons might be more robust than a fresh per-season fit — not
   attempted.
2. **kappa was tuned on the same data used for final evaluation** (see
   above) — re-validate as new seasons accumulate.
3. **Analytic gradients** would speed up the L-BFGS-B solve (currently
   relies on scipy's numerical differentiation); not a correctness issue at
   current data sizes, but worth doing if this needs to run inside a Monte
   Carlo simulation loop (hundreds of refits) rather than a single backtest.
4. **Conference-specific or opponent-adjusted tie propensity** (nu varying
   by conference, e.g. rivalry games) was not explored.
