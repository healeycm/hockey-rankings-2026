import pandas as pd
from src.rankings.npi import NPI

def analyze_reference_thresholds():
    # 1. Load Reference NPI Data
    print("Loading Reference NPI Data...")
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    
    # Create a map of Team -> Reference NPI
    ref_npi = {}
    for _, row in ref_df.iterrows():
        # Handle potential team name mismatches if strictly needed, but assuming standard names for now
        team_name = row['Team']
        npi_val = row['NPI']
        ref_npi[team_name] = npi_val
        
    print(f"Loaded {len(ref_npi)} teams from reference.")
    
    # 2. Load Games to get Schedule (who plays whom)
    print("Loading Games...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()

    # We need the NPI logic just for game weights/points, but not for ratings
    npi_sys = NPI(season_df)
    # We don't run fit(), we just want access to the helper 'calculate_game_points' or just the data 
    
    print(f"\n{'='*40}")
    print(f"FULL REMOVAL AUDIT (Reference NPIs)")
    print(f"{'='*40}\n")
    
    sorted_teams = sorted(ref_npi.keys(), key=lambda x: ref_npi[x], reverse=True)
    
    total_wins_removed = 0
    total_losses_removed = 0
    
    for team in sorted_teams:
        if team not in npi_sys.teams: continue
            
        current_npi = ref_npi[team]
        
        # Thresholds
        good_loss_thresh = current_npi / 0.75
        bad_win_thresh = (current_npi - 25.0) / 0.75 if current_npi > 25.0 else 0.0

        team_games = season_df[(season_df['HomeTeam'] == team) | (season_df['AwayTeam'] == team)]
        
        bad_wins = []
        good_losses = []
        
        for _, row in team_games.iterrows():
            if row['HomeTeam'] == team:
                opp = row['AwayTeam']
                is_win = row['Result'] == 1.0
            else:
                opp = row['HomeTeam']
                is_win = row['Result'] == 0.0
                
            if opp not in ref_npi: continue
            
            opp_npi_ref = ref_npi[opp]
            
            if is_win:
                contrib = 25.0 + (0.75 * opp_npi_ref)
                if contrib < current_npi:
                    bad_wins.append((opp, opp_npi_ref, contrib))
            elif not is_win and row['Result'] != 0.5:
                contrib = 0.75 * opp_npi_ref
                if contrib > current_npi:
                    good_losses.append((opp, opp_npi_ref, contrib))

        if bad_wins or good_losses:
             print(f"TEAM: {team} (NPI {current_npi:.2f})")
             if bad_wins:
                 print(f"  BAD WINS (Opp < {bad_win_thresh:.2f}):")
                 for opp, onpi, c in bad_wins:
                     print(f"    - vs {opp} (OppNPI {onpi:.2f}, Contrib {c:.2f})")
                 total_wins_removed += len(bad_wins)
                 
             if good_losses:
                 print(f"  GOOD LOSSES (Opp > {good_loss_thresh:.2f}):")
                 for opp, onpi, c in good_losses:
                     print(f"    - vs {opp} (OppNPI {onpi:.2f}, Contrib {c:.2f})")
                 total_losses_removed += len(good_losses)
             print("-" * 40)
             
    print(f"\nTotal Bad Wins Identified: {total_wins_removed}")
    print(f"Total Good Losses Identified: {total_losses_removed}")

if __name__ == "__main__":
    analyze_reference_thresholds()
