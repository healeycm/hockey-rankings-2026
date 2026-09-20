# W10 — Schedule manipulability on women's D-I hockey

**Status:** Done (single DGP — see limitation below). **Tests P8**
(pre-registered: "RPI remains the most schedule-manipulable metric").
**P8 is confirmed, and by an even larger margin than men's.**

## Method

Direct counterpart to the men's S8/E12
(`research/npi_critique/experiments/e12_schedule_manipulability.py`), same
hybrid design, reusing the shared simulation harness
(`research/npi_critique/harness/simulate.py`, imported read-only): a real
season's schedule *structure* (dates, home/away assignment) is held fixed
for one target team (St. Cloud State, 37 real games — the same
target-selection rule as men's, unchanged for women's since game counts
are in the same range), but the opponent on each date is redrawn from a
specific true-strength percentile band (0-20 through 80-100), and outcomes
are simulated from known ground truth — the target's own true strength is
fixed at the field median throughout, so any movement in its *induced
rank* as opponent strength changes is purely a schedule effect, not a real
ability change. 150 replications x 5 bands, matching men's exact
replication count for direct comparability.

## Result: schedule alpha (rank-position shift per unit of mean opponent strength)

| Model | Women's alpha | Interpretation |
|---|---:|---|
| **RPI** | **-21.07 +/- 0.76** | By far the most manipulable -- rank improves by ~21 positions per unit increase in opponent strength |
| NPI | +9.12 +/- 0.62 | Second-most manipulable -- but in the OPPOSITE direction (see below) |
| Massey | +3.60 +/- 0.61 | Small but statistically clear |
| KRACH | +1.16 +/- 0.71 | Smallest, closest to the "should be near zero" ideal |

Mean induced rank by band (true rank ~23.3 throughout, unchanged):

| Band | KRACH | Massey | NPI | RPI |
|---|---:|---:|---:|---:|
| 0-20 (weakest opponents) | 23.6 | 21.5 | **17.7** | 37.2 |
| 80-100 (strongest opponents) | 23.8 | 24.6 | **28.3** | **9.0** |

## RPI: confirms the men's finding, more sharply

**RPI's manipulability replicates and is larger in magnitude than the
men's-hockey result.** A median-strength team's RPI-induced rank swings
from 37th (worst) to 9th (best) -- over half the field -- purely by
schedule, with true ability never changing. This is the single largest
alpha this project has measured for RPI in either division and directly
confirms P8's headline claim.

## NPI: a genuine, unexpected divergence worth reporting plainly

**NPI moves in the opposite direction from RPI**, and this was not
predicted. Playing *weaker* opponents improves a median team's NPI rank
here (17.7 vs. 28.3 for strong opponents) -- the reverse of what NPI's
75%-SOS-weighted formula would suggest at first glance. A plausible
mechanism, not yet confirmed: a median-strength team facing mostly strong
opponents loses most of its games, and NPI's 25%-weighted win-percentage
term punishes that pile of losses more than the 75%-weighted SOS term
rewards facing strong competition -- i.e., for a team near the field's
middle, NOT winning may cost more than the opponent-quality bonus is worth.
This is a real, measured effect in this simulation, but it is **a
single-DGP result** (see limitation) and a genuinely new finding this
project hasn't seen in men's-hockey manipulability testing -- the men's S8
report does not describe NPI moving opposite to RPI's direction. Worth
flagging for a closer look rather than asserting as established.

## Limitation, stated directly

**This is one data-generating process, not the three the men's-hockey
critique's own methodological standard requires** ("every finding must be
robust across at least two different DGPs" -- PLAN.md's cross-cutting
requirement, inherited from `research/npi_critique/PLAN.md`). The men's
S8/E12 result itself was similarly run on one DGP before being
cross-validated in E17 (Bradley-Terry DGP) and E22 (DGP-C, deliberately
misspecified) -- that cross-validation has NOT yet been done for women's.
RPI's finding is large enough (-21 vs. the next-largest |9.1|) that it is
unlikely to be a pure DGP artifact, but the NPI reversal specifically
should be treated as provisional until checked under a second DGP --
exactly the kind of surprising result that most needs a robustness check
before it goes in a paper, not the kind that should be reported without one.
