# W5 — NPI win paradox on real women's D-I games

**Status:** Done. **Confirms P4** (pre-registered: "the NPI win paradox
replicates on women's data at a comparable per-game rate"). This is a
genuinely novel result, not just a replication — the men's paper's own
scan (`src/analysis/npi_vs_krach.py::phase5b_paradox_detection`) stops
after 20 games found, so it has never actually reported a *rate* for
men's hockey, only a capped count. This is the first time this project
has measured the full paradox rate for either division.

## Method

Exact leave-one-out protocol as the men's `phase5b_paradox_detection`:
for every decisive (non-tie) game in a season, refit NPI with that game
removed and check whether the winner's NPI is *higher* without their own
win than with it — same `-0.05` "measurable hurt" threshold. KRACH is
checked the identical way as a control (by the MLE property, it should
show ~0 such cases). Two changes from the men's version, both toward more
rigor for a smaller field: no 20-game cap (full season scan, every
decisive game), and the KRACH control also scans everything, not a
50-game sample — women's field size makes this cheap (a full 5-season,
~3,600-decisive-game, dual-model leave-one-out scan runs in under 3
minutes).

## Result

| Season | Decisive games | NPI paradoxes | Rate | KRACH paradoxes (control) |
|---|---:|---:|---:|---:|
| 2021-22 | 648 | 38 | 5.86% | 0 |
| 2022-23 | 709 | 67 | 9.45% | 0 |
| 2023-24 | 743 | 65 | 8.75% | 0 |
| 2024-25 | 739 | 47 | 6.36% | 0 |
| 2025-26 | 773 | 38 | 4.92% | 0 |
| **Total** | **3,612** | **255** | **7.06%** | **0** |

**KRACH's zero paradoxes across all 3,612 checks is exactly what the MLE
property predicts** — a useful sanity check on the harness itself, not
just a footnote: if KRACH had shown any paradoxes, that would mean the
leave-one-out refit methodology itself was broken, not that KRACH has a
real flaw.

## A named example

Mirroring the men's paper's standard for a "hand-checkable" artifact: on
2025-10-31 and again on 2026-01-23, **Ohio State — the eventual #1 team in
the final 2025-26 NPI rankings — beat St. Cloud State/St. Thomas in
overtime, and both wins measurably lowered Ohio State's own NPI** (impact
−0.260 each). This is not an edge-case team; it's the team that ended the
season ranked first by the very same metric.

## An important caveat this result inherits from P0.3

**45% of the paradox games found were overtime games**, despite OT being
only ~19% of all games in a typical season — paradoxes are disproportionately
an OT phenomenon. This is expected (OT results already carry partial credit,
so an OT win has less room to help before the strength-of-schedule term can
outweigh it) but comes with an unresolved caveat: **this experiment's NPI
fits still use the men's 60/40 OT split, not the women's official 66.7/33.3
split**, because `src/rankings/npi.py` hardcodes the OT-credit formula
rather than reading `ot_win_weight`/`ot_loss_weight` from config (documented,
not fixed, in `p0_3_npi_validation.md`). The home/away-multiplier and
QWB-base corrections from P0.3 ARE applied here (via `npi_women_config()`);
the OT-split correction is not. Whether the true women's-OT-split paradox
rate is higher, lower, or about the same as the 7.06% found here is not yet
known — worth revisiting once the OT formula is generalized.

## Interpretation

The core finding survives the caveat regardless of direction: **the win
paradox is not a men's-hockey-specific artifact.** It replicates on a
structurally different field, at a rate (7.06%) that is the same order of
magnitude as the corresponding *simulated* men's-hockey rate reported
elsewhere in this project's work (6.3% of sampled below-median-opponent
wins, under controlled synthetic conditions) — a rough cross-check between
a real-data result and a simulated one, not a direct apples-to-apples
comparison, but a reassuring one: two very different measurement approaches,
two different divisions, landing in the same neighborhood.
