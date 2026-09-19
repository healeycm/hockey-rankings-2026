# Keener's Method and Glicko-2: Two More Honest Negative Results

## Summary

Built two genuinely different ranking paradigms from anything already in
this codebase — Keener's Perron-Frobenius eigenvector method and Glicko-2's
sequential Bayesian filtering — as the remaining "different family" items
from the original methods survey (`reports/goal_based_ranking_plan.md`
listed these alongside RPI, SRS, TrueSkill, and Pythagorean ratings). Both
were implemented correctly (verified numerically, not just assumed) and
both lose decisively to Massey. Reported plainly, matching this project's
established practice.

## Keener's method

**What it is:** an eigenvector ranking (Keener 1993), structurally
different from this codebase's existing Markov/LRMC eigenvector models.
Markov/LRMC build a column-stochastic transition matrix (each team's
outgoing "vote" sums to 1) and take its stationary distribution. Keener
instead builds an *unnormalized* positive matrix from a **skewed
score-share** statistic and takes its Perron eigenvector directly:

```
s_i = i's goals in the game + 1        (Keener's own "credit for playing" adjustment)
r_ij = s_i / (s_i + s_j)
h(r) = 1/2 + sign(r - 1/2) * sqrt(|2r - 1|) / 2     (the "skew" function)
```

The skew function is the interesting part: it's a bounded S-curve that
*compresses* blowout score shares (a 10-1 win and a 5-1 win end up close
together after skewing) while staying sensitive near close games — a
different way of addressing the same "margin is a noisy signal in a
low-scoring sport" problem this project's LRMC work tackled via a hard
cap. Verified directly
(`tests/unit/test_keener.py::test_skew_function_compresses_extremes`): a
ratio 2.25x further from 0.5 (raw 0.45 vs. 0.2) compresses to a smaller
multiple after skewing.

A small positive perturbation `epsilon` is blended into every entry so the
matrix is strictly positive, which is what guarantees (via
Perron-Frobenius) a unique, positive dominant eigenvector — verified
directly that every team's rating comes out strictly positive.

**Result:** decisively behind Massey. Swept `epsilon` (0.01–0.3) — flat at
61.7–62.0% accuracy across the whole range, so this is a real gap, not an
undertuned hyperparameter:

| epsilon | Accuracy | Brier | LogLoss |
|---|---|---|---|
| 0.01 | 61.70% | 0.1837 | 0.6634 |
| 0.05 | 61.91% | 0.1827 | 0.6599 |
| **0.1** | **62.02%** | **0.1824** | **0.6589** |
| 0.2 | 61.90% | 0.1825 | 0.6589 |
| 0.3 | 61.68% | 0.1827 | 0.6593 |

Pooled paired test vs. Massey (n=8,371, `epsilon=0.1`):

| | Accuracy | Brier | LogLoss |
|---|---|---|---|
| Keener | 61.70% | 0.18374 | 0.66101 |
| Massey | 64.59% | 0.17338 | 0.63417 |
| **p-value** | **<0.0001 (McNemar)** | **6.5e-22** | **1.4e-24** |

## Glicko-2

