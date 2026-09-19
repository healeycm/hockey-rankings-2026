import pandas as pd
from src.rankings.npi import NPI

def check_sos_scenarios():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    # We need to manually calculate SOS for Michigan using Reference NPIs of opponents
    # because SOS depends on Opponent Ratings.
    
    # Load Reference NPIs
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    ref_npi = {row['Team']: row['NPI'] for _, row in ref_df.iterrows()}
    
    # Michigan Games
    team = "Michigan"
    team_games = season_df[(season_df['HomeTeam'] == team) | (season_df['AwayTeam'] == team)]
    
    opponents = []
    for _, row in team_games.iterrows():
        if row['HomeTeam'] == team:
            opp = row['AwayTeam']
            is_win = row['Result'] == 1.0
        else:
            opp = row['HomeTeam']
            is_win = row['Result'] == 0.0
            
        if opp in ref_npi:
             opponents.append({
                 'opp': opp,
                 'npi': ref_npi[opp],
                 'is_win': is_win
             })
             
    # Scenario 1: All Games SOS
    sos_all = sum(o['npi'] for o in opponents) / len(opponents)
    print(f"Scenario 1: All Games SOS (Count {len(opponents)}): {sos_all:.4f}")
    
    # Scenario 2: Current Logic removals
    # Bad Win: Opp < (60.39 - 25)/0.75 = 47.18
    valid_scen2 = [o for o in opponents if not (o['is_win'] and o['npi'] < 47.18)]
    sos_scen2 = sum(o['npi'] for o in valid_scen2) / len(valid_scen2)
    print(f"Scenario 2: Valid Games SOS (Threshold 47.18) (Count {len(valid_scen2)}): {sos_scen2:.4f}")
    
    # Compare with Reference SOS
    ref_sos = 52.387
    print(f"\nReference SOS: {ref_sos}")
    
    if abs(sos_all - ref_sos) < 0.1:
        print("MATCH: Reference uses ALL GAMES SOS.")
    elif abs(sos_scen2 - ref_sos) < 0.1:
         print("MATCH: Reference uses VALID GAMES SOS.")
    else:
        print("MISMATCH: Reference uses unknown logic.")

if __name__ == "__main__":
    check_sos_scenarios()
