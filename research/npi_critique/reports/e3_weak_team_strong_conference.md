# S2: The Weak Team in a Strong Conference

## Summary: a real, replicated finding that runs counter to the motivating concern

The concern (yours, and `reports/npi_critique.md`'s Ohio State case
study): a mediocre team stuck in an elite conference gets overrated,
especially after 1-2 lucky wins, because NPI's SOS term (75% of the
formula) credits opponent quality regardless of whether you beat them.

**In this simulation design, at n=300 replications, the opposite of that
ranking emerges.** A team of fixed, deliberately mediocre true strength
(true rank ~52-53 of 63) planted inside the real Big Ten's schedule shows
**KRACH exhibiting the larger overrating bias, not NPI**:

| Model | Mean rank error | % overrated | Worst single case |
|---|---:|---:|---:|
| KRACH | **+1.78** | 54.0% | **+25** |
| Massey | +0.95 | 54.0% | +16 |
| NPI | **-3.08** | 16.3% | +12 |

(Rank error = true rank − induced rank; positive = ranked *better* than
deserved, i.e. overrated. Symmetric control, a strong team planted in a
weak conference [Atlantic Hockey], confirms the same ordering in the
opposite direction: KRACH -2.45 mean / -27 worst underrate; NPI actually
+1.44 mean, i.e. *overrated* in that direction instead.) NPI is not
merely "less overrated than KRACH" -- on this design, its bias runs the
other way, mostly *under*rating the weak-in-elite team relative to its
already-bad true rank.

**This does not mean the original concern is wrong** -- it means this
specific, controlled test does not confirm it in the direction expected,
and that is worth knowing and reporting exactly as found, not adjusted
to fit the expected story. Section "Why this might be happening" below
proposes a mechanism, explicitly labeled as a hypothesis, not a
conclusion.

## Concrete example (replication 17, real Ohio State schedule)

The planted team (true strength 0.55, true rank 52/63) went **7-30**
against its real 2025-26 schedule, including 6 genuine upsets (beating a
team with higher true strength) mixed among blowout losses to its
(simulated-strong) conference mates:

```
Ohio State 4-3 Northern Michigan (OT)  <-- UPSET
Arizona State 1-2 Ohio State           <-- UPSET
Ohio State 6-5 Michigan                <-- UPSET
Ohio State 4-3 Wisconsin (OT)          <-- UPSET
Penn State 3-4 Ohio State              <-- UPSET
Ohio State 5-0 Notre Dame              <-- UPSET
...mixed among losses like Michigan State 13-2, Notre Dame 11-0, Wisconsin 8-1
```

Induced ranks: **KRACH #47** (better than true rank 52 by 5 spots --
overrated), **Massey #54** (worse by 2), **NPI #58** (worse by 6 -- the
most harshly-rated of the three, not the most lenient). This is the
literal "1-2 lucky wins in a strong conference" scenario you described --
here it's 6 flukey wins mixed into a 7-30 record -- and NPI is the model
that punishes it most, not least, in this specific case.

## Method

`research/npi_critique/experiments/e3_weak_team_strong_conference.py`.
Real 2025-26 conference structure (`get_conference_map` on the real
schedule): Big Ten (7 teams) fixed as the elite conference, Atlantic
Hockey (10 teams) fixed as the weak conference (deterministic log-scale
effects of +0.65/-0.65 across all 300 replications, isolating "given a
genuinely strong/weak conference exists" from any particular random
draw of which conference is strong). One real team's schedule in each
conference (Ohio State's, RIT's) has its assumed true strength
overridden to a fixed, deliberately mediocre (0.55) or strong (1.85)
value, while every other team's strength is drawn normally
(conference-stratified log-normal). "Genuine upset" = the planted team
beating an opponent with higher true strength that specific replication
-- computable only because ground truth is known, exactly the thing real
data can't provide.

## Why this might be happening (hypothesis, not conclusion)

Two candidate mechanisms, both plausible, neither confirmed here:

1. **KRACH's unbounded multiplicative scale is more volatile in a small,
   thin conference network.** The Big Ten here is only 7 teams; a team
   that upsets even one elite conference-mate can see its Bradley-Terry
   rating pulled up disproportionately, because that opponent's own
   rating is very high and KRACH has no ceiling (this project has
   already documented KRACH's rating spread reaching 1284x on real data
   -- `reports/hockey_bt_results.md`). NPI's bounded 0-100 scale and
   explicit SOS averaging may be *less* sensitive to a small number of
   high-leverage results than an MLE estimate is in a sparse network --
   which would mean the "conference credit" mechanism motivating this
   study is real in spirit, but attaches more to KRACH's estimation
   behavior on thin networks than to NPI's explicit formula. This
   connects directly to **Study S6** in `PLAN.md` (connectivity limits),
   not yet run.
