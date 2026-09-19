# E1: Truth Recovery in Simulated Seasons with Known Ground Truth

> **HEADLINE FINDING RETRACTED -- see `reports/e15_dgp_robustness.md`.**
> This report's claim that Massey recovers ground truth best does NOT
> survive a genuinely different data-generating process (Bradley-Terry
> outcomes instead of independent Poisson goals): under that DGP, NPI
> significantly beats Massey (p=1.1e-38) and Massey is only tied with
> KRACH, not ahead of it. The DGP caveat this report itself raised (and
> every subsequent report repeated without resolving) turned out to be
> exactly the problem it warned about. The NPI-dial-sweep and paradox-rate
> findings below are not model-comparison claims and are not affected by
> this. E10's re-verification of this report under the OT-rate fix is
> also unaffected in its own terms (same DGP throughout) but inherits
> this same retraction.

## Summary

Real data can never tell us which team was actually better -- only what
happened. This experiment simulates 200 seasons using a real season's
actual schedule (2025-26 Division I men's hockey: who played whom, when,
home ice, exhibition/conference-tournament structure) but with a
synthetic, *known* true team strength driving simulated outcomes instead
of the real ones. Every model's induced ranking is then scored directly
against ground truth via Spearman rank correlation -- a comparison real
data structurally cannot support.

**Headline result, and it complicates the existing real-data critique
rather than simply confirming it.** Massey recovers ground truth best
(ρ=0.912), significantly ahead of everything else (paired test, n=200,
p<1e-40 in every comparison). Among the NPI variants, however, the
**official 2025-26 dial (weight_sos=0.75) recovers ground truth
significantly *better* than lower weights** (0.66: p=1.3e-7; 0.5:
p=1.8e-16; 0.25 and 0.1: even larger gaps) -- the opposite direction from
`reports/npi_critique.md`'s real-data-based recommendation to reduce the
SOS weight to 0.66. NPI at an even higher weight (0.9) is much worse
(p=4.4e-64), so the relationship isn't simply "higher is better" either.
We discuss why this is not necessarily a contradiction below -- it
reflects two different, both-legitimate evaluation targets producing
different answers, which is itself a finding worth having.

## Method

**Schedule and outcome generation:**
`research/npi_critique/harness/simulate.py`. Each of the 63 real 2025-26
Division I teams is assigned a synthetic true strength (log-normal,
freshly drawn each replication). Game outcomes are drawn from a
Poisson-scoring generative model tilted by the ratio of true strengths,
with a modest home-ice multiplier and a compressed (near-coin-flip)
overtime resolution for regulation ties -- calibrated against this
project's own validated real-data findings (see
`research/npi_critique/experiments/e0_calibration_check.py`): home win
rate 56.1% (real: 56.65%), mean total goals/game 5.87 (real: ~5.5-6.0),
OT/shootout rate 14.4% (real: ~15-20%, our closest miss). We regard this
as a reasonably, not perfectly, calibrated simulator, and report its
calibration gap plainly rather than claim an exact match.

**Models:** KRACH, Massey (fitted home-ice and ridge, beta fit disabled
since we score by rank correlation, not by predicted probability), RPI,
and NPI -- both at its official dial and reweighted across
weight_sos $\in \{0.10, 0.25, 0.50, 0.66, 0.75, 0.90\}$.

**A real implementation gap found while building this, not new to this
project:** `NPI.fit()` (`src/rankings/npi.py`) hard-codes the 0.25/0.75
weight_wp/weight_sos split directly inside its vectorized iterative
solve -- passing a different value via `config` is silently a no-op,
confirmed directly (an earlier version of this script did exactly that
and produced bit-identical Spearman correlations across every "different"
dial value tested). This is not a new discovery -- `src/analysis/npi_vs_krach.py`
already hit this and built `reweight_npi()` as the documented
workaround, which is what `reports/npi_critique.md`'s own dial-sensitivity
analysis actually used, and what we reuse here for consistency. **This
matters for interpreting the result above**: `reweight_npi()` recomputes
ratings post-hoc from the *converged* adj_wp/sos/qwb components (still
produced by an iteration run at the hard-coded 0.75) using the requested
weights -- it does not re-run the iterative convergence itself at a
different weight, which would also change opponents' own NPI values (and
therefore SOS) at each candidate weight. What we -- and the original
real-data analysis -- actually measure is sensitivity to the *final
linear combination* step alone, holding the underlying iteration fixed at
0.75. A true full re-convergence at each weight is a materially larger
implementation effort (the iteration and the final combination are the
same hard-coded expression) and is flagged as an open item below rather
than attempted here.

**Paradox check:** mirroring `reports/npi_critique.md` Section 5b, for a
sample of decisive games where the losing team's NPI was below the
season's median, we leave that game out and refit NPI to see whether the
winning team's NPI *increases* without the win it just recorded. Run on
the first 20 of the 200 replications, capped at 15 candidate games per
replication (300 total) to keep the leave-one-out refit cost bounded.

