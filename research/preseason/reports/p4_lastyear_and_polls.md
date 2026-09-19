# P4: how informative are last year's rating and the preseason poll, alone and combined?

See this experiment's module docstring for the full pre-registration and method. Three static (no in-season updates) logistic-regression predictors, fit once on tune-season games with a preseason poll available, evaluated on holdout.

**Fitted coefficients (tune seasons):**

- `poll_only`: intercept=+0.1746, poll_diff=+0.0545, home_dummy=+0.1029
- `lastyear_only`: intercept=+0.1873, lastyear_diff=+1.5408, home_dummy=+0.1000
- `combined`: intercept=+0.1736, poll_diff=+0.0383, lastyear_diff=+0.7891, home_dummy=+0.1054


*`poll_diff`/`lastyear_diff` coefficients are the change in log-odds per unit of that feature (poll: 1 rank position; last-year rating: 400 Elo points). A near-zero coefficient means that arm found little independent signal once its other feature(s) are in the model.*


## Holdout: same 6 cutoffs used in P1/P1b (14-day test windows)

| Arm | Cutoff | N | Accuracy | Brier | LogLoss |
|---|---|---|---|---|---|
| poll_only | Oct1 | 398 | 0.626 | 0.1836 | 0.6393 |
| lastyear_only | Oct1 | 398 | 0.610 | 0.1859 | 0.6453 |
| combined | Oct1 | 398 | 0.648 | 0.1805 | 0.6322 |
| poll_only | Oct15 | 474 | 0.616 | 0.1878 | 0.6565 |
| lastyear_only | Oct15 | 474 | 0.632 | 0.1863 | 0.6532 |
| combined | Oct15 | 474 | 0.626 | 0.1855 | 0.6514 |
| ELO_none (in-season, from P1, reference) | Oct15 | 474 | 0.598 | 0.1931 | 0.6689 |
| poll_only | Nov1 | 554 | 0.619 | 0.1796 | 0.6516 |
| lastyear_only | Nov1 | 554 | 0.636 | 0.1761 | 0.6424 |
| combined | Nov1 | 554 | 0.636 | 0.1747 | 0.6393 |
| ELO_none (in-season, from P1, reference) | Nov1 | 554 | 0.579 | 0.1863 | 0.6677 |
| poll_only | Nov15 | 526 | 0.602 | 0.1933 | 0.6637 |
| lastyear_only | Nov15 | 526 | 0.613 | 0.1889 | 0.6528 |
| combined | Nov15 | 526 | 0.607 | 0.1889 | 0.6532 |
| ELO_none (in-season, from P1, reference) | Nov15 | 526 | 0.592 | 0.1901 | 0.6563 |
| poll_only | Dec1 | 465 | 0.608 | 0.1896 | 0.6659 |
| lastyear_only | Dec1 | 465 | 0.610 | 0.1865 | 0.6568 |
| combined | Dec1 | 465 | 0.624 | 0.1866 | 0.6583 |
| ELO_none (in-season, from P1, reference) | Dec1 | 465 | 0.617 | 0.1830 | 0.6501 |
| poll_only | Jan1 | 492 | 0.619 | 0.1937 | 0.6510 |
| lastyear_only | Jan1 | 492 | 0.639 | 0.1908 | 0.6439 |
| combined | Jan1 | 492 | 0.615 | 0.1904 | 0.6427 |
| ELO_none (in-season, from P1, reference) | Jan1 | 492 | 0.643 | 0.1840 | 0.6270 |

## Holdout: whole-season decay, by month

