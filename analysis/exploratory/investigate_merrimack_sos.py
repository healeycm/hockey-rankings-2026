import pandas as pd
import numpy as np

def investigate_merrimack_sos():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    # Load Reference NPIs
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    ref_npi = {row['Team']: row['NPI'] for _, row in ref_df.iterrows()}
    ref_sos_map = {row['Team']: float(row['SOS']) for _, row in ref_df.iterrows()}
    
    team = "Merrimack"
    target_sos = ref_sos_map[team]
    print(f"\nTarget Merrimack SOS: {target_sos}")
    
    # Get Merrimack Games
    team_games = season_df[(season_df['HomeTeam'] == team) | (season_df['AwayTeam'] == team)]
    
    # Build Dataset
    data = []
    for _, row in team_games.iterrows():
        if row['HomeTeam'] == team:
            opp = row['AwayTeam']
            loc = "Home"
        else:
            opp = row['HomeTeam']
            loc = "Away"
            
        if row['NeutralSite']:
            loc = "Neutral"
            
        if opp not in ref_npi: continue
        
        npi = ref_npi[opp]
        
        # Weights (Hypothetical)
        # Standard: Home=1.0, Away=1.0 (Effective)?
        # Or Home=1.0, Away=1.2?
        # NPI normally weights game RESULTS, but does it weight SOS?
        # Usually NPI SOS is "Average of Opponent NPIs". 
        # But maybe weighted by Game Weight?
        
        # Win/Loss
        is_win = (row['HomeTeam'] == team and row['Result'] == 1.0) or (row['AwayTeam'] == team and row['Result'] == 0.0)
        
        data.append({
            'opp': opp,
            'npi': npi,
            'loc': loc,
            'is_win': is_win,
            'is_ot': row.get('IsOT', False)
        })
        
    opponents = pd.DataFrame(data)
    opponents.sort_values('npi', inplace=True)
    
    # --- Tests ---
    
    # 1. Simple Average (All Games)
    avg_all = opponents['npi'].mean()
    print(f"1. Simple Average (All): {avg_all:.4f} (Diff {avg_all - target_sos:.4f})")
    
    # 2. Weighted Average
    # Scenario A: RPI Weights (Home=0.849, Neutral=1.0, Away=1.195? Or 0.8/1.2?)
    # Let's try standard 0.8 / 1.2
    w_home = 0.8
    w_away = 1.2
    w_neut = 1.0
    
    wgt_sum = 0
    wgt_val_sum = 0
    
    for _, row in opponents.iterrows():
        w = w_neut
        if row['loc'] == 'Home': w = w_home
        elif row['loc'] == 'Away': w = w_away
        
        wgt_sum += w
        wgt_val_sum += row['npi'] * w
        
    wgt_avg = wgt_val_sum / wgt_sum if wgt_sum > 0 else 0
    print(f"2a. Weighted (0.8/1.2): {wgt_avg:.4f} (Diff {wgt_avg - target_sos:.4f})")
    
    # Scenario B: Home=1.0, Away=1.2?
    w_home = 1.0
    w_away = 1.2
    wgt_sum = 0
    wgt_val_sum = 0
    for _, row in opponents.iterrows():
        w = w_neut
        if row['loc'] == 'Home': w = w_home
        elif row['loc'] == 'Away': w = w_away
        wgt_sum += w
        wgt_val_sum += row['npi'] * w
    wgt_avg_b = wgt_val_sum / wgt_sum if wgt_sum > 0 else 0
    print(f"2b. Weighted (1.0/1.2): {wgt_avg_b:.4f} (Diff {wgt_avg_b - target_sos:.4f})")
    
    # 3. Geometric Mean
    from scipy.stats import gmean
    geo_mean = gmean(opponents['npi'])
    print(f"3. Geometric Mean: {geo_mean:.4f} (Diff {geo_mean - target_sos:.4f})")
    
    # 5. Reverse Engineering the 50.80 Value
    # User says "Weighted (H/A) SOS... I get 50.80".
    # This is much lower than 51.66.
    # Hypothesis: Use NPI - QWB Component?
    # QWB Component approx 25% of score?
    # No, QWB in table is the raw points avg? Or component?
    # In table, "QWB" is usually the raw value added.
    # If we strip QWB from NPI, maybe that's what's averaged?
    
    print("\n--- Reverse Engineering 50.80 ---")
    
    opponents['npi_no_qwb'] = opponents.apply(lambda row: ref_npi[row['opp']] - ref_df[ref_df['Team'] == row['opp']]['QWB'].values[0], axis=1)
    
    avg_no_qwb = opponents['npi_no_qwb'].mean()
    print(f"Simple Avg (NPI - QWB): {avg_no_qwb:.4f} (Diff {avg_no_qwb - 50.80:.4f})")
    
    # Weighted Avg (NPI - QWB)
    w_home = 0.8
    w_away = 1.2
    wgt_sum = 0
    wgt_val_sum = 0
    for _, row in opponents.iterrows():
        w = 1.0
        if row['loc'] == 'Home': w = w_home
        elif row['loc'] == 'Away': w = w_away
        wgt_sum += w
        wgt_val_sum += row['npi_no_qwb'] * w
        
    wgt_avg_no_qwb = wgt_val_sum / wgt_sum
    print(f"Weighted Avg (NPI - QWB): {wgt_avg_no_qwb:.4f} (Diff {wgt_avg_no_qwb - 50.80:.4f})")
    
    # Hypothesis: Removing QWB means QWB component, not QWB value.
    # QWB Component = QWB Value / (Games * Base)? No.
    # Let's try to find a weight set NPIs that produces 50.80.
    # 51.66 -> 50.80. Roughly 0.86 drop.
    # Opponents range from 44 to 56.
    # We need to weight the 44-48 group heavily.
    # 44-48 group are mostly AWAY.
    # If Away Weight > Home Weight significantly?
    # Try weighting Away 2.0, Home 1.0?
    
    w_home = 1.0
    w_away = 2.0
    wgt_sum = 0
    wgt_val_sum = 0
    for _, row in opponents.iterrows():
        w = 1.0
        if row['loc'] == 'Home': w = w_home
        elif row['loc'] == 'Away': w = w_away
        wgt_sum += w
        wgt_val_sum += row['npi'] * w
        
    wgt_heavy_away = wgt_val_sum / wgt_sum
    print(f"Heavy Away Weight (1/2): {wgt_heavy_away:.4f} (Diff {wgt_heavy_away - 50.80:.4f})")
    
    # Hypothesis: User calculated weighted average manually and made a mistake?
    # Or maybe "Removing QWB" means excluding games where QWB was earned? (Wins vs top teams?)
    # If we exclude wins vs Top Teams?
    # Exclude Win vs Providence (56.5), QU (55.8), LIU (51.5)?
    
    # Hypothesis: User means "Weighted Average of (Opponent NPI - Opponent QWB)".
    # Reference Table QWB column: e.g. 1.354.
    # Is that component or raw?
    # Let's assume it's component.
    # Try (NPI - QWB) weighted.
    
    # Check if we can find exact match for 50.80 with any subset.
    for k in range(1, 10):
        # Drop k Highest
        s = opponents.sort_values('npi').iloc[:-k]
        v = s['npi'].mean()
        if abs(v - 50.80) < 0.1:
            print(f"Match 50.80: Drop Highest {k} (Avg {v:.4f})")
            
    # Check if "Opponent NPI" in table is BEFORE or AFTER removals?
    # Opponent NPI should be their final NPI.
    
    pass
    for i in range(1, 6):
        subset = opponents.iloc[i:]
        avg = subset['npi'].mean()
        print(f"Drop Lowest {i}: {avg:.4f} (Diff {avg - target_sos:.4f})")
        
    # 4. Drop Highest N (Maybe?)
    print("\n--- Drop Highest N ---")
    for i in range(1, 6):
        subset = opponents.iloc[:-i]
        avg = subset['npi'].mean()
        print(f"Drop Highest {i}: {avg:.4f} (Diff {avg - target_sos:.4f})")
        
    # 5. Drop Extremes (1 High, 1 Low)
    print("\n--- Drop Extremes ---")
    for i in range(1, 4):
        subset = opponents.iloc[i:-i]
        avg = subset['npi'].mean()
        print(f"Drop {i} High & {i} Low: {avg:.4f} (Diff {avg - target_sos:.4f})")
        
    # 6. Weighted by 'Effective Games'?
    # If they played a team twice, does it count twice? (Yes, assumed in dataset)
    
    # 7. Check specific opponents causing skew?
    # Print Schedule
    print("\n--- Full Schedule (Sorted by NPI) ---")
    print(opponents[['opp', 'npi', 'loc', 'is_win']])

if __name__ == "__main__":
    investigate_merrimack_sos()
