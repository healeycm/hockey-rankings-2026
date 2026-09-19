# S6 and S8, Verified a Third Time Under DGP-C

## Both findings now confirmed across all three data-generating processes tested

`reports/e20_dgp_c_misspecified.md` flagged that S6 and S8's
DGP-independence argument (plausible, but only directly checked under
the Bradley-Terry DGP in `e16`/`e17`) should also be checked under the
genuinely neutral, misspecified-for-everyone mixed DGP, especially
since that DGP produced one real surprise (a small-N false tie) for S9.
Checked directly rather than left as an assumption.

**S6 (connectivity, `e21_connectivity_dgp_c.py`, 80 replications):**

| Model | Poisson DGP | Bradley-Terry DGP | Mixed DGP (this report) |
|---|---:|---:|---:|
| **KRACH mean field-spread ratio** | 875,397x | 474,245x | **561,928x** |
| Massey | 1,217x | 692x | 348x |
| NPI | 1.65x | 1.63x | 1.63x |
| RPI | 1.61x | 1.59x | 1.59x |

KRACH's instability is the same order of magnitude (roughly half a
million to nearly a million times the field's normal spread) under all
three DGPs. NPI and RPI stay tightly bounded (~1.6x) under all three.
**Confirmed a third, independent way.**

**S8 (schedule manipulability, `e22_schedule_manipulability_dgp_c.py`,
150 replications):**

| Model | Schedule alpha, Poisson | Schedule alpha, Bradley-Terry | Schedule alpha, Mixed (this report) |
|---|---:|---:|---:|
| **KRACH** | +1.12 | +0.80 | **+2.92** |
| Massey | +4.78 | +2.06 | +4.87 |
| NPI | +12.52 | +6.79 | +11.48 |
| **RPI** | **-31.45** | **-24.54** | **-26.64** |

Same ordering and signs preserved across all three DGPs: KRACH remains
the smallest (most schedule-invariant), RPI remains dramatically the
largest in magnitude and in the damaging (negative) direction. **Also
confirmed a third, independent way.**

## Net effect

Every "formula structure" finding in this workspace that has been
checked against all three available data-generating processes (S6, S8,
and S9's field-accuracy result) has survived all three without
reversing. The only finding shown to be DGP-sensitive is E1's
truth-recovery model-vs-model comparison, and even that turned out to
be a real (2-of-3-DGP) result rather than an outright artifact once
properly checked (`reports/e20_dgp_c_misspecified.md`). At this point,
every major model-comparison claim in this workspace has been checked
against at least two data-generating processes, and every one except
E1's has been checked against all three.

## Shipped

- `research/npi_critique/experiments/e21_connectivity_dgp_c.py`.
- `research/npi_critique/experiments/e22_schedule_manipulability_dgp_c.py`.
- Results: `research/npi_critique/results/e21_connectivity_dgp_c/`,
  `research/npi_critique/results/e22_schedule_manipulability_dgp_c/`.

## Open items

None specific to this report. S5 (echo chamber) remains the one
structural finding not yet checked against any DGP beyond the default
`simulate_season()` -- flagged in `reports/e18_echo_chamber.md`'s own
open items.
