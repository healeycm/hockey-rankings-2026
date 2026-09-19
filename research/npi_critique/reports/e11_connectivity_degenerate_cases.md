# S6: Connectivity Limits and Degenerate Cases — The Honesty Study

## This is where NPI genuinely, dramatically wins

Every prior study in this workspace tested a place NPI might be worse
than KRACH or Massey. This one tests the specific property KRACH is
expected to fail on: as a Bradley-Terry MLE, an undefeated or winless
team is a "perfect separator" in the comparison graph, and the true
maximum-likelihood rating for one is infinite (or zero). `KRACH`'s
`max(points, 0.1)` floor prevents a literal divide-by-zero on the first
iteration, but nothing in the iterative solver stops it from driving
toward an extreme value over its full 1000 iterations. Tested directly,
not assumed:

| Model | Mean undefeated rating | Mean winless rating | Mean field-spread ratio | Max field-spread ratio |
|---|---:|---:|---:|---:|
| **KRACH** | **5,883** | **0.0092** | **875,397x** | **4,756,458x** |
| Massey | 1.43 | -1.45 | 1,217x | 87,884x |
| **NPI** | 63.3 | 38.4 | **1.65x** | 1.76x |
| **RPI** | 0.61 | 0.38 | **1.61x** | 1.78x |

(100 replications: a real 37-game team forced undefeated, a different
real 37-game team forced winless, every other game left as normally
simulated. "Field-spread ratio" = max rating / min positive rating
across all 63 teams.) **KRACH's field-spread ratio averages nearly a
million to one, reaching 4.76 million in the worst case tested.** NPI
and RPI stay within a factor of 2 by construction (both are bounded,
averaged formulas). This is not a subtle difference -- it is the
starkest gap this whole critique has found in either direction.

## One concrete example (replication 7)

```
NPI:    Ohio State (undefeated) rating=64.08 rank=1  |  Air Force (winless) rating=39.56 rank=63
KRACH:  Ohio State (undefeated) rating=4084   rank=1  |  Air Force (winless) rating=0.0037 rank=63
RPI:    Ohio State (undefeated) rating=0.619  rank=1  |  Air Force (winless) rating=0.401  rank=63
Massey: Ohio State (undefeated) rating=1.71   rank=2  |  Air Force (winless) rating=-1.26  rank=61
```

Note Massey doesn't even rank the forced-undefeated team #1 in this
instance -- a defensible property, not a failure: Massey's ridge-
regularized linear-regression approach also incorporates goal margin and
opponent strength more smoothly, so an undefeated team that happened to
squeak by weaker opponents isn't automatically credited as the single
best team in the field. KRACH's rating of 4084 (on a scale meant to
average 100 across the field) is not a usable number on its own terms --
it says nothing calibrated about how much better this team is, only that
the optimizer pushed as far in that direction as 1000 iterations allowed.

## The honest nuance: this doesn't clearly translate to collateral rank damage

The natural follow-up question -- does one wildly-mis-rated team distort
the *rest* of the field's rankings, not just its own rating? -- does
**not** show the expected "KRACH is worst" pattern:

| Model | Mean rank shift (other 61 teams) | % shifted 5+ ranks |
|---|---:|---:|
| KRACH | 1.68 | 7.1% |
| **Massey** | **1.22** | **2.9%** |
| NPI | 1.75 | 8.8% |
| RPI | 1.97 | 10.2% |

Massey shows the *least* collateral disruption, and KRACH is not
distinguishably worse than NPI here -- if anything RPI shows the most.
**This is a genuinely informative negative result, not a failure to find
one**: KRACH's per-iteration renormalization
(`ratings / ratings.mean() * 100`) is a global rescaling, and a global
rescaling does not, by itself, need to disturb the *relative order*
among teams that aren't directly connected to the degenerate node --
only its own value and its immediate opponents' values are directly
distorted upward/downward by the extreme rating. The failure mode
this study confirms is specifically about **rating-value usability and
interpretability** (a raw KRACH rating is not a meaningful number when
any team in the graph is undefeated or winless), not about wholesale
ranking collapse for unrelated teams.

## Why this matters beyond a numerical curiosity

A raw, wildly-scaled rating is a real practical problem wherever a
rating's *magnitude* -- not just its rank -- is used downstream, and
this project's own codebase has exactly such a use: **NPI's own SOS
term averages opponents' NPI ratings directly.** If any production
ranking method used KRACH-style ratings as an input to a further
averaging step the way NPI's SOS does, one undefeated or winless team
anywhere in the graph could disproportionately swing every one of its
opponents' schedule-strength credit. NPI's bounded 0-100 design
specifically avoids this failure mode, and this is the first study in
this critique where that design choice reads as a genuine, demonstrated
advantage rather than a merely plausible-sounding one.

## Follow-up: is the collateral effect real but localized to direct opponents?

Checked immediately rather than left open. Split the same collateral
data by whether a team is a direct opponent of the forced-undefeated or
forced-winless team (24 of the 61 other teams):

| Model | Mean shift, direct opponents | Mean shift, everyone else | Ratio |
|---|---:|---:|---:|
| KRACH | 2.40 | 1.21 | 2.0x |
| Massey | 1.81 | 0.83 | 2.2x |
| NPI | 2.90 | 1.01 | **2.9x** |
| RPI | 2.97 | 1.32 | 2.3x |

Every model shows more disruption to a degenerate team's direct
opponents than to the rest of the field, as expected (their own
win-loss records were literally changed by the forced result). **But
KRACH's concentration ratio is the smallest of the four, not the
largest** -- NPI actually shows the most relative concentration on
direct opponents. This further confirms, rather than qualifies, the
main finding: KRACH's failure mode here is specifically about its own
raw rating value being unusable for the degenerate team, not about
propagating rank-level damage to the teams connected to it.

## Method

`research/npi_critique/experiments/e11_connectivity_degenerate_cases.py`.
Real 2025-26 schedule; a normal simulated season (iid strengths), then
one real 37-game team's results are overridden to decisive wins in every
game and a different real 37-game team's to decisive losses in every
game, holding every other game's simulated outcome unchanged. All four
models refit on the modified season; compared against each model's fit
on the unmodified baseline for the collateral-distortion measure.

## Shipped

- `research/npi_critique/experiments/e11_connectivity_degenerate_cases.py`.
- Results: `research/npi_critique/results/e11_connectivity_degenerate_cases/`.

## Open items

1. **The Massey field-spread-ratio metric (1,217x mean, 87,884x max) is
   likely not meaningful as reported** -- Massey's ratings are centered
   near zero and can be negative or very close to zero by chance,
   making a max/min *ratio* statistic unstable in a way that doesn't
   reflect genuine rating extremity the way it does for NPI/KRACH/RPI's
   naturally positive scales. A better Massey-specific instability
   metric (e.g., rating range, or distance from the field's own
   standard deviation) would be a cleaner comparison; not built here.
2. **Only one undefeated/winless pair, on one real schedule, was
   tested.** Repeating with a genuinely sparse team (e.g., an
   independent with ~30 games against a narrow opponent pool) forced
   undefeated would more directly test the "thin real-network" version
   of this concern that motivated Study S6 in the first place (tied to
   S9's finding that KRACH disproportionately excludes real
   independents like LIU) -- not done in this pass.
3. ~~The collateral-distortion finding deserves a more targeted
   follow-up on direct opponents~~ -- done above; confirms rather than
   overturns the "no clear KRACH disadvantage" finding.
