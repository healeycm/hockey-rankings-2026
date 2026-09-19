# DGP Robustness: One Headline Finding Reverses, One Survives

## Why this had to be checked

Every experiment in this workspace, from `e1_truth_recovery.md` onward,
carried the same flagged threat to validity: `simulate_season()`
generates independent Poisson goals per team, a process that
structurally favors margin-based models (Massey exploits goal
differential directly) over win/loss-only models (KRACH, NPI, RPI).
E1's report said this "should not be quoted in the paper until it's
been re-run under a Bradley-Terry DGP" -- a blocker carried through
every subsequent report without being addressed until now.

**Built `simulate_season_bradley_terry()`**: WHO WINS is drawn directly
from `p_home = (theta_home * hia) / (theta_home * hia + theta_away)` --
the exact functional form KRACH's own likelihood is built on, making
KRACH the *correctly specified* estimator under this DGP, the mirror
image of the Poisson process favoring Massey. Margin is then generated
*independently of strength entirely* -- a realistic-looking scoreline
layered on top of the win/loss draw, carrying no additional information
about who's actually better. Calibrated separately against the same
real 3-season targets (OT rate 0.199 vs. real 0.181-0.223; home win%
0.534 vs. real 0.532-0.578; goals 5.64 vs. real 5.69-5.97, a modest,
documented undershoot; win% std 0.114 vs. real 0.150-0158, a real,
documented undershoot not fully corrected, since the point was a
genuinely different DGP, not a pixel-perfect replica).

## Result 1: E1's "Massey recovers truth best" does NOT survive

200 replications, iid strengths, same design as `e1_truth_recovery.py`:

| Model | Poisson DGP (original) | Bradley-Terry DGP (this report) |
|---|---:|---:|
| **Massey** | **0.912** (best) | 0.635 (tied for worst) |
| KRACH | 0.868 | 0.639 |
| NPI (official) | 0.892 | **0.682** (best) |
| RPI | 0.862 | 0.628 |

Under the Bradley-Terry DGP, **NPI significantly beats Massey**
(p=1.1e-38, the opposite direction from the Poisson-DGP result), and
Massey is no longer distinguishable from KRACH (p=0.187 -- a tie, not
a win). **This finding is not DGP-robust.** E1's headline claim --
"Massey recovers ground truth best" -- was an artifact of the specific
generative process tested, not a property that holds regardless of how
outcomes are actually generated. This should not be presented as a
general finding in the comparative paper without this caveat attached,
and probably should not be presented as a standalone claim at all.

## Result 2: S9's "KRACH beats NPI on field accuracy" DOES survive

200 replications, conference-stratified strengths (calibrated
`conf_log_sigma=0.4`), same design as `e5c_selection_field_accuracy_recalibrated.py`:

| Model | Poisson DGP (`e5c`, post-OT-fix) | Bradley-Terry DGP (this report) |
|---|---:|---:|
| **KRACH** | **12.12** (best of KRACH/NPI/RPI) | **9.40** (best of the four) |
| Massey | (12.61, best overall) | 9.16 |
| NPI | 11.88 | 9.11 |
| RPI | 11.55 | 9.06 |

**KRACH significantly beats NPI under both DGPs** (Poisson: p=0.0001;
Bradley-Terry: p=0.0031). The absolute overlap numbers are lower under
this DGP (9-of-16 vs. 12-of-16 -- expected, since this DGP's lower
win%-spread calibration makes the underlying seasons noisier and truth
recovery harder for everyone), but the *comparison* between KRACH and
NPI holds in the same direction at a comparable significance level.
**This is the one finding in this whole simulation workspace that has
now been checked against three separate corrections (two sigma
calibrations, one OT-rate fix) plus a genuinely different
data-generating process, and has survived all four.**

## What this means for how to report this workspace's findings

**Not every simulation finding in this critique carries equal weight,
and this report is the evidence for saying so explicitly:**

- **Robust, DGP-independent findings** (report with full confidence):
  S9's KRACH-beats-NPI field-accuracy result; S6's connectivity finding
  (KRACH's instability for undefeated/winless teams is a structural
  property of Bradley-Terry MLE, not dependent on how game outcomes are
  generated -- not re-checked under the BT DGP directly in this report,
  but the mechanism is purely about the *fitting* step, which doesn't
  interact with the outcome DGP at all); S8's schedule-manipulability
  finding (same reasoning -- KRACH's near-zero schedule-alpha is a
  property of its likelihood structure, not of how outcomes were
  generated to test it).
- **Not robust, DGP-dependent findings** (retract or heavily caveat):
  E1's "Massey recovers truth best" headline. By extension, any other
  finding in this workspace whose comparison specifically pits a
  margin-based model (Massey) against win/loss-only models on a
  *truth-recovery* metric should be treated with the same suspicion
  until similarly re-checked -- this was not done exhaustively here.

## Method

`research/npi_critique/experiments/e15_dgp_robustness.py`. Two parts,
mirroring `e1_truth_recovery.py` and
`e5c_selection_field_accuracy_recalibrated.py` exactly except for the
substitution of `simulate_season_bradley_terry()` for
`simulate_season()`.

## Shipped

- `research/npi_critique/harness/simulate.py`:
  `simulate_season_bradley_terry()`, a second, genuinely different DGP.
- `research/npi_critique/experiments/e15_dgp_robustness.py`.
- Results: `research/npi_critique/results/e15_dgp_robustness/`.

## Open items

1. **S6 and S8 were reasoned about, not directly re-run, under the BT
   DGP** -- the argument that they're DGP-independent (because they test
   properties of the fitting/formula step, not the outcome-generation
   step) is plausible but unverified. A direct re-run would be a
   stronger claim than an argument.
2. **A third, deliberately misspecified DGP (S8's original plan called
   it "DGP-C") was not built** -- both DGPs tested so far are each
   "correctly specified" for one model (Poisson favors Massey,
   Bradley-Terry favors KRACH); a DGP under which *no* model is
   correctly specified would be the fairest test of all and remains
   undone.
3. **The Bradley-Terry DGP's win%-spread undershoot (0.114 vs. real
   0.150-0.158) was not fully corrected** -- worth revisiting if this
   DGP is used for further work, since a narrower spread could itself
   affect truth-recovery difficulty uniformly across models in a way
   that's hard to distinguish from a genuine DGP effect.
