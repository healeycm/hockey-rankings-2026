# E6: Full Assumption Audit Against Three Real Seasons

## Summary

Every prior calibration check in this workspace (`e0_calibration_check.py`,
the sigma sweeps in `e4b`/`e5b`) validated against **2025-26 alone**.
Asked directly to restate every assumption and check it against the last
three complete seasons (2023-24, 2024-25, 2025-26), several real gaps
turned up that a single-season check missed -- one of them serious
enough to revisit before trusting the S9 reversal's exact magnitude.

## 1. Number of teams

**Assumption:** 63 teams, fixed at the 2025-26 roster, reused for every
replication in every experiment in this workspace.

**Reality:** stable. All three seasons have exactly 63 Division I teams,
and 2023-24's and 2024-25's team lists are *identical* to 2025-26's --
zero roster turnover across all three years. This assumption holds
cleanly; no correction needed.

## 2. Spread (best to worst)

**Assumption:** true strength ~ Lognormal(0, sigma=0.4), producing a
simulated win% std of 0.179 (40 replications).

**Reality:** real win% std is 0.150 (2023-24), 0.153 (2024-25), 0.158
(2025-26) -- a narrow, consistent range across all three years. **The
simulator overshoots all three, not just the one season previously
checked**, by roughly 13-19%. This is a real, mild, *consistent* bias
in the same direction (too much spread), not something the single-season
check happened to get right by chance -- but it's also not large enough
to be a first-order concern on its own. (Min/max ratio is a much noisier
statistic -- 28.6/6.2/6.9 across the three years -- driven by one
near-winless team in 2023-24; std is the more stable, trustworthy
comparison here.)

## 3. Distribution shape -- the assumption that turned out most wrong

**Assumption:** true strength is right-skewed by construction (a
lognormal always is: a few very strong teams, a long pack below
average).

**Reality:** real win% is close to **normally distributed**, if
anything **slightly left-skewed**, in all three seasons -- skew -0.15,
-0.24, -0.33; Shapiro-Wilk normality test fails to reject normality at
p=0.59, 0.76, 0.36 for 2023-24/2024-25/2025-26 respectively (i.e., real
win% is statistically indistinguishable from normal in every one of the
three years, and if it deviates at all, it leans the opposite direction
from what the simulator assumes). This is a genuine mismatch in
distributional *form*, not just spread magnitude, and it was never
checked before this audit -- every prior study implicitly assumed the
sport has a long right tail of elite teams and a compressed left tail of
weak ones; real data suggests roughly the opposite lean, or no
meaningful skew at all.

**Caveat, stated plainly:** win% is an observed, bounded [0,1] outcome,
not the same object as "true strength" (a team's win% is itself a noisy
function of true strength, schedule, and luck) -- so this is a proxy
comparison, not a rejection of the lognormal on its own terms. But it is
the best available check, and it points the same direction across all
three years, which a coincidence of schedule or luck in a single season
would not explain. **This is the assumption most worth revisiting** if
any future study's conclusion turns out to hinge on tail behavior (S2's
extreme-strength sweep and S4's cupcake-triggering mechanism both do).

## 4. Conference stratification and distribution

**Conference sizes are stable:** ECAC 12, Hockey East 11, Atlantic
Hockey 10, and NCHC/CCHA/Big Ten in the 7-9 range across all three
seasons -- CCHA and NCHC both grew by one team between 2023-24 and
2024-25 (8->9), and independents shrank from 7 to 5 over the same
transition (two programs joined conferences). Minor, not structurally
disruptive.

**The conference-effect SHARE OF VARIANCE is not stable, and this
matters.** Using a clean, apples-to-apples split (both between- and
overall-std computed on non-conference games only, correcting an
inconsistency in this session's earlier ad hoc calibration, which mixed
an all-games overall std against a non-conference-only between-conference
std):

| Season | Between-conf std | Overall std | Conference share of variance |
|---|---:|---:|---:|
| 2023-24 | 0.141 | 0.203 | **48.0%** |
| 2024-25 | 0.139 | 0.199 | **48.7%** |
| 2025-26 | 0.110 | 0.207 | **28.4%** |

