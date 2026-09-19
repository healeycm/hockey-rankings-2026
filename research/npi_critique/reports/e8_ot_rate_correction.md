# E8: Fixing the OT-Rate Undershoot

## The fix

E6 found the simulator's OT rate (14.3%) undershoots all three recent
real seasons (18.1-22.3%), and E7 confirmed (unlike the distribution-
shape item) this one is real -- not an artifact of comparing the wrong
object. Independent-Poisson scoring alone produces fewer regulation ties
than real hockey does, plausibly because real teams play measurably
tighter, more risk-averse hockey in a close third period than two
independent scoring processes with the same average rates would predict.

**Mechanism added:** `CLOSE_GAME_PROB` (`research/npi_critique/harness/simulate.py`).
With probability 0.07, a game's regulation goals are drawn from a single
**shared** count (`Poisson(sqrt(lam_home * lam_away))`, applied to both
teams) instead of two independent draws -- forcing a tie and sending the
game to OT. This is layered on top of the existing independent-Poisson
baseline (which still produces its own natural ties the rest of the
time), rather than replacing it, and uses the geometric mean of the two
teams' scoring rates so the "close game" mode doesn't systematically
add or remove goals relative to an ordinary game of the same matchup.

## Calibration, verified against all three real seasons and both strength-assignment methods

| | OT rate | Home win% | Mean goals |
|---|---:|---:|---:|
| **Simulator, iid, post-fix** | **0.205** | 0.557 | 5.93 |
| **Simulator, conf-stratified, post-fix** | **0.213** | 0.560 | 5.84 |
| Real 2023-24 | 0.216 | 0.578 | 5.97 |
| Real 2024-25 | 0.223 | 0.532 | 5.69 |
| Real 2025-26 | 0.181 | 0.551 | 5.89 |

OT rate now lands squarely inside the real 3-season range for both
strength-assignment methods, on the first calibration attempt (`CLOSE_GAME_PROB=0.07`,
chosen from a back-of-envelope estimate: natural tie rate ~14.3%, need
roughly +6pp, solve `p + (1-p)*0.143 = 0.20` for `p ≈ 0.067`, rounded to
0.07 and verified directly rather than trusted analytically). Home win%
and mean goals -- both already separately calibrated -- are essentially
unchanged from their pre-fix values, confirming the fix is targeted and
doesn't disturb the other two statistics it wasn't meant to touch.

Win% std ticked up slightly for the iid method (0.169 vs. the pre-fix
0.179 -- actually slightly closer to real's 0.150-0.158) and stayed
close to its calibrated target for the conference-stratified method
(0.131 vs. the 0.128 established in `e5c`'s calibration) -- neither
constitutes a new problem.

## Important: this changes the core simulator retroactively

`simulate_season()` is called by every experiment in this workspace --
E1, S1 (`e2`/`e2b`), S2 (`e3`/`e3b`/`e3c`), S4 (`e4`/`e4b`), and all
three versions of S9 (`e5`/`e5b`/`e5c`). **None of those experiments'
exact numbers are reproducible against the current code anymore** -- the
OT/tie mechanism they were generated under has changed. This is stated
plainly rather than left ambiguous.

**Expected impact is real but likely small for most findings.** Only 7%
of games are affected, and within those, the OT winner is still decided
by the same near-coin-flip mechanism as before (`OT_STRENGTH_EXPONENT`
is unchanged) -- what changes is *which* games reach that mechanism, not
how it resolves once there. The qualitative conclusions most likely to
be robust to this: S1's/S4's "no unique NPI games-played bias" nulls
(more OT games spreads noise symmetrically, doesn't obviously favor one
model), and E1's model-ranking on truth recovery. **The one result most
worth re-verifying specifically is S9's final field-accuracy numbers
(`e5c`)**, since that comparison's magnitude was already shown to be
sensitive to seemingly-small calibration choices twice in this
workspace's history (the sigma miscalibration) -- a third calibration
change (this one) landing on the same experiment without a re-check
would be inconsistent with the standard applied to the first two.

## Shipped

- `research/npi_critique/harness/simulate.py`: `CLOSE_GAME_PROB`
  constant and the shared-score close-game mechanism in
  `simulate_season()`.
- `research/npi_critique/experiments/e8_ot_rate_calibration.py` --
  reproduces the calibration check above; rerun this whenever
  `simulate_season()` changes again.

## Re-verification: S9's field-accuracy result, re-run under the fix

Done immediately rather than left as an open item, given the standard
this workspace has held itself to after the two sigma corrections.
`e5c_selection_field_accuracy_recalibrated.py` re-run, same design,
under the OT-rate-corrected simulator (300 replications):

| Model | Pre-fix (`e5c`) | Post-fix (this report) |
|---|---:|---:|
| Massey | 12.70 | 12.61 |
| KRACH | 12.34 | 12.12 |
| NPI | 11.92 | 11.88 |
| RPI | 11.84 | 11.55 |

**The ordering is unchanged (Massey > KRACH > NPI > RPI), and KRACH
still significantly beats NPI** (12.12 vs. 11.88, paired t-test
p=0.0001 -- smaller than the pre-fix p<0.0001 but still solidly
significant). **One real change: NPI vs. RPI, a statistical tie in the
pre-fix `e5c` (p=0.135), is now a clear, significant NPI win**
(p<0.0001) -- RPI dropped further than any other model under the
OT-rate fix, restoring the direction from the original iid result
(where NPI also beat RPI). This is a genuine, if non-headline, update:
the OT-rate correction did not just add noise uniformly across models --
it affected RPI's field accuracy more than the others', which is
itself worth understanding rather than treating as expected. Not
investigated further here.

**Net conclusion, now double-checked against both known calibration
issues in this workspace:** KRACH beating NPI on selection-field
accuracy, once realistic conference structure exists, holds up across
three sigma calibrations and one OT-rate correction. This is now the
most heavily re-verified finding in the whole critique.

## Open items

1. ~~Re-run `e5c` under the OT-rate-corrected simulator~~ -- done above.
2. **E1, S1, S2, S4's numbers are now stale** relative to current code.
   Not re-run here for scope reasons; whether they need re-verification
   depends on how much any individual finding is trusted to generalize
   without an exact re-check, which this workspace's own history
   (S9's two corrections) suggests should not be assumed casually.
3. **The unexplained real tie-rate discrepancy from E6 remains open**
   and is a different question from OT rate -- OT rate measures how
   often a game *reaches* overtime; the real "tie" flag E6 found (6.9-8.5%,
   `Result==0.5`) is a separate, still-uninvestigated data question.
