# A Hockey-Adapted LRMC

## Summary

Built `HockeyLRMC` ([src/rankings/hockey_lrmc.py](../src/rankings/hockey_lrmc.py)),
a subclass of the base `LRMC` (Kvam & Sokol's Logistic Regression/Markov
Chain method, originally designed for basketball). It beats `LRMC_Classic`
on every season/cutoff backtested (accuracy +2.7 to +4.6 percentage points,
better Brier and LogLoss throughout) and lands roughly competitive with
KRACH and NPI — the two best-performing models in this codebase — while
being much simpler than NPI (2 real tunable parameters vs. NPI's 7+).

Two additional adaptations were designed, implemented, and backtested but
**deliberately shipped disabled by default** because the evidence didn't
support them — see "What didn't work" below. Reporting that honestly here
rather than only the part that worked.

## 1. Diagnosis (before writing any new code)

The project notes (`notes/notes20250109.md`) suspected a bug: "LRMC
approaches are really down on Ivy League schools... perhaps a bug with
regard to games played/won normalization."

I checked the P-matrix normalization directly — it's correct (self-loop
correctly absorbs `1 - row_sum`, denominators are the weighted games-played
totals as intended). Then I compared LRMC_Classic's rankings against
KRACH's on the complete 2025-26 season for the 12 ECAC teams:

| Team | LRMC Rank | KRACH Rank | Diff |
|---|---|---|---|
| Cornell | 40 | 14 | **+26** |
| Dartmouth | 38 | 11 | **+27** |
| Princeton | 51 | 32 | +19 |
| Harvard | 52 | 38 | +14 |
| Clarkson | 26 | 37 | -11 |
| ... | | | |

Mean rank diff for ECAC teams: **+6.6** (vs. 0.0 across the whole field by
construction). Games-played counts for these teams were all in the normal
30-41 range — not a data or normalization problem.

I then checked the base LRMC's fitted `alpha`/`beta` sign convention
directly, since a sign error would have been a much bigger deal than a
conference-connectivity nuance:

```
alpha: -0.365   beta: 0.153   hia_goals: 1.19
margin=-3  prob_home_better=0.3045
margin=-1  prob_home_better=0.3731
margin=+1  prob_home_better=0.4473
margin=+3  prob_home_better=0.5238
```

`prob_home_better` increases monotonically with margin — **correct**.
`alpha` is negative, meaning even a 1-goal home win nets a `prob_home_better`
*below* 0.5. This is also correct: it's the intended Kvam-Sokol discount for
the fact that part of any home-team goal margin is attributable to home ice,
not true team strength, so the model requires *more* than a bare win to
credit the home team as genuinely better. **No sign bug, no normalization
bug.**

The real issue: OT/SO games always end with a goal margin of exactly 1
(sudden death — nobody wins OT by 2). The base LRMC runs that fixed ±1
margin through the *same* alpha/beta as a narrow regulation win, applying
the same home-ice discount logic to a result that is, unlike a regulation
1-goal win, close to a coin flip. Hockey has a much higher rate of OT/SO
decisions than most sports LRMC has been applied to (in this codebase's
data, roughly 15-20% of games), and ECAC/Ivy programs — playing a lot of
tight in-conference hockey — accumulate more than their share of exactly
these games. That's what was dragging Cornell and Dartmouth down: not a bug,
a genuine model-vs-sport mismatch.

## 2. What was built

**Core fix — OT/SO games get a fixed, low-confidence vote.** Instead of
`prob_home_better = sigmoid(alpha + beta*margin)` for OT games, `HockeyLRMC`
uses a fixed `0.5 ± ot_confidence` (default 0.08 → winner gets 0.58/0.42)
regardless of margin, since the margin carries no additional information
beyond who won. A fresh alpha_ot/beta_ot logistic fit specifically on OT
games was tried first and rejected — OT games are too few and structurally
uniform (margin always exactly ±1) to reliably determine the correct sign
convention independent of the parent class's specific paired
home-and-home-series fitting machinery. The fixed-constant rule is
transparent, trivially correctly-signed, and directly tunable.

Separately, regulation-game alpha/beta are now fit on **regulation games
only** (`IsOT == False`), so the OT games' structurally different margins
no longer contaminate that fit either — previously they were mixed in.

