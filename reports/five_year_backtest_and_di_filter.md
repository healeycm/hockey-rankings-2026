# Five-Year Backtest & the Division-I Opponent Filter

## Summary

Two related pieces of work: (1) centralized a Division-I opponent filter
that only `NPI`/`NPIGames` previously had, fixing a real numerical
degeneracy in the LRMC family; (2) re-ran the model comparison across 5
seasons with 4 cutoffs each (20 splits, 8,371 test games — up from the
earlier 4-season/3-cutoff, 12-split backtests) to get a statistically
sturdier picture. Net result: `HockeyLRMC` now essentially matches KRACH/NPI
on accuracy, but a **calibration gap** (Brier/LogLoss) remains and traces to
a specific, previously-unidentified structural issue — see "What's still
open" below.

## 1. The DI-opponent filtering mechanism

### The bug it fixes

`NPI` and `NPIGames` filtered their input to Division-I opponents only
(`data/teams/team_info.csv`). No other ranker did — `KRACH`, `LRMC`,
`Colley`, `Massey`, `Markov` all took whatever games they were given,
including non-exhibition ("counting") games against non-D-I opponents (some
independents — LIU, Stonehill — schedule real games against schools like
Assumption and Saint Anselm that aren't tagged as exhibitions).

This isn't cosmetic. A team that goes 0-for-N against real opponents but
also has one or two real games against non-D-I minnows becomes a
near-isolated, near-winless node in a win/loss- or Markov-chain-based
model's graph. Direct evidence, traced during last session's "why does LRMC
underperform" investigation: on the 2024-25 season with a Feb-1 cutoff,
`LRMC_Zero`'s rating for **Assumption and Saint Anselm collapsed to exactly
0.0** (out of a field with mean rating 100). Since `LRMC.predict()` computes
`log(r_home / r_away)`, a rating of 0 sends that to ±∞ — `predict()` returns
a probability that rounds to exactly 0 or 1. When one of those
zero-information, maximally-overconfident calls is wrong, the log-loss
penalty is enormous (`-log(epsilon) ≈ 34.5` for a single game) and can
distort a whole backtest slice's average on its own. This is exactly what
produced the earlier session's mystifying `LRMC_Zero` log-loss values of
3.5–9.2 (vs. KRACH's stable ~0.65–0.74) on the Dec/Feb cutoffs.

### The fix

Centralized in [src/rankings/base_ranker.py](../src/rankings/base_ranker.py)
— `BaseRanker.__init__` now calls `_apply_di_filter()`, which every ranker
gets automatically (no subclass changes needed for `KRACH`, `Colley`,
`Massey`, `Markov`, which don't override `__init__`; `LRMC`/`HockeyLRMC`/
`NPI`/`NPIGames` call `super().__init__(games_df)` so they get it too).
`NPI`'s and `NPIGames`' own duplicate filtering code was removed —
centralizing it also deleted ~15 lines of copy-pasted logic from each.

**Safety guard:** the filter only applies when the games actually look like
USCHO-named production data. If fewer than half the teams in a given
dataset match `team_info.csv`'s DI list, filtering is skipped (with a
warning if there's partial-but-low overlap, silently if there's zero
overlap). This matters because unit tests use synthetic team names
("Team A"/"Team B") that would otherwise get filtered down to nothing — the
guard is what lets `filter_di_teams=True` be a safe default everywhere
instead of something every caller has to remember to think about. Verified:
all pre-existing unit tests (synthetic-data fixtures) still pass unchanged.

Can be explicitly disabled per-call via `filter_di_teams=False` for any
ranker that doesn't override `__init__` with its own signature (`KRACH`
directly; others would need their `__init__` extended to forward the kwarg
if that's ever needed).

### Verified effect

On the same 2024-25/Feb-1 case that surfaced the bug:

| | Before | After |
|---|---|---|
| Games in training set | 810 | 781 (29 non-DI games dropped) |
| Assumption/Saint Anselm present? | Yes (rating = 0.0) | No |
| Rating spread (min/max ratio) | ∞ (literal zero) | 190.6x |

New tests: [tests/unit/test_di_filter.py](../tests/unit/test_di_filter.py)
— confirms a non-DI opponent gets dropped, confirms synthetic test data is
NOT wiped out, confirms explicit opt-out works.

## 2. Five-year backtest (Jan/Feb cutoffs, 20 splits)

**Seasons:** 2021-22 through 2025-26 (5 seasons; excludes the COVID-shortened
2020-21 and 2016-17, which has no raw data file — consistent with existing
precedent in `src/analysis/npi_vs_krach.py`).

**Cutoffs:** Jan 1, Jan 15, Feb 1, Feb 15 — deliberately **dropping the
December cutoff** used in earlier backtests. Too little training data by
early December is exactly the regime that produced the `LRMC_Zero`
degeneracy above; Jan-on cutoffs give ratings enough games to stabilize
while still leaving most of the season as a test set. 5 seasons × 4 cutoffs
= 20 independent train/test splits, **8,371 total test games per model** —
roughly 2x the examples of the earlier 12-split backtests, for a more
statistically robust comparison.

Reproducible via `python -m analysis.exploratory.five_year_backtest`
([tests/five_year_backtest.py](../tests/five_year_backtest.py)); raw output
in `data/validation/backtest_results/five_year_summary.csv`.

### Results (mean across all 20 splits)

> **Numbers below were corrected after this report was first written.** A
> later session found that `BacktestEngine.run()` never passed `history_df`
> to models, so every `fit_source: 'history'` config silently fell back to
> season-only fitting. See reports/lrmc_empty_net.md § "Bug found along the
> way". The table below is the post-fix re-run; conclusions were unchanged,
> but LRMC_Classic (the model most flattered by the bug) dropped ~0.9pp.

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| **KRACH** | **63.80%** | 0.1840 | 0.6682 |
| NPI | 62.44% | **0.1764** | **0.6452** |
| HockeyLRMC | 62.39% | 0.1891 | 0.7050 |
| LRMC_Classic | 59.02% | 0.1930 | 0.7143 |

**HockeyLRMC vs. LRMC_Classic:** +3.4pp accuracy, better on every metric —
confirms last session's finding held up on a much larger sample.

**HockeyLRMC vs. KRACH/NPI:** accuracy is now within 0.1-1.4pp (essentially
tied with NPI, ~1.4pp behind KRACH) — a much smaller gap than before the DI
filter fix. But Brier and LogLoss are still clearly worse than both. That
gap is real and traceable to something specific — not just "LRMC is worse."

## 3. What's still open: a calibration mismatch, not (just) noise

Accuracy asks "did it pick the right winner"; Brier/LogLoss ask "was the
*confidence* right." HockeyLRMC's accuracy caught up; its confidence didn't.
Checked directly (2024-25 season, Jan-15 cutoff, 507 test games):

| | Mean predicted P(home win) | **Std dev** | % predictions <5% or >95% |
|---|---|---|---|
| KRACH | 0.540 | **0.244** | 2.4% |
| HockeyLRMC | 0.559 | **0.102** | 3.6% |

HockeyLRMC's predictions are much *more* compressed toward 0.5 overall
(under-confident on the easy, correctly-callable games — wasted calibration
credit) **while still having a slightly fatter extreme tail** (more
rare-but-wrong overconfident blowups than KRACH). That combination — narrow
middle, occasional wild outlier — is a worse shape for Brier/LogLoss than
either "appropriately wide and calibrated" (KRACH) or "appropriately narrow"
would be alone.

**Why this happens:** KRACH's win-probability formula, `K_i / (K_i + K_j)`,
*is* the Bradley-Terry model whose likelihood was maximized to produce the
ratings in the first place — fitting and prediction use the same functional
form, so it's self-consistently calibrated by construction. `LRMC.predict()`
uses an unrelated, never-separately-validated formula:
`sigmoid(hia + log(r_home/r_away))` (`src/rankings/lrmc.py:predict`) applied
to ratings that came from a completely different process (a
separately-fit margin-to-probability logistic feeding a Markov chain's
stationary distribution). Nothing ties the *scale* of `log(r_home/r_away)`
to how confident that gap should actually make you — it's a plausible-looking
formula that was never calibrated against real outcomes the way the rating
estimation itself was.

**This is a third, independent way LRMC falls short of KRACH's design**,
distinct from the two already addressed:
1. Margin-as-signal noise in a low-scoring sport (partially fixed:
   HockeyLRMC's OT-specific handling)
2. Numerical fragility from ungoverned graph structure (fixed: DI filter,
   this document)
3. **Un-calibrated prediction formula** (not yet addressed)

**Suggested follow-up, not implemented here:** fit a scale/temperature
parameter for `log(r_home/r_away)` via logistic regression against actual
historical outcomes (the same kind of fitting LRMC already does for
`alpha`/`beta` on margin, just applied to the rating-ratio-to-probability
step instead of assuming the raw log-ratio is already the correct logit).
Want me to build that next?