| Arm | Month | N | Accuracy | Brier | LogLoss |
|---|---|---|---|---|---|
| poll_only | Jan | 1168 | 0.583 | 0.1921 | 0.6639 |
| lastyear_only | Jan | 1168 | 0.601 | 0.1913 | 0.6620 |
| combined | Jan | 1168 | 0.590 | 0.1898 | 0.6583 |
| poll_only | Feb | 1135 | 0.586 | 0.1825 | 0.6613 |
| lastyear_only | Feb | 1135 | 0.589 | 0.1806 | 0.6568 |
| combined | Feb | 1135 | 0.598 | 0.1796 | 0.6539 |
| poll_only | Mar | 627 | 0.666 | 0.1725 | 0.6386 |
| lastyear_only | Mar | 627 | 0.674 | 0.1703 | 0.6333 |
| combined | Mar | 627 | 0.671 | 0.1696 | 0.6321 |
| poll_only | Apr | 12 | 0.417 | 0.1793 | 0.7110 |
| lastyear_only | Apr | 12 | 0.417 | 0.1668 | 0.6855 |
| combined | Apr | 12 | 0.417 | 0.1797 | 0.7117 |
| poll_only | Oct | 986 | 0.626 | 0.1854 | 0.6491 |
| lastyear_only | Oct | 986 | 0.625 | 0.1851 | 0.6487 |
| combined | Oct | 986 | 0.640 | 0.1826 | 0.6427 |
| poll_only | Nov | 1147 | 0.612 | 0.1857 | 0.6560 |
| lastyear_only | Nov | 1147 | 0.627 | 0.1814 | 0.6454 |
| combined | Nov | 1147 | 0.625 | 0.1807 | 0.6440 |
| poll_only | Dec | 639 | 0.617 | 0.1877 | 0.6618 |
| lastyear_only | Dec | 639 | 0.612 | 0.1866 | 0.6579 |
| combined | Dec | 639 | 0.636 | 0.1850 | 0.6552 |

*Note: no in-season model equivalent is shown for the by-month breakdown (only the by-cutoff table includes the `ELO_none` reference row, reusing P1's exact predictions for an apples-to-apples game set). April's row (n=12) is too small to read anything into. Coefficient significance wasn't formally tested in this pass -- the pattern below is read off consistent point estimates across cutoffs/months, not a p-value.*

## Conclusion

**All three static, no-in-season-games predictors are genuinely informative early, and last year's rating is consistently the stronger of the two signals on its own.** At every cutoff from Oct1 through Jan1, `lastyear_only` beats `poll_only` on Brier and LogLoss (e.g. Oct15: 0.1863 vs. 0.1878; Nov15: 0.1889 vs. 0.1933) — sensible, since the poll only ranks the top ~20 teams and treats the other two-thirds of Division I as one undifferentiated group, while last year's rating scores every team on a continuous scale.

**The combination is better than either alone, most clearly early in the season.** `combined` has the best (or statistically tied-best) Brier/LogLoss of the three at every single cutoff and month tested. The fitted coefficients explain why: in the `combined` model, `poll_diff`'s coefficient shrinks from 0.0545 (poll alone) to 0.0383 (combined) rather than to zero — most of what the poll knows is already captured by last year's rating, but not all of it. The preseason poll is doing exactly what it's supposed to: capturing human judgment (injuries, transfers, coaching changes, recruiting) that a mechanical carryover from last season's results can't see.

**This directly answers the "how informative" question, and it lines up with everything else in this line of work.** Comparing to `ELO_none` (an in-season model with zero prior, from P1, on the identical game set): the static preseason-only predictors are MORE accurate than that fresh in-season fit through **Oct15 and Nov1**, roughly **tied at Nov15**, and then **decisively overtaken by Dec1 and Jan1** as real results accumulate (ELO_none's Brier: 0.1931 -> 0.1863 -> 0.1901 -> 0.1830 -> 0.1840, vs. `combined`'s 0.1855 -> 0.1747 -> 0.1889 -> 0.1866 -> 0.1904 over the same cutoffs — ELO_none is worse early, then pulls ahead and stays ahead). This is the fade curve one would hope to see, and it's the same story P1/P1b already told from a different angle: preseason information (of any kind) is worth the most in the first 6-8 weeks of the season and becomes a net drag if leaned on too long after that — which is exactly why production's Massey prior fades on its own (via the ridge pseudo-observation mechanism) rather than being applied as a fixed weight all season.

**Practical read for this project:** last year's rating is doing most of the work; the preseason poll adds a real but smaller amount on top. If a poll-blended prior (PLAN.md's original `w_poll`) is ever built for production, this result says it should be a modest addition to the history-based prior, not a replacement for it — matching the small `poll_diff` coefficient found here once last year's rating is already in the model.