# Roster / draft / returning-production exploration

An isolated workspace for player-level research: season-by-season rosters, NHL draft picks, and returning-production, all sourced from College Hockey News (CHN). This is a **sibling** to `research/preseason/`, not part of it — a separate, independent exploration with its own isolation guarantees, started 2026-09-15 after the earlier decision to avoid player-based approaches was explicitly reversed.

See [PLAN.md](PLAN.md) for the actual research plan and current status.

## Isolation rules (same shape as `research/preseason/README.md`, enforced together with it)

| Rule | Enforced by |
|---|---|
| `src/`, `scripts/`, and `webpage/` never import `research` (any workspace under it, including this one) | `tests/unit/test_research_isolation.py` |
| Scrapers/experiments write **only** under `research/roster_talent/` | `harness/paths.py`'s `research_path()`, which raises if a path resolves outside this workspace |
| This workspace never writes into `research/preseason/`'s data/results/reports, or vice versa | `test_research_workspaces_do_not_overlap` in the isolation test |
| Collected data (rosters, player stats) goes in `research/roster_talent/data/`, never `data/` at the project root | Convention, plus the isolation test |
| Production code (`src/data/*_scraper.py`) may be **read** for URL/HTTP conventions, never edited | Code review |

## Layout

```
research/roster_talent/
  README.md            this file
  PLAN.md               research plan and current status
  harness/              shared scraping helpers, safe paths
  experiments/          one module per scraper/analysis step
  data/
    rosters/             one CSV per team per season
    player_stats/         one CSV per team per season (skaters + goalies)
  results/              derived tables (returning-production, draft counts, ...)
  reports/              one self-contained report per exploration step
```

Run scripts from the project root as modules, e.g. `python -m research.roster_talent.experiments.build_team_id_map`.

## Promotion to production

Same discipline as `research/preseason/`: nothing here feeds the live pipeline, `config.yaml`, or the public site without an explicit, separate, approved promotion step.
