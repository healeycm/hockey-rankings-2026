# Experiment plan: men's vs. women's D-I hockey rankings

**Status:** plan only. No experiments run, no production code touched.
**Workspace:** `research/womens_comparison/` (isolated per the convention in
`tests/unit/test_research_isolation.py`).

---

## Framing

All three papers (`paper/draft.md`, `paper/npi_critique_draft.md`,
`paper/lrmc_draft.md`) were written on men's D-I data. Women's D-I is not a
second dataset that happens to be smaller — it is a **structurally different
field that the NCAA governs with the identical NPI formula**: 25% win
percentage / 75% strength of schedule, quality-win-bonus base 51.5,
multiplier 0.5, the same dials, with no published sensitivity analysis for
either division ([NCAA NPI guide](https://ncaaorg.s3.amazonaws.com/championships/resources/d2/D2CH_NPIQA.pdf),
[USCHO women's NPI](https://www.uscho.com/rankings/npi/d-i-women)).

That makes women's hockey a **natural robustness experiment**, not a
courtesy extension. Every structural claim in the NPI critique — connectivity
sensitivity, dial sensitivity, selection-field accuracy, the win paradox —
is a claim about how a formula behaves on a schedule graph. We now have a
second, differently-shaped graph that the same formula is applied to, with
real selection consequences.

**The results decide the publication route, not the other way round.** See
"Publication decision rule" at the end. Nothing in this plan assumes women's
results will support, or fail to support, any men's finding.

---

## The central methodological problem: three confounds

A naive "women's accuracy is 74.5%, men's is 63.8%, therefore models behave
differently" comparison is invalid. Three things differ at once, and they
must be separated before any cross-division claim is made.

Measured from `data/processed/`, 2025-26 season (preliminary, computed while
drafting this plan — to be re-derived properly in W1):

| Property | Men's | Women's | Note |
|---|---:|---:|---|
| Teams | 63 | 45 | smaller field |
| Games/season | 1,143 | 817 | fewer total games |
| **Games/team** | **36.3** | **36.3** | **identical** |
| Home win rate | 0.518 | 0.523 | ~same |
| Tie rate | 0.069 | 0.054 | ~same |
| OT rate | 0.181 | 0.191 | ~same |
| **sd(win %)** | **0.158** | **0.199** | **women's ~26% more dispersed** |
| Distinct opponents/team | 15.3 (24.6% of field) | 13.6 (30.8% of field) | women's graph **denser** |
| Fiedler value (algebraic connectivity) | 4.044 | 3.810 | women's slightly **less** connected |

Three confounds follow:

1. **Talent dispersion (C1).** Women's D-I has substantially more spread in
   true team strength. More dispersion ⇒ more predictable games ⇒ higher
   accuracy for *every* model. Most or all of the 10-point accuracy gap may
   be a property of the field, not the models. **Any raw cross-division
   accuracy comparison is confounded by this and must not be made.**
2. **Field size and statistical power (C2).** Women's has ~5 seasons at ~817
   games vs. men's 8,371 pooled held-out games — roughly 0.6-0.7× the test
   games, so meaningfully less power. A men's-significant result that comes
   back non-significant on women's data is **not evidence of divergence**
   until a power analysis says the test could have detected it.
3. **Graph shape (C3).** Counterintuitively, women's teams play a *larger
   fraction* of their field (denser) but the graph is *slightly less
   algebraically connected* — consistent with NEWHA (a conference of
   otherwise-D-II schools) being relatively isolated. Connectivity findings
   could go either way and the naive "smaller field ⇒ worse connectivity"
   intuition is already falsified.

The simulation harness (`research/npi_critique/harness/simulate.py`) is the
instrument that resolves C1 and C3: `assign_true_strengths(sigma=...)`,
`make_multiconference_schedule(n_conferences, teams_per_conf, cross_frac,
games_per_team)` let us hold dispersion fixed while varying field size, or
vice versa. That harness is already fully parameterized — no changes needed,
only different arguments.

---

## Pre-registered predictions

Recorded before running anything. Being wrong here is a result, not a
failure; the point is that we cannot retrofit the story afterwards.

| # | Prediction | Confidence | What would falsify it |
|---|---|---|---|
| P1 | Massey remains the single best model on women's accuracy/Brier/LogLoss | High | Any other model beats it on ≥2 of 3 with significance |
| P2 | The men's calibration ordering does **not** transfer (men's: NPI/ELO best-calibrated; women's prelim: HockeyBT) | High | HockeyBT is not best-calibrated once NPI is included |
| P3 | Most of the accuracy gap is explained by dispersion (C1), not by models behaving differently | High | Dispersion-matched comparison leaves >3pp unexplained |
| P4 | The NPI win paradox replicates on women's data at a comparable per-game rate | Medium | Zero paradox games found across 5 seasons |
| P5 | NPI's optimal dials differ materially between divisions | Medium | Optimal (weight, QWB) region overlaps men's within noise |
| P6 | NPI-vs-KRACH selection-field disagreement is **higher** for women's (smaller field, 6 at-large slots, more dispersion ⇒ a sharper bubble) | Medium-low | Disagreement rate is equal or lower |
| P7 | The men's connectivity finding (favors NPI) weakens or reverses on women's structure | Medium-low | Effect replicates at same magnitude |
| P8 | RPI remains the most schedule-manipulable metric (men's finding) | Medium | NPI or another metric is worse for women's |

---

## Phase 0 — Prerequisites (hard blockers)

**Status (2026-09-20): all four done.** See each item's report:
`research/womens_comparison/reports/p0_1_conference_data.md`,
`p0_2_paired_significance.md`, `p0_3_npi_validation.md`,
`p0_4_power_analysis.md`. One of these (P0.3) surfaced a real production
bug — women's NPI was silently computed with men's-hockey dials (no
home/away multiplier exists for women's NPI at all; QWB base also
differed) — fixed in `config.yaml`/`src/run_system.py`, see that report for
the before/after impact. Cheapest-first sequencing below is now historical
context for how this was approached, not a to-do list.

These gate later phases. None are research; all are plumbing or validation.

**P0.1 — Populate women's conference data. BLOCKS W7, W9, W10, W12.**
`data/teams/college_hockey_teams_women.csv` has **0 of 45** conferences
populated. `reports/womens_hockey_import.md` deliberately left it blank
after an assumption about Penn State's conference turned out wrong. Needs a
verified source (NCAA/USCHO conference listings), cross-checked, not
inferred from the men's file — the two divisions' conference maps genuinely
differ (NEWHA, AHA, WCHA have no men's equivalent with the same membership).
Without this, no conference-stratified experiment can run.

**P0.2 — Persist per-game predictions for paired significance tests.**
`reports/womens_hockey_import.md` records this as a blocker, but it is
smaller than described: `BacktestEngine` **already** collects per-game rows
in `self.all_predictions` (`src/backtesting/backtest_engine.py:191`), with
`Season`, `Cutoff`, `Date`, `HomeTeam`, `AwayTeam`, `Result`, `IsOT`,
`HomeWinProb`, `Model` — everything pairing needs. `save_results()` simply
never writes them. The men's scripts already do paired tests off
`engine.all_predictions` in-process (see
`analysis/exploratory/hockey_bt_backtest.py:49-81`). So this is:
(a) add a `save_predictions()` to the engine, and (b) copy the existing
paired t-test / McNemar block into the women's backtest script. Estimated
effort: under an hour, not a project.

**P0.3 — Validate women's NPI against published numbers.**
We now compute women's NPI (backfilled 2026-09-20) but have never checked it
against USCHO's published women's NPI, the way the men's implementation was
validated in `reports/npi_investigation_2026.md`. **Every NPI experiment
below is worthless if this doesn't pass.** Same known failure modes to check
first: date-cutoff handling and the SOS opponent filter. Note the published
women's parameters match our defaults exactly (0.25/0.75, QWB 51.5/0.5,
0.8/1.2 multipliers), so no re-parameterization is expected — if a
discrepancy appears, it is a bug or a data issue, not a dial difference.

**P0.4 — Power analysis.** Before interpreting any null result as
divergence: given women's pooled test-game count, what effect size can each
paired test actually detect at α=0.05, 80% power? Produces an explicit
"minimum detectable difference" per metric, quoted in every later report.
Non-negotiable given C2.

---

## Phase 1 — Characterize the two fields (descriptive)

**W1 — Structural comparison.** Formalize the preliminary table above across
all 5 shared seasons: team counts, games/team distribution, home-ice rate,
OT/tie rate, win% dispersion, schedule-graph density, Fiedler value,
cross-conference fraction (after P0.1), and the size of the largest
weakly-connected component. Deliverable: the control-variable inventory that
every later experiment conditions on.

*Why first:* it defines which differences are "the field" and which are
candidates for "the models."

---

## Phase 2 — Does the models paper replicate? (real data)

**Status (2026-09-20): W2 done** — see `reports/w2_full_backtest_with_npi.md`.
W3/W4 not started.

**W2 — Full 6-model backtest with significance.** Massey, HockeyBT, KRACH,
ELO, RPI, **and NPI** (never previously backtested on women's data), 5
seasons × 4 cutoffs, men's protocol exactly, with the paired t-test/McNemar
tests unblocked by P0.2. *Failure criterion for P1:* Massey loses to any
model on ≥2 of 3 primary metrics with significance.

**W3 — The dispersion confound (C1), directly.** Is women's higher accuracy a
model property or a field property? Two independent attacks, both reported:
(a) *Difficulty-matched subsampling* — bin games by pre-game rating gap and
compare within-bin accuracy across divisions, so only comparably-hard games
are compared; (b) *Simulation control* — generate seasons at men's field size
with women's dispersion and vice versa, measure how much of the gap each
factor reproduces. *Failure criterion for P3:* >3pp of the gap survives both
controls, implying something model-relevant actually differs.

**W4 — Calibration/resolution decomposition.** The models paper's secondary
headline is that model quality splits along two axes the incumbents don't
jointly optimize (men's: NPI best-calibrated, Massey best resolution).
Re-run the ECE/Brier-decomposition/reliability analysis on women's with NPI
included. Women's preliminary numbers (`reports/womens_hockey_import.md`)
put HockeyBT at the best ECE (0.0568 vs. ELO 0.0706, Massey 0.0747), so the
ordering already looks different — this pins down whether the *two-axis
structure* still holds even though the *occupants of each axis* change.

---

## Phase 3 — Does the NPI critique replicate? (the strongest angle)

**Status (2026-09-20): W5, W6, W8, W10 done** — see `reports/w5_win_paradox.md`,
`reports/w6_dial_sensitivity.md`, `reports/w8_bubble_divergence.md`,
`reports/w10_schedule_manipulability.md` (single-DGP pass; a 2nd/3rd DGP
robustness check, matching the men's E17/E22 pattern, is a natural next
step, not yet done). W7, W9 not started.

This is where a women's extension is most likely to be genuinely novel,
because the NPI paper's claims are claims about a formula's behavior on a
graph, and we now have a second graph with real selection stakes.

**W5 — Win paradox on real women's games.** The men's paper documents 20
real games where a team's own win lowered its computed NPI. Same scan across
5 women's seasons. Report the raw count *and* the per-game rate (the fields
differ in size, so raw counts aren't comparable). *Falsifies P4 if zero.*

**W6 — Dial sensitivity sweep.** The men's 98-configuration sweep produced
632 rank changes >3 positions (vs. zero for KRACH). Re-run at women's
structure. The sharpest possible finding here: **the NCAA applies identical
dials to both divisions; if the dial surface's sensible region differs by
division, then at most one division's dials can be well-chosen, and neither
has a published justification.** That is a clean, policy-relevant result
that does not depend on NPI being "bad" in any absolute sense.

**W7 — Selection-field accuracy at real field sizes.** Men's: top-16 of ~63.
Women's: **11-team field, 5 automatic qualifiers, 6 at-large** ([2026 field](https://www.ncaa.com/news/icehockey-women/article/2026-03-08/2026-national-collegiate-womens-ice-hockey-championship-field-announced)).
Fewer at-large slots and a more dispersed field may make the bubble either
sharper (easier) or more brittle (harder) — genuinely unclear, which is why
it's worth running. Must model the auto-bid structure correctly rather than
naively taking a top-11, since auto-bids remove teams from the at-large pool.

**W8 — Real bubble divergence.** The men's paper's most concrete artifact is
a named team on opposite sides of the line (Miami: NPI 32nd, KRACH 15th).
Compute NPI-vs-KRACH/Massey top-11 disagreement per team-season for women's,
and name the teams. *Tests P6.*

**W9 — Connectivity.** Men's finding: thin connectivity destabilizes
Bradley-Terry ratings, and this is the axis where NPI *wins*. Women's graph
is denser but slightly less algebraically connected (C3), and NEWHA is a
natural real-world isolation case. Run both the real-data version and the
simulated `make_multiconference_schedule` version at women's parameters.
*Tests P7.* This one is a coin flip and should be run precisely because we
can't predict it.

**W10 — Schedule manipulability.** Men's finding: RPI is the worst offender,
not NPI, by a DGP-independent margin. Re-run at women's structure. *Tests
P8.* A men's-favorable finding about NPI that fails to replicate is as
publishable as a critical one — and protects the critique from the charge of
being advocacy.

---

## Phase 4 — Simulation at women's parameters

**W11 — Re-parameterized DGP suite.** Re-run the men's simulation
experiments (truth recovery, field accuracy, connectivity, manipulability)
with the harness set to women's structure: `n_teams≈45`, dispersion
calibrated to women's observed sd(win%)≈0.20, women's conference layout
(after P0.1), 11-team field with 5 auto-bids, `games_per_team=36`.

Per the existing plan's standard, **every finding must survive all three
DGPs** (Poisson, Bradley-Terry, mixed/misspecified). No exceptions for this
being a "secondary" division.

**W12 — Field-size vs. dispersion factorial.** The cleanest causal design
available: a 2×2 (field size: 45/63) × (dispersion: 0.20/0.16), plus the
conference structure of each division. This separates "is it women's hockey"
from "is it a small field" from "is it a spread-out field" — a claim real
data structurally cannot support, and the strongest methodological
contribution a cross-division paper could make.

---

## Publication decision rule

Decided by the results, recorded in advance:

- **If Phase 2-3 findings largely replicate** → fold into the existing papers
  as robustness sections ("the finding holds on a second, structurally
  different NCAA field governed by the same formula"). This strengthens the
  men's papers at low cost and needs no separate venue.
- **If findings materially diverge** (P5, P7, or P2 in particular) → a
  standalone paper. The framing writes itself: *the NCAA applies one
  formula, with one set of dials, to two structurally different fields; here
  is what that costs in the division nobody validated it on.*
- **If mixed** (the likeliest outcome) → the divergences *are* the
  contribution. A paper reporting "these three findings transfer, these two
  don't, and here's the structural reason" is more useful than either pure
  outcome.

Do not decide this before Phase 3 is complete.

---

## Reporting discipline

Inherited from `research/npi_critique/PLAN.md`, plus two additions specific
to this study:

1. **Every report quotes its minimum detectable effect** (P0.4). A null is
   reported as "no difference detected, MDE = X" — never as "no difference."
2. **Multiple comparisons.** ~12 experiments × 6 models × 2 divisions is a
   large surface to find a p<0.05 in. All results reported, including the
   boring ones; corrections applied where a family of tests is genuinely
   being screened.
3. Violation rates and worst cases before means; named, hand-checkable
   minimal examples for any structural claim.
4. Negative and men's-favorable results get equal prominence. The men's
   critique already reports three findings that complicate its own case
   (no games-played bias, no echo chamber, RPI more manipulable than NPI) —
   the women's extension holds the same standard or it isn't worth running.

---

## Sequencing summary

| Phase | Contents | Gated by | Rough order |
|---|---|---|---|
| 0 | Conference data, per-game predictions, NPI validation, power analysis | — | First, all four |
| 1 | W1 structural comparison | P0.1 | Fast |
| 2 | W2-W4 models-paper replication | P0.2, P0.4 | Moderate |
| 3 | W5-W10 NPI-critique replication | P0.1, P0.3 | The bulk of the work |
| 4 | W11-W12 simulation | P0.1, Phase 3 | Harness already supports it |

**Cheapest high-value first:** P0.2 → W2 → W5. That sequence alone answers
"does the headline model ranking hold?" and "does the win paradox exist in
women's hockey?" with a day or two of work, and either result is worth
knowing before committing to the rest.
