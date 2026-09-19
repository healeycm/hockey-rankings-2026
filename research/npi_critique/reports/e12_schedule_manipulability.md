# S8: Schedule Manipulability — RPI, Not NPI, Is the Most Exploitable Metric

## The question real data can never answer

Can a team raise its rank without getting any better, purely through
who it schedules? Real teams can't be re-run on a counterfactual
schedule, so this is uniquely a simulation question. Design: fix one
team's true strength at the field median for all 150 replications. Hold
its schedule *structure* exactly fixed (same dates, same home/away
assignment, same total games -- its real 37-game 2025-26 slate) and only
relabel *who* it plays, drawing opponents from five true-strength
percentile bands (weakest fifth of the field through strongest fifth).
Its resulting win-loss record necessarily changes with opponent strength
-- a fixed-ability team beats weak opponents more -- that's expected and
correct. The question is whether induced rank moves by *more* than the
unchanged true strength justifies.

## Result: KRACH is nearly invariant, NPI shows a real effect, RPI is dramatically worse than both

| Opponent band | KRACH | Massey | NPI | **RPI** |
|---|---:|---:|---:|---:|
| Weakest fifth (0-20) | 33.6 | 30.8 | 25.3 | **52.5** |
| 20-40 | 33.1 | 31.8 | 29.8 | **41.7** |
| Middle fifth (40-60) | 33.8 | 33.1 | 33.3 | **33.4** |
| 60-80 | 32.8 | 33.1 | 34.6 | **23.3** |
| Strongest fifth (80-100) | 33.9 | 35.7 | 40.2 | **12.9** |

**Schedule alpha** (fitted slope, rank positions per unit of mean
opponent strength; true rank is ~32 throughout, unchanged by
construction):

| Model | Alpha |
|---|---:|
| **KRACH** | **+1.12** |
| Massey | +4.78 |
| NPI | +12.52 |
| **RPI** | **-31.45** |

**KRACH is essentially schedule-invariant** -- its induced rank for this
fixed-ability team barely moves (33.6 to 33.9) regardless of whether it
plays the weakest or strongest fifth of the field. This is exactly the
theoretical prediction for an opponent-strength-adjusted MLE, now
empirically confirmed rather than assumed. **NPI shows a real,
substantial effect** -- an 11x larger slope than KRACH's -- consistent
with the underrating-a-schedule-battered-team pattern already found in
S2's strength sweep (`e3b`). **RPI shows an effect nearly 3x larger than
NPI's, in magnitude, and it runs in the surprising direction**: going
from the weakest to the strongest opponent band improves this
fixed-ability team's rank from 52.5 to 12.9 -- a roughly 40-position
swing from scheduling alone.

## Why this reframes earlier findings

`reports/rpi_results.md` found RPI beats NPI on predictive accuracy and
recommended it as evidence that "going back to the plain RPI weights...
would likely have been a better direction than NPI's actual evolution."
**This study complicates that recommendation directly.** On the
specific axis of schedule manipulability -- arguably the more
policy-relevant property for a *selection* metric, since it's exactly
the failure mode a team's own scheduling choices could exploit -- RPI is
dramatically worse than NPI, not better. The likely mechanism: RPI's
formula is 75% opponent-quality by weight (`0.50*OWP + 0.25*OOWP`), and
unlike NPI's single-level SOS average, RPI's OWP term compounds -- it
credits a team for playing opponents whose *own* win percentage (itself
inflated by whatever schedule those opponents played) is high, a
two-level schedule-strength cascade that NPI's flatter formula doesn't
have. **No single model in this roster is uniformly better or worse
across every axis tested in this critique** -- NPI beats RPI here just
as clearly as RPI beat NPI on accuracy in the earlier report, and both
findings should be reported together, not separately.

## Method

`research/npi_critique/experiments/e12_schedule_manipulability.py`. One
real 37-game team (schedule dates/home-away fixed), true strength fixed
at the field median; for each replication, all other teams' strengths
drawn iid (sigma=0.4); the target's opponent on each of its scheduled
dates redrawn (with replacement) from one of five true-strength
percentile bands among the other 62 teams. Every other team's own
real-schedule games are otherwise unaffected, with one documented,
minor bookkeeping side effect: a substitute opponent gains one extra
game against the target beyond its own real slate for each date it's
drawn, at the cost of whichever team was originally scheduled there --
this does not bias the target's own measured rank, which is this
study's only outcome of interest.

## Shipped

- `research/npi_critique/experiments/e12_schedule_manipulability.py`.
- Results: `research/npi_critique/results/e12_schedule_manipulability/results.csv`.

## Open items

1. **Only one target team and one true-strength value (field median)
   were tested.** Repeating at a below-median or above-median true
   strength would show whether RPI's dramatic effect is specific to a
   .500-caliber team or general across the strength range -- connects
   directly to S2's finding (`e3b`) that NPI's own schedule-sensitivity
   is itself strength-dependent.
2. **The mechanism for RPI's effect (OWP's two-level schedule-strength
   cascade) is a plausible explanation, not a directly verified one** --
   would require decomposing RPI's WP/OWP/OOWP components separately
   across the percentile bands to confirm which term is actually
   driving the swing.
3. **Massey's small but nonzero alpha (+4.78) was not investigated
   further** -- plausibly its fitted home-ice/rest covariates or ridge
   shrinkage interacting with a smaller effective sample as opponent
   composition shifts, not examined directly.
