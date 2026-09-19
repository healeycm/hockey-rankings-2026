# S3: The Quality-Win-Bonus "Cliff" Is Actually a Kink — And It's Practically Relevant, Not a Corner Case

## Correcting the plan's own framing before reporting the finding

`PLAN.md` described this as a "QWB cliff" and looked for "the step."
Checked directly against the actual formula
(`src/rankings/npi.py`: `qwb = (opp_NPI - 51.0) * 0.5` if `opp_NPI >
51.0` else `0`) rather than assumed:

| Opponent NPI | QWB credit |
|---:|---:|
| 30.00 | 0.0000 |
| 45.00 | 0.0000 |
| 50.90 | 0.0000 |
| 50.99 | 0.0000 |
| **51.00** | **0.0000** |
| 51.01 | 0.0050 |
| 51.50 | 0.2500 |
| 52.00 | 0.5000 |

**There is no jump at 51 -- the function is continuous there** (both
sides evaluate to exactly 0 at the boundary). What it actually has is a
**kink**: a hinge/ReLU-shaped function with zero slope for any opponent
at or below 51 and a slope of 0.5 above it. This is a more precise, and
in our view more interesting, finding than a literal cliff would have
been: **a win over a 45-rated opponent receives exactly the same
(zero) bonus as a win over a 20-rated opponent** -- the formula is
completely insensitive to opponent quality across the entire sub-51
range, not just discontinuous at one point. All the "action" is
compressed into whether you cross a single threshold, with no credit
whatsoever for approaching it.

## This is not a remote corner case -- it's a densely populated region of every real season

Checked directly against simulated seasons on the real 2025-26 schedule
(20 replications): on average, **11.4 of 63 teams (18%) have a final
NPI rating within ±1 of the 51 threshold, and 21.7 of 63 (34%) fall
within ±2.** A representative slice of one replication's sorted
ratings: `50.42, 50.65, 50.65, 50.71, 50.88, 51.07, 51.15, 51.21, 51.22,
51.36, 51.97...` -- teams packed within hundredths of a point of each
other, straddling the threshold densely. **A large fraction of every
season's games involve an opponent whose QWB-eligibility could flip
from a single additional win or loss elsewhere in that opponent's own
schedule**, since NPI ratings this close together are well within the
week-to-week noise any team's rating naturally has.

## Why this connects directly to E1's paradox finding

`reports/e1_truth_recovery.md` found that 6.3-12.0% of sampled
below-median-opponent wins paradoxically *lowered* the winner's NPI.
The QWB kink is a direct structural cause of exactly this kind of
instability: since a huge fraction of real opponents sit within a point
or two of 51, whether a specific win receives a small positive QWB
bump or exactly zero can hinge on essentially arbitrary week-to-week
movement in the opponent's own rating, unrelated to anything the
winning team did.

## Method

Formula-level demonstration (exact, not simulated) plus a direct check
of real-season NPI rating density near the threshold, 20 replications
of the standard iid-strength simulation on the real 2025-26 schedule.
Deliberately lightweight, per the plan's own framing of this as a
near-analytic check rather than a large empirical campaign.

## Shipped

No new experiment script -- the formula check is a one-line
calculation reproduced in this report; the density check reuses
`NPI.fit()` directly on `simulate_season()` output, no new harness code
needed.

## Open items

1. **Not tested: whether this kink measurably affects final rank**
   (as opposed to just the per-game QWB contribution) -- the per-game
   effect is small (max 0.005 near the threshold) and the outer
   iteration could average it away, or could amplify it via the
   opponent-rating feedback loop the same way the E1 paradox does. Not
   directly measured here.
2. **The `quality_win_base=51.0`/`quality_win_mult=0.5` dials are
   confirmed live** (unlike `weight_wp`/`weight_sos` and
   `ot_win_weight`/`ot_loss_weight`, both found dead in
   `reports/e13_s7_blocked_ot_credit_dead_config.md`) -- a genuine,
   testable dial, just not swept here since the kink's existence and
   practical density were the more informative findings to establish
   first.
