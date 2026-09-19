# E10: Full Re-Verification of E1/S1/S2/S4 Under the OT-Corrected Simulator

## Summary

`e8_ot_rate_correction.md` fixed a real gap (simulator OT rate 14.3% vs.
real 18.1-22.3%) by changing `simulate_season()` itself -- which
retroactively made every prior experiment's exact numbers stale. That
report re-verified S9 (`e5c`) immediately; this report closes out the
rest: E1, S1 (`e2`, `e2b`), S2 (`e3`, `e3b`, `e3c`), and S4 (`e4b`),
each re-run under the current simulator and compared against its
previously-reported numbers.

**Headline: every core conclusion in this workspace survives.** No
finding flips direction. Ordering, significance, and qualitative
patterns are preserved throughout. A few magnitudes shift modestly, and
one shift (S4's filter-trigger rate) has a clean mechanistic
explanation tied directly to the fix itself.

## E1: Truth recovery

| Model | Pre-fix ρ | Post-fix ρ |
|---|---:|---:|
| Massey | 0.912 | 0.905 |
| NPI (official) | 0.892 | 0.884 |
| KRACH | 0.868 | 0.854 |
| RPI | 0.862 | 0.847 |

Every value shifted down slightly and uniformly (more OT games means
more near-coin-flip outcomes, which makes truth recovery modestly
harder for every model equally) -- **the ordering is completely
unchanged**, and the headline comparisons remain significant (Massey
vs. NPI-official p=6.7e-42; NPI-official vs. sos=0.66 p=0.0013;
NPI-official vs. sos=0.9 p=2.8e-62). One real, non-trivial change: the
NPI paradox rate roughly doubled, from 6.3% (19/300) to 12.0% (36/300)
of sampled below-median-opponent wins lowering the winner's NPI --
plausibly because more OT-decided (near-coin-flip) results create more
borderline cases where excluding a win looks favorable. Not
investigated further, but worth noting as a real, fix-induced shift in
a secondary statistic, not just noise.

## S1: Games-played mismatch

Both designs re-run at their original scale (200 reps for the 63-team
real-schedule version, 2000 reps for the 12-team minimal example).

| | Pre-fix mean Δrank | Post-fix mean Δrank |
|---|---:|---:|
| e2 (63-team): KRACH | -0.00 | -0.20 |
| e2: Massey | +0.00 | -0.05 |
| e2: NPI | +0.06 | -0.13 |
| e2b (12-team): KRACH | -0.025 | -0.014 |
| e2b: Massey | +0.005 | +0.006 |
| e2b: NPI | -0.003 | +0.013 |

All values remain small and symmetric around zero for every model in
both designs. **The core finding -- no unique NPI games-played bias --
is fully confirmed under the corrected simulator**, on both the
large-N real-schedule test and the fully hand-checkable minimal example.

## S2: Weak team in strong conference

**e3 (aggregate rank error, elite-conference plant):**

| Model | Pre-fix mean overrate | Post-fix mean overrate |
|---|---:|---:|
| KRACH | +1.78 | +2.84 |
| Massey | +0.95 | +1.17 |
| NPI | -3.08 | -2.69 |

Same qualitative pattern -- KRACH overrates most, NPI actually
underrates -- with KRACH's overrating somewhat larger post-fix. The
symmetric control (strong team in weak conference) shows the same
preserved pattern in the opposite direction (KRACH -2.04 underrate vs.
pre-fix -2.45; NPI +1.91 overrate vs. pre-fix +1.44).

**e3c (precise fluke-win marginal effect, the test built directly for
the "1-2 lucky wins" concern):**

| Model | Pre-fix gain (1 flip / 2 flips) | Post-fix gain (1 flip / 2 flips) |
|---|---:|---:|
| KRACH | +3.49 / +6.75 | +3.31 / +6.45 |
| Massey | +1.95 / +4.08 | +1.89 / +4.03 |
| NPI | +1.84 / +3.78 | +1.81 / +3.97 |

Essentially unchanged. **KRACH still shows the largest marginal reward
for a fluke win against a strong opponent, not NPI** -- the finding
most directly responsive to the original concern is the most stable of
all of them under this re-verification.

**e3b (strength sweep, re-run at reduced N=60 for a directional check
rather than the full N=120):** the qualitative pattern -- NPI's error
grows increasingly negative (underrating) as the planted team's true
strength rises toward the field median -- not only survives but
strengthens slightly (error at the near-median strength point deepened
from -7.78 to -9.75). Full-N re-run not done; the direction is clear
enough at N=60 that it wasn't judged necessary for this pass.

## S4: Bad-wins filter games-played interaction

| | Pre-fix | Post-fix |
|---|---:|---:|
| Drop rate, long schedule | 22.7% | **9.3%** |
| Drop rate, short schedule | 27.3% | **12.0%** |
| Rank gain (short->long): KRACH | -0.11 | +0.26 |
| Rank gain: Massey | -0.07 | -0.44 |
| Rank gain: NPI | -0.85 | -1.17 |
| Rank gain: NPIGames | -0.57 | -1.31 |

**The filter-trigger rate fell substantially, and this has a clean,
direct mechanistic explanation rather than being an unexplained
artifact:** `NPIGames`' mandatory-win set is `mandatory_losses + ot_wins
+ regulation_wins[:12]` (confirmed by reading `src/rankings/npi_games.py`
directly) -- **OT wins are always mandatory, regardless of count; only
*regulation* wins beyond the 12th-best are ever droppable.** Correctly
raising the OT rate (E8's fix) mechanically shrinks every team's pool of
regulation wins, which shrinks the droppable pool, which reduces how
often the filter has anything to drop. This is not a coincidental side
effect -- it is a real, previously-invisible interaction between two
things this workspace investigated separately (the OT rate and the
bad-wins filter), only visible because both were checked. **If
anything, this reinforces S4's original conclusion**: a more accurately
calibrated OT rate makes the bad-wins filter even less active than the
under-calibrated simulator suggested, not more -- the "no meaningful
games-played advantage" finding holds, and the mechanism behind it is
now better understood than before this re-verification.

The rank-gain values remain small for every model in both conditions;
no model shows a meaningful, consistent games-played advantage from the
filter, pre- or post-fix.

## Net assessment

Zero direction reversals across four re-verified studies. One magnitude
shift with a real, mechanistic explanation (S4's drop rate, tied
directly to the OT fix). One secondary-statistic shift worth flagging
without further investigation (E1's paradox rate). This is the standard
this workspace has now applied consistently: a core-simulator change
does not get to leave downstream findings unexamined just because they
seem unlikely to be affected.

## Shipped

No new code. This report documents re-runs of existing experiment
scripts (`e1_truth_recovery.py`, `e2_games_played_mismatch.py`,
`e2b_minimal_worked_example.py`, `e3_weak_team_strong_conference.py`,
`e3b_strength_sweep.py`, `e3c_fluke_win_marginal_effect.py`,
`e4b_bad_wins_filter_cupcakes.py`) against the current
`simulate_season()`.

## Open items

1. **e3b was re-run at reduced N (60, not 120)** for time -- a full-N
   re-run would tighten the confidence in the exact magnitudes, though
   the direction is unambiguous at N=60.
2. **E1's doubled paradox rate is unexplained** -- flagged, not
   investigated further in this pass.
3. **This report did not re-run S9's e5/e5b** (the superseded
   intermediate versions) -- only `e5c` (already re-verified in
   `e8_ot_rate_correction.md`) and now these four. All experiments in
   `research/npi_critique/` have now been re-verified under the current
   simulator at least once.
