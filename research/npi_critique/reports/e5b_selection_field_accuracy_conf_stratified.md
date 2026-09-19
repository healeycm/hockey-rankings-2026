# S9, Corrected: Selection-Field Accuracy Under Realistic Conference Structure

> **MAGNITUDE SUPERSEDED -- see `reports/e5c_selection_field_accuracy_recalibrated.md`.**
> This report's `conf_log_sigma=1.1` was calibrated against 2025-26
> alone using an inconsistent measurement basis, and turns out to
> substantially overshoot a properly, consistently calibrated value
> (0.4) once checked against all three recent seasons. The direction of
> the finding below (KRACH beats NPI once conference structure exists)
> survives in the corrected report, but the magnitude here (13.97 vs.
> 13.09) is inflated -- the corrected gap is 12.34 vs. 11.92. Kept for
> the record, not deleted.

## This reverses the previous headline finding, and the previous finding should not be trusted

`reports/e5_selection_field_accuracy.md` reported NPI seating more of
the true top-16 than KRACH or RPI, calling it "NPI's first clear
strength in this workspace." That result used
`assign_true_strengths` -- every team's true strength drawn
independently, which implicitly assumes **all conferences are equal in
expectation**. This was not a deliberate modeling choice defended
anywhere; it was the default carried over from E1 without being
questioned, and it was wrong: checked directly against real 2025-26
data, conferences differ substantially (non-conference win% ranges from
0.38 for independents to 0.64 for NCHC/Big Ten, a real conference in
this dataset), and conference membership accounts for roughly 40% of
total team-level win% variance (between-conference std 0.102 vs.
overall 0.158). The iid design set that share to zero.

**Re-run with true strengths drawn from a properly calibrated
conference-stratified model instead (`conf_log_sigma=1.1`,
`team_log_sigma=0.30` -- tuned to match real between-conference std
0.080 vs. target 0.102, and overall std 0.156 vs. target 0.158; this
still somewhat undershoots real conference dispersion, so if the effect
below scales with conference-strength realism, the true effect may be
larger than what's reported here, not smaller):**

| Model | Mean overlap of 16 (iid, e5) | Mean overlap of 16 (conf-stratified, this report) |
|---|---:|---:|
| **KRACH** | 12.01 | **13.97** |
| **Massey** | 12.72 | **13.89** |
| NPI | 12.35 | 13.09 |
| RPI | 11.83 | 12.97 |

**The ranking inverts.** Under iid strengths, NPI beat KRACH and RPI.
Under realistic conference structure, KRACH and Massey are
statistically indistinguishable at the top, and NPI and RPI both fall
behind -- the direction, not just the magnitude, changes. This is not a
subtle recalibration; it is the opposite conclusion from the same
experiment under a corrected input assumption.

## Why this makes sense

KRACH's opponent-adjusted maximum likelihood is, by construction,
explicitly built to disentangle "this team is genuinely strong" from
"this team's record looks good/bad because of who it played" --
precisely the question that matters once conferences genuinely differ
in strength. NPI's SOS term does something superficially similar
(averaging opponents' own NPI), but the averaging is linear and
un-iterated to the same degree, is diluted by the 25% raw-win%
component, and interacts with the QWB cliff and bad-wins filter in ways
this workspace has already shown can behave unpredictably (S2, S4).
When conferences are truly equal (the iid world), none of that
opponent-adjustment machinery has real signal to work with, and the
comparison mostly reduces to noise plus each formula's other quirks --
which is exactly the regime where NPI's simpler structure looked fine.
Once genuine conference-strength signal exists, KRACH's more principled
opponent adjustment has something real to extract, and does so better.

## A related pattern in the wrongly-included teams

Independents (weakest real conference-equivalent group in this
calibration, 0.38 non-conference win%) are wrongly included in the
tournament field far more often by NPI (124 instances) and RPI (160)
than by KRACH (50) or Massey (68), out of 300 replications. This
complements, rather than contradicts, e5's original finding that KRACH
disproportionately *excludes* real independent teams (LIU, Alaska
Anchorage) -- both are real distortions on thin-network/independent
teams, just opposite in direction and different in which model produces
them. KRACH's distortion on these teams is a false-negative pattern
(wrongly leaving them out); NPI's and RPI's is a false-positive pattern
(wrongly letting a weak one in). Neither model handles this class of
team cleanly, and a future study should quantify both errors on the
same team set to see which failure mode is worse for actual selection
consequences.

## What still stands from the original e5 report

The games-played findings (no meaningful bias for any model) and the
specific KRACH-excludes-independents pattern do not depend on the
iid-vs-conference-stratified choice -- games-played variation is a
property of the real schedule regardless of how strength is assigned,
and the independent-exclusion pattern is, if anything, reinforced here
(the "wrongly included" side of the same coin). Only the
overall-field-accuracy ranking (which model seats the field best) is
reversed.

## Method

`research/npi_critique/experiments/e5b_selection_field_accuracy_conf_stratified.py`.
Identical to `e5_selection_field_accuracy.py` except for strength
assignment: `assign_conference_stratified_strengths` with the
calibrated sigmas above, 300 replications, real 2025-26 schedule.

## Shipped

- `research/npi_critique/experiments/e5b_selection_field_accuracy_conf_stratified.py`.
- Results: `research/npi_critique/results/e5b_selection_field_accuracy_conf_stratified/`.
- `reports/e5_selection_field_accuracy.md` annotated with a superseded
  notice pointing here, rather than deleted -- the games-played and
  independent-exclusion findings there still stand.

## Open items

1. **Calibration still undershoots real between-conference dispersion**
   (0.080 vs. 0.102) -- a closer match might show an even larger KRACH/
   Massey advantage. Worth pushing `conf_log_sigma` further and
   re-checking, though real conference-mean estimates themselves carry
   sampling noise from small per-conference team counts (5-12 teams),
   limiting how precisely 0.102 itself should be trusted as a target.
2. **Every other iid-strength result in this workspace (E1, S1, S4)
   should be flagged with the same caveat**, even though none of their
   core mechanisms (truth-recovery generally, games-played specifically)
   are as directly conference-strength-dependent as field-selection
   accuracy is. Not re-run here for scope reasons, but the assumption
   should not be treated as validated elsewhere just because it was
   caught and fixed here.
3. **DGP caveat still applies** (Poisson scoring, per `e1_truth_recovery.md`).
