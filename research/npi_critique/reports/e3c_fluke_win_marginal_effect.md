# S2, precise version: The Marginal Effect of a Fluke Win Against a Strong Opponent

## The question, stated precisely

Your concern, restated: not "does a mediocre team in a strong conference
end up overrated overall" (e3's question -- and the answer there was
subtler than expected, see `e3_weak_team_strong_conference.md`) but the
specific causal mechanism: **holding a below-.500 team's season
otherwise fixed, does flipping one or two of its losses against very
highly-ranked opponents into narrow wins produce a disproportionate
rating/rank gain?** That is the fluke-win/quality-win-bonus mechanism
directly, isolated from the team's overall record and conference context.

## Result: real for all three models -- and largest for KRACH, not NPI

**The underlying mechanism you're worried about is real and confirmed:
all three models respond positively to a fluke win against a strong
opponent.** But the magnitude ordering is the opposite of the naive
expectation:

| Model | Mean rank gain, 1 flip | Mean rank gain, 2 flips | % of replications with a gain (1 flip) |
|---|---:|---:|---:|
| **KRACH** | **+3.49** | **+6.75** | 94.0% |
| Massey | +1.95 | +4.08 | 84.7% |
| NPI | +1.84 | +3.78 | 83.3% |

(150 replications, 450 valid model-observations; a below-.500-caliber
team, true strength 0.85, planted in the real Big Ten schedule; "gain" =
baseline rank minus post-flip rank, positive = moved up.) **KRACH's
opponent-adjusted maximum-likelihood structure produces nearly double
NPI's marginal reward for the same fluke win**, not a smaller one. NPI's
capped quality-win-bonus formula (`(opp_NPI - 51) x 0.5`, a bounded
linear bonus) is, on this evidence, the *more conservative* of the two
mechanisms, not the more exploitable one.

## Why this makes mathematical sense

Beating a very highly-rated opponent is strong evidence under a
Bradley-Terry likelihood specifically *because* it's a low-probability
event under the model if you're actually weak -- a single upset over a
top team can move a KRACH-style MLE rating substantially, since the
model has to reconcile "this team beat someone very strong" with
whatever else it knows. NPI's QWB is a flat, bounded linear function of
the opponent's rating with no such likelihood-driven amplification. This
is a structural property of the two model families, not a bug in either
-- but it means the "fluke win against a strong team" concern, to the
extent it's a real distortion, is *better aimed at Bradley-Terry-style
methods (KRACH) than at NPI's explicit formula*, which is close to the
opposite of the intuition the real Ohio State case study suggested.

## Concrete example (replication 5)

Planted team's two toughest losses that replication, both against a
true-strength-3.19 Michigan State (extremely strong relative to the
~1.0 field average): a 1-3 home loss and a 7-2 road loss. Flipping both
to narrow OT wins:

```
NPI:    rank 56 -> 55 (1 flip) -> 53 (2 flips)   [gain: 3]
KRACH:  rank 42 -> 38 (1 flip) -> 37 (2 flips)   [gain: 5]
Massey: rank 55 -> 52 (1 flip) -> 50 (2 flips)   [gain: 5]
```

Every model gains from the flip, as expected; KRACH and Massey gain more
than NPI in this specific instance, consistent with the aggregate result.

## How this fits with e3's aggregate finding

This result and `e3_weak_team_strong_conference.md`'s aggregate
rank-error finding are complementary, not contradictory: e3 found that
KRACH's *overall* overrating of a very weak planted team was largest at
the extreme end of the strength range, shrinking toward zero as the
planted team approached the field median (where NPI's *underrating*
grew instead). This experiment isolates one specific piece of the
mechanism -- the marginal effect of an upset win -- and finds KRACH more
responsive to it in isolation too. Put together: KRACH's opponent-
adjusted likelihood makes it *more* sensitive, in both directions, to
individual high-leverage results (a single upset, in this experiment; a
team's overall placement in a thin conference network, in e3) than
NPI's more averaged, capped formula is. That is a specific, falsifiable,
mechanistic claim -- not merely "KRACH happened to score worse in these
two experiments" -- and it is worth stating as the paper's actual
finding: **the intuition that NPI's explicit SOS/QWB formula is the more
exploitable mechanism is not supported by either study run so far; if
anything, KRACH's likelihood-based structure shows larger single-result
leverage.**

## Method

`research/npi_critique/experiments/e3c_fluke_win_marginal_effect.py`.
Same elite-conference setup as `e3_weak_team_strong_conference.py`
(real Big Ten schedule, elite conference effect fixed at +0.65), planted
team's true strength set to 0.85 (a genuinely below-.500-caliber team,
deliberately less extreme than e3's original 0.55 tail case, per that
report's own recommended follow-up). Each replication: simulate a full
season, identify the two losses against the highest-true-strength
opponents played, flip the first (and then, for a second data point,
both) into a narrow one-goal OT win with every other game held
identically fixed, and refit all three models on baseline and both
counterfactuals.

## Shipped

- `research/npi_critique/experiments/e3c_fluke_win_marginal_effect.py`.
- Results: `research/npi_critique/results/e3c_fluke_win_marginal_effect/marginal_gain.csv`.

## Open items

1. **Only one magnitude of "narrow win" was tested** (a 1-goal OT
   margin). A blowout upset win might show a different, possibly larger,
   marginal effect for the goal-differential-sensitive models (Massey);
   NPI and KRACH are both win/loss-based (margin-insensitive) for this
   mechanism specifically, so this matters mainly for calibrating
   Massey's comparison fairly.
2. **Only the two toughest losses were tested**, and only for one planted
   strength (0.85) and one conference. A full sweep crossing this
   experiment's design with e3b's strength sweep was not run.
3. **DGP and NPIGames-filter caveats apply here identically** to every
   other experiment in this workspace -- see `e1_truth_recovery.md`.