**What it is:** a genuinely different computational paradigm — sequential
Bayesian-filtering updates, one game at a time in chronological order
(same date-sorted iteration style already used by this codebase's ELO),
rather than a batch MLE/eigenvector/least-squares solve over the whole
schedule at once. Each team carries three state variables, not one:
rating (`mu`), rating deviation (`phi`, uncertainty), and volatility
(`sigma`, how erratically the team's true strength itself seems to change).
Implemented the full published algorithm including the Illinois-algorithm
(bracketed regula-falsi) root-find for the volatility update — the one
genuinely nontrivial numerical step — and verified it doesn't diverge or
produce NaN/Inf across the backtest.

**Verified working as designed**, not just "runs without crashing":
- `tests/unit/test_glicko2.py::test_rd_shrinks_with_more_games` — RD
  (uncertainty) provably decreases as a team accumulates games, the core
  property that distinguishes this from ELO.
- `test_home_advantage_recovered_when_present` — a deliberately-injected
  home-ice effect is recovered by the held-out calibration fit.
- Swept `tau` (the volatility-change system constant, Glickman's
  recommended range 0.3–1.2) from 0.2–1.0: **completely flat, zero
  measurable effect.** Checked why: fitted team volatilities stay within
  ~0.0002 of their starting value all season (`0.0600`–`0.0603` in the
  smoke test) — college hockey teams don't display enough within-season
  strength drift for Glicko-2's volatility mechanism to have anything to
  react to. This is a real, checked finding about the sport, not an
  implementation gap.

**Result:** behind Massey, and doesn't clearly beat even plain ELO (its
closest relative — both are sequential win/loss/margin-driven raters).
Pooled paired test (n=8,371):

| vs. | Accuracy | Brier | LogLoss |
|---|---|---|---|
| **Glicko2 vs Massey** | 63.78% vs 64.59% (McNemar **p=0.037**) | 0.1827 vs 0.1734 (**p=7.8e-25**) | 0.6577 vs 0.6342 (**p=2.3e-20**) |
| **Glicko2 vs ELO** | 63.78% vs 63.44% (p=0.454, tied) | 0.1827 vs 0.1751 (**p=3.8e-11**) | 0.6577 vs 0.6400 (**p=3.1e-8**) |

Glicko-2's extra machinery (uncertainty tracking, volatility) doesn't
translate into better predictions than plain ELO here — it ties ELO on
accuracy but is significantly worse calibrated, and loses to Massey
outright.

## Interpretation

Both results fit the pattern this project has established repeatedly:
genuinely different mathematical structures (a different eigenvector
matrix, a different fitting paradigm entirely) don't automatically produce
better predictions than the win/loss-and-margin-based models already
validated here. What keeps winning is the combination already identified —
goal-margin information (Massey) properly calibrated (fit, not guessed) —
regardless of how the alternative model represents team strength
internally.

## What's genuinely useful despite losing the horse race

- **Keener's skew function** is a legitimate, different answer to the
  "margin is noisy" problem than HockeyLRMC's hard cap — worth remembering
  as a documented alternative if margin-handling is revisited.
- **Glicko-2's RD (uncertainty per team)** is a real capability nothing
  else in this codebase has — useful for a "how confident is this ranking"
  question independent of whether it wins on raw accuracy/Brier/LogLoss.
  Not surfaced anywhere in the current reporting pipeline; would need
  separate work to expose if wanted.

## Shipped

- `config.yaml`: `keener:` and `glicko2:` config blocks added with the
  validated defaults. **Neither added to `active_models`** — both lose
  decisively to Massey.
- `run_system.py`: dispatches both if added to `active_models`.
- `src/rankings/keener.py` ships with `epsilon=0.1`.
- `src/rankings/glicko2.py` ships with `tau=0.5`, `fit_home_advantage=true`.
- Tests: [tests/unit/test_keener.py](../tests/unit/test_keener.py) (6
  tests) and [tests/unit/test_glicko2.py](../tests/unit/test_glicko2.py)
  (6 tests) — including the skew-function-compression and
  RD-shrinks-with-games property checks that verify each model does what
  it's supposed to mathematically, not just that it runs.
- Reproducible:
  [tests/keener_glicko2_backtest.py](../tests/keener_glicko2_backtest.py)
  (`python -m analysis.exploratory.keener_glicko2_backtest`).

## Open items

1. **Glicko-2's per-game "rating period" simplification** — real Glicko-2
   is designed for batched periods with an explicit RD-inflation step for
   players who don't play in a period; here every game updates both
   participants immediately, so a team on a long layoff doesn't get the
   "more uncertain the longer you've been unobserved" treatment the
   published algorithm intends. Given the flat `tau` result, this
   simplification is unlikely to be hiding a large missed effect, but
   wasn't tested directly.
2. **Keener's `score_offset` (+1 credit-for-playing constant)** wasn't
   swept independently of `epsilon` — a secondary hyperparameter, unlikely
   to close a 3pp accuracy gap on its own.
3. **Both models' calibration (beta/home-effect) are tuned on the same
   historical data used for final evaluation** — the same acknowledged
   limitation as every other model in this project's comparison work.

## Remaining from the original "more methods" survey

SRS (redundant with Massey's family, not built), TrueSkill (redundant with
Glicko-2's uncertainty-tracking niche, not built), Pythagorean ratings (a
simple heuristic, not a fitted model, not built) — all three were
triaged as lower-priority in the original plan and stayed that way after
seeing RPI/Keener/Glicko-2's results reinforce the same pattern.
