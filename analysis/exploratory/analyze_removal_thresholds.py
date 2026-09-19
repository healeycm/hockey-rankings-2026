import pandas as pd
from src.rankings.npi import NPI

def analyze_thresholds():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit()
    
    print(f"{'Team':<25} | {'NPI':<8} | {'Good Loss If Opp >':<20} | {'Bad Win If Opp <':<20}")
    print("-" * 80)
    
    # Sort teams by NPI
    sorted_teams = sorted(npi.teams, key=lambda x: npi.ratings[x], reverse=True)
    
    for team in sorted_teams:
        current_npi = npi.ratings[team]
        
        # Good Loss Threshold: Opp_NPI > Team_NPI / 0.75
        good_loss_thresh = current_npi / 0.75
        
        # Bad Win Threshold: 25 + 0.75 * Opp_NPI < Team_NPI
        # 0.75 * Opp_NPI < Team_NPI - 25
        # Opp_NPI < (Team_NPI - 25) / 0.75
        if current_npi > 25.0:
            bad_win_thresh = (current_npi - 25.0) / 0.75
        else:
            bad_win_thresh = 0.0 # Impossible to have a bad win if NPI < 25 (since min win contrib is 25)
            
        print(f"{team:<25} | {current_npi:6.2f}   | {good_loss_thresh:6.2f}               | {bad_win_thresh:6.2f}")

if __name__ == "__main__":
    analyze_thresholds()
