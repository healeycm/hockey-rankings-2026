# W6 — NPI dial sensitivity on women's D-I hockey

**Status:** Done. **Tests P5** (pre-registered: "NPI's optimal dials differ
materially between divisions"). Result is nuanced: the *committee-chosen*
dials genuinely differ (already established in P0.3), and the *sensitivity
structure* around them is qualitatively similar in shape but not identical
in magnitude between divisions — closer to a partial confirmation than a
clean yes/no.

## An unplanned discovery this experiment surfaced

Building this exposed a real, previously-undocumented bug: **`weight_wp`/
`weight_sos` in `NPI`'s config are dead config**, exactly like the
`ot_win_weight`/`ot_loss_weight` dead config P0.3 already found.
`src/rankings/npi.py`'s fit loop hardcodes the 0.25/0.75 split and never
reads `self.conf['weight_wp']` at all — confirmed by direct test (fitting
the same season at `weight_wp=0.15` and `weight_wp=0.35` produced
byte-identical ratings) and by `grep`, which shows the key only in the
constructor's default dict, nowhere in `fit()`. The men's-hockey critique's
own weight sweep (`reports/npi_critique.md`'s "2a. SOS Weight Sweep")
never actually hits this bug, because it doesn't refit with a new
`weight_wp` — it uses `reweight_npi()`
(`src/analysis/npi_vs_krach.py`), which recombines an already-converged
fit's `adj_wp`/`sos`/`qwb` components post-hoc. That function is reused
here directly rather than reimplemented (production code, read-only
import). **NPI now has THREE dead-config dials, not one**: `weight_wp`/
`weight_sos`, and `ot_win_weight`/`ot_loss_weight` — only
`home_multiplier`/`away_multiplier` and `quality_win_base`/
`quality_win_mult` are genuinely wired up. Worth a `config.yaml` comment
update and, eventually, a real fix; not done in this pass, flagged here so
it isn't lost.

## Method

- **weight_wp sweep** (0.10–0.50, `weight_sos = 1 − weight_wp`): via
  `reweight_npi()`, the statistically valid approach, identical mechanism
  to the men's-hockey sweep. Kendall's τ vs. the official (25/75) ranking,
  plus count of teams shifted >3 ranks, per season, averaged across all 5
  women's seasons.
- **QWB base sweep** (49.0–53.0, multiplier held fixed at the official
  0.5): genuine refit, since this dial IS wired up (confirmed in P0.3 and
  by the non-degenerate results below). **Not directly comparable to the
  men's-hockey QWB table**, which takes the max across multiplier 0.3–0.7
  at each base value — mine holds multiplier fixed, so it isolates the
  base-value effect alone rather than the base×multiplier joint effect.

## Result: weight_wp sweep (mean across 5 seasons, ~44 teams/season)

| WP% | SOS% | τ vs. official | Teams shifted >3 | Max rank change |
|---|---|---:|---:|---:|
| 10% | 90% | 0.741 | 19.4 | 16.6 |
| 15% | 85% | 0.845 | 12.0 | 10.0 |
| 20% | 80% | 0.935 | 2.6 | 5.8 |
| **25%** | **75%** | **1.000 (official)** | **0.0** | **0.0** |
| 30% | 70% | 0.952 | 1.6 | 5.0 |
| 35% | 65% | 0.921 | 4.6 | 6.6 |
| 40% | 60% | 0.897 | 6.8 | 7.8 |
| 45% | 55% | 0.870 | 9.2 | 9.6 |
| 50% | 50% | 0.854 | 11.0 | 10.2 |

Men's-hockey equivalent (`reports/npi_critique.md`, same 25/75 official
baseline, ~63-team field, single season):

| WP% | τ vs. official | Teams shifted >3 |
|---|---:|---:|
| 10% | 0.688 | 39 |
| 25% | 1.000 (official) | 0 |
| 50% | 0.877 | 22 |

**The shape is the same — a monotonic instability that grows the further
the dial moves from 25/75 in either direction — and this replicates
cleanly.** The *magnitude*, normalized for field size, is somewhat smaller
for women's: at the 10% extreme, 19.4/44 ≈ 44% of the women's field shifts
>3 ranks vs. 39/63 ≈ 62% of the men's field; at the 50% extreme, 11.0/44 ≈
25% vs. 22/63 ≈ 35%. Women's NPI rankings are directionally *more* stable
under a WP/SOS reweighting than men's, not less — the opposite direction
from P6's already-falsified prediction (W8) that women's would be more
fragile, and consistent with it.

## Result: QWB base sweep (mean across 5 seasons)

| QWB base | τ vs. official (51.5) | Teams shifted >3 |
|---|---:|---:|
| 49.0 | 0.952 | 1.4 |
| 50.0 | 0.973 | 0.4 |
| 51.0 | 0.991 | 0.2 |
| **51.5** | **1.000 (official)** | **0.0** |
| 52.0 | 0.993 | 0.0 |
| 53.0 | 0.984 | 0.2 |

Small, smooth, and roughly symmetric around the official 51.5 base — no
sign of the sharp "cliff" the men's-hockey QWB sweep found around its own
official value (19 teams shifted at the official base, collapsing to 2 one
half-point away — the men's paper's documented "QWB kink"). **This
specific comparison isn't apples-to-apples** (the men's table varies
multiplier jointly with base; this one holds multiplier fixed at 0.5), so
it does not by itself establish that the kink is men's-specific — a proper
joint sweep (varying multiplier 0.3–0.7 at each base, matching the men's
methodology exactly) is the natural next step, not done in this pass.

## Interpretation

P5 is a partial confirmation: the committee-chosen dials genuinely differ
(P0.3), and this experiment adds that the *sensitivity magnitude* around
those dials also differs somewhat (women's modestly more stable under a
WP/SOS reweighting) — but the qualitative *shape* of the instability (a
smooth, monotonic degradation moving away from 25/75) replicates cleanly.
Combined with the unplanned dead-config discovery, this experiment's
biggest contribution may end up being methodological rather than
substantive: it identifies exactly which of NPI's "7+ tunable parameters"
(per `npi_critique_draft.md`'s framing) are actually tunable in this
project's implementation, which the existing men's-hockey critique never
had reason to check since its own sweep already used the correct
(`reweight_npi`) workaround without ever diagnosing why it was necessary.
