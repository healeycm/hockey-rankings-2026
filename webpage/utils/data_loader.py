import pandas as pd
import glob
import os
import shutil
import yaml
from pathlib import Path
import datetime

# --- PATH DEFINITIONS ---
# webpage/utils/ -> webpage/ -> root
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed"
OUTPUT_DIR = ROOT_DIR / "output"
TEAM_INFO_DIR = ROOT_DIR / "data" / "teams"
LOGO_DIR = TEAM_INFO_DIR / "team_logos"


def _data_dir(division='men'):
    """'men' (default) is the original, unnamespaced data/processed/ path —
    unchanged from before division support existed. 'women' points at the
    parallel data/processed/women/ tree (see reports/womens_hockey_import.md
    for why physical separation, not a shared file, was the chosen design)."""
    return DATA_DIR if division == 'men' else (DATA_DIR / division)


def _output_dir(division='men'):
    return OUTPUT_DIR if division == 'men' else (OUTPUT_DIR / division)


def _team_info_path(division='men'):
    """The DI-filter/roster CSV — team_info.csv for men (unchanged path),
    team_info_women.csv for women (a differently-NAMED file, not a
    subdirectory, matching how src/rankings/base_ranker.py's
    using_di_team_path() already references it)."""
    return TEAM_INFO_DIR / ("team_info.csv" if division == 'men' else "team_info_women.csv")


def _college_teams_path(division='men'):
    return TEAM_INFO_DIR / ("college_hockey_teams.csv" if division == 'men' else "college_hockey_teams_women.csv")


import re

# --- HELPER FUNCTIONS ---

def normalize_name(name):
    """
    Normalizes a team name for fuzzy comparison.
    Converts to lowercase, removes punctuation, spaces, etc.
    e.g. "St. Cloud State" -> "stcloudstate"
         "pennstate" -> "pennstate"
    """
    if not isinstance(name, str):
        return ""
    # simple lower and remove all non-alphanumeric
    res = re.sub(r'[^a-z0-9]', '', name.lower())
    # Handle common abbreviations to unify (e.g. UMass Lowell vs Mass.-Lowell)
    res = res.replace('umass', 'mass')
    return res

def _load_canonical_mapping(division='men'):
    """
    Loads both CHN -> USCHO and USCHO -> USCHO mappings to ensure
    any variation maps to the canonical USCHO name.
    """
    mapping = {}
    info_path = _team_info_path(division)
    if info_path.exists():
        df = pd.read_csv(info_path)
        for _, row in df.iterrows():
            uscho = row['USCHO_Name']
            chn = row['CHN_Name']
            # Map everything to USCHO name as the canonical standard
            mapping[normalize_name(uscho)] = uscho
            mapping[normalize_name(chn)] = uscho
    return mapping

# Singleton-style cache for the mapping, one per division -- men's and
# women's team_info files are separate rosters (see _team_info_path), so a
# single shared cache would resolve women's-only program names (no men's
# team) to themselves incorrectly, and silently map shared-name schools
# (e.g. "Boston College") the same either way, which happens to work but
# only by coincidence.
_CANONICAL_MAPPING = {}

def get_canonical_name(name, division='men'):
    """
    Returns the canonical USCHO name for any team name variation.
    """
    if division not in _CANONICAL_MAPPING:
        _CANONICAL_MAPPING[division] = _load_canonical_mapping(division)

    norm = normalize_name(name)
    return _CANONICAL_MAPPING[division].get(norm, name)

def get_latest_file(folder_pattern):
    """Finds the most recent file in a folder based on filename sorting (assumes date-based naming)."""
    files = glob.glob(str(folder_pattern))
    if not files:
        return None
    return sorted(files)[-1]

def get_current_season():
    """Reads the target season from the main config.yaml file."""
    try:
        config_path = ROOT_DIR / "config.yaml"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config.get('system', {}).get('season')
    except Exception as e:
        print(f"Error reading config: {e}")
    return None

