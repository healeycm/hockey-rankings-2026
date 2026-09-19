# S5: The Echo Chamber Is Real for KRACH and Massey — Not for NPI

## The question real data can't isolate

`reports/npi_critique.md` Section 6 found a strong real-data correlation
(ρ=0.886) between a conference's non-conference win% and its members'
average schedule strength -- suggestive of an echo chamber where a
conference's own success inflates everyone in it. But real conferences
always have *some* true strength difference confounded with their
connectivity, so real data alone can't tell whether that correlation
reflects genuine signal or a structural artifact of sparse
cross-conference play. Simulation can, by setting every conference's
true strength EQUAL (the null hypothesis) and varying only the
cross-conference game fraction.

## Design

A fully synthetic schedule (6 conferences of 10 teams each,
`make_multiconference_schedule`), cross-conference game fraction swept
from sparse (10%) to well-mixed (60%) -- the real 2025-26 league-wide
average is 38.5%, between the 0.25 and 0.40 levels tested. Every team's
true strength drawn from the SAME distribution regardless of conference
(zero true conference effect by construction). Any measured clustering
of ratings by conference is therefore provably a network artifact, not
signal. Measured as normalized clustering = (between-conference rating
std) / (overall rating std), comparable in scale across all four models.

## Result: KRACH and Massey have a real echo chamber; NPI mostly doesn't; RPI gets *worse* with more mixing

| Cross-conf. fraction | KRACH | Massey | NPI | RPI |
|---:|---:|---:|---:|---:|
| 0.10 (sparse) | **0.507** | 0.428 | **0.273** | 0.294 |
| 0.25 (~ real average) | 0.405 | 0.350 | 0.281 | 0.354 |
| 0.40 | 0.352 | 0.326 | 0.289 | 0.389 |
| 0.60 (well-mixed) | 0.307 | 0.315 | 0.301 | **0.383** |

**Sparse-to-mixed change, with significance:**

| Model | Δ (sparse → mixed) | p-value |
|---|---:|---:|
| **KRACH** | -0.199 | **p=9.98e-17** |
| **Massey** | -0.113 | **p=6.04e-09** |
| NPI | +0.028 | p=0.079 (not significant) |
| **RPI** | +0.089 | **p=1.82e-06** |

**KRACH shows the largest genuine echo-chamber artifact of any model,
and it is real and substantial** -- at sparse connectivity, KRACH's
apparent conference clustering (0.507) is nearly double NPI's (0.273),
purely from network sparsity with zero true conference difference to
detect. This fades significantly as cross-conference play increases.
Massey shows the same pattern, smaller in magnitude. **NPI shows no
significant echo-chamber effect at all** across the entire range
tested, and critically, **it starts the lowest of all four models at
the sparse end** -- exactly the connectivity regime real conferences
with limited non-conference scheduling actually sit in.

**This reverses the a priori concern.** NPI's explicit SOS-averaging
mechanism was the natural suspect for an echo chamber (it's literally
built to average opponents' ratings), while KRACH's opponent-adjusted
MLE was assumed likely to handle sparse connectivity more gracefully.
The opposite is true here: KRACH's iterative fixed-point solution is
apparently *more* sensitive to sparse-network noise producing spurious
between-group structure, while NPI's simpler, bounded averaging is
comparatively immune to it.

**RPI is the real outlier, and its pattern is not explained.** RPI's
clustering *increases* significantly as cross-conference play
increases -- the opposite direction from both the a priori hypothesis
and from KRACH/Massey's pattern. This is plausibly connected to RPI's
OWP/OOWP two-level compounding structure already implicated in its
extreme schedule-manipulability result (`reports/e12_schedule_manipulability.md`),
since more cross-conference games mean more of a team's schedule
strength is computed through that compounding mechanism against
unfamiliar opponents -- but this is a plausible mechanism, not a
verified one.

## Why this matters for the critique's overall shape

This is the second finding (after S9's field-accuracy result and S6's
connectivity result) where **KRACH, not NPI, shows the structural
weakness a reader might expect NPI to have.** Combined with S8 (RPI is
the most schedule-manipulable, not NPI), the accumulating pattern
across this whole critique is not "NPI is worse across the board" --
it's that different formulas have different, specific failure modes,
and NPI's crude, bounded, averaged design is repeatedly *more* robust
to network-structure artifacts than either KRACH's likelihood-based or
RPI's compounding approach, even though NPI loses on other axes (S2,
S8's own moderate schedule-alpha, the QWB kink in S3, the two dead
config dials in S7).

## Method

`research/npi_critique/experiments/e18_echo_chamber.py`. New harness
function `make_multiconference_schedule()` (in `simulate.py`):
synthetic schedule with controllable cross-conference fraction, 60
replications per level. Note: the generator's per-team game count
requires the input `games_per_team` parameter to be roughly half the
intended realized value (each team's own opponent draws plus its
appearances as others' opponents roughly double the count) -- verified
directly (input 18 → realized mean 36.0 games/team, comparable to the
real schedule's 30-41 range) and documented in the harness code.

## Shipped

- `research/npi_critique/harness/simulate.py`: `make_multiconference_schedule()`.
- `research/npi_critique/experiments/e18_echo_chamber.py`.
- Results: `research/npi_critique/results/e18_echo_chamber/results.csv`.

## Open items

1. **RPI's increasing-clustering pattern is unexplained** -- the OWP/OOWP
   compounding hypothesis is plausible but not directly tested; would
   need per-component decomposition (as flagged for S8) to confirm.
2. **Only one conference size/count configuration tested** (6
   conferences of 10). Real conferences range from 7 to 12 teams;
   whether the pattern holds at more realistic, uneven conference sizes
   is untested.
3. **Not re-checked under the Bradley-Terry DGP** -- unlike S6 and S8,
   this finding depends partly on how margin/outcomes propagate through
   an iterative average (Massey's regression, NPI's SOS iteration), so
   it may be less safely assumed DGP-independent than S6/S8 were, and
   the reasoning in `PLAN.md`'s "READ THIS FIRST" section should not be
   extended to this result without a direct check.
