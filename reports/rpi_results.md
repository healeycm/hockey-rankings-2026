# RPI: Did NPI Actually Improve on What It Replaced?

## Summary

Built `RPI` ([src/rankings/rpi.py](../src/rankings/rpi.py)) — a faithful
implementation of the Ratings Percentage Index, the direct historical
predecessor to NPI for NCAA hockey tournament selection (RPI → Pairwise
Rankings → NPI). This directly tests a question this project has circled
since its first NPI critique
([reports/npi_critique.md](npi_critique.md)): did NPI's added machinery —
a 75% strength-of-schedule weight, a quality-win bonus, and an outcome-based
"bad wins" filter — actually improve on the system it replaced?

**Answer: no.** RPI significantly beats NPI on accuracy (McNemar
p=0.0002 — the same pattern already found for HockeyBT vs. NPI) and is
nominally better on Brier and LogLoss too, though those don't reach
significance. RPI does *not* beat fixed Massey — it's essentially tied on
accuracy but significantly worse on calibration (p<3e-5 on both Brier and
LogLoss).

## The model

Classic three-component formula:

```
RPI = weight_wp * WP + weight_owp * OWP + weight_oowp * OOWP
```

- **WP** — the team's own weighted win percentage (using NPI's own
  home/away multiplier convention, 0.8/1.2, so RPI and NPI are compared on
  equal footing for the win-pct component rather than RPI using a cruder
  calculation)
- **OWP** — average, over the team's own games, of that specific
  opponent's win percentage — **computed excluding games between the team
  and that opponent**. This exclusion is the standard, correct RPI
  convention; skipping it is a well-known implementation bug, since a
  team's own good record would otherwise leak into its opponents'
  calculated strength. Verified directly on a hand-checkable 4-game toy
  case (`tests/unit/test_rpi.py::test_owp_excludes_head_to_head`): team A's
  only opponent B has an overall 2-1 record, but excluding the A-B game
  (B's one loss) leaves B 2-0 against everyone else — OWP for A must be
  1.0, not 2/3. Confirmed exactly.
- **OOWP** — average of the team's opponents' OWP (no further exclusion,
  matching typical implementations)

Weights: 0.25/0.50/0.25, the standard RPI convention (distinct from NPI's
0.25/0.75 two-level WP/SOS split with no OOWP term at all).

Deliberately does **not** implement NPI's bad-wins filter or quality-win
bonus — this is meant to isolate "the older, simpler system" as its own
thing, not RPI-plus-some-of-NPI's-extra-mechanisms.

`predict()`'s probability mapping (`beta`) is fit via the same genuinely
held-out temporal split used for Massey — not naive in-sample
recalibration.

## Results

**Split-averaged (5-year, 20 splits):**

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| Massey | 64.90% | 0.1721 | 0.6322 |
| **RPI** | 64.41% | 0.1750 | 0.6416 |
| NPI | 62.44% | 0.1764 | 0.6452 |

**Pooled, paired per-game test (8,371 test games,
`python -m analysis.exploratory.rpi_backtest`):**

| vs. | Accuracy | Brier | LogLoss |
|---|---|---|---|
| **RPI vs NPI** | **64.19% vs 62.00% (McNemar p=0.0002)** | 0.1763 vs 0.1773 (p=0.298) | 0.6435 vs 0.6462 (p=0.270) |
| **RPI vs Massey** | 64.19% vs 64.59% (p=0.331) | 0.1763 vs 0.1734 (**p=2.5e-5**) | 0.6435 vs 0.6342 (**p=1.2e-7**) |

## Interpretation

RPI beating NPI is a second, independent confirmation of a finding this
project already reached with HockeyBT — a simpler, differently-motivated
model outperforms NPI on the exact axis (win/loss prediction accuracy) that
matters most for tournament selection. Two unrelated approaches (a
Bradley-Terry extension and a linear win-pct formula) both clearing NPI's
bar reinforces
[reports/npi_critique.md](npi_critique.md)'s core argument: NPI's
complexity — the 75% SOS weight in particular, and the bad-wins filter's
selection bias — is not earning its keep. **Going back to the plain RPI
weights and dropping the bad-wins filter entirely would likely have been a
better direction than NPI's actual evolution.**

RPI losing to Massey confirms the pattern established throughout this
project's model-comparison work: a model built around goal differential
(once properly calibrated) captures more signal than one built purely from
win/loss/tie outcomes, regardless of which win/loss-based formula is used
(RPI's linear WP/OWP/OOWP, NPI's iterative weighted average, KRACH's MLE,
HockeyBT's Davidson-Beaver extension — Massey beats all of them on
calibration).

## Shipped

- `config.yaml`: added to `active_models` (kept active for its direct
  diagnostic value to the NPI question, not because it's the top model)
  plus an `rpi:` config block with the validated defaults.
- `run_system.py`: dispatches `RPI`.
- Tests: [tests/unit/test_rpi.py](../tests/unit/test_rpi.py) (7 tests) —
  fit/predict sanity, the RPI-equals-its-components formula check, the
  hand-verified OWP head-to-head exclusion, beta fit/fallback behavior, and
  a guard on the shipped defaults.
- Reproducible: [tests/rpi_backtest.py](../tests/rpi_backtest.py)
  (`python -m analysis.exploratory.rpi_backtest`).

## Open items

1. **The literal historical Pairwise Rankings (PWR) system** — which
   layered a discrete pairwise-comparison-count on top of RPI (record vs.
   common opponents, head-to-head, RPI itself, and record vs.
   tournament-caliber teams as four separate criteria) — was not
   implemented. PWR produces a rank ordering, not naturally a calibrated
   win probability, so it doesn't fit this project's predict()-based
   backtest harness without an awkward conversion step. RPI alone (the
   continuous rating PWR was partly built around) answers the "did NPI
   improve on what it replaced" question directly enough that building the
   full discrete PWR wasn't pursued.
2. **beta and the WP home/away multipliers are tuned on the same
   historical data used for final evaluation** — the same acknowledged
   limitation as every other model in this project's comparison work.