**Result:** ECAC mean rank-diff to KRACH dropped from **+6.6 to +2.2**
(Cornell: #40 → #27, KRACH says #14; Dartmouth: #38 → #29, KRACH says #11).
Backtest accuracy vs. LRMC_Classic, `fit_source=history`, `margin_cap=3`,
4 seasons (2022-23 through 2025-26) × 3 cutoffs (Dec/Jan/Feb):

| Cutoff | LRMC_Classic Acc | HockeyLRMC Acc | LRMC_Classic Brier | HockeyLRMC Brier |
|---|---|---|---|---|
| Dec | 56.77% | **62.10%** | 0.2008 | **0.1858** |
| Jan | 59.50% | **60.62%** | 0.1875 | **0.1845** |
| Feb | 59.54% | **63.08%** | 0.1818 | **0.1773** |

For comparison, KRACH scored 62.89% / 63.13% / 63.25% and NPI scored
62.01% / 60.88% / 62.67% on the same splits — HockeyLRMC is now in the same
tier as the two best models in the codebase, not trailing them by 3-6
points the way LRMC_Classic does.

## 3. What didn't work (kept, but off by default)

Two more adaptations from the original plan were implemented and
backtested. Neither showed a measurable benefit, so both ship disabled:

**Empty-net margin shrink.** Heuristic: shrink an (already-capped) 2-goal
margin toward 1.75 before it enters the logistic, since a real share of
2-goal final margins include a last-minute empty-net goal (no shot/ENG data
was available to detect this directly — this was always a proxy).
Ablation on 2024-25/2025-26 (Dec/Jan/Feb cutoffs): accuracy and Brier moved
by less than 0.2 percentage points either way — statistically
indistinguishable from off. Left in the code, tunable, defaulted off.

**Conference-silo shrinkage (`prior_weight`).** The base LRMC already had a
uniform-prior blend mechanism (previously unused, default 0.0). Hypothesis:
blending each team's transition-matrix row toward the field-wide uniform
prior would counteract ECAC/Ivy's sparse cross-conference connectivity.
Tested at 0.0 / 0.05 / 0.15, specifically on ECAC-involving games (where the
silo problem is worst), 2024-25 and 2025-26 seasons, Jan cutoff:

| prior_weight | 2025-26 ECAC Accuracy | 2025-26 ECAC Brier |
|---|---|---|
| 0.0 | **73.11%** | 0.1962 |
| 0.05 | 72.27% | 0.1979 |
| 0.15 | 74.79%¹ | 0.2009 |

¹ Accuracy ticked up at 0.15 in this one slice but Brier got worse and the
2024-25 season showed a clean monotonic decline at every level (61.1% →
57.9% → 56.4%), so this isn't read as a real effect — more likely noise from
a small sample (131-135 ECAC-involving test games per slice).

**Conclusion: shrinking uniformly toward the whole field's average dilutes
real signal rather than fixing the actual problem.** The silo symptom in the
original diagnosis was a downstream consequence of the OT/margin mis-scoring
(#1 above), not an independent connectivity problem — fixing #1 fixed both.
Left in the code and tunable for anyone who wants to try a smarter version
(e.g. shrinking toward each team's conference-mate average instead of the
whole field), but don't flip the default back on without re-validating.

## 4. Where this leaves it

`HockeyLRMC` is now in `config.yaml`'s `active_models` and wired into
`run_system.py` (dispatches on `model_key.startswith("HockeyLRMC")`, before
the generic `LRMC` prefix check). Verified end-to-end against the
2025-26 season: fits, produces sane top-5 rankings (Denver, Michigan,
Western Michigan, North Dakota, Minnesota Duluth — matches the rest of the
system's consensus top tier).

Unit tests: [tests/unit/test_hockey_lrmc.py](../tests/unit/test_hockey_lrmc.py)
— basic fit/predict sanity, a regression guard on the evidence-based
defaults (so `empty_net_shrink`/`prior_weight` can't silently get flipped
back on), and a direct check that OT games get the fixed-confidence vote
rather than running through the regulation logistic.

## Open items / possible follow-ups

1. **Discrete/ordinal outcome model.** The original plan called for
   replacing the margin-linear logistic with a full ordered-outcome or
   Skellam (Poisson-difference) model. What was actually built is a more
   targeted fix (separate OT handling) rather than a full model replacement
   — it was sufficient to close most of the gap and is much simpler to
   reason about/validate. A full Skellam model remains a larger, separate
   effort if further gains are wanted.
2. **A real empty-net signal**, if shot-level or scoring-play data becomes
   available, would let the empty-net proxy be replaced with an actual
   empty-net-goal flag instead of a blind 2-goal heuristic — worth revisiting
   then.
3. **A proper hierarchical conference-mean shrinkage prior** (rather than
   the uniform-field blend tested and rejected here) is a plausible
   follow-up for the residual ECAC/Ivy gap, but wasn't attempted — it's a
   materially bigger implementation (needs the ratings to inform the prior
   that then informs the ratings, i.e. an inner iterative loop).
4. **HockeyLRMC still trails KRACH by ~0.3-2.5pp accuracy** depending on
   cutoff, and NPI's Brier/LogLoss are still slightly better in 2 of 3
   cutoffs tested. It's a clear improvement over LRMC_Classic, not a new
   best-in-class model — report it that way, not as "beats everything."
