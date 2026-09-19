import pandas as pd
from src.rankings.npi import NPI

def debug_sos():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit() # Run standard fit first to get ratings
    
    target_team = "Michigan"
    if target_team not in npi.teams:
        print(f"{target_team} not found.")
        return

    ratings = npi.ratings
    team_games = []
    
    # Extract raw games
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == target_team:
            team_games.append({'opponent': row['AwayTeam'], 'wgt': 0.8 if row['Result']==1.0 else 1.2})
        elif row['AwayTeam'] == target_team:
            team_games.append({'opponent': row['HomeTeam'], 'wgt': 1.2 if row['Result']==0.0 else 0.8})

    # Scenario 1: Raw Average of ALL games
    opp_npis = [ratings.get(g['opponent'], 50.0) for g in team_games]
    sos_all_raw = sum(opp_npis) / len(opp_npis)
    
    # Scenario 2: Weighted Average of ALL games
    wgts = [g['wgt'] for g in team_games]
    sos_all_wgt = sum(n*w for n, w in zip(opp_npis, wgts)) / sum(wgts)
    
    print(f"--- SOS Debug for {target_team} ---")
    print(f"Current NPI Output SOS: {npi.details[target_team]['sos']:.4f}")
    print(f"Target SOS: 52.387")
    print(f"Scenario 1 (Raw Avg ALL): {sos_all_raw:.4f}")
    print(f"Scenario 2 (Wgt Avg ALL): {sos_all_wgt:.4f}")

if __name__ == "__main__":
    debug_sos()
