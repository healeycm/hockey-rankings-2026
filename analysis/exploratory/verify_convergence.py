import pandas as pd
import numpy as np
from src.rankings.npi import NPI

def verify_convergence():
    # 1. Load Reference Data
    print("Loading Reference NPIs...")
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    ref_npi = {}
    for _, row in ref_df.iterrows():
        ref_npi[row['Team']] = float(row['NPI'])
        
    # 2. Load Games
    print("Loading Games...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    # 3. Initialize NPI
    npi = NPI(season_df)
    
    # 4. Fit with Seeding (1 Iteration to check immediate stability)
    print("Running Single Iteration with Seeded Values...")
    npi.fit(max_iterations=1, initial_ratings=ref_npi)
    
    # 5. Compare
    print(f"\n{'Team':<25} | {'Ref NPI':<8} | {'Calc NPI':<8} | {'Delta':<8}")
    print("-" * 60)
    
    total_error = 0.0
    count = 0
    max_delta = 0.0
    max_delta_team = ""
    
    sorted_teams = sorted(ref_npi.keys(), key=lambda x: ref_npi[x], reverse=True)
    
    for team in sorted_teams:
        if team not in npi.ratings: continue
        
        ref_val = ref_npi[team]
        calc_val = npi.ratings[team]
        delta = calc_val - ref_val
        
        total_error += abs(delta)
        count += 1
        if abs(delta) > max_delta:
            max_delta = abs(delta)
            max_delta_team = team
            
        print(f"{team:<25} | {ref_val:6.4f}   | {calc_val:6.4f}   | {delta:+.4f}")
        
    print("-" * 60)
    mae = total_error / count if count > 0 else 0
    print(f"Mean Absolute Error: {mae:.6f}")
    print(f"Max Delta: {max_delta:.6f} ({max_delta_team})")
    
    if mae < 0.005: 
        print("\n[SUCCESS] System effectively stable using Reference Data.")
    else:
        print("\n[WARNING] System moved from Reference Data. Logic mismatch possible.")

if __name__ == "__main__":
    verify_convergence()
