# E9: The Tie-Rate "Discrepancy" Was Not a Bug — And I Misquoted the Project's Own Prior Finding

## Conclusion first

The nonzero real tie rate flagged as an open, unexplained question in
`reports/e6_assumption_audit.md` (6.9-8.5% of games across the last
three seasons show `Result==0.5`) is **not a data pipeline bug**. These
are genuine, correctly-recorded ties. Verified by cross-checking against
College Hockey News -- a second, independently-scraped data source --
using exact date-and-team matching: **0 mismatches across 32
cross-checkable games.** Every one both sources agree ended in a tie.

**No code change was needed or made.** This report documents a
diagnostic process that reversed its own initial hypothesis, not a fix.

## The investigation, including where I went wrong twice

**First hypothesis (wrong): a scraper timing/logic bug.** 79 of 1143
games in 2025-26 (and the same ~37-39%-of-OT-games pattern in
2023-24/2024-25) show `IsOT=True` with `HomeGoals==AwayGoals` -- a
recorded tie despite going to overtime. Checked the raw scrape
(`data/raw/games_2025_2026.csv`): the tie is already present there,
`Is_Final=True`, ruling out a processing-stage bug. Checked the scraper
code (`src/data/scraper.py`): it reads USCHO's composite-schedule table
literally, with no separate field indicating an OT/shootout *winner* --
only a type tag (`OT_Info`). This looked consistent with "USCHO's own
page doesn't reflect the shootout goal for some games" and I reported it
as a likely, if unconfirmed, production data-integrity bug.

**First cross-check (produced a false alarm of its own): fuzzy
team-name matching against CHN data.** An initial spot-check against
`data/raw_advanced/chn_games_2025_2026.csv` using loose substring
matching on team names found 8 of 20 "mismatches" -- CHN apparently
showing decisive scores for the same games. This looked like it
confirmed the bug. **It didn't hold up**: inspecting one mismatch
(Minnesota vs. Boston College) directly showed the two teams played
*twice*, on consecutive days (Oct 9 and Oct 10) -- the loose match had
grabbed the wrong one of the two meetings. The correctly-dated game
(Oct 10, extracted from CHN's own `url` field, which encodes the date)
shows CHN **also** recording a 2-2 tie, agreeing with USCHO.

**Corrected cross-check: exact date + team-name-mapped matching**,
using the project's own `team_info.csv` USCHO-to-CHN name mapping and
dates parsed from CHN's `url` field (avoiding both the team-naming and
the multiple-meetings problems that broke the first attempt): of 79
USCHO-recorded tied-OT games, 32 were found in CHN's data (coverage is
partial, consistent with this project's previously-documented CHN
coverage gaps), and **all 32 agree it was a tie. Zero mismatches.**

## My own error: mischaracterizing this project's prior finding

E6's report stated: *"This project's own prior reports
(`reports/hockey_bt_results.md`) describe modern-rules ties as
essentially eliminated by shootouts, with any residual tie flag confined
to specific historical rule eras."* **This is not what that report
says.** The actual text: *"ties (`Result==0.5`) are not a data artifact
-- some eras permitted a standings tie after non-shootout OT, and 99.3%
of all ties occur in OT/SO games specifically."* That is already the
correct characterization -- ties are real, not an artifact, and
concentrated in OT/SO games -- and I misquoted it as claiming the
opposite (that modern rules eliminate them), which is what sent this
investigation looking for a bug that didn't exist. The project's own
prior work had already gotten this right; my audit introduced the
error, not the codebase.

## Why NCAA hockey games can still end in a recorded tie

Not independently re-verified against NCAA rules text in this session,
but consistent with all the evidence gathered: NCAA Division I men's
hockey regular-season games use a single sudden-death overtime period,
and if unresolved, the *official* result recorded for a game (and used
for RPI/PairWise/NPI purposes) is a tie -- some conferences additionally
play a supplementary shootout purely to award a bonus standings point,
which does not change the official win-loss-tie record. This is
consistent with both data sources treating the same games as ties, and
with this project's existing `ot_win_weight`/`ot_loss_weight` dials
being reserved for genuinely decisive OT/SO games (the ~60-65% of OT
games that are NOT recorded as ties), separate from the ~35-40% that
are genuine ties.

## What this means for production

**Nothing is broken.** `NPI`, `KRACH`, and `RPI` all treat
`Result==0.5` as a genuine tie (split credit), and `Massey` treats the
zero goal margin as a genuine zero-margin result -- all correct
behavior for what is, in fact, a real tied outcome. No model needs a
fix. E6's flag is resolved as a non-issue, joining E7 (distribution
shape) as the second "investigated, found not to be a problem" item in
this audit chain -- a useful reminder that not every flagged
discrepancy is a bug, and that a second independent data source,
matched correctly, is worth more than a plausible-sounding first
hypothesis.

## Shipped

- No code changes.
- `reports/e6_assumption_audit.md`'s tie-rate open item should be read
  as resolved by this report.

## Open items

None. This closes the last open item from E6's original audit: spread
(fine as-is), distribution shape (resolved as non-issue, E7),
conference-effect calibration (corrected via the sigma recalibration
work), OT rate (fixed, E8), and tie rate (resolved as non-issue, this
report) are now all accounted for.
