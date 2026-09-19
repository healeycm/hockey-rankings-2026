import pandas as pd

def investigate_sos():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    # Load Reference NPIs
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    ref_npi = {row['Team']: row['NPI'] for _, row in ref_df.iterrows()}
    
    # Target SOS from Table
    target_sos = 52.387
    print(f"\nTarget Michigan SOS: {target_sos}")
    
    # 1. Get Michigan Games
    team = "Michigan"
    team_games = season_df[(season_df['HomeTeam'] == team) | (season_df['AwayTeam'] == team)]
    
    opponents = []
    for _, row in team_games.iterrows():
        if row['HomeTeam'] == team:
            opp = row['AwayTeam']
            is_win = row['Result'] == 1.0
            pts = 1.0 if is_win else 0.0 # Just raw points for win/loss context
        else:
            opp = row['HomeTeam']
            is_win = row['Result'] == 0.0
            
        if opp in ref_npi:
             # Basic Weight (Conference = 1.0, etc. assuming standard for now or just 1.0)
             # Let's assume weight = 1.0 for simplicity first, then check weighted.
             opponents.append({
                 'opp': opp,
                 'npi': ref_npi[opp],
                 'is_win': is_win
             })
             
    # SCENARIOS
    
    # 1. All Games, Unweighted
    sos_1 = sum(o['npi'] for o in opponents) / len(opponents)
    print(f"1. All Games (Unweighted): {sos_1:.4f} (Diff {sos_1 - target_sos:.4f})")
    
    # 2. All Games, Weighted (Using actual game weights)
    # We need to get the weights.
    # Re-calculate weights based on game type
    wgt_sum = 0
    wgt_npi_sum = 0
    
    # Assuming NPI class logic for weights:
    # Regulation Win/Loss: 1.0 (Home/Away mults are 1.0 for now based on recent findings, check conf)
    # OT Win: ~0.55-0.6? NO, we set it to 1.0 recently? Let's check pure weights.
    # Actually, let's just use the 'wgt' from the game row if we can re-derive it or just standard rules.
    # Standard Rule: Reg/OT games = 1.0. 
    # BUT, what if Weights are applied?
    
    # Let's try Weighted Average with standard 1.0 weights (same as unweighted)
    # Let's try Weighted Average where OT Games = 0.5?
    
    print("\n--- Weighted Scenarios ---")
    ot_games = [o for o in opponents if 'OT' in str(o)] # Need row data for OT
    # We didn't save row data. Let's re-loop.
    
    wgt_npi_sum_ot55 = 0
    wgt_sum_ot55 = 0
    
    for _, row in team_games.iterrows():
        if row['HomeTeam'] == team:
            opp = row['AwayTeam']
        else:
            opp = row['HomeTeam']
            
        if opp not in ref_npi: continue
        
        npi_val = ref_npi[opp]
        is_ot = row['IsOT'] # Assuming IsOT column exists and is populated
        
        # Weight Scenario A: OT = 1.0 (Standard) -> Same as Unweighted
        
        # Weight Scenario B: OT = 0.55 (Old KRAach?)
        w = 1.0
        if is_ot: w = 0.55
        
        wgt_npi_sum_ot55 += npi_val * w
        wgt_sum_ot55 += w
        
    sos_ot55 = wgt_npi_sum_ot55 / wgt_sum_ot55
    print(f"Weighted (OT=0.55): {sos_ot55:.4f} (Diff {sos_ot55 - target_sos:.4f})")
    
    # Check if 'Bad Wins' are removed from SOS but 'Good Losses' kept?
    # Michigan has Bad Wins.
    # Try removing 1 Bad Win, 2 Bad Wins, etc.
    
    print("\n--- Removal Scenarios (Weighted SOS?) ---")
    # Let's try removing games based on Reference NPI strict threshold
    # Bad Win < 47.18
    
    opps_sorted = sorted(opponents, key=lambda x: x['npi'])
    
    # 6. Conference Only SOS?
    conf_opps = [o for o in opponents] # Need row data for conference check. 
    # Let's re-loop and store everything
    full_data = []
    for _, row in team_games.iterrows():
        if row['HomeTeam'] == team:
            opp = row['AwayTeam']
        else:
            opp = row['HomeTeam']
        if opp in ref_npi:
             full_data.append({
                 'opp': opp,
                 'npi': ref_npi[opp],
                 'is_win': (row['Result'] == 1.0 and row['HomeTeam'] == team) or (row['Result'] == 0.0 and row['AwayTeam'] == team),
                 'type': row.get('Type', 'NC'),
                 'is_ot': row.get('IsOT', False),
                 'date': row['Date']
             })
             
    # Conf Only
    conf_subset = [o for o in full_data if o['type'].upper() != 'NC']
    if conf_subset:
        sos_conf = sum(o['npi'] for o in conf_subset) / len(conf_subset)
        print(f"Conference Only SOS (Count {len(conf_subset)}): {sos_conf:.4f} (Diff {sos_conf - target_sos:.4f})")
        
    # Is it dropping the lowest X games regardless of win/loss?
    # Target 52.387
    # All Games 51.966
    
    # Try dropping exactly the games that are 'Bad Wins' based on the Table Logic?
    # Table Logic: Bad Win if Opp < (60.39 - 25)/0.75 = 47.18
    # Michigan has opponent Mercyhurst (41.05).
    # And Robert Morris (46.77).
    # And Notre Dame (46.45).
    # And Ferrish State? No.
    
    # Let's verify which opponents are < 47.18
    low_opps = [o for o in full_data if o['npi'] < 47.18]
    print(f"\nOpponents < 47.18 ({len(low_opps)}):")
    for o in low_opps:
        print(f"  {o['opp']} ({o['npi']}) - Win: {o['is_win']}")
        
    # If we drop ALL of these (Count 16)?
    full_valid = [o for o in full_data if o['npi'] >= 47.18]
    # SOS was 55.3585. Too high.
    
    # What if we only drop the WORST of these?
    # Drop Mercyhurst (2 games)?
    # Drop Mercyhurst + Stonehill?
    
    sorted_all = sorted(full_data, key=lambda x: x['npi'])
    
    print("\n--- Combinatorial Drops ---")
    # Try dropping bottom k games
    for k in range(1, 10):
        s = sorted_all[k:]
        v = sum(o['npi'] for o in s) / len(s)
        if abs(v - target_sos) < 0.05:
             print(f"MATCH FOUND! Drop Bottom {k}: {v:.4f}")
        else:
             print(f"Drop Bottom {k}: {v:.4f}")
             
    # Try dropping bottom k Wins only
    wins_only = [o for o in full_data if o['is_win']]
    losses_only = [o for o in full_data if not o['is_win']]
    wins_sorted = sorted(wins_only, key=lambda x: x['npi'])
    
    for k in range(1, 10):
        kept_wins = wins_sorted[k:]
        combined = kept_wins + losses_only
        v = sum(o['npi'] for o in combined) / len(combined)
        if abs(v - target_sos) < 0.05:
            print(f"MATCH FOUND! Drop Bottom {k} Wins: {v:.4f}")
            
    # Try dropping Non-Conference
    nc_subset = [o for o in full_data if o['type'].upper() == 'NC']
    if nc_subset:
         sos_nc = sum(o['npi'] for o in nc_subset) / len(nc_subset)
         print(f"NC Only SOS: {sos_nc:.4f}")

if __name__ == "__main__":
    investigate_sos()
