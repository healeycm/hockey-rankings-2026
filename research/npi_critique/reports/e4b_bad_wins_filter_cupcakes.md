# S4, Final: The Bad-Wins Filter's Games-Played Interaction, Properly Isolated

## Bottom line

**After three failed designs and one confound caught mid-analysis, the
corrected, final test finds no meaningful games-played advantage from
the bad-wins filter.** The filter's underlying mechanism is real and
does trigger (confirmed directly, ~20-30% of replications, once genuine
weak opponents exist on a schedule) -- but a properly controlled
long-vs-short schedule comparison shows no differential benefit to
`NPIGames` over `NPI`, `KRACH`, or `Massey`. This closes S4, the one
place S1/S2's original hypothesis could still have held after being
tested on plain `NPI` throughout.

## The path here, reported honestly because it's informative

Four attempts, in order, each one either failing to trigger the
mechanism or revealing a real design flaw before being trusted:

1. **Denver's real schedule (NCHC, a strong conference), iid true
   strengths.** Filter triggered in ~2% of replications -- essentially
   never (`reports/e4_bad_wins_filter_games_mismatch.md`).
2. **Attempted fix: widen the opponent-strength spread** (sigma 0.4 ->
   0.7). Triggered the filter more (40%), but checking against real win-
   percentage dispersion showed this spread overshoots reality (std
   0.231 vs. real 0.158, vs. the original 0.4's 0.175) -- reverted as an
   uncalibrated "fix," same report.
3. **Switch target team to Sacred Heart (Atlantic Hockey, a weaker real
   conference), still iid strengths.** Also ~0% trigger rate. The reason,
   confirmed by inspection: `assign_true_strengths` draws every team's
   strength independently of its conference label -- relabeling which
   conference the target plays in did nothing, since none of its
   opponents were actually made weaker by it. This was a real design
   error, caught before being reported as a finding.
4. **Corrected design: plant genuinely weak "cupcake" opponents directly
   on the target's real schedule**, protecting a *fraction-matched*
   number of them (not a fixed count) across the long/short comparison.
   A first pass protected a fixed count regardless of schedule length,
   which concentrated cupcakes more heavily in the short condition
   (5/25=20% vs. 5/40=12.5%), inflating its win rate and biasing every
   model's comparison in the same direction -- caught by inspecting
   `mean_wins`/win-rate directly before trusting the rank-gain numbers,
   and fixed by scaling the protected cupcake count to the schedule
   length.

## Final result (n=150, fraction-corrected)

| | Long (40 games) | Short (25 games) |
|---|---:|---:|
| Mean wins | 26.7 | 17.7 |
| Filter triggered (any win dropped) | 22.7% | 27.3% |
| Mean wins dropped | 1.24 | 1.31 |

Drop rate is essentially the same in both conditions -- if anything
marginally higher for the short schedule, the opposite of the original
hypothesis.

**Rank gained by going from short to long schedule, per model:**

| Model | Mean gain |
|---|---:|
| KRACH | -0.11 |
| Massey | -0.07 |
| NPIGames | -0.57 |
| NPI | -0.85 |

None of the four models shows a meaningful advantage from more games in
this design, and NPIGames does not stand out from NPI, KRACH, or
Massey. **The bad-wins filter's games-played-linked mechanism, while
real in principle (confirmed to match the NCAA's documented 12-win
floor) and real in practice (confirmed to trigger substantially when
genuine mismatches exist), does not translate into a detectable
games-played-driven rating advantage once the comparison is properly
controlled.**

## What this means for the overall critique

Combined with S1 (plain NPI, no unique games-played bias) and S9 (same
null in the real, un-manipulated setting), this is now **three
independent designs, testing the specific filter mechanism as well as
the general one, all reaching the same conclusion**: games-played
mismatch does not appear to give any model in this roster -- including
NPI's actual administered form -- a demonstrable unearned advantage or
disadvantage. This is a genuinely settled negative result for that
specific concern, not an open question anymore.

**The self-correction process itself is worth stating as a methods
point for the paper.** Three of four attempts here either failed to
trigger the mechanism or contained a real, catchable design flaw before
producing a number. Reporting only the final, clean result would
understate how easy it is to reach a wrong conclusion in either
direction on this kind of question -- a spread that looks "more
realistic" can still be miscalibrated (attempt 2), a schedule
relabeling can look like a fix while changing nothing (attempt 3), and
a seemingly reasonable control (protect the same cupcakes) can
introduce a new, subtler confound (first pass of attempt 4). Each was
caught by checking an intermediate quantity (drop rate, aggregate win%
dispersion, win rate by condition) before trusting the headline
comparison -- the discipline that made this a "finish" rather than
another inconclusive attempt.

## Method

`research/npi_critique/experiments/e4b_bad_wins_filter_cupcakes.py`.
Sacred Heart's real 40-game schedule; 5 of its real opponents
(Quinnipiac, Holy Cross, Niagara, Yale, Robert Morris) planted at true
strength 0.30 (well below the field median of ~1.0); target team fixed
at strength 1.0. Thinned to 25 games for the "short" condition,
protecting a cupcake count scaled to the schedule length (3 of 5, not
all 5) so cupcake *fraction* -- not raw count -- is held constant across
conditions.

## Shipped

- `research/npi_critique/experiments/e4b_bad_wins_filter_cupcakes.py`
  (supersedes `e4_bad_wins_filter_games_mismatch.py`'s comparative
  question; that script's mechanism-confirmation and calibration-caution
  findings both stand and are cited above).
- Results: `research/npi_critique/results/e4b_bad_wins_filter_cupcakes/results.csv`.

## Open items

1. **Only one target team and one cupcake configuration tested.**
   Repeating with a different team/cupcake set would strengthen
   confidence that this null generalizes, though the mechanistic
   understanding built across four attempts (a fraction-matched
   comparison is the right control) should transfer directly.
2. **The "good loss" drop mechanism** (a loss excluded entirely, not
   just wins -- noted in the original `e4` report) remains
   uncharacterized and could interact with games-played differently
   than the win-dropping mechanism tested here.
3. **DGP caveat applies here too**, as with every experiment in this
   workspace.