**2025-26 -- the one season every calibration in this workspace used --
shows nearly the smallest conference effect of the three years.** Two of
the last three seasons show conference membership explaining roughly
**48%** of win% variance, not 28%. The `conf_log_sigma=1.1` value used
in `e5b`'s reversal of the S9 finding was tuned to match 2025-26
specifically. **If 2023-24/2024-25 are more representative of a typical
season, the true conference effect is likely larger than what was
calibrated, meaning the S9 reversal (KRACH/Massey beating NPI/RPI once
real conference structure is present) is probably conservative, not
overstated.** This should be re-checked with a sigma calibrated against
the 3-season average share (~42%) rather than 2025-26 alone before the
reversal's exact magnitude is treated as final -- though the *direction*
of the reversal is, if anything, reinforced by this finding, not
undermined.

## 5. Win probabilities

| Season | Home win% | OT rate | Mean goals | Tie rate |
|---|---:|---:|---:|---:|
| 2023-24 | 0.578 | 0.216 | 5.97 | 0.085 |
| 2024-25 | 0.532 | 0.223 | 5.69 | 0.083 |
| 2025-26 | 0.551 | 0.181 | 5.89 | 0.069 |
| **Simulator** | **0.562** | **0.143** | **5.89** | n/a (always resolved) |

**Home win% and mean goals are both fine** -- the simulator's 0.562 and
5.89 sit within or very close to the real three-year range (0.532-0.578,
5.69-5.97).

**OT rate is a real, consistent undershoot, worse than previously
characterized.** The original single-season check called 0.143 vs.
2025-26's 0.181 "the closest miss" and moved on. Seeing all three years
(0.181-0.223), the simulator undershoots *every one of them*, by
20-36% relatively. This is a real calibration gap in the scoring model
(`MEAN_GOALS_PER_TEAM`/regulation-tie probability), not a rounding
difference against one unusually low year -- 2025-26 turns out to be the
low outlier here too, meaning the original calibration target was
already the most forgiving of the three years available.

**Tie rate is an open, unexplained observation, stated without
interpretation.** Real data shows a nonzero "tie" rate (`Result==0.5`)
of 6.9-8.5% across all three seasons. This project's own prior reports
(`reports/hockey_bt_results.md`) describe modern-rules ties as
essentially eliminated by shootouts, with any residual tie flag confined
to specific historical rule eras. Whether this real, present-day nonzero
rate reflects an actual current-rules edge case, a data/labeling
convention in `games_archive.csv`, or something else was not
investigated here -- flagged as a genuine open question rather than
explained away, since asserting a cause without checking would repeat
exactly the mistake this workspace's audits exist to catch.

## Net assessment

Of five assumption categories audited against three real seasons instead
of one: **team count and home-ice/scoring rates hold up well; win%
spread is a mild, consistent overshoot; distribution shape is a real
mismatch in an unexpected direction; conference-effect magnitude was
calibrated against the least representative of the three available
years; OT rate is a real, previously understated undershoot.** None of
these individually invalidates a prior finding, but two of them
(conference-effect magnitude, distribution shape) bear directly on
studies whose results depend on tail behavior or realistic
conference-strength separation -- S2, S4, and S9 most directly.

## Shipped

- `research/npi_critique/experiments/e6_assumption_audit.py` -- run
  this again whenever a new season's data becomes available; it is
  written to make the three-season (or N-season) comparison a single
  command rather than an ad hoc check.

## Open items

1. **Re-calibrate `conf_log_sigma` against the 3-season average
   conference-variance share (~42%)** rather than 2025-26 alone, and
   re-run `e5b`'s field-accuracy comparison under it.
2. **Investigate the OT-rate undershoot properly** -- likely needs a
   lower `MEAN_GOALS_PER_TEAM` or an adjusted regulation-tie probability
   in `simulate_season`, re-validated against all three seasons rather
   than one.
3. **The tie-rate discrepancy is unexplained** -- worth a short,
   dedicated check of `games_archive.csv`'s `Result==0.5` rows before
   it's used to justify or contradict anything else.
4. **Distribution-shape mismatch not yet acted on** -- no immediate fix
   proposed; flagged as the assumption most likely to matter for
   tail-dependent studies (S2, S4) if it is investigated further.
