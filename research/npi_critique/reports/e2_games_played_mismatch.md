# S1: Games-Played Mismatch

## A bug found and fixed before trusting these numbers

The first version of this experiment had a real bug, caught while
building the companion minimal worked example
(`e2b_minimal_worked_example.py`): `thin_multiple_teams` applied
`thin_team_schedule` sequentially per team with no protection between
calls, so if two designated teams happened to play each other,
thinning the *second* team could drop their shared game and silently
push the *first* team below its already-achieved target -- in the
12-team minimal example, deliberately constructed so the two thinned
teams play each other, this caused one team to end up with 6 games
instead of the intended 14. Fixed in
`research/npi_critique/harness/simulate.py` by having each subsequent
team's thinning pass protect already-finalized teams' games from being
dropped. Re-verified directly (`games_played()` on the fixed output
matches the target exactly) and both this experiment and
`e2b_minimal_worked_example.py` were re-run under the fix; a second,
independent bug in `e2b`'s own diagnostic print (comparing indices across
a DataFrame whose index had been reset by thinning) was also found and
fixed while verifying the first fix. Per your stated priority
(correctness over significance), both fixes and re-runs happened before
any number below was trusted enough to write up.

Effect on this experiment's conclusions: **negligible** -- only 1 of
1,600 thinning operations (200 reps x 8 teams) hit the rare fallback
edge case, since two randomly-chosen teams out of 60 rarely happen to
play each other in a 63-team league. The bug mattered far more for the
12-team minimal example below, where it was originally deterministic
(the two chosen teams always play each other).

## Summary

**Honest null result for the design tested so far.** Using the standard
`NPI` class (linear WP/SOS/QWB combination, no bad-wins filter),
randomly thinning 8 teams' schedules from ~36-41 games down to 31 --
matching the real Yale/Brown count -- while holding true strength and the
*already-simulated* game outcomes fixed, produces symmetric,
approximately zero-mean rank noise for **all three models tested**
(NPI, KRACH, Massey), not a unique NPI bias:

| Model | Mean Δrank | p05 | p95 | Worst single case |
|---|---:|---:|---:|---:|
| NPI | +0.06 | -6 | +6 | Δ=14 (true-rank 38, 39→31 games) |
| KRACH | -0.00 | -6 | +6 | Δ=17 (true-rank 50, 37→31 games) |
| Massey | +0.00 | -6 | +6 | Δ=16 (true-rank 29, 39→31 games) |

(200 replications, 8 randomly-selected teams thinned per replication,
4,800 team-model observations total; positive Δrank = got worse after
losing games.) No model shows a directional skew -- the tails are
symmetric around zero for all three -- and worst-case single-replication
swings are comparable in magnitude across models (14-17 rank positions).

## Corroborated by a small, hand-checkable minimal example

`e2b_minimal_worked_example.py`: a fully synthetic 12-team round-robin
league (every pair plays home-and-home, 22 games/team), two
middle-of-the-pack teams (true ranks 6 and 7 of 12) cut from 22 to 14
games -- a deliberately more aggressive 36% cut than the real ~14%
Yale/Brown cut, chosen to make any effect maximally visible in a system
this small. 2,000 replications, same fixed true strengths throughout (so
every replication is a fresh random *outcome* draw from identical
ground truth -- isolating outcome-luck as the only source of variation,
matching the "1-2 lucky results" framing directly):

| Model | Mean Δrank | Worst | Best |
|---|---:|---:|---:|
| NPI | -0.003 | +5 | -4 |
| KRACH | -0.025 | +6 | -5 |
| Massey | +0.005 | +4 | -4 |

Same conclusion as the large-N study: small, symmetric, model-agnostic
noise, not a directional NPI bias. One concrete replication (#42) is
printed in full in the script's output -- every one of Team06's and
Team07's 22 games, which 8 were dropped, and the resulting rank change
under all three models -- as the literal, hand-verifiable artifact this
project's reporting standard calls for.

**This does not mean the games-played concern is unfounded** -- it means
this specific design didn't find the mechanism the concern predicts, and
the most likely reason is scoped correctly below rather than papered
over.

## Why this design likely undersells the real concern

The mechanism motivating S1 in `PLAN.md` was specifically the
**bad-wins filter**: a team with more games has more discardable
bad results, so a *filtered* NPI variant should show a games-played
advantage that a games-played-agnostic model wouldn't. This experiment
used the plain `NPI` class, which (confirmed while building E1) does
**not** implement that filter -- `NPIGames` does, and is a materially
different implementation (its own iterative mandatory/optional-game
selection logic, different default QWB constants), not a simple
config toggle on `NPI`. Testing the filter's specific contribution
properly requires reconciling `NPIGames` against the same harness, which
was scoped out of this pass (see `reports/e1_truth_recovery.md` and
`PLAN.md`'s "Known blockers"). **The result above should be read as "the
linear NPI formula alone does not show a unique games-played bias," not
as "games-played mismatch is not a problem for NPI as actually
administered"** -- the actual administered system may use the filtered
variant, in which case this null result doesn't yet apply to it.

## What does hold up, regardless of model

All three models show real, symmetric sensitivity to games played -- a
team's rank can swing by double digits from losing 10 games' worth of
information alone, with no bias in either direction. This is expected
(A3 is about *systematic* bias, not variance) but worth stating plainly:
**a short schedule makes any of these metrics noisier, even if it
doesn't make any of them systematically wrong.** For a single-draw
selection decision, noise alone -- without bias -- can still mean a
short-schedule bubble team's fate depends more on luck than a
long-schedule team's does. That is a real fairness concern independent
of whether it's also a *bias* concern, and worth keeping distinct in the
paper's framing.

## Method

`research/npi_critique/experiments/e2_games_played_mismatch.py`. Real
2025-26 schedule; one full-season simulation per replication (Poisson
scoring DGP -- see the DGP caveat in `e1_truth_recovery.md`, which
applies here identically); 8 of the 60 teams with >31 games chosen at
random each replication (independent of true strength) and thinned to
exactly 31 by dropping non-conference games first (mirroring the real
mechanism -- a late-starting team misses early non-conference dates, not
a uniform random subset of its season). Every model refit on both the
full and thinned realizations of the *same* simulated outcomes, isolating
games-played from re-drawn randomness.

## Shipped

- `research/npi_critique/harness/simulate.py`: `thin_team_schedule`,
  `thin_multiple_teams` (both fixed for the cross-team protection bug
  above), `games_played`, `get_conference_map` (used by S2),
  `make_round_robin_schedule` (used by the minimal example below).
- `research/npi_critique/experiments/e2_games_played_mismatch.py` and
  `e2b_minimal_worked_example.py`.
- Results: `research/npi_critique/results/e2_games_played_mismatch/delta_rank_by_model.csv`,
  `research/npi_critique/results/e2b_minimal_worked_example/delta_rank.csv`.

## Open items

1. **The bad-wins-filter-specific test (`NPIGames`) is the real
   follow-up** -- this null result increases, not decreases, the
   importance of running it, since it's now the most likely place left
   for the hypothesized mechanism to actually show up.
2. ~~A small, hand-checkable minimal example~~ -- done, see above
   (`e2b_minimal_worked_example.py`).
3. Only one thinning target (31 games) and one group size (8 teams) were
   tested. A dose-response sweep (thin to 34, 32, 30, 28...) was not run.
