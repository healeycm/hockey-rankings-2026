# Simulation study plan: NPI vs. KRACH/Massey

## Framing: correctness, not significance

Per direction, these studies are designed to answer **"does the metric get
it right?"** rather than **"is the difference significant?"** With 200+
simulated seasons, essentially every difference is significant; that's
not the interesting part. The interesting part is whether a metric
violates a property a selection metric ought to satisfy, how often, and
how badly in the worst case.

So each study below is framed as a **testable correctness property**,
with an explicit failure criterion, rather than as a hypothesis test.

### The correctness properties (axioms)

| # | Property | Plain statement | Expected: NPI | Expected: KRACH | Expected: Massey |
|---|---|---|---|---|---|
| A1 | **Win monotonicity** | Adding a win never lowers your rating | ✗ violates | ✓ by MLE | ✓ |
| A2 | **Opponent monotonicity** | Beating a stronger team helps at least as much as beating a weaker one | ✗ (QWB cliff) | ✓ | ✓ |
| A3 | **Game-count invariance** | Expected rating depends on how good you are, not how many games you played | ? | ✓ (variance only) | ~ (ridge shrinks low-N) |
| A4 | **Schedule non-manipulability** | You can't raise your rating by scheduling alone, without playing better | ✗ (75% SOS) | ✓ | ✓ |
| A5 | **Conference neutrality** | Equal true strength ⇒ equal expected rating, regardless of conference | ✗ | ~ | ~ |
| A6 | **Data completeness** | Every game counts; none removed based on its outcome | ✗ (bad-wins filter) | ✓ | ✓ |
| A7 | **Continuity** | Small input change ⇒ small output change | ✗ (QWB threshold) | ✓ | ✓ |
| A8 | **Well-definedness** | A rating always exists and is finite | ✓ (bounded 0–100) | ✗ (diverges on disconnected/undefeated) | ✓ (ridge guarantees) |

Note A8: this is the one where NPI is expected to **win** and KRACH to
**lose**. It must be run and reported. A critique that only tests the
axioms its target fails is advocacy, not analysis.

### Reporting standard for every study

In priority order:
1. **Violation rate** — in what fraction of simulated seasons does the property fail?
2. **Worst case** — largest rank error observed, and for which kind of team.
3. **A named minimal example** — a specific team, schedule, and set of results where the failure is visible and hand-checkable. This is the most persuasive artifact for a reader and the hardest to wave away.
4. Distributions/percentiles (esp. upper tail).
5. Means and paired tests — kept, but not the headline.

Tail matters more than mean here: tournament selection is a
**single-draw** decision. A metric that is unbiased on average but
occasionally puts a true-#40 team in the field is worse, for this
purpose, than one slightly biased but tight.

---

## Cross-cutting methodological requirement (important)

**Every finding must be robust across at least two different
data-generating processes (DGPs).** If we simulate outcomes from a
Bradley-Terry process, KRACH is the correctly-specified estimator and
will win by construction; if we simulate from a Poisson-scoring process,
Massey/Dixon-Coles are favored. Either alone proves nothing about the
real sport.

Planned DGPs:
- **DGP-A (Poisson scoring)** — what `harness/simulate.py` does now: per-team Poisson goal rates tilted by strength ratio. Favors margin-based models.
- **DGP-B (Bradley-Terry outcome)** — draw win/loss directly from `θ_h/(θ_h+θ_a)`, then attach a goal margin conditionally. Favors win/loss-based models.
- **DGP-C (heavy-tailed / misspecified)** — e.g., team strength that drifts within season, or occasional "bad night" outliers, so no model in the roster is correctly specified. The fairest test.

**This retroactively qualifies E1's headline.** E1 reported Massey
recovering ground truth best (ρ=0.912) under DGP-A only — a process
whose scoring structure is closer to Massey's own assumptions than to
KRACH's. That result should not be quoted in the paper until it's been
re-run under DGP-B and DGP-C. Flagged in
`reports/e1_truth_recovery.md`'s open items; upgrading it to a blocker
here.

