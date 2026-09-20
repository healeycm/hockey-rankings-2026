# P0.3 — Validating our women's NPI against the NCAA's own published formula

**Status:** Done, with a real bug found and fixed. This was the highest-risk
prerequisite ("every NPI experiment below is worthless if this doesn't
pass" — PLAN.md) and it did not pass on the first check.

## What was checked, and how

Following the same protocol as `reports/npi_investigation_2026.md` (the
men's-hockey NPI validation): compare our implementation's *formula
parameters* against the NCAA's own official published values, not just
spot-check output numbers. Unlike the men's case (where the bug was a data-
leakage/date-cutoff issue), this check went one level up — the dials
themselves — because there is no reason to assume the NCAA sets identical
dials for two different sport committees, and it turns out they don't.

**Source: NCAA's own official document**, `NCWIH_PairWiseExplained.pdf`
(National Collegiate Women's Ice Hockey Committee), fetched directly and
read as a PDF, not summarized from a secondary source. Cross-checked
against two independent web sources (a general search and a direct fetch of
a USCHO Fan Forum thread discussing committee meeting notes) before
treating any number as reliable — both agreed with the primary document on
every point below.

Direct quote: *"National Collegiate Women's Ice Hockey currently uses an
NPI based on 25% win percentage and 75% strength of schedule, with a
Quality Win Bonus base of 51.5 and a multiplier of 0.5. Three-on-three
overtime wins are credited as 2/3 of win and 1/3 of a loss... Game sites
are not currently weighted, i.e no distinction is made between home/away
victories or losses."*

## What we found: `src/rankings/npi.py`'s defaults were the MEN'S dials, applied to everyone

| Parameter | Our code's default (`config.yaml`'s `npi:` block) | Official men's D-I | Official women's D-I |
|---|---|---:|---:|
| Win% / SOS split | 25/75 | 25/75 ✓ | 25/75 ✓ (no bug here) |
| Home/away multiplier | 0.8 / 1.2 | 0.8/1.2 (confirmed via web search — not independently re-verified against a primary document in this pass) | **none — 1.0/1.0** |
| QWB base | 51.0 | 51.0 ✓ | **51.5** |
| QWB multiplier | 0.5 | 0.5 ✓ | 0.5 ✓ (no bug here) |
| OT win/loss split | 60% / 40% (hardcoded in the formula, not config-driven — see below) | 60/40 ✓ | **66.7% / 33.3%** |

Every existing women's NPI rating this project has ever computed —
including the numbers backfilled and published to the live public site
earlier today (2026-09-20, before this check ran) — used the men's dials.
**The missing home/away multiplier is the structurally larger issue**: it
isn't a constant off by half a point, it's an entire scoring dimension
(location) that shouldn't exist in the women's formula at all but was
being applied to every single game.

## Fix applied

1. `config.yaml`: added a new `npi_women` config block alongside the
   existing `npi` block, with `home_multiplier: 1.0, away_multiplier: 1.0,
   quality_win_base: 51.5` (the two verified corrections) and
   `ot_win_weight: 0.667, ot_loss_weight: 0.333` (recorded correctly, but
   see the caveat below — not yet wired to anything).
2. `src/run_system.py`: for `division == 'women'`, swaps `npi_women`'s
   config into `config['models']['npi']` (the exact key
   `registry.py`'s division-agnostic `get_model_config()` already reads)
   via a shallow copy, so this division's run picks it up automatically
   and a men's run in the same process is never affected. No change to
   `registry.py` or `npi.py` itself — the dials were already
   configurable, they just weren't being configured per division.

## Result: how much did this actually change?

Regenerated women's NPI (2025-26 season) with both the old (wrong,
men's-dial) and corrected config for a direct comparison:

- **Max rank movement: 5 places** (Vermont: 27th → 22nd).
- **1 of 45 teams** moved 3+ places.
- **Top 4 unchanged** (Ohio State, Wisconsin, Penn State, Northeastern).
- Spearman rank correlation between old and corrected rankings: **0.996** —
  the bug was real and now fixed, but its practical impact on this
  particular season's ordering was modest, not dramatic. It would be a
  mistake to read "modest impact this season" as "modest impact always" —
  a 5-place move landing on a bubble team in a tighter year is exactly the
  kind of thing that matters for an 11-team field with 6 at-large spots
  (PLAN.md's W7/W8).

Full before/after table available by re-running the comparison (not
checked into `results/` in this pass — see Open Items).

## What this does NOT yet fix

- **The OT split (60/40 vs. 66.7/33.3) is recorded but not applied.**
  `src/rankings/npi.py` hardcodes the OT-credit formula directly
  (`pts = 0.4 * win_mult + 0.2`, derived specifically to produce a 60/40
  split when `win_mult=1`) rather than reading `ot_win_weight`/
  `ot_loss_weight` from config — those keys are dead config for BOTH
  divisions, not a women's-specific gap. Generalizing that formula to
  accept an arbitrary split requires understanding exactly how the
  0.4/0.2 decomposition was derived (it is not simply "60% of a win"; see
  the surrounding comments in `npi.py`), which this pass deliberately did
  not rush. OT games are ~19% of a typical season, so this is a real,
  not-yet-quantified residual gap — smaller in scope than the home/away
  fix (which touched every game, not just OT ones) but not zero.
- **The men's home/away multiplier (0.8/1.2) was not independently
  re-verified against a primary NCAA document in this pass** — it was
  already validated in `reports/npi_investigation_2026.md`'s original
  work, and this pass's web search corroborated it, but no primary-source
  PDF was fetched for men's specifically the way one was for women's.
  Lower priority since it's the value that was already shipping correctly.
- **This fix has been verified in an isolated worktree, not yet applied to
  the actual production `output/` tree that feeds the public site.** The
  incorrect women's NPI numbers backfilled and published earlier today are
  still live until this fix is separately applied there and republished —
  intentionally treated as a distinct, explicit step (see the parent
  conversation) rather than silently folded into this research branch.
- Does not re-validate the full `reports/npi_investigation_2026.md`
  date-cutoff/SOS-filter bugs specifically against women's data — that
  investigation was about a *pipeline* bug (leakage across a season), not
  a *formula-parameter* bug, and is a separate, not-yet-done check.
