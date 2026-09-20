# W8 — Real bubble divergence on women's D-I hockey

**Status:** Done. **Tests P6** (pre-registered: "NPI-vs-KRACH/Massey
selection-field disagreement is higher for women's" — smaller field, more
dispersion, sharper bubble). **P6 is falsified**: the women's rate is
lower than men's, not higher.

## Method

Direct counterpart to the men's paper's E24
(`research/npi_critique/experiments/e24_real_bubble_divergence.py`), same
methodology and same documented simplification carried over unchanged:
each metric's own unconditional top-`FIELD_SIZE` (11 for women's, matching
the real 2025-26 field — 5 automatic qualifiers + 6 at-large), not a
reconstructed real bracket with actual conference-tournament results. This
answers "does the metric's own ranking disagree with another metric's own
ranking at the cutoff that matters," the same question E24 asks for men's.

All 5 complete women's seasons (2021-22 through 2025-26), 216 team-seasons
with a rank from all three models.

## Result

| Comparison | Disagreements | Rate |
|---|---:|---:|
| NPI vs. KRACH (top-11 membership) | 8 / 216 | 3.70% |
| NPI vs. Massey (top-11 membership) | 6 / 216 | 2.78% |
| NPI vs. (KRACH **or** Massey) — the men's paper's exact statistic | 8 / 216 | **3.70%** |

**The men's-hockey equivalent (`reports/npi_critique.md`, `npi_critique_draft.md`)
is 8.3% of team-seasons.** Women's is meaningfully lower, not higher —
**P6 is falsified**, and this is worth taking at face value rather than
explained away: a smaller, more talent-dispersed field with an already-
sharper competitive hierarchy does not automatically produce more bubble
disagreement between metrics. If anything, the opposite pattern shows up
here.

## Named examples

Every one of the 8 disagreement cases, not just the largest:

| Season | Team | NPI rank | KRACH rank | Massey rank | In NPI's field? | In KRACH's? |
|---|---|---:|---:|---:|---|---|
| 2021-22 | Connecticut | 11 | 13 | 13 | ✓ | ✗ |
| 2021-22 | Minnesota State | 19 | 10 | 11 | ✗ | ✓ |
| 2022-23 | St. Cloud State | 13 | 9 | 9 | ✗ | ✓ |
| 2022-23 | Vermont | 11 | 15 | 12 | ✓ | ✗ |
| 2024-25 | Boston University | 11 | 12 | 17 | ✓ | ✗ |
| 2024-25 | St. Cloud State | 15 | 8 | 11 | ✗ | ✓ |
| 2025-26 | Cornell | 11 | 12 | 10 | ✓ | ✗ |
| 2025-26 | Minnesota State | 17 | 10 | 12 | ✗ | ✓ |

**St. Cloud State appears twice**, in two different seasons (2022-23 and
2024-25), always on the same side of the discrepancy — NPI ranks them
outside the field (13th, 15th) while both KRACH and Massey put them
comfortably inside (9th/9th and 8th/11th). This is the closest women's
equivalent to the men's paper's Miami 2025-26 case study (NPI 32nd, KRACH
15th) — a specific, real, recurring, hand-checkable disagreement, not a
one-off.

**Minnesota State also appears twice** (2021-22, 2025-26), on the opposite
side: NPI ranks them well outside the field (19th, 17th) while KRACH and
(mostly) Massey rank them inside.

## Interpretation

This is a genuine divergence from the men's-hockey finding, not a
replication, and that is itself the more interesting result for a
comparison paper: the magnitude of NPI's structural disagreement with
KRACH/Massey is not a fixed property of the formula, it depends on the
field it's applied to. Two teams — St. Cloud State and Minnesota State —
account for half of every disagreement found across 5 full seasons,
suggesting whatever drives this divergence is concentrated in a handful of
teams with an unusual profile (worth a follow-up: both are WCHA teams;
whether that's coincidence or a real conference-strength effect on NPI's
SOS term specifically is an open question this experiment doesn't answer).
