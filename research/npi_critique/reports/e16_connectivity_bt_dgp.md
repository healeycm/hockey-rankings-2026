# S6, DGP-Verified: The Connectivity Finding Is Confirmed DGP-Independent

## Result: the argument in e15 was correct, now directly checked rather than assumed

`reports/e15_dgp_robustness.md` argued that S6's connectivity finding
should be DGP-independent, since it tests a property of KRACH's
iterative MLE fitting procedure applied to a given win/loss record, not
of how that record was generated -- but did not verify this directly.
Re-ran `e11_connectivity_degenerate_cases.py`'s exact design under
`simulate_season_bradley_terry()` instead of `simulate_season()` (100
replications, same forced-undefeated/forced-winless setup):

| Model | Poisson DGP (`e11`) | Bradley-Terry DGP (this report) |
|---|---:|---:|
| **KRACH mean field-spread ratio** | **875,397x** | **474,245x** |
| Massey mean field-spread ratio | 1,217x | 692x |
| NPI mean field-spread ratio | 1.65x | 1.63x |
| RPI mean field-spread ratio | 1.61x | 1.59x |
| KRACH mean undefeated rating | 5,883 | 5,915 |
| KRACH mean winless rating | 0.0092 | 0.0138 |

**The finding is confirmed, not just plausible.** KRACH's instability is
the same order of magnitude under a completely different way of
generating who wins each game (474,245x vs. 875,397x -- both roughly
half a million to a million times the field's normal spread), while
NPI and RPI stay tightly bounded (~1.6-1.7x) under both DGPs, exactly as
the theoretical argument predicted: this is a property of the *fitting*
step (an unregularized Bradley-Terry MLE has no finite optimum for a
perfect separator, regardless of how the perfect-separator record came
to exist), not of the outcome-generating process.

Collateral distortion to the rest of the field also replicates the
earlier pattern: Massey shows the least disruption to unrelated teams'
ranks under both DGPs (1.85 here vs. 1.22 in `e11`), and KRACH is not
distinguishably worse than NPI/RPI on this specific measure under
either DGP.

## What this means

S6 now joins S9 as a finding verified under two genuinely different
data-generating processes. Combined with S8 (verified separately, see
`reports/e17_schedule_manipulability_bt_dgp.md`), **every "formula
structure" finding in this workspace that was checked against a second
DGP has survived**, while the one "model-vs-model truth-recovery
comparison" checked (E1) did not. This is consistent with, and
strengthens, the practical rule stated in `PLAN.md`'s "READ THIS FIRST"
section.

## Shipped

- `research/npi_critique/experiments/e16_connectivity_bt_dgp.py`.
- Results: `research/npi_critique/results/e16_connectivity_bt_dgp/`.

## Open items

None specific to this report -- the open items from `e11`'s original
report (Massey's spread-ratio metric not being fully meaningful on its
own natural scale; only one undefeated/winless pair tested) apply
identically here.
