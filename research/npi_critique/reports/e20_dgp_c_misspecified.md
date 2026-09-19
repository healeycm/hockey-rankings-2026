# DGP-C: The Fairest Test, and It Corrects an Overstated Earlier Conclusion

## Why this DGP, and why it changes the story again

`reports/e15_dgp_robustness.md` tested two DGPs, each correctly
specified for exactly one model: independent Poisson goals (correctly
specified for Massey, which regresses on margin) and direct
Bradley-Terry outcomes (correctly specified for KRACH, whose likelihood
*is* that functional form). Neither alone answers "which model is
actually best" -- each answers "which model matches this particular
assumption." `simulate_season_mixed()` (each game independently drawn
from one mechanism or the other, 50/50) is misspecified for *every*
model in the roster -- the fairest test available, and the one E15's
own open items flagged as still missing.

## Result: Massey's truth-recovery win returns; KRACH's field-accuracy win is now confirmed 3-for-3

**Part 1, truth recovery (200 replications, iid strengths):**

| Model | Poisson DGP | Bradley-Terry DGP | **Mixed DGP (this report)** |
|---|---:|---:|---:|
| **Massey** | **0.912** (best) | 0.635 | **0.822** (best) |
| NPI | 0.892 | **0.682** (best) | 0.805 |
| KRACH | 0.868 | 0.639 | 0.765 |
| RPI | 0.862 | 0.628 | 0.758 |

Under the neutral, misspecified-for-everyone DGP, **Massey wins again,
significantly** (vs. NPI: p=4.25e-17; vs. KRACH: p=4.55e-68; vs. RPI:
p=9.43e-66). Massey now wins under 2 of the 3 DGPs tested -- the
original Poisson DGP and this neutral one -- and loses only under the
Bradley-Terry DGP, which is specifically, maximally structured to favor
KRACH's (and secondarily NPI's win/loss-based) functional form over
Massey's margin-based one.

**Part 2, selection-field accuracy (200 replications, conference-stratified):**

| Model | Poisson DGP | Bradley-Terry DGP | **Mixed DGP (this report)** |
|---|---:|---:|---:|
| Massey | 12.61 (best) | -- | **11.36** (best) |
| **KRACH** | **12.12** | **9.40** | **10.99** |
| NPI | 11.88 | 9.11 | 10.70 |
| RPI | 11.55 | 9.06 | 10.57 |

**KRACH significantly beats NPI under all three DGPs now** (Poisson
p=0.0001; Bradley-Terry p=0.0031; Mixed p=0.0012). A first pass at
n=20 replications showed this as a statistical tie (p=0.85) -- caught
before being trusted by scaling to the full 200 and re-checking, the
same discipline this workspace applied to the sigma calibrations. At
full sample size the KRACH-over-NPI finding is confirmed a third
independent way.

## Correcting `reports/e1_truth_recovery.md`'s retraction notice

That notice said the Massey-recovers-truth-best finding was
"RETRACTED." **That was an overstatement, corrected here.** The
accurate characterization: Massey's truth-recovery advantage holds
under 2 of 3 tested data-generating processes, including the
deliberately neutral one built to favor no model -- it fails
specifically under the one DGP built to maximally favor KRACH's exact
functional form. This is a real, worth-reporting DGP-sensitivity, not
grounds for a blanket retraction. The paper should present this as "not
robust to the most adversarial DGP tested" rather than "wrong."

## What this means for the overall critique

**S9's KRACH-beats-NPI field-accuracy finding is now the single most
rigorously verified result in this entire workspace**: confirmed across
two sigma-calibration corrections, one OT-rate fix, and three distinct
data-generating processes (Poisson, Bradley-Terry, and neutral-mixed),
without reversing once. Massey's truth-recovery advantage is real and
holds in the majority of tested conditions but is more fragile,
specifically to a DGP engineered to favor its main rival's functional
form -- a meaningfully different, more precise conclusion than either
"Massey wins" or "Massey's win is an artifact" alone.

## Method

`research/npi_critique/experiments/e20_dgp_c_misspecified.py`, mirroring
`e15_dgp_robustness.py` exactly except for `simulate_season_mixed()`
(each game independently Poisson or Bradley-Terry, 50/50, no per-game
correlation between the two mechanisms). Calibrated automatically well
against all three real-season targets (OT rate 0.201, home win% 0.544,
mean goals 5.78 -- all within the real 3-season ranges on the first
attempt, since it inherits both already-separately-calibrated
mechanisms).

## Shipped

- `research/npi_critique/harness/simulate.py`: `simulate_season_mixed()`.
- `research/npi_critique/experiments/e20_dgp_c_misspecified.py`.
- Results: `research/npi_critique/results/e20_dgp_c_misspecified/`.
- `reports/e1_truth_recovery.md` and `reports/e15_dgp_robustness.md`
  annotated with this correction.

## Open items

1. **Only a 50/50 mixture was tested** -- a sweep of the mixing fraction
   (e.g., 25/75, 75/25) would show how sensitive the Massey/NPI
   crossover is to exactly how much of the process resembles each
   mechanism, rather than only the single midpoint.
2. **S6 and S8 were not re-checked under this third DGP** -- only under
   the Bradley-Terry one (`e16`, `e17`). Given the mixed DGP produced a
   genuine (if minor) surprise at small N for S9, the same caution
   applies: their DGP-independence argument, while plausible, remains
   unverified against this specific mixture.
