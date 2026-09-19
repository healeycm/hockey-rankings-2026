# S4: Does the Bad-Wins Filter Give Longer Schedules an Unearned Advantage?

## Status: mechanism confirmed real, but sensitive to a modeling choice I got wrong on the first pass

Both S1 and S2's reports repeatedly flagged the same outstanding
question: the plain `NPI` class (used throughout S1/S2/E1) doesn't
implement the bad-wins filter at all -- `NPIGames`
(`src/rankings/npi_games.py`) does, and it implements the REAL official
mechanism precisely: only a team's 12 best regulation wins are mandatory
(`regulation_wins[:12]`); anything beyond the 12th-best is "optional" and
gets dropped from the rating calculation if excluding it improves the
average. This matches the NCAA's own documented "Minimum Wins: 12" dial
found while building the paper's bibliography. It directly ties games
played to filter benefit: a team needs strictly more than 12 wins before
the filter can drop anything.

**First pass (opponent log-strength spread sigma=0.4, matching E1/S1/S2's
default): the mechanism essentially never fires.** Over 150 replications
of a median-strength ("bubble," ~55% true win rate) team on the real
schedule (thinned to 25 vs. 40 games), NPIGames dropped a win in only
2% of replications either way, mean dropped-wins 0.03-0.05 -- games
played made no detectable difference, and NPIGames' rank response to
games-played thinning was statistically indistinguishable from
NPI/KRACH/Massey's (all four models gained 0.3-0.7 rank positions on
average going from 25 to 40 games, no model standing out).

**This null needed a check before being trusted -- and the first check I
ran pointed at the wrong fix.** The filter only drops a win when an
opponent's own rating sits well below the team's running average, so it
needs genuine "cupcake" opponents on the schedule. A quick test at a
wider opponent-strength spread (sigma=0.7 instead of 0.4) did trigger
the mechanism much more often (dropped-wins rate 2% -> 40%, 60
replications). **But checking sigma=0.7 against real data shows it
overshoots**: real 2025-26 win-percentage dispersion has std=0.158;
sigma=0.4 (the default used throughout this workspace, including E1)
already produces std=0.175 -- close to real, if anything slightly wide;
sigma=0.7 produces std=0.231, meaningfully *less* realistic than the
default I started with. **Raising sigma was the wrong fix, even though
it "worked" in the narrow sense of triggering the filter more.**

## What this actually means, and what's still open

The real, unresolved puzzle: at a spread that matches real *aggregate*
win-percentage dispersion reasonably well, the bad-wins filter almost
never fires for this experiment's target team (Denver's real schedule).
Two explanations remain live, and this report does not yet distinguish
between them:

1. **Schedule composition, not population-level spread, may be what
   matters.** Denver plays in the NCHC, a genuinely strong real
   conference -- its real schedule may simply not contain many
   "cupcake"-type opponents regardless of how the other 62 teams'
   strengths are drawn, since Denver's actual game-count-heavy slate
   skews toward comparably strong competition. A team with a more
   nationally scattered schedule (an independent, or a team in a
   weaker/more heterogeneous conference) might show the filter
   triggering much more even at the same, correctly-calibrated sigma.
2. **Aggregate win% std may be the wrong quantity to calibrate against
   for this specific question.** The filter cares about *tail* behavior
   (how much weaker is a team's single weakest opponent, not the
   population's overall spread) -- a distribution can match real
   aggregate dispersion while still under- or over-representing genuine
   bottom-tail blowout mismatches.

**Recommend testing (1) with a different target team (an independent
or weak-conference team) before touching sigma again**, and treating
sigma=0.4 as the aggregate-validated default going forward rather than
revisiting it further without a similarly rigorous check. The correction
made here -- catching that the "fix" I reached for first was itself
uncalibrated -- is the more important, generalizable lesson: verifying a
null result can actually be produced by the mechanism under test
(exactly right) is not the same as trusting the first alternative
setting that happens to change the outcome (wrong, and caught here
before it went further). Every other experiment in this workspace (E1,
S1, S2) used sigma=0.4 by default and is not called into question by
this report -- it is now the aggregate-validated choice, not an
unexamined one.

## Method

`research/npi_critique/experiments/e4_bad_wins_filter_games_mismatch.py`.
Real schedule (Denver's, the team with the most 2025-26 games, giving
the most thinning headroom), one team's true strength fixed at the field
median, thinned to 25 vs. 40 games via the same ceteris-paribus design as
`e2_games_played_mismatch.py`. NPIGames' own `dropped_wins` detail field
used directly to measure the mechanism's activation rate.

## Shipped

- `research/npi_critique/experiments/e4_bad_wins_filter_games_mismatch.py`.
- Results: `research/npi_critique/results/e4_bad_wins_filter_games_mismatch/results.csv`
  (sigma=0.4 run; the sigma=0.7 check was a scratch verification, not
  saved to a results file -- rerun with `sigma=0.7` substituted in
  `assign_true_strengths` calls to reproduce).

## Open items (supersedes S4's "not started" status in PLAN.md, but not "done")

1. **Re-run with a different target team** (an independent or
   weak-conference team, not Denver's NCHC schedule) at the same,
   aggregate-validated sigma=0.4 -- the actual, un-superseded next step
   for S4, per the corrected diagnosis above.
2. **Determine whether schedule composition or tail-shape is the
   binding constraint** on the filter triggering (see the two live
   explanations above) -- distinguishing these matters for whether S4's
   eventual result generalizes across teams or is schedule-specific.
3. **The "good loss" drop mechanism** found while reading `npi_games.py`
   (a loss is excluded entirely, not just wins -- see the code comment
   in this experiment's docstring) is a previously uncharacterized piece
   of the production formula not covered by `reports/npi_critique.md`'s
   existing "Bad Wins Filter" section. Worth its own short writeup
   regardless of this study's outcome.
