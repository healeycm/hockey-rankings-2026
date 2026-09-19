# research/roster_talent/experiments/collect_player_stats.py
"""
R2: scrapes each team's per-player season stats (skaters + goalies).

Confirmed by hand (research/roster_talent/PLAN.md section 1) that:
  - current season:  /stats/team/{Slug}/{ID}
  - past seasons:    /stats/team/{Slug}/{ID}/overall,{SeasonCode}
  - skater columns:  Name/Yr, GP, G, A, Pts, Pt/GP, Shots, Sh%, PIM, GWG, PPG, SHG, +/-, TOI/G
  - goalie columns:  Name/Yr, GP, W, L, T, GA, MIN, GAA, SH, SV, SV%
  - the page has TWO tables (skaters, then goalies) -- the current season's
    tables are empty (headers only) until games are actually played, same
    as every other "preseason" state this project has already handled.

Skip-and-log discipline, same as collect_rosters.py.

Usage (from project root):
    python -m research.roster_talent.experiments.collect_player_stats                # smoke test: 3 teams x 2 seasons
    python -m research.roster_talent.experiments.collect_player_stats --full          # every team x every archived season
"""
import argparse
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from research.roster_talent.harness.paths import research_path  # noqa: E402
from research.roster_talent.harness.scrape import fetch  # noqa: E402


def stats_url(slug, team_id, season_code=None):
    base = f"/stats/team/{slug}/{team_id}"
    return base if season_code is None else f"{base}/overall,{season_code}"


def _clean_columns(df):
    """The raw table has a 2-level header (a "Scoring"/"Goaltending" group
    row over the real field names) and many trailing all-NaN padding
    columns (confirmed by hand: Michigan 2024-25's skater table parses as
    28 rows x 99 columns, but only the first ~15 columns ever have data --
    the rest are "Unnamed: N_level_1" with every value NaN, presumably
    hidden/expandable columns in the page's HTML that aren't populated).
    Flattens to the field-name level and drops the padding."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[-1] for c in df.columns]
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
    df = df.dropna(axis=1, how='all')
    return df


def _split_name_field(df, is_goalie=False):
    """The player-identity column arrives as one combined string, e.g.
    "T.J. Hughes, F, Jr" (skaters: Name, Position, Class) or
    "Cameron Korpi, Fr" (goalies: Name, Class -- Position is always G,
    implied by which table this came from). Splits it into separate
    Name/Position/Class columns so R3 can join against roster names
    without re-parsing this later."""
    name_col = next((c for c in df.columns if 'name' in c.lower()), None)
    if name_col is None:
        return df
    parts = df[name_col].astype(str).str.split(',', expand=True)
    df = df.copy()
    df['Name'] = parts[0].str.strip()
    if is_goalie:
        df['Position'] = 'G'
        df['Class'] = parts[1].str.strip() if parts.shape[1] > 1 else None
    else:
        df['Position'] = parts[1].str.strip() if parts.shape[1] > 1 else None
        df['Class'] = parts[2].str.strip() if parts.shape[1] > 2 else None
    df = df.drop(columns=[name_col])
    return df


def parse_stats_tables(html):
    """Returns (skaters_df, goalies_df), either possibly None if not
    found/empty (e.g. a future season with no games played yet)."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 1:
        return None, None

    dfs = []
    for t in tables[:2]:
        try:
            parsed = pd.read_html(StringIO(str(t)))
            if parsed:
                dfs.append(_clean_columns(parsed[0]))
        except ValueError:
            dfs.append(None)

    skaters = dfs[0] if len(dfs) > 0 else None
    goalies = dfs[1] if len(dfs) > 1 else None

    # BUG FIX (found after the first full backfill: 83/1449 team-seasons
    # produced garbage files with columns literally named "0,1,2,3,4,5").
    # Root cause: a team that didn't exist yet in the requested season gets
    # CHN's generic "/reports/" team-index page back with HTTP 200 (not a
    # 404), whose only table is the site's conference/team NAVIGATION menu,
    # not a stats table. `name_col is None` was ALREADY the correct signal
    # that a table isn't a real stats table -- the bug was that the `if ...
    # and name_col:` branch just left such a table untouched (still not
    # None) instead of discarding it, so it got saved to disk as-is.
    name_col = next((c for c in (skaters.columns if skaters is not None else []) if 'name' in c.lower()), None)
    if skaters is not None and name_col:
        skaters = skaters[skaters[name_col].notna()]
        skaters = skaters[~skaters[name_col].astype(str).str.upper().str.startswith('TOTAL')]
        skaters = _split_name_field(skaters, is_goalie=False) if not skaters.empty else None
    else:
        skaters = None

    name_col_g = next((c for c in (goalies.columns if goalies is not None else []) if 'name' in c.lower()), None)
    if goalies is not None and name_col_g:
        goalies = goalies[goalies[name_col_g].notna()]
        goalies = goalies[~goalies[name_col_g].astype(str).str.upper().str.startswith('TOTAL')]
        goalies = _split_name_field(goalies, is_goalie=True) if not goalies.empty else None
    else:
        goalies = None

    return (skaters if skaters is None or not skaters.empty else None,
            goalies if goalies is None or not goalies.empty else None)


