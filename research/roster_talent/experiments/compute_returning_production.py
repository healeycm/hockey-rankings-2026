# research/roster_talent/experiments/compute_returning_production.py
"""
R3: for each team x season S (where season S-1's player stats also exist),
finds which of season S's rostered players appeared in season S-1's stats
for the SAME team (i.e. returning, not a transfer arriving from elsewhere),
and computes what share of that team's prior-season production they
represent. Also summarizes draft picks from season S's own roster (already
parsed by collect_rosters.py -- no extra scrape needed).

Name-matching caveat (confirmed by hand, see this module's normalize_name):
roster names arrive as "Last, First" (e.g. "Callahan, James") while stats
names arrive as "First Last" after collect_player_stats.py's own parsing
(e.g. "T.J. Hughes") -- these must be normalized to the same form before
comparing. This is the single biggest correctness risk in this step, which
is why main() always writes a per-team-season match-rate diagnostic
alongside the aggregate numbers (PLAN.md section 3, R3's explicit
requirement), not just the final shares.

Usage (from project root):
    python -m research.roster_talent.experiments.compute_returning_production
"""
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from research.roster_talent.harness.paths import research_path  # noqa: E402


def normalize_name(name):
    """"Callahan, James" -> "jamescallahan"; "T.J. Hughes" -> "tjhughes".
    Handles the Last,-First vs First-Last mismatch by detecting the comma
    and swapping, then strips everything but lowercase letters/digits so
    punctuation differences (periods, hyphens) don't cause a false miss."""
    if not isinstance(name, str) or not name.strip():
        return ""
    name = name.strip()
    if ',' in name:
        last, _, first = name.partition(',')
        name = f"{first.strip()} {last.strip()}"
    return re.sub(r'[^a-z0-9]', '', name.lower())


def load_roster(team_slug, season):
    path = research_path("data", "rosters", f"{team_slug}_{season}.csv", mkdir_parent=False)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df = df[df['Name'].notna()].copy()
    df['NormName'] = df['Name'].apply(normalize_name)
    return df


def load_stats(team_slug, season):
    """Returns (skaters_df, goalies_df), either possibly None."""
    skaters_path = research_path("data", "player_stats", f"{team_slug}_{season}_skaters.csv", mkdir_parent=False)
    goalies_path = research_path("data", "player_stats", f"{team_slug}_{season}_goalies.csv", mkdir_parent=False)
    skaters = pd.read_csv(skaters_path) if skaters_path.exists() else None
    goalies = pd.read_csv(goalies_path) if goalies_path.exists() else None
    if skaters is not None:
        skaters = skaters[skaters['Name'].notna()].copy()
        skaters['NormName'] = skaters['Name'].apply(normalize_name)
    if goalies is not None:
        goalies = goalies[goalies['Name'].notna()].copy()
        goalies['NormName'] = goalies['Name'].apply(normalize_name)
    return skaters, goalies


def compute_one(team_slug, team_name, season, prior_season):
    roster = load_roster(team_slug, season)
    prior_skaters, prior_goalies = load_stats(team_slug, prior_season)

    if roster is None or (prior_skaters is None and prior_goalies is None):
        return None, None

    row = {"Team": team_name, "Season": season, "PriorSeason": prior_season}
    diagnostics = []

    roster_names = set(roster['NormName'])

    if prior_skaters is not None and not prior_skaters.empty and 'Pts.' in prior_skaters.columns:
        prior_skaters = prior_skaters.copy()
        prior_skaters['IsReturning'] = prior_skaters['NormName'].isin(roster_names)
        total_pts = prior_skaters['Pts.'].sum()
        returning_pts = prior_skaters.loc[prior_skaters['IsReturning'], 'Pts.'].sum()
        row['ReturningPointsShare'] = (returning_pts / total_pts) if total_pts > 0 else None
        row['PriorSkaterCount'] = len(prior_skaters)
        row['ReturningSkaterCount'] = int(prior_skaters['IsReturning'].sum())
        diagnostics.append(prior_skaters[['Name', 'NormName', 'Pts.', 'IsReturning']].assign(Kind='skater'))

    if prior_goalies is not None and not prior_goalies.empty and 'MIN' in prior_goalies.columns:
        prior_goalies = prior_goalies.copy()
        prior_goalies['IsReturning'] = prior_goalies['NormName'].isin(roster_names)
        total_min = prior_goalies['MIN'].sum()
        returning_min = prior_goalies.loc[prior_goalies['IsReturning'], 'MIN'].sum()
        row['ReturningGoalieMinutesShare'] = (returning_min / total_min) if total_min > 0 else None
        diagnostics.append(prior_goalies[['Name', 'NormName', 'MIN', 'IsReturning']].rename(columns={'MIN': 'Pts.'}).assign(Kind='goalie'))

    if 'DraftYear' in roster.columns:
        drafted = roster[roster['DraftYear'].notna()]
        row['DraftedPlayerCount'] = len(drafted)
        row['DraftedPlayerCount_Round1_2'] = int((drafted['DraftRound'] <= 2).sum())

    diag_df = pd.concat(diagnostics, ignore_index=True) if diagnostics else None
    if diag_df is not None:
        diag_df.insert(0, 'Team', team_name)
        diag_df.insert(1, 'Season', season)
    return row, diag_df


def main():
    team_map = pd.read_csv(research_path("data", "team_id_map.csv", mkdir_parent=False))
    archive = pd.read_csv(PROJECT_ROOT / "research" / "preseason" / "data" / "extended_archive.csv")
    all_seasons = sorted(archive['Season'].astype(str).unique())

    results = []
    all_diagnostics = []
    for team in team_map.to_dict('records'):
        for i, season in enumerate(all_seasons):
            if i == 0:
                continue
            prior_season = all_seasons[i - 1]
            row, diag = compute_one(team['Slug'], team['Name'], season, prior_season)
            if row is not None:
                results.append(row)
            if diag is not None:
                all_diagnostics.append(diag)

    if not results:
        print("No team-seasons had both a roster and prior-season stats available -- "
              "has the full collect_rosters.py/collect_player_stats.py backfill run yet?")
        return

    results_df = pd.DataFrame(results)
    out_path = research_path("results", "returning_production.csv")
    results_df.to_csv(out_path, index=False)
    print(f"Saved {len(results_df)} team-season rows to {out_path}")

    if all_diagnostics:
        diag_df = pd.concat(all_diagnostics, ignore_index=True)
        diag_path = research_path("results", "returning_production_name_match_diagnostic.csv")
        diag_df.to_csv(diag_path, index=False)
        match_rate = diag_df['IsReturning'].mean()
        print(f"Name-match diagnostic saved to {diag_path} (informational only, "
              f"{match_rate:.1%} of prior-season players matched to a returning roster spot -- "
              f"this INCLUDES players who genuinely graduated/left, so it is not expected to be "
              f"anywhere near 100%; use this file to spot-check for name-format mismatches "
              f"specifically, not to judge this number against 100%).")

    print("\nSummary (mean across all team-seasons):")
    for col in ['ReturningPointsShare', 'ReturningGoalieMinutesShare', 'DraftedPlayerCount', 'DraftedPlayerCount_Round1_2']:
        if col in results_df.columns:
            print(f"  {col}: {results_df[col].mean():.3f}")


if __name__ == "__main__":
    main()
