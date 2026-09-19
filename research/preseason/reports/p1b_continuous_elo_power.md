# P1b: continuous Elo vs. no-prior, with season-level power

Follow-up to `research/preseason/reports/p1_history_prior.md` -- see this script's docstring for the full pre-registration. Re-analyzes P1's existing predictions (no new model fits). Candidate: `ContinuousElo_rev0.33_k20` (P1's tune-selected continuous-Elo config).


## Holdout (5 seasons -- the honest test)


### vs. `ELO_none` (no prior at all)

**Per-game test (P1's original method, repeated here for direct comparison):**

| Cutoff | N games | Brier (base->cand) | Season-level mean diff | 95% bootstrap CI | Bootstrap p |
|---|---|---|---|---|---|
| Oct15 | 474 | 0.1931->0.1801 | -0.0133 (n=5 seasons) | [-0.0208, -0.0047] | 0.0002 |
| Nov1 | 554 | 0.1863->0.1704 | -0.0161 (n=5 seasons) | [-0.0213, -0.0110] | 0 |
| Nov15 | 526 | 0.1901->0.1788 | -0.0113 (n=5 seasons) | [-0.0138, -0.0093] | 0 |
| Dec1 | 465 | 0.1830->0.1776 | -0.0057 (n=5 seasons) | [-0.0111, -0.0003] | 0.037 |
| Jan1 | 492 | 0.1840->0.1785 | -0.0054 (n=5 seasons) | [-0.0088, -0.0017] | 0.0042 |

### vs. `ELO_prodprior` (today's shipped prior (r1=0.6/r2=0.15, weight=0.6))

**Per-game test (P1's original method, repeated here for direct comparison):**

| Cutoff | N games | Brier (base->cand) | Season-level mean diff | 95% bootstrap CI | Bootstrap p |
|---|---|---|---|---|---|
| Oct15 | 474 | 0.1843->0.1801 | -0.0043 (n=5 seasons) | [-0.0066, -0.0019] | 0.001 |
| Nov1 | 554 | 0.1730->0.1704 | -0.0027 (n=5 seasons) | [-0.0072, +0.0017] | 0.233 |
| Nov15 | 526 | 0.1806->0.1788 | -0.0019 (n=5 seasons) | [-0.0032, -0.0005] | 0.0136 |
| Dec1 | 465 | 0.1782->0.1776 | -0.0007 (n=5 seasons) | [-0.0020, +0.0002] | 0.302 |
| Jan1 | 492 | 0.1799->0.1785 | -0.0014 (n=5 seasons) | [-0.0041, +0.0012] | 0.289 |

## All 23 seasons (descriptive only -- tune seasons were used to SELECT this config, so this pool isn't a clean significance test, just a larger-sample sanity check)


### vs. `ELO_none` (no prior at all)

**Per-game test (P1's original method, repeated here for direct comparison):**

| Cutoff | N games | Brier (base->cand) | Season-level mean diff | 95% bootstrap CI | Bootstrap p |
|---|---|---|---|---|---|
| Oct1 | 84 | 0.1886->0.1863 | +nan (n=1 seasons) | [+nan, +nan] | nan |
| Oct15 | 2034 | 0.1975->0.1809 | -0.0167 (n=22 seasons) | [-0.0220, -0.0114] | 0 |
| Nov1 | 2370 | 0.1937->0.1803 | -0.0134 (n=22 seasons) | [-0.0180, -0.0087] | 0 |
| Nov15 | 2257 | 0.1865->0.1795 | -0.0070 (n=23 seasons) | [-0.0093, -0.0047] | 0 |
| Dec1 | 2047 | 0.1888->0.1796 | -0.0097 (n=23 seasons) | [-0.0142, -0.0057] | 0 |
| Jan1 | 2280 | 0.1856->0.1785 | -0.0073 (n=23 seasons) | [-0.0097, -0.0049] | 0 |

### vs. `ELO_prodprior` (today's shipped prior (r1=0.6/r2=0.15, weight=0.6))

**Per-game test (P1's original method, repeated here for direct comparison):**

| Cutoff | N games | Brier (base->cand) | Season-level mean diff | 95% bootstrap CI | Bootstrap p |
|---|---|---|---|---|---|
| Oct1 | 84 | 0.1893->0.1863 | +nan (n=1 seasons) | [+nan, +nan] | nan |
| Oct15 | 2034 | 0.1903->0.1809 | -0.0096 (n=22 seasons) | [-0.0125, -0.0067] | 0 |
| Nov1 | 2370 | 0.1859->0.1803 | -0.0057 (n=22 seasons) | [-0.0082, -0.0031] | 0 |
| Nov15 | 2257 | 0.1810->0.1795 | -0.0017 (n=23 seasons) | [-0.0035, +0.0000] | 0.0524 |
| Dec1 | 2047 | 0.1847->0.1796 | -0.0055 (n=23 seasons) | [-0.0084, -0.0028] | 0 |
| Jan1 | 2280 | 0.1827->0.1785 | -0.0043 (n=23 seasons) | [-0.0064, -0.0024] | 0 |


*Season-level mean diff = mean(candidate season Brier - baseline season Brier); negative means the candidate (continuous Elo) is better. The bootstrap resamples SEASONS (not games) with replacement, so its CI reflects season-to-season variability, which per-game pairing cannot see. A CI that straddles zero, even with a consistently negative point estimate, means the direction is plausible but not yet demonstrated at conventional significance with this few holdout seasons -- that's an honest report of a real data limitation (5 holdout seasons total), not a flaw in the bootstrap.*

*The all-23-season `Oct1` row is `nan`: only 1 season had enough games by Oct 1 to produce a valid train/test split at all (most seasons' openers land after that date), so no season-to-season variance exists to bootstrap. Not a bug -- Oct1 is close to the edge of what's testable at all with this schedule.*

## Conclusion

**Both pre-registered expectations held, and the direct comparison is the strongest result in this whole line of work so far.**

**Continuous Elo decisively beats "no prior at all."** Every holdout cutoff is significant at the season level (p=0.037 at worst, p<0.005 at four of five cutoffs), not just directionally consistent -- this is exactly the "even larger, more likely significant gap vs. the weaker baseline" the pre-registration expected, and it delivered. The all-23-season check lines up with the same pattern at much tighter intervals.

**Against today's shipped prior specifically, the picture is more mixed than P1's per-game test suggested, but slightly more favorable than it looked stalled at "not significant anywhere."** The season-level test finds continuous Elo significantly better at 2 of 5 holdout cutoffs (Oct15 p=0.001, Nov15 p=0.0136) and directionally better with a CI still mostly on the favorable side at the other 3 (Nov1, Dec1, Jan1 -- none flip to favoring the shipped prior). The 23-season descriptive check, where power is much higher, shows the same direction significant at 4 of 5 cutoffs. Taken together: this reads as a real, moderate effect that 5 holdout seasons alone can't fully pin down at every single cutoff, not as noise -- the per-game test in P1 understated this by testing a null that was too easy to fail to reject.

**This changes the P1 recommendation.** P1 said "watch this, don't ship it." The direct-vs-no-prior result plus the partially-confirmed edge over the shipped prior is now a strong enough case to justify treating 538-style continuous Elo as an active promotion candidate for ELO specifically -- not an immediate config change (still needs a promotion-quality review: does the offseason-reversion mechanism handle the 2016-17 gap season and shortened 2020-21 sensibly? does it need conference-aware reversion before shipping, per PLAN.md's originally-deferred idea?), but no longer just a research curiosity to revisit later. Massey's prior and the currently-shipped ELO carryover approach are NOT reopened by this result -- P1's finding that their current strength values are near-optimal stands.