def get_available_models(division='men'):
    """
    Lists ranking models that have a file for the LATEST available date across all models.
    This prevents comparing stale data (e.g., comparing last week's poll to this week's).
    """
    rank_root = _output_dir(division) / "rankings"
    if not rank_root.exists():
        return []
    
    # 1. Find all ranking CSVs and extract dates
    # Pattern: output/rankings/<Model>/rankings_<Model>_<YYYY-MM-DD>.csv
    all_files = list(rank_root.rglob("*.csv"))
    
    if not all_files:
        return []

    # Extract dates
    dates = []
    for p in all_files:
        try:
            # Filename format: rankings_ModelName_YYYY-MM-DD.csv
            # Safe way: extract last 10 chars before .csv
            date_str = p.stem[-10:] 
            # Check if valid date format to be sure
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            continue
            
    if not dates:
        return []
        
    # Get global max date
    latest_global_date = max(dates)
    
    # 2. Filter models that have a file with this date
    valid_models = []
    for d in rank_root.iterdir():
        if d.is_dir():
            expected_file = d / f"rankings_{d.name}_{latest_global_date}.csv"
            if expected_file.exists():
                valid_models.append(d.name)
                
    return sorted(valid_models)


# --- LOGO HANDLING ---

def ensure_logos_in_assets():
    """Copies team logos to the webpage assets directory for serving."""
    # Destination: webpage/assets/logos
    # webpage/utils/ -> webpage/ -> webpage/assets/logos
    ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "logos"
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Copy Default Logo if not exists
    default_src = TEAM_INFO_DIR / "default.png" # Assuming one exists, or we create it
    default_dst = ASSETS_DIR / "default.png"
    
    # If we don't have a source default, ensure at least something is there or handle gracefully
    
    if not LOGO_DIR.exists():
        return

    # Read mapping to know which files to copy. Women's logos mostly point
    # at the SAME physical files as men's (shared schools), so this is
    # mainly a no-op for those, but it's here so a genuinely women's-only
    # logo added later is picked up automatically.
    for info_path in [_college_teams_path('men'), _college_teams_path('women')]:
        if not info_path.exists():
            continue
        df = pd.read_csv(info_path)
        for _, row in df.iterrows():
            if pd.isna(row.get('Local Image Path')) or not row.get('Local Image Path'):
                continue

            src = TEAM_INFO_DIR / row['Local Image Path']
            if src.exists():
                dst = ASSETS_DIR / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                    
    # Failsafe: If no default logo exists in assets, try to copy one or create a placeholder
    if not default_dst.exists():
        # Try to find a 'NCAA' logo or similar, else check if source has one
        pass


def get_logo_url(team_name, division='men'):
    """Returns the web URL for a team logo."""
    # This relies on ensure_logos_in_assets having run
    info_path = _college_teams_path(division)

    canonical_name = get_canonical_name(team_name, division=division)
    norm_canonical = normalize_name(canonical_name)
    
    if info_path.exists():
        df = pd.read_csv(info_path)
        # 1. Try exact match on 'Team Name'
        row = df[df["Team Name"] == canonical_name]
        
        # 2. Try normalized fuzzy match
        if row.empty:
            df['norm'] = df['Team Name'].apply(normalize_name)
            row = df[df['norm'] == norm_canonical]

        if not row.empty:
            path = row.iloc[0]['Local Image Path']
            if pd.notna(path):
                filename = Path(path).name
                return f"/assets/logos/{filename}"
    
    # Fallback
    return "/assets/logos/default.png"

# --- DATA LOADING ---