---

## Study S1 — Games-played mismatch (priority: HIGH, user-raised)

**The concern.** Ivy teams start late and play fewer games. Does that
systematically distort their rating?

**Premise verified against real data (2025-26 DI):** games played range
**30 to 41**, mean 36.3. Yale and Brown play 31, Princeton 33,
Harvard/Cornell/Dartmouth 34 — versus Denver 41, Bentley/Duluth/Sacred
Heart/Minnesota State 40. That is up to a **32% difference in sample
size** between teams competing for the same tournament spots. Alaska (33),
Alaska Anchorage (33), LIU (32), Lindenwood (30) sit down there too, so
this is not only an Ivy issue.

**Mechanism to test.** Two competing effects, which should be
*decomposed*, not just observed in aggregate:
- (i) Fewer games ⇒ noisier win% and noisier SOS ⇒ more variance. Affects everyone symmetrically; not a correctness failure per se.
- (ii) The bad-wins filter (A6) lets a team discard wins that lower its rating. **A 41-game team has more discardable games than a 31-game team.** If so, the filter converts a schedule-length difference into a systematic *rating* advantage — a genuine correctness failure, and one nobody has tested.

**Design.**
- **S1a (observational):** real schedule as-is, iid true strengths. Plot rank error vs. games played per team. Is there systematic drift, or just widening variance?
- **S1b (causal):** *randomly* designate a subgroup and thin their schedule 38 → 34 → 30 → 26 games, holding true strength fixed. Random assignment removes the confound that real short-schedule teams might also genuinely differ in strength. Measure Δ(expected rank) for the thinned group.
- **S1c (decomposition):** repeat S1b with the bad-wins filter on vs. off, to isolate effect (ii) from effect (i).

**Failure criterion.** Expected rating/rank of a team of *fixed* true
strength changes materially with its number of games. (A3 violation.)

**Honesty note.** Massey's ridge regularization shrinks low-data teams
toward the mean — so Massey may well show its own A3 deviation here. It
is a defensible, principled kind of bias (that's what regularization is
for), but it is still a game-count-dependent effect and must be reported
as one, not excused.

**Harness work needed:** schedule-thinning utility.

---

## Study S2 — The weak team in a strong conference (priority: HIGH, user-raised)

**The concern.** A sub-.500 team in an elite conference gets ranked well
above its merit, especially after one or two lucky wins over top teams.

**Mechanism.** `NPI = 0.25·AdjWP + 0.75·SOS + QWB`. The SOS term is an
average of *opponents' NPI* — you receive it for **showing up**, whether
you win or lose. So conference membership alone confers rating. The QWB
then adds a bonus for each win over a 51+ opponent. A weak team in a
monster conference therefore gets: a large structural SOS floor, plus
lottery-ticket upside from any upset. KRACH, by contrast, credits
*results given opponents*; losing to a strong team does not raise a
KRACH rating.

