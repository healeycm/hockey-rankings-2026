# S10: Single-Game Leverage — Massey Is Most Stable, RPI Least

## Result

Leave-one-game-out across simulated full seasons (10 replications, 40
randomly sampled game removals each, 400 total, all four models refit
on both the full season and the season-minus-one-game): how far does a
single game's removal move the two teams that played it?

| Model | Mean direct rank shift | 90th pct. | Max observed | Mean field-wide shift |
|---|---:|---:|---:|---:|
| **Massey** | **1.35** | 3.0 | 7 | **0.101** |
| NPI | 1.60 | 4.0 | 6 | 0.106 |
| KRACH | 1.77 | 4.0 | 10 | 0.127 |
| **RPI** | **1.85** | 4.0 | 8 | **0.157** |

**Massey is significantly the most stable of the four** (beats KRACH,
NPI, and RPI, all p<0.003) -- a single game's outcome moves the two
teams involved by about 1.35 rank positions on average under Massey,
versus 1.85 under RPI. **RPI is significantly the least stable**
(worse than NPI, p=0.0058; worse than Massey, p<0.0001). NPI sits
between Massey and KRACH, marginally better than KRACH (p=0.066, not
quite significant) and significantly better than RPI.

## Consistent with the pattern across S5, S8, and this study

This is the third study in the workspace (after S8's schedule
manipulability and S5's echo chamber) where **RPI, not NPI, comes out
as the most fragile/exploitable model**, and where **Massey shows the
most consistent stability**. NPI lands in the middle across all three:
never the best, never clearly the worst. A single game occasionally
moving a team by up to 10 rank positions (KRACH's max) or 8 (RPI's max)
is a real, concrete illustration of why a selection metric's stability
matters beyond its average accuracy -- for a single bubble team on
selection day, that occasional large single-game swing is exactly the
scenario that matters most, and it isn't visible in an average-accuracy
number at all.

## Method

`research/npi_critique/experiments/e19_single_game_leverage.py`. Real
2025-26 schedule, iid true strengths, 10 replications; 40 games per
replication removed one at a time (all others held fixed) and every
model refit on both the full season and the season-minus-one-game.
Direct shift = the larger of the two rank changes for the specific
teams that played the removed game; field shift = mean absolute rank
change across the entire 63-team field, capturing any broader ripple
effect beyond the two teams directly involved.

## Shipped

- `research/npi_critique/experiments/e19_single_game_leverage.py`.
- Results: `research/npi_critique/results/e19_single_game_leverage/results.csv`.

## Open items

1. **Only iid strengths were tested** -- not re-run under
   conference-stratified strengths or either alternative DGP.
2. **Games were sampled uniformly at random**, not targeted at
   bubble-relevant (e.g., top-30) teams specifically, where leverage
   arguably matters most for actual selection consequences -- a
   targeted resample would be a natural follow-up.