def load_records(division='men'):
    """
    Calculates current W-L-T and OT records for the ACTIVE SEASON only.
    Reads from games_archive.csv.
    """
    archive_path = _data_dir(division) / "games_archive.csv"
    if not archive_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(archive_path)

    # Filter by Current Season. config.yaml's system.season is men's-only
    # (women's has no config entry / no future schedule scraped yet as of
    # this writing) -- for women, target_season is always None below, so
    # this falls straight through to the "max season in the archive"
    # fallback, which correctly resolves to the most recently completed
    # women's season.
    #
    # For men, if the configured/current season has zero games so far
    # (preseason -- see reports/season_2026_27_rollover_audit.md), ALSO
    # fall back to the max season rather than returning empty records: the
    # rankings CSVs themselves are last season's real final numbers (the
    # last run before the new season started), so records/conference
    # should match them instead of going blank while rankings look
    # populated -- see the "make men's/women's pages behave the same" fix.
    target_season = get_current_season() if division == 'men' else None
    if target_season and 'Season' in df.columns and (df['Season'] == target_season).any():
        df = df[df['Season'] == target_season]
    elif 'Season' in df.columns and not df.empty:
        # Fallback to max season (either no target season configured, or
        # the target season has zero games recorded yet).
        df = df[df['Season'] == df['Season'].max()]

    # Calculate Records
    records = {}

    def update_record(team, result, is_ot):
        canonical_team = get_canonical_name(team, division=division)
        if canonical_team not in records:
            records[canonical_team] = {'W': 0, 'L': 0, 'T': 0, 'OTW': 0, 'OTL': 0}

        if result == 1.0:  # Win
            records[canonical_team]['W'] += 1
            if is_ot: records[canonical_team]['OTW'] += 1
        elif result == 0.0:  # Loss
            records[canonical_team]['L'] += 1
            if is_ot: records[canonical_team]['OTL'] += 1
        else:  # Tie
            records[canonical_team]['T'] += 1

    for _, row in df.iterrows():
        is_ot = row.get('IsOT', False)
        # Home
        update_record(row['HomeTeam'], row['Result'], is_ot)
        # Away
        away_res = 1.0 - row['Result'] if row['Result'] != 0.5 else 0.5
        update_record(row['AwayTeam'], away_res, is_ot)

    if not records:
        return pd.DataFrame(columns=['Team', 'W', 'L', 'Record', 'OT Record'])

    # Convert to DataFrame
    rec_df = pd.DataFrame.from_dict(records, orient='index').reset_index()
    rec_df.columns = ['Team', 'W', 'L', 'T', 'OTW', 'OTL']
    rec_df['Record'] = rec_df.apply(lambda x: f"{x['W']}-{x['L']}-{x['T']} ({x['OTW']}-{x['OTL']})", axis=1)
    
    return rec_df[['Team', 'W', 'L', 'T', 'OTW', 'OTL', 'Record']]


def load_rankings(selected_model="KRACH", division='men'):
    """
    Merges W-L records with the selected model's rankings.
    Returns DataFrame: [Team, W, L, Record, OT Record, <Model>_Rank, <Model>_Val, Conference]
    """
    master_df = load_records(division=division)
    if master_df.empty:
        master_df = pd.DataFrame(columns=['Team'])

    # Path to selected model
    model_dir = _output_dir(division) / "rankings" / selected_model
    latest = get_latest_file(model_dir / "*.csv")

    if latest:
        df = pd.read_csv(latest)
        # Apply canonical names to the rankings file as well
        if 'Team' in df.columns:
            df['Team'] = df['Team'].apply(lambda t: get_canonical_name(t, division=division))
            
        # Expected cols: Rank, Team, <ValueCol>
        # We need to find the value column (not Rank or Team)
        val_col = [c for c in df.columns if c not in ['Rank', 'Team']]
        
        if val_col:
            val_col_name = val_col[0]
            df = df.rename(columns={
                'Rank': f'{selected_model}_Rank',
                val_col_name: f'{selected_model}_Val'
            })
            
            # Merge with records
            master_df = pd.merge(master_df, df, on='Team', how='outer')
            
    # --- Merge Conference Info ---
    info_path = _college_teams_path(division)
    if info_path.exists():
        info_df = pd.read_csv(info_path)
        # Canonicalize team names in info_df for robust merging
        if 'Team Name' in info_df.columns and 'Conference' in info_df.columns:
            info_df['Team'] = info_df['Team Name'].apply(lambda t: get_canonical_name(t, division=division))
            conf_df = info_df[['Team', 'Conference']]
            master_df = pd.merge(master_df, conf_df, on='Team', how='left')

    return master_df

def load_projections(model_name="LRMC_Classic", division='men'):
    """Loads the latest projection file."""
    proj_dir = _output_dir(division) / "projections" / model_name
    latest = get_latest_file(proj_dir / "*.csv")

    if latest:
        df = pd.read_csv(latest)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
        return df
    return pd.DataFrame()

