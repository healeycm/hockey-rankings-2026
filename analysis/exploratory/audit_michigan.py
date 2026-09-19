import pandas as pd
from src.rankings.npi import NPI

def audit_michigan():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    
    # Manually run the points calculation for Michigan
    team = "Michigan"
    mich_games = []
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            mich_games.append({
                'Date': row['Date'],
                'Opponent': row['AwayTeam'],
                'Venue': 'Home',
                'Type': row['Type'],
                'Result': 'Win' if row['Result'] == 1.0 else ('Tie' if row['Result'] == 0.5 else 'Loss'),
                'IsOT': row.get('IsOT', False),
                'Pts': pts,
                'Wgt': wgt
            })
        elif row['AwayTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            mich_games.append({
                'Date': row['Date'],
                'Opponent': row['HomeTeam'],
                'Venue': 'Away',
                'Type': row['Type'],
                'Result': 'Win' if row['Result'] == 0.0 else ('Tie' if row['Result'] == 0.5 else 'Loss'),
                'IsOT': row.get('IsOT', False),
                'Pts': pts,
                'Wgt': wgt
            })
            
    df = pd.DataFrame(mich_games)
    print("Michigan Game Audit:")
    print(df.to_string(index=False))
    
    total_pts = df['Pts'].sum()
    total_wgt = df['Wgt'].sum()
    raw_adjwp = (total_pts / total_wgt) * 100
    
    print(f"\nTotal Points: {total_pts:.4f}")
    print(total_wgt)
    print(f"Raw AdjWP (Pre-removal): {raw_adjwp:.4f}%")
    
    # Now run fit with details to see post-removal
    npi.fit()
    if hasattr(npi, 'details') and team in npi.details:
        print(f"Final AdjWP (Post-removal): {npi.details[team]['adj_wp']:.4f}%")
        
        # Re-run the removal logic one last time to see what happens
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        # This is a bit tricky to reconstruct without modifying NPI class to store 'valid_games'
        # But we can look at the counts.
        # Actually, let's just create a temporary helper in NPI? 
        # Or just trust the raw vs final difference.
        
        # Let's verify the "Good Loss" logic assumption.
        # If I change the logic to KEEP all losses, does it approximate the target?
        pass

if __name__ == "__main__":
    audit_michigan()
