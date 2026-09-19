# Roster / draft / returning-production: research plan

**Goal:** answer three questions using College Hockey News (CHN) as the source: (1) who was on each team's roster each season, (2) how many draft picks (and how highly drafted) did each team have, as a general portrayal of talent, and (3) how much of last season's production is returning this season. This feeds the preseason-prior work in `research/preseason/` (specifically its parked P5/P6 ideas) once real signal is demonstrated here, but this workspace is independent and doesn't depend on that one.

**Context / reversal:** `research/preseason/PLAN.md` §1a explicitly parked player-based signals on 2026-09-13 because CHN's *box-score* scraper (`src/data/advanced_metrics_scraper.py`) only pulls team-level per-game data, not rosters or player stats. That conclusion was too narrow — CHN's site has dedicated roster and player-stats pages that scraper never touched. The user asked to reopen this on 2026-09-15. Treat this as a deliberate reversal, not a contradiction to flag every time.

## 1. What CHN actually has (confirmed 2026-09-15, by hand before writing any scraper)

| Need | CHN page | URL pattern | Confirmed |
|---|---|---|---|
| Team ID mapping | Standings/reports page | `/reports/standings.php` (links contain each team's numeric CHN ID) | Yes — spot-checked 5 teams |
| Roster (name, class, position, height/weight, hometown, last team, **NHL draft**) | Team roster page | `/reports/roster/{TeamSlug}/{ID}` (current), `/reports/roster/{TeamSlug}/{ID}/{SeasonCode}` (past seasons, back to 1922-23) | Yes — Michigan 2026-27 and 2024-25 both checked |
| Player season stats (GP, G, A, Pts, Sh%, PIM, +/-, TOI/G for skaters; GP, W-L-T, GAA, SV% for goalies) | Team stats page | `/stats/team/{TeamSlug}/{ID}` (current), `/stats/team/{TeamSlug}/{ID}/overall,{SeasonCode}` (past seasons) | Yes — Michigan 2024-25 checked, real data confirmed |

**NHL Draft is a column directly on the roster page** (format `{Year}-{NHLTeam}-{Round}`, e.g. `2024-MTL-1`) — no separate draft-tracking source needed, which simplifies the "draft picks per team" question considerably: it's derivable from the same roster scrape as everything else, not a fourth data source.

**SeasonCode matches this project's own convention** (`20242025` = 2024-25), so joining against `data/processed/games_archive.csv` / `research/preseason/data/extended_archive.csv` needs no season-format translation.

## 2. Scope and what "returning production" actually means here

- **Roster identity across seasons**: a player is "returning" if their name appears on the same team's roster in season S and season S-1. Name-matching risk: CHN's roster name format (`Last, First`) should be internally consistent season-to-season on the same site, but transfers (player leaves team A, appears on team B) need to be handled as "not returning to team A" (correct) and separately as "new to team B" (not double-counted as A's departure being B's gain in the naive per-team sum).
- **Production**: each returning skater's PRIOR season's (G, A, Pts, GP) from the stats page; each returning goalie's PRIOR season's (GP, MIN, SV%) similarly. "Returning production share" for a team = sum of returning players' prior-season point production / team's total prior-season point production (the standard SP+-style metric).
- **Draft picks per team**: NOT "how many of a team's alumni have been drafted" (that's usually tracked elsewhere and is a lagging/reputational signal) — this plan means **how many *currently rostered* players were drafted**, and how highly (round matters — 1st-round picks are a stronger signal than 7th-round ones). This is a live, season-specific roster-talent signal, matching what SP+-style recruiting composites are trying to capture with a college-hockey-appropriate source (the draft, not a recruiting service ranking, which doesn't really exist for hockey the way it does for football/basketball).
- **NOT in scope yet**: translating drafted-but-not-yet-enrolled recruits' junior-league stats (an "NHLe"-style conversion) — that was PLAN.md (preseason)'s P6, still genuinely blocked without a junior-league stats source. This exploration only uses players who actually appear on a CHN roster, i.e. currently enrolled players. A drafted player who hasn't arrived yet contributes nothing until they show up on a roster.

## 3. Phases

### R0: Team ID map + scraping harness
- `experiments/build_team_id_map.py`: scrape `/reports/standings.php`, extract every team's CHN slug + numeric ID, save to `research/roster_talent/data/team_id_map.csv`. Cross-check against `data/teams/team_info.csv`'s `CHN_Name` column (read-only) to catch naming mismatches early.
- `harness/scrape.py`: shared polite-fetch helper (User-Agent, delay between requests, retry-once-then-skip-and-log) — plain `requests`/`urllib`, no Selenium needed (confirmed: these are static HTML pages, same as the Wikipedia poll pages in `research/preseason/`).
- **Skip-and-log discipline** (same as every other scraper in this project's research work): a team/season that 404s or doesn't parse is logged and skipped, never crashes the run.

### R1: Roster + draft scraper
- `experiments/collect_rosters.py`: for every team × every season present in the game archive (2001-02 through 2025-26, matching `research/preseason/data/extended_archive.csv`'s coverage), fetch the roster page and save `data/rosters/{team}_{season}.csv` (Number, Name, Class, Position, Height, Weight, DOB, Hometown, LastTeam, DraftInfo parsed into DraftYear/DraftTeam/DraftRound).
- This is a LARGE scrape (~60 teams × ~24 seasons ≈ 1,400 requests) — run with a real politeness delay, in the background, and report actual coverage (how many seasons CHN has rosters for per team — older/smaller programs may have thinner history than the powerhouse programs).
- Output: draft-picks-per-team-per-season is then just a groupby on the parsed DraftInfo column — no separate step needed.

### R2: Player stats scraper
- `experiments/collect_player_stats.py`: same team × season loop, fetch the stats page, save `data/player_stats/{team}_{season}.csv` (skaters and goalies, two tables per file or two files).
- Reuses R1's team ID map and scraping harness.

### R3: Returning-production computation
- `experiments/compute_returning_production.py`: for each team × season (where season S-1's stats exist), join season-S roster names against season-(S-1) stats (same team) to find returning players, sum their prior production, divide by team's total prior production. Output: `results/returning_production.csv` (Team, Season, ReturningPointsShare, ReturningGoalieMinutesShare, DraftedPlayerCount, DraftedPlayerCount_Round1-2, ...).
- **Name-matching caveat to handle explicitly**: CHN's own name formatting should be self-consistent, but verify with a spot-check report (R3's report should show a sample of matched/unmatched names per team, not just aggregate numbers) before trusting the output.

### R4: Diagnostic — does any of this actually predict anything?
- This is the point of the whole exploration, and it reuses `research/preseason/`'s existing evaluation machinery (read-only import of `research.preseason.harness.eval`, or a straight copy if importing across research workspaces turns out to be awkward — TBD when this phase is reached) rather than re-inventing it.
- Same protocol as `research/preseason/reports/p4_lastyear_and_polls.md`: does `ReturningPointsShare` / `DraftedPlayerCount` (alone, and combined with last year's rating) improve on last year's rating alone as an early-season predictor? Pre-register the expectation before running: returning production should matter MOST for teams whose roster changed a lot (high turnover), and should add the least where last year's rating already captures persistent program strength.
- **Gate:** must show holdout improvement over `research/preseason/reports/p4_lastyear_and_polls.md`'s `lastyear_only`/`combined` arms, not just over a coin flip, to be worth carrying into `research/preseason/`'s P5/P6.

## 4. Order and effort

| Phase | Effort | Depends on |
|---|---|---|
| R0 (team ID map + harness) | ~1 hour | none |
| R1 (rosters + draft) | ~1,400 requests, run in background, a few hours of wall-clock at a polite pace | R0 |
| R2 (player stats) | another ~1,400 requests, same pattern | R0 |
| R3 (returning production) | ~1 hour, pure computation | R1, R2 |
| R4 (diagnostic) | ~1 day | R3, `research/preseason/reports/p4_lastyear_and_polls.md` |

**Immediate next step:** R0, then a small-scale proof-of-concept on a handful of teams/seasons before committing to the full ~2,800-request historical backfill.

## 5. Status (2026-09-15): R0-R3 complete, R4 not started

- **R0:** `data/team_id_map.csv` — 62/63 teams matched to production's `CHN_Name` (only "Maryville" unmatched).
- **R1 (rosters):** 1,303/1,449 team-seasons collected (89.9%). Failures are spread evenly across older seasons (8-9 per season), consistent with newer/smaller programs not having roster pages that far back — not a bug.
- **R2 (player stats):** collected in two passes. First full run produced 83 corrupted files: for a team that didn't exist yet in a given season, CHN returns its generic team-index page with **HTTP 200** (not a 404), and that page's only table is the site's navigation menu, not a stats table — the original parser had a real bug where `name_col is None` correctly identified this but then left the garbage table in place instead of discarding it. **Fixed** in `collect_player_stats.py` (see its inline comment); the 83 bad files were deleted and all 155 affected team-seasons (83 corrupted + 72 originally-legitimate errors) were re-attempted. Spot-checked two of the "still no data" results by hand against `research/preseason/data/extended_archive.csv` (Alaska-Anchorage 2020-21 AND 2021-22) and confirmed the team genuinely played zero games in our own game archive both seasons — a real multi-year program pause, not a scraper defect.
- **R3 (returning production):** 1,230 team-season rows computed. Name-matching handles the "Last, First" (roster) vs. "First Last" (stats) format mismatch correctly — spot-checked on Michigan 2025-26 by hand (graduating seniors correctly marked not-returning, underclassmen correctly marked returning). Aggregate sanity check: mean `ReturningPointsShare` 0.525, `ReturningGoalieMinutesShare` 0.590, `DraftedPlayerCount` 3.88/team-season — all in a plausible range for college hockey's typical roster turnover.
- **R4 (the actual diagnostic — does any of this predict anything beyond `research/preseason`'s existing signals): NOT STARTED.** This is the real point of the whole exploration and is the natural next step.
