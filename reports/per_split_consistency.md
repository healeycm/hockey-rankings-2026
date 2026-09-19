# Does Massey's Dominance Hold Across All Splits?

## Summary

**No — pooled significance was hiding real per-split and per-season
structure.** The headline pooled paired tests (`p<1e-30` vs. KRACH, etc.)
are still valid statements about the *average* effect, but "beats X with
p<0.05" does not mean "beats X on every split." Breaking down the same
already-collected backtest data by season and cutoff surfaces two distinct,
worth-knowing patterns: an early-season instability effect (expected) and a
genuine season-level exception (not obviously expected, not fully
explained).

Method: no new model fits — this reuses per-split results already saved
across this session's backtest CSVs (`data/validation/backtest_results/`),
joined on `(Season, Cutoff)`.

## Results by comparison (20 splits each)

| Comparison | Accuracy wins | Brier wins | LogLoss wins |
|---|---|---|---|
| Massey vs. KRACH | 13/20 | **20/20** | **20/20** |
| Massey vs. NPI | 18/20 | 17/20 | **20/20** |
| Massey vs. ELO | 15/20 | 16/20 | 16/20 |
| Massey vs. HockeyBT | 13/20 | 15/20 | 15/20 |
| Massey vs. DixonColes | 12/20 | 10/20 | 8/20 |

## Pattern 1: vs. KRACH, dominance really is unanimous

Brier and LogLoss favor Massey in **every single split**, not just on
average. This is the one comparison in this table where the pooled p-value
and the per-split picture tell the same story without qualification.

## Pattern 2: vs. ELO, reversals cluster in early-season cutoffs

All 4 Brier reversals are `Jan1`/`Jan15` splits from two specific seasons
(2022-23, 2025-26) — the thinnest-training-data cutoffs in the backtest
design. This is the expected, previously-flagged failure mode (small
training sets destabilize fitted calibration parameters) rather than a
surprise, and doesn't undercut the pooled result — it explains where the
weaker part of the p=0.02 margin (vs. ELO's Brier) actually comes from.

## Pattern 3: vs. HockeyBT, a genuine season-level exception

The 5 Brier reversals are **the entire 2023-24 season (all 4 cutoffs)** plus
one 2024-25 split. This is not early-season noise — it's a full season
where HockeyBT's calibration beat Massey's regardless of how much of the
season had been played. Checked basic season-level stats (OT rate, tie
rate, mean margin, blowout rate) looking for an explanation:

| Season | OT% | Tie% | Mean \|margin\| | % 1-goal games | % blowouts (≥4) |
|---|---|---|---|---|---|
| 2021-22 | 18.6% | 6.4% | 2.32 | 41.1% | 21.1% |
| 2022-23 | 20.5% | 7.5% | 2.32 | 39.0% | 21.2% |
| **2023-24** | **21.5%** | **8.5%** | 2.31 | 39.8% | 21.0% |
| 2024-25 | 22.1% | 8.2% | 2.20 | 42.1% | 17.4% |
| 2025-26 | 18.1% | 6.9% | 2.38 | 35.7% | 21.9% |

2023-24 has the highest tie rate and OT rate of the five seasons, but not
dramatically so (8.5% vs. 2024-25's 8.2% or 2022-23's 7.5%) — not a clean,
large enough outlier to obviously explain a whole-season reversal on its
own. **No confident explanation found at this level of analysis.** Plausible
candidates not checked here: a specific set of upset results that season,
a particular team or cluster of teams whose games are disproportionately
influential, or simply that season-to-season noise at this sample size
(~1,170 games) is larger than intuition suggests. Flagged as an open item
rather than force-fit an explanation.

## Pattern 4: vs. DixonColes, the "tie" holds at the split level too

10/20 and 8/20 — genuinely mixed, consistent with the pooled paired test's
"no significant difference" finding. This is reassuring: the tie isn't an
artifact of aggregation either.

## What this changes

- **The recommendation to use Massey as the primary model stands** — its
  advantage over KRACH is unanimous, and its advantage over ELO/HockeyBT,
  while not unanimous, still holds in a clear majority of splits with the
  reversals traceable to identifiable causes (thin training data) in one
  case.
- **The 2023-24 HockeyBT exception is worth keeping in mind for anything
  season-specific** — e.g., if this system is ever used to generate a
  single season's live rankings rather than an aggregate backtest,
  consulting more than one model (see the ensembling work) has a concrete
  justification here, not just a generic "more models are safer" instinct.
- **Pooled p-values in this project's other reports remain valid** as
  statements about average performance — this doesn't retract any of them,
  it adds the per-split context that should accompany "beats X" claims
  going forward.

## Recommendation for future backtest reports

Report per-split win-rate alongside pooled p-values as a matter of course,
not just when specifically asked — this analysis was cheap (no new model
fits, pure re-analysis of existing CSVs) and surfaced a real, actionable
finding on the first pass.