def collect_one(slug, team_id, team_name, season_code):
    html, err = fetch(stats_url(slug, team_id, season_code))
    if html is None:
        return None, None, f"fetch_error: {err}"
    skaters, goalies = parse_stats_tables(html)
    if skaters is None and goalies is None:
        return None, None, "no_data (likely a season with no games played yet)"
    if skaters is not None:
        skaters = skaters.copy()
        skaters.insert(0, 'Team', team_name)
        skaters.insert(1, 'Season', season_code)
    if goalies is not None:
        goalies = goalies.copy()
        goalies.insert(0, 'Team', team_name)
        goalies.insert(1, 'Season', season_code)
    return skaters, goalies, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()

    team_map = pd.read_csv(research_path("data", "team_id_map.csv", mkdir_parent=False))
    archive = pd.read_csv(PROJECT_ROOT / "research" / "preseason" / "data" / "extended_archive.csv")
    all_seasons = sorted(archive['Season'].unique())

    if args.full:
        teams_to_run = team_map.to_dict('records')
        seasons_to_run = all_seasons
    else:
        print("Smoke-test mode (--full not passed): 3 teams x 2 seasons.")
        teams_to_run = team_map.head(3).to_dict('records')
        seasons_to_run = all_seasons[-2:]

    log_rows = []
    for team in teams_to_run:
        for season in seasons_to_run:
            season_str = str(season)
            skaters, goalies, err = collect_one(team['Slug'], team['TeamID'], team['Name'], season_str)
            if err:
                print(f"  ! {team['Name']} {season_str}: {err}")
                log_rows.append({"Team": team['Name'], "Season": season_str, "Status": "error", "Detail": err})
                continue
            n_skaters = len(skaters) if skaters is not None else 0
            n_goalies = len(goalies) if goalies is not None else 0
            if skaters is not None:
                skaters.to_csv(research_path("data", "player_stats", f"{team['Slug']}_{season_str}_skaters.csv"), index=False)
            if goalies is not None:
                goalies.to_csv(research_path("data", "player_stats", f"{team['Slug']}_{season_str}_goalies.csv"), index=False)
            print(f"  -> {team['Name']} {season_str}: {n_skaters} skaters, {n_goalies} goalies")
            log_rows.append({"Team": team['Name'], "Season": season_str, "Status": "ok",
                              "Detail": f"{n_skaters} skaters, {n_goalies} goalies"})

    log_df = pd.DataFrame(log_rows)
    log_path = research_path("data", "player_stats", "_collection_log.csv")
    log_df.to_csv(log_path, index=False)
    print(f"\n{(log_df['Status'] == 'ok').sum()}/{len(log_df)} team-seasons collected successfully.")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
