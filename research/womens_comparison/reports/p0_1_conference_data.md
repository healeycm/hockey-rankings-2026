# P0.1 — Women's D-I conference assignments

**Status:** Done. Unblocks W7, W9, W10, W12 (conference-stratified experiments)
and closes the corresponding item in `reports/womens_hockey_import.md`'s
Open Items, which had deliberately left this blank after an earlier
unverified guess about Penn State's conference turned out wrong.

## What changed

`data/teams/college_hockey_teams_women.csv`'s `Conference` column: 0/45
populated → 45/45 populated.

## Sourcing (verified, not inferred — per the explicit caution in
`reports/womens_hockey_import.md` that motivated leaving this blank in the
first place)

Every team's conference was cross-checked against **at least two
independent sources** before being written:

1. A web search synthesizing conference membership lists (AHA, ECAC, Hockey
   East, NEWHA, WCHA) for the 2025-26 season.
2. Wikipedia's dedicated ["NCAA Division I women's ice hockey conferences
   and teams"](https://en.wikipedia.org/wiki/NCAA_Division_I_women%27s_ice_hockey_conferences_and_teams)
   page, fetched directly — an independent listing that matched (1) exactly,
   team for team, conference for conference.
3. For the two specific facts that determined edge cases: RPI's ECAC
   membership was confirmed directly (RPI Engineers women's ice hockey is
   an ECAC member — not to be confused with the RPI *ranking model* this
   project also has), and Delaware's active-not-pending Atlantic Hockey
   America membership was confirmed via a news article reporting Delaware's
   actual 2025-26 season results (2-30 record, lost to Robert Morris in the
   AHA championship game) — i.e. verified from real, played games, not a
   "joining" announcement that might not have taken effect yet.

All three sources agreed on every one of the 45 teams. No team was assigned
from a single source, and no team was assigned by analogy to the men's
conference structure (deliberately — see below).

## Result

| Conference | Teams | Members |
|---|---:|---|
| ECAC | 12 | Brown, Clarkson, Colgate, Cornell, Dartmouth, Harvard, Princeton, Quinnipiac, RPI, St. Lawrence, Union, Yale |
| Hockey East | 10 | Boston College, Boston University, Connecticut, Holy Cross, Maine, Merrimack, New Hampshire, Northeastern, Providence, Vermont |
| Atlantic Hockey America | 7 | Delaware, Lindenwood, Mercyhurst, Penn State, RIT, Robert Morris, Syracuse |
| NEWHA | 8 | Assumption, Franklin Pierce, LIU, Post, Sacred Heart, Saint Anselm, St. Michael's, Stonehill |
| WCHA | 8 | Bemidji State, Minnesota, Minnesota Duluth, Minnesota State, Ohio State, St. Cloud State, St. Thomas, Wisconsin |

12 + 10 + 7 + 8 + 8 = 45. Every team in `college_hockey_teams_women.csv`
accounted for exactly once; no leftover, no duplicate.

Verified end-to-end through the real data pipeline, not just the CSV:
`load_rankings('KRACH', division='women')` (`webpage/utils/data_loader.py`)
now returns 45/45 non-null `Conference` values (was 0/45).

## Notable differences from the men's conference structure

This matters for W9/W10 (connectivity, manipulability) specifically, since
those experiments are sensitive to cross-conference structure:

- **Atlantic Hockey America ≠ men's "Atlantic Hockey."** The women's
  conference was formed by merging the men's Atlantic Hockey Association
  with the former women's-only College Hockey America (CHA) in 2024. Its
  women's membership (Delaware, Lindenwood, Mercyhurst, Penn State, RIT,
  Robert Morris, Syracuse) is **entirely different** from men's Atlantic
  Hockey's membership (Air Force, Army, Bentley, Canisius, Holy Cross,
  etc. — none of which field women's teams in this conference). Written to
  the CSV as `Atlantic Hockey America`, distinct from the men's
  `Atlantic Hockey` string in `college_hockey_teams.csv`, specifically so
  the two are never silently conflated by a shared-string join.
- **NEWHA and WCHA have no men's-side equivalent membership at all** —
  confirms the caution already flagged in `reports/womens_hockey_import.md`
  about NEWHA being "an NCAA-granted D-I-for-hockey-only conference (its
  members are otherwise D-II schools)."
- **ECAC and Hockey East share their brand name with men's conferences of
  the same name**, but not identical membership — e.g. women's Hockey East
  has Holy Cross and Merrimack; men's Hockey East also has UMass Lowell and
  UMass, which don't field women's D-I teams in this conference.

## What this does not yet do

- Does not backfill conference for any season before 2025-26 — if a team
  changed conferences within the 5-year backtest window (2021-22 through
  2025-26), this file records only its *current* conference, same
  limitation the men's `college_hockey_teams.csv` already has. Worth
  flagging for W9 specifically, since conference realignment is exactly
  what changes a schedule graph's connectivity over time. Atlantic Hockey
  America's 2024 formation is the one realignment event known to fall
  inside this window; not yet checked whether any of the 6 teams that were
  in the old CHA (Lindenwood, Mercyhurst, Penn State, RIT, Robert Morris,
  Syracuse) played earlier seasons under a different conference label that
  would need reconciling for a season-by-season stratified analysis.
