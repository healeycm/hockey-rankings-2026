# S9, Final: Selection-Field Accuracy, Properly Calibrated Against Three Seasons

## This corrects e5b's magnitude, not its direction

`reports/e5b_selection_field_accuracy_conf_stratified.md` found KRACH
and Massey clearly beating NPI and RPI (13.97/13.89 vs. 13.09/12.97 of
16) using `conf_log_sigma=1.1`. `reports/e6_assumption_audit.md` then
found that calibration was built on an inconsistent measurement basis
(the real target was computed on non-conference games only; the
simulator check that justified 1.1 was not) and against 2025-26 alone,
which turns out to have the smallest conference-effect share of the
last three seasons (28% vs. 2023-24/2024-25's ~48%). Recalibrating
`conf_log_sigma` to 0.4 against the 3-season average with one
consistent measurement basis throughout (see the harness docstring in
`simulate.py` for the full chain), and re-running the exact same
field-accuracy experiment:

| Model | iid (e5) | Over-calibrated (e5b, conf_sigma=1.1) | **Properly calibrated (this report, conf_sigma=0.4)** |
|---|---:|---:|---:|
| Massey | 12.72 | 13.89 | **12.70** |
| KRACH | 12.01 | 13.97 | **12.34** |
| NPI | 12.35 | 13.09 | **11.92** |
| RPI | 11.83 | 12.97 | **11.84** |

**The direction of e5b's reversal survives: KRACH significantly beats
NPI (12.34 vs. 11.92, paired t-test p<0.0001).** But the magnitude is
far more modest than e5b suggested, and two things change materially
once measured correctly:

- **Massey and RPI both land almost exactly back at their iid-world
  values** (12.70 vs. 12.72; 11.84 vs. 11.83) -- the inflated
  conference-stratified numbers in e5b (13.89, 12.97) were mostly an
  artifact of the miscalibrated sigma, not a real property of adding
  conference structure at all.
- **NPI vs. RPI is now a statistical tie** (11.92 vs. 11.84, p=0.135) --
  under iid strengths NPI clearly beat RPI; under a properly calibrated
  conference-stratified world, it doesn't.

## The honest summary of this whole chain

Three tellings of the same experiment, same underlying question, three
different numbers -- and the correct lesson is not "the third one is
finally right, trust it absolutely." It's: **field-accuracy ranking
between NPI and KRACH is directionally in KRACH's favor once realistic
conference structure exists, the effect is real but modest (not the
dramatic 13.97-vs-13.09 gap first reported), and even this "final"
calibration rests on assumptions (a normal-ish, not log-normal,
strength distribution per e6; a single log-normal conference-effect
model at all) that have not themselves been stress-tested.** Reporting
a smaller, better-justified effect with its own remaining caveats
stated plainly is more useful than either of the two earlier, more
dramatic-looking numbers.

## Method

`research/npi_critique/experiments/e5c_selection_field_accuracy_recalibrated.py`.
Identical design to `e5`/`e5b`; only the calibration of
`assign_conference_stratified_strengths`'s sigmas changed
(`conf_log_sigma=0.4`, `team_log_sigma=0.24`, both verified to reproduce
the 3-season-average real between-/overall-win%-std targets within 2%
using one consistent, non-conference-games-only measurement basis for
both real and simulated data).

## Shipped

- `research/npi_critique/experiments/e5c_selection_field_accuracy_recalibrated.py`.
- `research/npi_critique/harness/simulate.py`: docstring rewritten with
  the full two-correction calibration history, so a future reader
  doesn't have to reconstruct it from report cross-references.
- Results: `research/npi_critique/results/e5c_selection_field_accuracy_recalibrated/`.
- `reports/e5b_...md` should be read as superseded on magnitude (not
  direction) by this report, the same way `e5_...md` was superseded by
  `e5b`. Kept, not deleted, for the record.

## Open items

1. **The distribution-shape mismatch from `e6` is still unaddressed.**
   All three tellings of this experiment (iid, e5b, e5c) draw true
   strength from a lognormal; real win% looks closer to normal, slightly
   left-skewed, in all three real seasons. Not yet tested whether this
   changes the field-accuracy ranking the way the conference-effect
   correction did.
2. **S2's e3/e3b/e3c still use the original, uncalibrated
   `conf_log_sigma=0.35` default** and have not been re-checked under
   either the e5b or e5c calibration.
3. **Only one random seed's worth of conference-effect draws underlies
   each season in this design** (a fresh conference effect is drawn
   every replication) -- this is appropriate for the "what if conference
   strength varies" question but means no single replication should be
   read as "this is what 2026-27 will look like."
