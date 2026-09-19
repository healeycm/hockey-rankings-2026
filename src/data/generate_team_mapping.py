import argparse
import sys
import pandas as pd
import difflib
from pathlib import Path

# --- Configuration ---
CURRENT_FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE_PATH.parents[2]
DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT))
from src.utils.season import get_current_season_code, season_start_year, season_end_year

_current_season = get_current_season_code()
_sy, _ey = season_start_year(_current_season), season_end_year(_current_season)

# Input Files (defaults track the current season; override via CLI args below)
USCHO_FILE = DATA_DIR / "raw" / f"games_{_sy}_{_ey}.csv"
CHN_FILE = DATA_DIR / "validation" / f"chn_krach_{_ey}.csv"

# Output File — this is the live, hand-curated DI team mapping used
# everywhere (NPI's DI filter, conference codes, logos, etc). Running this
# script with --write will OVERWRITE it with a fresh fuzzy-match, discarding
# any manual corrections. Defaults to a side-by-side draft file instead.
OUTPUT_FILE = DATA_DIR / "teams" / "team_info.csv"
DRAFT_OUTPUT_FILE = DATA_DIR / "teams" / f"team_info_draft_{_ey}.csv"


def get_best_match(name, choices):
    """
    Finds the best string match from a list of choices.
    Returns (best_match, score).
    """
    # 1. Exact match (case insensitive)
    for choice in choices:
        if name.lower() == choice.lower():
            return choice, 1.0

    # 2. Fuzzy match
    matches = difflib.get_close_matches(name, choices, n=1, cutoff=0.0)
    if matches:
        best = matches[0]
        score = difflib.SequenceMatcher(None, name, best).ratio()
        return best, score

    return None, 0.0


def normalize_bool(val):
    """
    Helper to convert 'Yes'/'No', 'True'/'False', 1/0 to Python Boolean.
    """
    s = str(val).lower().strip()
    return s in ['yes', 'true', '1', 't', 'y']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--uscho-file', type=Path, default=USCHO_FILE)
    parser.add_argument('--chn-file', type=Path, default=CHN_FILE)
    parser.add_argument('--write', action='store_true',
                         help=f"Overwrite the live {OUTPUT_FILE.name} directly. "
                              f"Without this flag, output goes to {DRAFT_OUTPUT_FILE.name} "
                              "for manual review/diff before replacing the curated file.")
    args = parser.parse_args()

    uscho_file, chn_file = args.uscho_file, args.chn_file
    output_file = OUTPUT_FILE if args.write else DRAFT_OUTPUT_FILE

    print("--- Generating Team Name Mapping ---")

    # 1. Load USCHO Data
    if not uscho_file.exists():
        print(f"ERROR: Could not find USCHO file at {uscho_file}")
        return

    print(f"Loading USCHO data from: {uscho_file.name}")
    uscho_df = pd.read_csv(uscho_file)

    # --- FILTERING LOGIC ---
    # Standardize columns to boolean
    uscho_df['Is_Exhibition_Bool'] = uscho_df['Is_Exhibition'].apply(normalize_bool)
    uscho_df['Is_Neutral_Bool'] = uscho_df['Is_Neutral'].apply(normalize_bool)

    # Filter: Exclude Exhibition AND Exclude Neutral
    # We only want standard Home/Away games to identify valid D1 teams
    clean_df = uscho_df[
        (uscho_df['Is_Exhibition_Bool'] == False) &
        (uscho_df['Is_Neutral_Bool'] == False)
        ]

    dropped_count = len(uscho_df) - len(clean_df)
    print(f"Filtered out {dropped_count} rows (Exhibition or Neutral site games).")

    # Extract unique teams from filtered data
    uscho_teams = pd.concat([clean_df['Visitor_Team'], clean_df['Home_Team']]).unique()
    uscho_teams = sorted([t for t in uscho_teams if isinstance(t, str) and t.strip()])
    print(f"Found {len(uscho_teams)} unique teams in USCHO data (after filtering).")

    # 2. Load CHN Data
    if not chn_file.exists():
        print(f"ERROR: Could not find CHN file at {chn_file}")
        return

    print(f"Loading CHN data from: {chn_file.name}")
    chn_df = pd.read_csv(chn_file)

    # Handle potential column name variations
    chn_team_col = 'Team'
    if 'Team' not in chn_df.columns:
        # Fallback if column flattened oddly
        possible = [c for c in chn_df.columns if 'team' in c.lower()]
        if possible:
            chn_team_col = possible[0]
        else:
            print(f"ERROR: Could not find 'Team' column in CHN file. Columns: {chn_df.columns}")
            return

    chn_teams = chn_df[chn_team_col].unique()
    chn_teams = [t for t in chn_teams if isinstance(t, str) and t.strip()]
    print(f"Found {len(chn_teams)} unique teams in CHN data.")

    # 3. Perform Mapping
    print("Mapping teams...")
    mapping_data = []

    for uscho_name in uscho_teams:
        chn_match, score = get_best_match(uscho_name, chn_teams)

        # Round score for readability
        score = round(score, 3)

        mapping_data.append({
            'USCHO_Name': uscho_name,
            'CHN_Name': chn_match,
            'Match_Confidence': score
        })

    # Create DataFrame
    mapping_df = pd.DataFrame(mapping_data)

    # 4. Save Result
    # Ensure directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    mapping_df.to_csv(output_file, index=False)
    print("-" * 40)
    print(f"Mapping saved to: {output_file}")
    print("-" * 40)

    # 5. Review Low Confidence Matches
    low_conf = mapping_df[mapping_df['Match_Confidence'] < 0.85]
    if not low_conf.empty:
        print("\nWARNING: The following matches have low confidence. Please review the output CSV manually:")
        print(low_conf[['USCHO_Name', 'CHN_Name', 'Match_Confidence']].to_string(index=False))
    else:
        print("\nAll matches look high confidence.")


if __name__ == "__main__":
    main()