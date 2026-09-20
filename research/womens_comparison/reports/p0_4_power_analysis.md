# P0.4 — Minimum detectable effect (power analysis)

**Status:** Done. Every later report in this workspace should quote the
relevant row from `results/p0_4_power_analysis/mde_by_pair.csv` (or re-run
the script for a new comparison) alongside any null result, per PLAN.md's
reporting discipline: *"a null is reported as 'no difference detected, MDE
= X' — never as 'no difference.'"*

## Method

Computed from the **observed** per-game variance in the pooled women's
5-year/20-split backtest (n=4,841 paired games, 4,550 decisive), not an
assumed textbook standard deviation:

- **Paired t-test (Brier, LogLoss):** MDE = (z_{α/2} + z_{power}) × sd(paired
  diff) / √n, the standard normal-approximation formula for a paired-t MDE,
  valid at these sample sizes. α=0.05, power=0.80.
- **McNemar's test (Accuracy):** solved the (continuity-corrected) test
  statistic for the minimum |b01 − b10| that reaches χ²-critical at α=0.05,
  given the actually-observed total discordant count for each pair. This is
  an α-only detectability boundary, not a true 80%-power MDE (McNemar power
  depends on the unknown true discordant split, which has no closed form to
  invert) — reported and labeled as such, not conflated with the paired-t MDEs.
- Repeated at the **men's-hockey pooled n (8,371, from `paper/draft.md`'s
  abstract)**, holding women's-observed variance fixed, to make the
  power gap (PLAN.md's C2) concrete rather than a vague "less power" claim.
  This assumes comparable per-game variance between divisions, which is an
  assumption, not a measured fact — flagged, not hidden.

Full table: `results/p0_4_power_analysis/mde_by_pair.csv` (all 10 pairs
among the 5 backtested models).

## Headline numbers

For the two closest, most decision-relevant pairs:

| Pair | MDE Brier (women's n=4,841) | MDE Brier (men's n=8,371) | MDE LogLoss (women's n) | McNemar: min. detectable split |
|---|---:|---:|---:|---|
| Massey vs. HockeyBT | 0.00222 | 0.00169 | 0.00752 | 56.1% / 43.9% of 279 discordant games |
| KRACH vs. ELO | 0.00546 | 0.00415 | 0.02336 | 55.9% / 44.1% of 651 discordant games |

**The power gap is real but modest, not severe**, for this specific
backtest: MDE scales as 1/√n, so going from women's n=4,841 to men's
n=8,371 shrinks the detectable effect by a factor of √(8371/4841) ≈ **1.31×**
— i.e., the women's backtest can detect effects about 31% larger than the
men's backtest can, at the same power, holding variance fixed. That is a
real, quantifiable handicap (PLAN.md's C2 is not hypothetical), but it is
not order-of-magnitude — a genuinely large effect (like Massey vs.
KRACH/ELO/RPI, already significant with p<0.03 in `p0_2_paired_significance.md`)
is comfortably within reach at women's sample sizes; only a genuinely close
comparison (Massey vs. HockeyBT, which *is* the interesting borderline case
here) sits near the detection boundary.

## How this changes the reading of P0.2's results

`p0_2_paired_significance.md` found Massey vs. HockeyBT non-significant on
Brier (diff=−0.0003, p=0.71) and LogLoss (diff=−0.003, p=0.26). Against
this section's MDEs (0.00222 Brier, 0.00752 LogLoss), the **observed
differences are themselves smaller than what this backtest could reliably
detect** — so "no significant difference" here is a real null with adequate
power to see a meaningfully-sized effect, not an underpowered non-result.
This strengthens, rather than weakens, the earlier interpretation that
Massey and HockeyBT are genuinely close on calibrated scoring for women's
hockey.

## Caveats

- MDE is reported at the model-*pair* level because paired-difference
  variance differs by pair (Brier-diff sd ranges 0.065–0.136 across the 10
  pairs) — a single "one MDE for the whole study" number would understate
  precision for some pairs and overstate it for others.
- The men's-n comparison assumes the SAME per-game paired-difference
  variance as observed on women's data. If women's hockey's greater talent
  dispersion (PLAN.md's C1) also means less per-game *prediction-error*
  variance (plausible, not yet checked), the true men's MDE at n=8,371
  could differ from what's shown here. This should be re-checked directly
  against men's per-game predictions once P0.2's `save_predictions()`
  mechanism is used on a men's backtest run (not done in this pass).
- McNemar's "detectable split" column is the α-only boundary, not an
  80%-power MDE — noted above, repeated here so it isn't read past its
  actual meaning if this table is copied elsewhere.
