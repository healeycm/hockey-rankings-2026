import pandas as pd
from src.rankings.npi import NPI

def audit_stt():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    
    team = "St. Thomas"
    games = []
    
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            games.append({
                'Date': row['Date'],
                'Opponent': row['AwayTeam'],
                'Venue': 'Home',
                'Result': 'Win' if row['Result'] == 1.0 else ('Tie' if row['Result'] == 0.5 else 'Loss'),
                'IsOT': row.get('IsOT', False),
                'Pts': pts,
                'Wgt': wgt
            })
        elif row['AwayTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            games.append({
                'Date': row['Date'],
                'Opponent': row['HomeTeam'],
                'Venue': 'Away',
                'Result': 'Win' if row['Result'] == 0.0 else ('Tie' if row['Result'] == 0.5 else 'Loss'),
                'IsOT': row.get('IsOT', False),
                'Pts': pts,
                'Wgt': wgt
            })
            
    df = pd.DataFrame(games)
    print("St. Thomas Game Audit:")
    print(df.to_string(index=False))
    
    total_pts = df['Pts'].sum()
    total_wgt = df['Wgt'].sum()
    raw_adjwp = (total_pts / total_wgt) * 100 if total_wgt > 0 else 0
    
    print(f"\nTotal Points: {total_pts:.4f}")
    print(f"Total Weight: {total_wgt:.4f}")
    print(f"Current Raw AdjWP: {raw_adjwp:.4f}%")
    print(f"Target: 66.917%")
    
    # Simulation: What if all Reg Ties were 0.5?
    sim_pts = 0
    for idx, row in df.iterrows():
        p = row['Pts']
        if row['Result'] == 'Tie' and not row['IsOT']:
            # Currently 0.4 (Home) or 0.6 (Away). Reset to 0.5.
            p = 0.5
        sim_pts += p
        
    sim_wp = (sim_pts / total_wgt) * 100
    print(f"Simulated Unweighted Reg Ties: {sim_wp:.4f}%")

if __name__ == "__main__":
    audit_stt()