## Results

**Table: mean Spearman correlation with true team strength, 200
replications, paired significance vs. NPI's official dial.**

| Model | Mean ρ | Std | vs. NPI-official, paired p |
|---|---:|---:|---:|
| **Massey** | **0.9121** | 0.0261 | 3.2e-43 |
| NPI (official, sos=0.75) | 0.8919 | 0.0337 | -- |
| NPI (sos=0.66) | 0.8893 | 0.0341 | 1.3e-07 |
| NPI (sos=0.50) | 0.8841 | 0.0351 | 1.8e-16 |
| NPI (sos=0.25) | 0.8786 | 0.0366 | (smaller, not separately reported) |
| NPI (sos=0.10) | 0.8763 | 0.0372 | (smaller, not separately reported) |
| KRACH | 0.8683 | 0.0398 | 9.2e-40 |
| RPI | 0.8615 | 0.0404 | 9.9e-58 |
| NPI (sos=0.90) | 0.8320 | 0.0484 | 4.4e-64 |

All differences from NPI-official are statistically significant in both
directions (n=200 paired seasons throughout).

**Paradox rate:** 19 of 300 sampled below-median-opponent wins (6.3%)
paradoxically *lowered* the winning team's NPI. This is a nontrivial
minority rate under controlled conditions with a known-random schedule of
true strengths, consistent in direction (a real, non-rare phenomenon, not
an artifact of one unusual real season) with the 20 instances
`reports/npi_critique.md` found by inspection in a single real season --
though the two counts are not directly comparable (different sample
sizes, different candidate-selection procedures), so we report this as
corroborating the mechanism's existence and rate order of magnitude, not
as a matched replication.

## Interpretation: two different questions, two different answers

The real-data critique (`reports/npi_critique.md`) recommends lowering
NPI's SOS weight from 0.75 to 0.66 based on **predictive accuracy against
realized game outcomes**. This experiment asks a different question --
**how well does a ranking recover known ground-truth team strength** --
and gets a different answer: 0.75 beats 0.66 here, significantly. We do
not think these results contradict each other; we think they measure
genuinely different properties, and the paper's Discussion (Section 5.2
of `paper/draft.md`) already established exactly this kind of
resolution-vs-calibration split for the model comparison generally.
Predictive accuracy against realized outcomes is sensitive to the
specific noise structure of the games that were actually played (which
teams happened to have close games, upsets, etc.); ground-truth recovery
in repeated simulation averages that noise away and asks the more
literal question the metric's name implies ("power index" -- how well
does it rank teams by their real underlying power). **Both are
legitimate, and a full NPI critique should report both rather than
picking the one that tells a cleaner story.** The genuinely damning
findings -- the paradox property, the sharp degradation at the high
extreme (weight_sos=0.9), and NPI's across-the-board underperformance
relative to Massey regardless of dial value -- hold up in both framings
and are the more defensible core of the critique; the specific
"reduce to 0.66" recommendation is the one finding this experiment
complicates rather than confirms, and the paper should say so rather than
quietly keep only the framing that agrees.

## Shipped

- `research/npi_critique/harness/simulate.py` -- the generative model,
  calibration-checked in `e0_calibration_check.py`.
- `research/npi_critique/experiments/e1_truth_recovery.py` -- this
  experiment, `python -m research.npi_critique.experiments.e1_truth_recovery`.
- Raw results: `research/npi_critique/results/e1_truth_recovery/spearman_by_model.csv`
  (200 replications x 9 models = 1800 rows).

## Open items

1. **A true full-reconvergence dial sweep** (patching `NPI.fit()` to
   actually read `weight_wp`/`weight_sos` inside the iteration, not just
   `reweight_npi()`'s post-hoc linear step) would answer the sharper
   version of question (b) and might resolve, sharpen, or further
   complicate the tension described above. Larger effort -- the iteration
   and final combination share one hard-coded expression currently.
2. **Only one simulation design was tested** -- one real schedule
   (2025-26), one true-strength distribution shape (log-normal,
   sigma=0.4). Whether the 0.75-beats-0.66 result is sensitive to the
   strength distribution's spread (e.g., a field with much more or much
   less separation between best and worst teams) is untested.
3. **The paradox-rate comparison to real data is directional, not a
   matched replication** -- worth a like-for-like real-vs-simulated
   paradox rate at matched sample sizes if this becomes a headline claim
   in the paper rather than corroborating evidence.
4. **A minimal, hand-constructed analytic example of the paradox**
   (a handful of teams, chosen to guarantee the mechanism) was planned
   but not built in this pass -- would make the mechanism transparent
   pedagogically in a way 19/300 simulated instances doesn't by itself.