def load_team_analysis(team_name, model="KRACH", division='men'):
    """
    Loads detailed team analysis (stats, best wins, worst losses).
    Returns dict: { 'stats': {}, 'top_wins': df, 'worst_losses': df, 'model': str }
    """
    analysis_root = _output_dir(division) / "analysis" / model
    # Analysis folder contains date folders: output/analysis/KRACH/2026-01-10/
    latest_dir_path = get_latest_file(analysis_root / "*")
    
    if not latest_dir_path:
        return None
        
    latest_date_path = Path(latest_dir_path)
    if not latest_date_path.is_dir():
         return None
    
    results = {
        "stats": {},
        "top_wins": pd.DataFrame(),
        "worst_losses": pd.DataFrame(),
        "model": model,
        "date": latest_date_path.name
    }

    canonical_name = get_canonical_name(team_name, division=division)

    # 1. Season Summary (WinPct, SOS)
    summary_path = latest_date_path / "season_summary.csv"
    if summary_path.exists():
        sdf = pd.read_csv(summary_path)
        # Match using canonical name
        row = sdf[sdf['Team'].apply(lambda t: get_canonical_name(t, division=division)) == canonical_name]
        if not row.empty:
            results["stats"] = row.iloc[0].to_dict()

    # 2. Team Specific File (Game by game rating impact)
    csv_files = list(latest_date_path.glob("*.csv"))
    file_map = {normalize_name(f.stem): f for f in csv_files}
    
    # Try normalized canonical name directly
    team_file = file_map.get(normalize_name(canonical_name))
    
    # If not found, fall back to matching the original input just in case
    if not team_file:
        team_file = file_map.get(normalize_name(team_name))

    if team_file:
        tdf = pd.read_csv(team_file)
        if 'Result' in tdf.columns and 'Rating Impact' in tdf.columns:
            # Best Wins: Result='Win', highest Rating Impact
            wins = tdf[tdf['Result'] == 'Win'].sort_values('Rating Impact', ascending=False)
            # Worst Losses: Result='Loss', lowest (most negative) Rating Impact ? 
            # OR Rating Impact is negative for bad losses? Usually "Rating Impact" is explicitly how much rating changed.
            # A bad loss drops rating the most (most negative).
            losses = tdf[tdf['Result'] == 'Loss'].sort_values('Rating Impact', ascending=True)
            
            results["top_wins"] = wins.head(3)
            results["worst_losses"] = losses.head(3)
            
    return results

def get_team_schedule(team_name, model="LRMC_Classic", division='men'):
    """
    Gets schedule + win probs for a team.
    Calculates specific WinProb (Home vs Away perspective).
    """
    df = load_projections(model, division=division)
    if df.empty:
        return df

    canonical_name = get_canonical_name(team_name, division=division)

    # Filter for team in either Home or Away
    if not df.empty:
        # Normalize Home/Away cols for comparison
        team_games = df[
            (df['HomeTeam'].apply(lambda t: get_canonical_name(t, division=division)) == canonical_name) |
            (df['AwayTeam'].apply(lambda t: get_canonical_name(t, division=division)) == canonical_name)
        ].copy()

    if team_games.empty:
        return team_games

    # helper
    def calc_prob(row):
        # Use canonical name for comparison to ensure correct home/away assignment
        return row['HomeWinProb'] if get_canonical_name(row['HomeTeam'], division=division) == canonical_name else (1.0 - row['HomeWinProb'])

    team_games['WinProb'] = team_games.apply(calc_prob, axis=1)

    team_games['Opponent'] = team_games.apply(
        lambda x: x['AwayTeam'] if get_canonical_name(x['HomeTeam'], division=division) == canonical_name else x['HomeTeam'], axis=1
    )
    
    team_games['Location'] = team_games.apply(
        lambda x: 'vs' if x['HomeTeam'] == team_name else '@', axis=1
    )
    
    if 'Date' in team_games.columns:
        # Filter for upcoming/current games (today onwards)
        today = pd.Timestamp(datetime.date.today())
        team_games = team_games[team_games['Date'] >= today]
        team_games = team_games.sort_values('Date')
        
    return team_games
def load_rank_distribution(team_name, model="KRACH", division='men'):
    """
    Loads rank distribution for a team from simulation results.
    Returns: df with [Rank, Probability]
    """
    sim_root = _output_dir(division) / "simulator" / model
    latest = get_latest_file(sim_root / "*.csv")

    canonical_name = get_canonical_name(team_name, division=division)

    if latest:
        df = pd.read_csv(latest)
        # Filter using canonical name
        team_df = df[df['Team'].apply(lambda t: get_canonical_name(t, division=division)) == canonical_name]
        if not team_df.empty:
            return team_df[['Rank', 'Probability']].sort_values('Rank')
            
    return pd.DataFrame()
