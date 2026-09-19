import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))
sys.path.append(str(root / "webpage"))

from webpage.utils.data_loader import (
    get_team_schedule, 
    get_logo_url, 
    load_team_analysis, 
    load_rankings, 
    load_rank_distribution,
    get_canonical_name
)

def test_team_page(team_name, model="KRACH"):
    print(f"--- Testing Team Page Data: {team_name} (Model: {model}) ---")
    
    # 0. Canonical Name
    canonical = get_canonical_name(team_name)
    print(f"Canonical Name: '{canonical}'")
    
    # 1. Logo
    logo = get_logo_url(team_name)
    print(f"Logo URL: {logo}")
    
    # 2. Rankings/Record
    rank_df = load_rankings(model)
    team_row = rank_df[rank_df['Team'] == team_name]
    print(f"Rankings check for '{team_row}': {'FOUND' if not team_row.empty else 'NOT FOUND'}")
    if not team_row.empty:
        print(f"  Record: {team_row.iloc[0].get('Record')}")
        print(f"  Conference: {team_row.iloc[0].get('Conference')}")
    else:
        # Check canonical match
        team_row_can = rank_df[rank_df['Team'] == canonical]
        print(f"Rankings check for canonical '{canonical}': {'FOUND' if not team_row_can.empty else 'NOT FOUND'}")
        if not team_row_can.empty:
            print(f"  Record: {team_row_can.iloc[0].get('Record')}")

    # 3. Analysis
    analysis = load_team_analysis(team_name, model=model)
    print(f"Analysis Stats: {'FOUND' if analysis and analysis.get('stats') else 'MISSING'}")
    if analysis:
        print(f"  Wins: {len(analysis.get('top_wins', []))}")
        print(f"  Losses: {len(analysis.get('worst_losses', []))}")

    # 4. Schedule
    schedule = get_team_schedule(team_name, model=model)
    print(f"Schedule Games: {len(schedule)}")

    # 5. Distribution
    dist = load_rank_distribution(team_name, model=model)
    print(f"Rank Distribution: {len(dist)} rows")

if __name__ == "__main__":
    test_team_page("Michigan State")
    print("\n")
    test_team_page("North Dakota")
    print("\n")
    test_team_page("Minnesota-Duluth")
    print("\n")
    test_team_page("UMass Lowell")
