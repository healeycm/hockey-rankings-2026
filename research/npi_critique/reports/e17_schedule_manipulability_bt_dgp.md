# S8, DGP-Verified: Schedule Manipulability Confirmed Robust

## Result: same ordering, same signs, smaller magnitudes

Re-ran `e12_schedule_manipulability.py`'s exact design (one team's true
strength fixed at the field median, its real schedule structure held
fixed while opponents are redrawn from five true-strength percentile
bands) under `simulate_season_bradley_terry()` instead of
`simulate_season()`, 150 replications:

| Model | Schedule alpha, Poisson DGP (`e12`) | Schedule alpha, Bradley-Terry DGP (this report) |
|---|---:|---:|
| **KRACH** | **+1.12** | **+0.80** |
| Massey | +4.78 | +2.06 |
| NPI | +12.52 | +6.79 |
| **RPI** | **-31.45** | **-24.54** |

**Every model's sign and relative ordering is preserved.** KRACH remains
the most schedule-invariant by a wide margin under both DGPs. RPI
remains dramatically the most schedule-manipulable, in the same
(damaging) direction, under both DGPs -- still roughly 3-4x larger in
magnitude than NPI's effect, still negative (rank *improves* with a
tougher schedule, holding true ability fixed). NPI's real, moderate
effect also survives, roughly halved in magnitude but not eliminated.

**S8's finding is confirmed DGP-robust, joining S6 and S9.** Combined
with `reports/e16_connectivity_bt_dgp.md`, every "formula structure"
finding in this workspace that has now been checked against a second,
genuinely different data-generating process has survived the check --
consistent with the reasoning in `reports/e15_dgp_robustness.md` that
these properties depend on how a model fits a given record, not on how
that record was generated.

## Shipped

- `research/npi_critique/experiments/e17_schedule_manipulability_bt_dgp.py`.
- Results: `research/npi_critique/results/e17_schedule_manipulability_bt_dgp/`.

## Open items

None specific to this report -- `e12`'s original open items (single
target team/strength value tested; RPI's mechanism not directly
decomposed) apply identically here.
