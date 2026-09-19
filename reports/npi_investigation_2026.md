# NPI Discrepancy Investigation (2026-01-27 snapshot)

**Goal:** figure out why `data/processed/npi_comparison_2026_01_27.csv` showed
our calculated NPI running low by a fairly consistent amount relative to the
published USCHO/CHN reference (`data/raw/npi_2026_01_27.csv`).

## Summary

The dominant error was **not a formula bug**. It was a data-leakage bug in the
comparison pipeline: our recalculation used every game in the season file
regardless of date, while the reference snapshot was frozen on 2026-01-27.
By the time the comparison was generated, additional games had been played
and folded into `games_archive.csv`, so the comparison was silently scoring
"NPI computed with extra information the reference didn't have" against "NPI
as of Jan 27" — for every team, every game.

A second, smaller bug compounded it: SOS (and the displayed Wgt W%) were
computed only over the games that survived the "bad wins" filter, instead of
over the full schedule.

| Metric | Before | After |
|---|---|---|
| NPI mean diff | −0.193 | −0.017 (residual now ~0-mean noise) |
| NPI MAE | ~0.19 | **0.069** |
| NPI RMSE | ~0.20 | **0.093** |
| SOS diff std | 0.406 | 0.186 |

## Root cause 1: no date cutoff in the comparison pipeline

`tests/run_npi_games.py` loaded `games_archive.csv` and filtered only by
`Season == 20252026` — no date filter. `tests/compare_npi_results.py` then
diffed that output against a reference file that represents a specific
calendar date. Any games played between 2026-01-27 and whenever the
comparison was actually run leaked into "our" numbers.

This explains the uniformity of the original bias: it wasn't one bad game per
team, it was every team's rating drifting from the extra weeks of the season
being folded into a converged, fully-interdependent rating system (NPI is a
fixed point over the whole graph — new games anywhere shift everyone's SOS,
not just the two teams that played them).

**Fix:** `run_npi_games.py` now accepts `--cutoff YYYY-MM-DD` and filters
`Date <= cutoff` before fitting. Applying `--cutoff 2026-01-27` alone dropped
the mean NPI bias from −0.193 to −0.017.

## Root cause 2: SOS computed over the filtered set, not the full schedule

`NPIGames.fit()` implements the "bad wins" filter: regulation wins beyond the
top 12 are only kept if they raise the weighted average, and some "good
losses" are dropped. The SOS and Wgt W% fields were being computed from
`final_games` — the post-filter survivor set — rather than the team's full
schedule.

Empirically, computing SOS over **all games** (independent of the bad-wins
filter) roughly halved the SOS error: diff std 0.406 → 0.186, MAE 0.245 →
0.147, tested across all 63 teams. This matches how the published numbers
behave — e.g. Western Michigan (1 dropped win) had its SOS overstated by
+0.58 under the old filtered-SOS logic vs. +0.21 after the fix, because
dropping a win removes a (usually weaker) opponent from the average and
inflates it.

**Fix:** [src/rankings/npi_games.py](../src/rankings/npi_games.py) now
computes both `sos` and `wp` (the displayed Wgt W%) over the team's full
game list, not `final_games`. Note: `src/rankings/npi.py` (the vectorized
model actually wired into `active_models` in `config.yaml`) has no bad-wins
filter at all, so it was never affected by this particular bug — but it also
means `npi.py` and `npi_games.py` are two different implementations that can
disagree (see "Open item" below).

## What's confirmed correct

A brute-force per-game formula search (toggling OT/neutral/location weight
schemes against every team's reference Wgt W%) confirms the win-weighting
formula already in the code — including the `(0.4 × location_mult) + 0.2`
OT-win credit and its complementary loss credit — reproduces the reference
Wgt W% **exactly** for the large majority of teams (many diffs of 0.000) and
with MAE 0.079% across all 63 teams. Alternative schemes tested (flat 0.6/0.4
OT split with or without location weighting) were all worse. **The core NPI
formula is not the source of the remaining error.**

## Residual error: isolated per-team data issues, not a formula bug

After both fixes, MAE is 0.069 (NPI) and the remaining outliers are
concentrated in a handful of teams (RPI, Minnesota State, Alaska Anchorage,
Union, LIU, Bemidji State...) rather than spread uniformly. A targeted
single-field toggle search (flip `IsOT`, `NeutralSite`, or `Result` on any
one game in a team's schedule) could not reproduce RPI's reference Wgt W%
via any plausible single correction — only flipping the actual winner of a
game got it within tolerance, which is not a credible data-entry error. This
points to either:
- a genuinely missing/extra game in our archive vs. the official record for
  these specific teams, or
- the reference snapshot's own cutoff timestamp not lining up exactly with
  midnight on 2026-01-27 (e.g. a same-day game already reflected in the
  reference but not yet in ours, or vice versa).

Chasing this further requires the official box-score-level schedule for the
handful of outlier teams, which wasn't available in this pass. Given the
overall MAE is now within season-to-season noise, this was left as an open
item rather than pursued team-by-team.

## Changes made

- [tests/run_npi_games.py](../tests/run_npi_games.py) — added `--season` /
  `--cutoff` args; **always pass `--cutoff` matching the reference date**
  when regenerating a comparison.
- [src/rankings/npi_games.py](../src/rankings/npi_games.py) — SOS and Wgt W%
  now computed over the full schedule, not the bad-wins-filter survivor set.
- [tests/unit/test_npi_reference.py](../tests/unit/test_npi_reference.py) —
  new regression test: fails if NPI/SOS MAE against the reference snapshot
  exceeds tolerance, so this doesn't silently drift again.
- `data/processed/npi_games_rankings.csv` and
  `data/processed/npi_comparison_2026_01_27.csv` regenerated with the fixes
  and the correct cutoff.

## Open items (not addressed here)

1. **`npi.py` vs `npi_games.py` divergence.** The production model
   (`npi.py`, vectorized, no bad-wins filter, QWB base/mult = 51.0/0.5) and
   the filter-implementing model (`npi_games.py`, QWB base/mult =
   50.5/0.45) disagree on defaults and on whether the bad-wins filter runs
   at all. `config.yaml`'s `weight_wp`/`weight_sos` keys are also unused by
   `npi.py`, which hardcodes 0.25/0.75 in the iteration loop. Worth
   consolidating into one canonical implementation before doing further
   NPI tuning work.
2. **RPI/Union/LIU/Alaska Anchorage residuals** — see above, needs official
   box scores to fully resolve.
