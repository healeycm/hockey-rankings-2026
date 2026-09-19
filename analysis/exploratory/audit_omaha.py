import pandas as pd
from src.rankings.npi import NPI

def audit_omaha():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    
    # Manually run the points calculation for Omaha
    team = "Omaha"
    omaha_games = []
    
    # Just to double check if I can filter by team first to speed it up?
    # Actually just iterate npi.games
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            omaha_games.append({
                'Date': row['Date'],
                'Opponent': row['AwayTeam'],
                'Venue': 'Home',
                'Type': row['Type'],
                'Result': 'Win' if row['Result'] == 1.0 else 'Loss',
                'Pts': pts,
                'Wgt': wgt
            })
        elif row['AwayTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            omaha_games.append({
                'Date': row['Date'],
                'Opponent': row['HomeTeam'],
                'Venue': 'Away',
                'Type': row['Type'],
                'Result': 'Win' if row['Result'] == 0.0 else 'Loss',
                'Pts': pts,
                'Wgt': wgt
            })
            
    df = pd.DataFrame(omaha_games)
    print("Omaha Game Audit:")
    print(df.to_string(index=False))
    
    total_pts = df['Pts'].sum()
    total_wgt = df['Wgt'].sum()
    raw_adjwp = (total_pts / total_wgt) * 100
    
    print(f"\nTotal Points: {total_pts:.4f}")
    print(f"Total Weight: {total_wgt:.4f}")
    print(f"Raw AdjWP (Pre-removal): {raw_adjwp:.4f}%")
    
    # Fit to see post-removal
    npi.fit()
    if hasattr(npi, 'details') and team in npi.details:
        print(f"Final AdjWP (Post-removal): {npi.details[team]['adj_wp']:.4f}%")

if __name__ == "__main__":
    audit_omaha()
