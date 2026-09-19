# S9: Selection-Field Accuracy — NPI's First Clear Strength in This Workspace

> **SUPERSEDED, in part -- see `reports/e5b_selection_field_accuracy_conf_stratified.md`.**
> This report's headline finding rests on `assign_true_strengths`,
> which draws every team's strength independently -- implicitly
> assuming all conferences are equal in expectation. Checked against
> real 2025-26 data, they are not (real conferences differ by up to
> 0.26 in non-conference win%, and conference membership accounts for
> roughly 40% of total team-level win% variance). Re-run with a
> properly calibrated conference-stratified strength assignment, **the
> finding below reverses**: KRACH and Massey lead, NPI and RPI fall
> behind. Kept below for the record and because the games-played and
> per-team findings (LIU/independents exclusion pattern) are not
> conference-strength-dependent and still stand -- but the "NPI's first
> clear strength" framing in this report's title and summary should be
> read as retracted, not confirmed. Caught by a direct question, not by
> this project's own review process -- see the linked report for the
> full account.

## Summary

Every prior study in this workspace tested a specific mechanism
(games-played, conference effects, the bad-wins filter) using a
deliberately constructed scenario. This one asks the actual policy
question directly, with no construction at all: **given a real season's
schedule and a known ground-truth team strength, how many of the true
top-16 teams does each metric actually seat in the tournament field?**
300 replications, standard iid true strengths (log-normal, sigma=0.4,
validated against real win% dispersion in
`reports/e4_bad_wins_filter_games_mismatch.md`), the real 2025-26
schedule.

**NPI is not the worst model on this metric -- it beats both KRACH and
RPI.**

| Model | Mean overlap (of 16) | % of seasons missing 4+ true top-16 teams |
|---|---:|---:|
| **Massey** | **12.72** | **43.3%** |
| NPI | 12.35 | 55.3% |
| KRACH | 12.01 | 64.3% |
| RPI | 11.83 | 68.3% |

This is worth stating plainly since it cuts against the framing this
workspace's studies have mostly been testing: on the one metric that
most directly operationalizes "did the committee pick the right field,"
**NPI outperforms two of the three alternative methods tested here**,
trailing only Massey. This is a genuine point in NPI's favor, not a
weakness, and the paper should report it as such.

## No games-played selection bias, confirmed a second, independent way

S1 (`reports/e2_games_played_mismatch.md`) found no unique NPI bias from
games-played alone, using a deliberately constructed thinning
experiment. This experiment finds the same null in the real,
un-manipulated setting: every model's wrongly-excluded and
wrongly-included teams sit within a few points of the real schedule's
baseline rate of below-median-games-played teams (31.7%):

| Model | % wrongly-excluded that are below-median-games | % wrongly-included that are below-median-games |
|---|---:|---:|
| KRACH | 34.8% | 31.3% |
| Massey | 35.2% | 34.3% |
| NPI | 33.0% | 34.9% |
| RPI | 30.8% | 36.3% |

No model shows a meaningful games-played-driven selection bias here.
Combined with S1, this is now two independent designs -- one
constructed, one using the real schedule as-is -- reaching the same
conclusion.

## A genuinely new finding: KRACH disproportionately EXCLUDES real independents

Looking at which specific real teams are most often wrongly excluded is
more informative than the aggregate rate above. **KRACH's top-5
wrongly-excluded list is dominated by real independent/thin-schedule
programs** (LIU, excluded in 37/300 replications -- far more than any
other team for any model; Alaska Anchorage, 30/300) -- teams that play
concentrated, low-cross-connectivity schedules by definition, discussed
as a connectivity risk in `PLAN.md`'s Study S6 (not yet run) and in
`reports/five_year_backtest_and_di_filter.md`'s original finding that
LRMC-family ratings could collapse to exactly 0.0 for exactly this kind
of team. **NPI's wrongly-excluded list contains no independents at all**
in its top 5 (Massachusetts, Connecticut, Yale, Lake Superior,
Minnesota -- all well-connected conference programs).

This is the first concrete, real-team evidence (not a constructed
scenario) that KRACH's opponent-adjusted MLE is specifically vulnerable
on thin-network teams, complementing S2's finding that KRACH showed
*larger* conference-driven rating swings than NPI in both directions
(overrating and underrating). The mechanism is consistent across both
studies: **a Bradley-Terry-style likelihood is more sensitive to a
team's specific position in a sparse comparison graph than NPI's
bounded, averaged formula is** -- sometimes that sensitivity inflates a
rating (S2's fluke-win result), sometimes it deflates one (this
finding). NPI's cruder, more averaged mechanism is less exciting in
either direction, which on this specific dimension is a point in its
favor.

## Open question: conference-size confound

Raw counts of wrongly-included teams by conference (ECAC leads for every
model) are not yet normalized by conference size (ECAC has 12 teams, the
most of any conference) -- a larger conference will mechanically produce
more raw wrongly-included instances even with no per-team bias. This
needs a per-team-rate normalization before any conference-level claim
can be trusted; not done in this pass.

## Method

`research/npi_critique/experiments/e5_selection_field_accuracy.py`. Real
2025-26 schedule, 300 replications of the standard iid true-strength
assignment. Field = top 16 by rating for each model; true field = top 16
by known ground truth. Every wrongly-excluded/included team tagged with
its real games-played count and real conference for pattern-checking.

## Shipped

- `research/npi_critique/experiments/e5_selection_field_accuracy.py`.
- Results: `research/npi_critique/results/e5_selection_field_accuracy/field_overlap.csv`,
  `.../team_errors.csv`.

## Open items

1. **Normalize the conference-distribution finding by conference size**
   before drawing any conclusion from it.
2. **The KRACH-excludes-independents finding should be checked against
   S6** (connectivity limits, not yet run) directly -- this result is
   consistent with S6's premise and is a reason to prioritize running it.
3. **Only iid true strengths were tested here** -- rerunning with
   conference-stratified strengths (S2's design) would show whether the
   field-accuracy ranking (Massey > NPI > KRACH > RPI) holds when real
   conference-strength differences are present, not just random team-level
   noise.
4. **DGP caveat applies here too** (Poisson scoring, per `e1_truth_recovery.md`).
