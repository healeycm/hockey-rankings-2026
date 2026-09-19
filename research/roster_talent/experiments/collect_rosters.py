# research/roster_talent/experiments/collect_rosters.py
"""
R1: scrapes each team's roster for each season, parsing the NHL Draft
column (format "{Year}-{NHLTeam}-{Round}", e.g. "2024-MTL-1") into
DraftYear/DraftNHLTeam/DraftRound so "draft picks per team" is just a
groupby on this output later, not a separate scrape.

Confirmed by hand (research/roster_talent/PLAN.md section 1) that:
  - current season:  /reports/roster/{Slug}/{ID}
  - past seasons:    /reports/roster/{Slug}/{ID}/{SeasonCode}
  - columns: No., Name, Yr., Pos, Ht., Wt., DOB, Hometown, Last Team, NHL Draft

Skip-and-log discipline: a team/season combination that 404s or doesn't
parse is logged and skipped, never crashes the run -- CHN's roster history
depth likely varies by program (smaller/newer programs may not have pages
that far back), which is expected, not an error.

Usage (from project root):
    python -m research.roster_talent.experiments.collect_rosters                 # smoke test: 3 teams x 2 seasons
    python -m research.roster_talent.experiments.collect_rosters --full           # every team x every archived season
"""
import argparse
import re
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from research.roster_talent.harness.paths import research_path  # noqa: E402
from research.roster_talent.harness.scrape import fetch  # noqa: E402

DRAFT_RE = re.compile(r"^(\d{4})-([A-Z]{2,3})-(\d)$")


def roster_url(slug, team_id, season_code=None):
    base = f"/reports/roster/{slug}/{team_id}"
    return base if season_code is None else f"{base}/{season_code}"


def parse_roster_table(html):
    """Returns a DataFrame of players, or None if no roster table found."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return None

    dfs = pd.read_html(StringIO(str(table)))
    if not dfs:
        return None
    df = dfs[0]

    # Normalize column names -- confirmed headers are No./Name/Yr./Pos/Ht./
    # Wt./DOB/Hometown/Last Team/NHL Draft, but be defensive about exact
    # punctuation since pandas.read_html strips some of it inconsistently.
    col_map = {}
    for c in df.columns:
        cl = str(c).strip().lower().rstrip('.')
        if cl in ('no', '#'):
            col_map[c] = 'Number'
        elif cl == 'name':
            col_map[c] = 'Name'
        elif cl in ('yr', 'year', 'cl'):
            col_map[c] = 'Class'
        elif cl == 'pos':
            col_map[c] = 'Position'
        elif cl in ('ht',):
            col_map[c] = 'Height'
        elif cl in ('wt',):
            col_map[c] = 'Weight'
        elif cl == 'dob':
            col_map[c] = 'DOB'
        elif cl == 'hometown':
            col_map[c] = 'Hometown'
        elif 'last team' in cl:
            col_map[c] = 'LastTeam'
        elif 'draft' in cl:
            col_map[c] = 'DraftRaw'
    df = df.rename(columns=col_map)

    if 'Name' not in df.columns:
        return None

    df = df[df['Name'].notna()].copy()
    df = df[df['Name'].astype(str).str.strip() != '']

    # The roster table embeds section sub-headers ("Defensemen", "Forwards",
    # "Goaltenders") as pseudo-rows where every column repeats the same
    # string (confirmed by hand on Michigan 2024-25: row 0 has
    # Name=Class=Position="Defensemen"). Drop those, not real players.
    if 'Class' in df.columns and 'Position' in df.columns:
        is_section_header = (df['Name'] == df['Class']) & (df['Name'] == df['Position'])
        df = df[~is_section_header]

    df = df.reset_index(drop=True)
    if df.empty:
        return None

    if 'DraftRaw' in df.columns:
        parsed = df['DraftRaw'].astype(str).apply(_parse_draft)
        df['DraftYear'] = [p[0] for p in parsed]
        df['DraftNHLTeam'] = [p[1] for p in parsed]
        df['DraftRound'] = [p[2] for p in parsed]

    return df


def _parse_draft(raw):
    m = DRAFT_RE.match(raw.strip())
    if not m:
        return None, None, None
    return int(m.group(1)), m.group(2), int(m.group(3))


def collect_one(slug, team_id, team_name, season_code):
    html, err = fetch(roster_url(slug, team_id, season_code))
    if html is None:
        return None, f"fetch_error: {err}"
    df = parse_roster_table(html)
    if df is None or df.empty:
        return None, "no_table_or_empty"
    df.insert(0, 'Team', team_name)
    df.insert(1, 'Season', season_code)
    return df, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help="Scrape every team x every archived season (large).")
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
            df, err = collect_one(team['Slug'], team['TeamID'], team['Name'], season_str)
            if err:
                print(f"  ! {team['Name']} {season_str}: {err}")
                log_rows.append({"Team": team['Name'], "Season": season_str, "Status": "error", "Detail": err})
                continue
            out_path = research_path("data", "rosters", f"{team['Slug']}_{season_str}.csv")
            df.to_csv(out_path, index=False)
            n_drafted = df['DraftYear'].notna().sum() if 'DraftYear' in df.columns else 0
            print(f"  -> {team['Name']} {season_str}: {len(df)} players, {n_drafted} drafted")
            log_rows.append({"Team": team['Name'], "Season": season_str, "Status": "ok",
                              "Detail": f"{len(df)} players, {n_drafted} drafted"})

    log_df = pd.DataFrame(log_rows)
    log_path = research_path("data", "rosters", "_collection_log.csv")
    log_df.to_csv(log_path, index=False)
    print(f"\n{(log_df['Status'] == 'ok').sum()}/{len(log_df)} team-seasons collected successfully.")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