2. **NPI's 25% own-win% term may dominate for a team this bad.** A 7-30
   record's Adjusted WP component is severely negative regardless of
   opponent quality, and QWB is near zero (rarely beating a 51+
   opponent), so the formula may simply not have enough SOS-driven
   lift left to overcome a genuinely poor record at this level of
   mediocrity. This suggests the concern may be **strength-dependent**:
   real teams like the actual Ohio State (14-13-8, a near-.500 record)
   sit in a different regime than the planted team here (7-30, a true
   rank of 52nd), and this experiment's planted strength (0.55) may be
   testing a more extreme case than the real-world scenario that
   motivated it.

## Follow-up: does the bias direction depend on how weak the team truly is?

Ran immediately as the obvious next check (`e3b_strength_sweep.py`, 120
replications per strength value, same elite conference, five planted
strengths from a true bottom-feeder up to roughly the field median):

| Planted strength | Mean true rank | KRACH error | Massey error | NPI error |
|---:|---:|---:|---:|---:|
| 0.55 | 58 | **+2.33** | +1.42 | -0.75 |
| 0.70 | 51 | **+4.21** | +1.99 | -1.77 |
| 0.85 | 43 | +3.08 | -0.92 | -5.38 |
| 0.95 | 37 | +1.09 | -0.86 | -7.88 |
| 1.05 | 32 (~field median) | **+0.28** | -2.33 | **-7.78** |

(Error = true rank − induced rank; positive = overrated.) **The result
is not a simple confirmation or reversal of hypothesis 2 -- it's
qualitatively different from either.** As the planted team's true
strength rises from "true bottom-feeder" toward "genuinely average, just
saddled with a brutal schedule":

- **KRACH's overrating shrinks toward zero** (+2.3 -> +4.2 -> +3.1 -> +1.1
  -> +0.3) rather than growing -- it resolves *best*, not worst, for a
  team that's actually average but schedule-battered. This is consistent
  with KRACH's core design: an opponent-strength-adjusted likelihood
  should specifically avoid penalizing a competent team for a bad-looking
  raw record built against tough opposition.
- **NPI's error flips sign and grows sharply in the *underrating*
  direction** (-0.75 -> -1.77 -> -5.38 -> -7.88 -> -7.78) -- at the
  near-median end, NPI ranks this actually-average team **nearly 8 spots
  worse than its true rank**, not better. NPI's 25% direct win-percentage
  term appears to punish a schedule-depressed record more than its 75%
  SOS credit compensates, for a team whose true talent doesn't
  fall neatly into "clearly bad" or "clearly good."
- **Massey tracks a middle path**, mildly overrating the weakest planted
  team and mildly underrating the near-median one.

**Restated plainly: this experiment does not support "NPI overrates a
mediocre team stuck in a strong conference" at any point in the strength
range tested.** It supports a related but different, and arguably more
policy-relevant, concern: **NPI may *underrate* a genuinely competent
team that has the misfortune of a difficult schedule and a resulting
rough win-loss record** -- the mirror image of the original worry, and
one that cuts against a team's tournament case rather than inflating an
undeserving one. Both are real selection-fairness issues; they are not
the same issue, and the paper should not conflate them just because both
involve "a team's conference distorting its rating."

## Shipped

- `research/npi_critique/harness/simulate.py`: `get_conference_map`,
  `assign_conference_stratified_strengths` (both used here; the former
  also usable by future studies).
- `research/npi_critique/experiments/e3_weak_team_strong_conference.py`.
- Results: `research/npi_critique/results/e3_weak_team_strong_conference/rank_error.csv`.

## Open items

1. **Sweep planted strength** (e.g. 0.55, 0.75, 0.90, 0.95 -- moving from
   "true bottom-feeder" to "true near-.500") to test hypothesis 2 above
   directly -- the most important follow-up, per above.
2. **Sweep conference size and the elite/weak effect magnitude** -- is
   the KRACH-larger-swing pattern specific to a small 7-team conference,
   or does it hold for larger ones too? Connects to Study S5 (echo
   chamber) and S6 (connectivity) in `PLAN.md`.
3. **Only one elite/weak conference pair tested** (Big Ten / Atlantic
   Hockey). Repeating with a different pair would check whether some
   other real structural feature of these specific conferences (schedule
   density, which teams are independents nearby, etc.) is driving the
   result rather than "elite vs. weak" alone.
4. **DGP caveat applies here too** (see `e1_truth_recovery.md`) -- this
   used the Poisson-scoring DGP; not yet reproduced under a Bradley-Terry
   or misspecified DGP.
5. This experiment used the standard `NPI` class, not `NPIGames` (the
   bad-wins-filter variant) -- same scoping note as S1.