This is the Ohio State case in `reports/npi_critique.md` (14-13-8; NPI
#19, KRACH #24, win% #43) — but real data can't prove it's wrong, because
we don't know Ohio State's true strength. Simulation can.

**Design.**
- Assign true strengths **stratified by conference** rather than iid: designate one conference genuinely elite, one genuinely weak, rest average.
- **Plant** teams of known-mediocre true strength inside the elite conference, and (symmetrically) known-strong teams inside the weak conference.
- Simulate many seasons; track each planted team's rank vs. its true rank under each metric.
- **The "lucky outcome" slice:** condition on seasons where a planted weak team beat ≥1 elite opponent, and report its rank distribution *in those seasons specifically*. That is precisely the scenario described — one or two upsets — and conditioning makes it directly answerable.
- Report the **upper tail** (90th/99th percentile rank inflation), not just the mean.

**Failure criterion.** Two teams of identical true strength in different
conferences have materially different expected rank. (A5 violation.)

**Symmetric control is mandatory.** Also measure suppression of the
strong-team-in-weak-conference. If we only test the direction that
indicts NPI, the result is not credible.

**Harness work needed:** conference-stratified strength assignment
(conference map can be derived from the `Type` column the same way
`npi.py` already does it).

---

## Study S3 — The quality-win-bonus cliff

**Mechanism.** `QWB = (opp_NPI − 51.0) × 0.5`, awarded only on a win and
only when `opp_NPI > 51.0`. That is a **discontinuity**: beating a 51.1
opponent pays, beating a 50.9 opponent pays nothing — and still drags
your SOS average down. Two nearly identical wins, wildly different
credit. This is also the root cause of the A1 paradox already measured
(6.3% of below-median wins lowered the winner's NPI in E1).

**Design.** Construct opponents whose true strength places their NPI in a
tight band around 51. Measure rating credit as a continuous function of
opponent strength; look for the step.

**Failure criterion.** Non-monotone or discontinuous response of rating
to opponent strength. (A2, A7.) KRACH and Massey are smooth by
construction, so this is expected to be a clean, near-analytic
demonstration rather than a statistical one — ideal for the "named
minimal example" reporting standard.

---

## Study S4 — The bad-wins filter as outcome-conditioned deletion

**Mechanism.** NPI drops regulation wins that lower the team's rating
(subject to a 12-win minimum). Deleting data points *because of their
outcome* is textbook selection bias.

**Design.** Identical simulated seasons, NPI with filter on vs. off;
measure truth recovery. Cross with S1 (does the filter's benefit scale
with games played?).

**Failure criterion.** The filter degrades truth recovery. (A6.)

**Implementation note.** The removal logic lives in `NPIGames`
(`src/rankings/npi_games.py`), not `NPI` — the comparison must use the
right class, and the plan should confirm which one the production /
official-replication path actually uses before drawing conclusions.

---

## Study S5 — Conference echo chamber under controlled connectivity

**Premise verified:** most teams play only **23–29% non-conference
games**; the full-season DI graph is heavily siloed. Real data shows
ρ=0.886 between a conference's non-conference win% and its members'
average SOS.

**The design that real data cannot do:** set every conference's true mean
strength to be **identical**, then vary the cross-conference game
fraction (≈10% → 50%). Any conference-level clustering in the output
ratings is then *provably* an artifact, since there is no true
conference-level difference to detect.

**Failure criterion.** Between-conference variance in mean rating
materially exceeds what the null (identical true conference strength)
allows, and grows as cross-conference play thins. (A5.)

---

## Study S6 — Connectivity limits and degenerate cases (the honesty study)

**This is where KRACH is expected to lose.** As an MLE over a comparison
graph, KRACH requires the graph to be strongly connected; undefeated or
winless teams drive ratings to infinity/zero. This project has already
hit the adjacent version of this (LRMC-family ratings collapsing to
exactly 0.0, which motivated the DI-opponent filter).

Real teams at risk: the independents — Alaska, Alaska Anchorage,
Lindenwood, LIU, Stonehill all play **100% non-conference** schedules by
definition and are the weakly-attached nodes in the graph.

**Design.** Dial connectivity down; deliberately construct undefeated and
winless teams; measure whether each metric produces a finite, sane
rating.

**Failure criterion.** Rating undefined, infinite, or wildly unstable.
(A8.) Expect NPI (bounded 0–100) to pass and KRACH to fail; Massey's
ridge should also pass, which is a genuine and reportable advantage of
regularization.

---

## Study S7 — OT/shootout credit (the fair-minded dial test)

NPI counts an OT win as 0.6 win / 0.4 loss. This project's own validated
finding is that OT outcomes are close to a coin flip
(`reports/lrmc_hockey_adaptation.md`), so 60/40 may be roughly right.

**Design.** Sweep OT credit (50/50, 60/40, 67/33, 100/0) against known
truth. **This is a dial NPI may well get right**, and confirming that
strengthens the rest of the critique's credibility.

---

## Study S8 — Schedule manipulability (the sharpest theoretical result)

**The question that matters most for a selection metric:** can a team
raise its rating **without getting any better**?

**Design.** Fix true strengths. For a target team, generate alternative
schedules — weak-heavy, strong-heavy, balanced — holding games played
constant. Simulate many seasons under each. Compare expected rank.

**Quantify as "schedule alpha":** rank positions gained per unit increase
in mean opponent strength, holding own true strength fixed. KRACH's
should be ≈0 (it estimates strength; strength didn't change). NPI's
should be clearly positive, since 75% of the formula is opponent quality
you receive for showing up.

**Failure criterion.** Expected rank changes materially with schedule
alone. (A4.) This is impossible to establish with real data — teams can't
be re-run on counterfactual schedules — and it is the most
policy-damaging finding available if it holds, because it implies the
metric rewards athletic-department scheduling decisions rather than play.

---

## Study S9 — Selection-field accuracy (the policy outcome)

Everything above is instrumental; **this is what the metric is actually
for.** NPI picks an at-large field.

**Design.** For each simulated season, take each metric's top 16 and
compare to the *true* top 16. Report: overlap count distribution; how
often a true-top-16 team is excluded; how often a true-#30+ team is
included; and **who** the errors are — are they short-schedule teams
(→S1)? weak-conference-elite teams (→S2)? That ties the mechanism
studies to the consequence.

This measure does not currently exist anywhere in the project —
`reports/calibration_metrics.md` flags "no rank-stability or bubble-team
accuracy metric was formalized" as an open item. S9 closes it.

---

## Study S10 — Single-game leverage / rank stability

**Design.** Leave-one-game-out across a full season; measure how far each
metric's rankings move. A metric where one result swings a bubble team 10
places is fragile for selection regardless of its average accuracy.
Reuses the LOO machinery already written for the paradox check in E1.

---

## Status (updated after S1/S2 first pass)

**S1 -- DONE (`e2_games_played_mismatch.py`, `e2b_minimal_worked_example.py`).**
Honest null result on the design tested: games-played mismatch alone
(plain `NPI`, no bad-wins filter) produces small, *symmetric* rank noise
for NPI, KRACH, and Massey alike -- no unique NPI bias found. Two real
bugs found and fixed along the way (a cross-team thinning-protection bug
in the harness; an index-alignment bug in a diagnostic print), both
documented in `reports/e2_games_played_mismatch.md`. This raises, not
lowers, the priority of testing the bad-wins filter specifically
(`NPIGames`), which remains untested -- see "Known blockers" below.

**S2 -- DONE, first pass, result is genuinely surprising
(`e3_weak_team_strong_conference.py`, `e3b_strength_sweep.py`,
`e3c_fluke_win_marginal_effect.py`).** Three separate designs, all
pointing the same direction, none confirming the original hypothesis in
its expected form:
- A team's *overall* conference-driven rank distortion is larger for
  KRACH than NPI at the weak extreme, and NPI's error actually flips to
  *underrating* as the planted team's true strength rises toward the
  field median (`e3`, `e3b`).
- The **precise mechanism you described** -- one or two fluke wins
  against very strong opponents -- is real and positive for all three
  models, but **largest for KRACH, not NPI** (`e3c`: KRACH +3.5 rank
  positions per fluke win vs. NPI's +1.8, at n=150).

**Net effect on the critique's shape:** the "NPI's SOS/QWB formula is
uniquely exploitable" framing is not supported by any of the three
designs run so far. What IS supported: KRACH's opponent-adjusted
likelihood shows *larger* single-result leverage than NPI's capped,
averaged formula, in both the overall-distortion and marginal-fluke-win
framings. This is a more nuanced, more defensible, and arguably more
interesting paper than the original hypothesis would have produced --
report it as found, not adjusted to fit the motivating concern.

**This does not mean NPI is vindicated.** The real-data critique
(`reports/npi_critique.md`)'s core findings -- 7+ arbitrary parameters,
632 dial-sensitivity rank shifts vs. KRACH's zero, the QWB
discontinuity, the bad-wins-filter selection bias, worse predictive
accuracy than its own predecessor (RPI) -- are untouched by this section
and stand independently. What's now in question is specifically the
*conference-inflation-via-lucky-wins* framing, not the broader critique.

**S9 -- DONE, reversed, then re-calibrated a second time. Final numbers
below (`e5` -> `e5b` -> `e5c`, in that order of correction).** The
original run (iid true strengths) found NPI seating more of the true
top-16 than KRACH or RPI (12.35 vs. 12.01 and 11.83). Asked directly
whether that assumed all conferences are equal: yes, and real data
shows they aren't -- re-run with a conference-stratified model
(`e5b`, `conf_log_sigma=1.1` calibrated against 2025-26 alone) and the
ranking inverted dramatically (KRACH 13.97, Massey 13.89 vs. NPI 13.09,
RPI 12.97). A full three-season assumption audit (E6) then found that
calibration itself was built on an inconsistent measurement basis and
tuned against the least representative of the last three seasons.
Recalibrated properly against the 3-season average with one consistent
basis (`e5c`, `conf_log_sigma=0.4`): **the direction survives, the
magnitude shrinks substantially** -- KRACH 12.34 vs. NPI 11.92
(paired p<0.0001, still significant), Massey and RPI essentially
unchanged from the iid-world values (12.70, 11.84). NPI vs. RPI, which
iid had NPI clearly winning, is now a statistical tie. **Three tellings
of the same experiment produced three different numbers; the lesson is
not "the last one is finally correct" but that field-accuracy ranking
between NPI and KRACH is real, directionally in KRACH's favor, and far
more modest than either earlier version suggested.** What survives
unchanged throughout all three versions: no games-played selection bias
for any model, and the independents-mishandling pattern (KRACH
disproportionately excludes them; NPI/RPI disproportionately include
weak ones) in both directions.

**Broader implication, still open: E1, S1, and S4 carry the same
iid-conference assumption and have not been re-checked under either
conference calibration.** None of their core findings are as directly
conference-strength-dependent as field-selection accuracy turned out to
be, but none should be treated as validated against this gap just
because S9 was -- and S9's own history (two corrections needed before
trusting a number) is a caution against assuming a first recalibration
is the last one needed.

**E7 -- distribution-shape mismatch (E6 open item) checked and resolved
as a non-issue (`e7_distribution_shape_check.py`,
`reports/e7_distribution_shape_resolution.md`).** E6 found real win% is
close to normal/slightly left-skewed while the simulator assumes
right-skewed lognormal true strength, and flagged it as the assumption
most likely to matter for tail-dependent studies. Checked before
changing anything: the simulator's actual *output* win% distribution
(not the input assumption) already matches real data's shape and tails
closely, for both strength-assignment methods used in this workspace --
win%'s boundedness and the ~36-game averaging dampens the input's skew
before it reaches anything a study measures. No code change made. This
is the reverse-direction version of the S9 lesson: check whether a
superficial mismatch actually propagates before spending effort "fixing"
it.

**E8 -- OT-rate undershoot (E6's other open item) fixed and verified
(`e8_ot_rate_calibration.py`, `reports/e8_ot_rate_correction.md`).**
Unlike distribution shape, this one was real: simulator gave 14.3% OT
rate vs. real 18.1-22.3% across all three seasons. Added a
`CLOSE_GAME_PROB=0.07` mechanism (7% of games drawn as a shared,
forced-tie score instead of independent Poisson) to `simulate_season()`
-- OT rate now lands at 0.205 (iid) / 0.213 (conf-stratified), squarely
in the real range, on the first calibration attempt, with home win% and
mean goals essentially undisturbed. **This changes the core simulator
retroactively -- every experiment in this workspace's exact numbers are
now stale relative to current code.** Re-ran S9's final result (`e5c`)
immediately rather than leave it stale: the ordering (Massey > KRACH >
NPI > RPI) and the KRACH-beats-NPI finding both survive (12.12 vs.
11.88, p=0.0001), making this the most heavily re-verified finding in
the whole critique (three sigma calibrations plus one OT-rate
correction). One real, non-headline change: NPI vs. RPI flipped from a
tie to a clear NPI win, since RPI's field accuracy dropped more than
the other three models' under the fix -- not investigated further.
**E1, S1, S2, and S4 were not re-run and remain stale** -- flagged, not
assumed fine.

**S4 -- DONE (`e4_bad_wins_filter_games_mismatch.py`,
`e4b_bad_wins_filter_cupcakes.py`; see `reports/e4b_bad_wins_filter_cupcakes.md`
for the definitive account).** The one place S1/S2's hypothesis could
still hold, since S1/S2 both used plain `NPI` (no filter). Took four
attempts, three of which either failed to trigger the mechanism or
contained a real design flaw caught before being trusted (a
strong-conference target team; an uncalibrated opponent-strength widen;
a conference relabeling that did nothing under iid strengths; a
cupcake-protection scheme that inadvertently concentrated weak
opponents more heavily in the short-schedule condition). **Final,
properly controlled result: no meaningful games-played advantage from
the filter.** The mechanism is real and triggers substantially (~20-30%
of replications) once genuine weak opponents exist on a schedule, but a
fraction-matched long-vs-short comparison shows drop rates and rank
effects statistically indistinguishable across schedule lengths, and
NPIGames does not stand out from NPI/KRACH/Massey. Combined with S1 and
S9, this is now three independent designs reaching the same conclusion
-- **games-played mismatch is a settled negative result**, not an open
question.

---

## Priority order

| Order | Study | Status |
|---|---|---|
| 1 | **S1** games-played mismatch | **Done** -- null result, see above |
| 2 | **S2** weak-team-in-strong-conference | **Done, first pass** -- surprising result, see above |
| 3 | **S9** selection-field accuracy | **Done, corrected twice** -- KRACH beats NPI, modestly (12.34 vs 11.92), see below |
| 4 | **S8** schedule manipulability | Not started; sharpest theoretical result remaining |
| 5 | **DGP-B/C robustness** | Not started; blocks quoting E1/S1/S2 in the paper |
| 6 | S4 bad-wins filter (`NPIGames`) | **Done** -- no meaningful games-played advantage, see above |
| 7 | S3 QWB cliff | Not started |
| 8 | S5 echo chamber | Not started |
| 9 | S6 connectivity | Not started; honesty study, must appear before submission |
| 10 | S7 OT credit | Not started |
| 11 | S10 stability | Not started |

S1 and S2 can start immediately — they use official dials only, so they
do **not** depend on fixing the hard-coded-weights issue below.

---

## Known blockers / prerequisites

1. **`NPI.fit()` hard-codes 0.25/0.75.** Any study that varies
   `weight_wp`/`weight_sos` (S5, parts of S2) currently has to use
   `reweight_npi()`'s post-hoc recombination, which does *not* re-run the
   iteration at the new weight. Studies S3/S4/S7 vary *other* dials
   (QWB base/mult, OT credit) — need to confirm which of those `fit()`
   actually reads before trusting any sweep over them. **Verify each dial
   is live before sweeping it**; E1 already produced bit-identical
   "different" results from a dial that turned out to be dead.
2. **Harness additions:** schedule thinning (S1), conference-stratified
   strengths (S2), schedule rewiring (S5, S8), alternative DGPs (B and C).
3. **Which NPI class is authoritative** — `NPI` vs `NPIGames` — for the
   bad-wins filter (S4).
