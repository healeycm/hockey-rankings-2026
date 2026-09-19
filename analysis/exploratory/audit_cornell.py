import pandas as pd
from src.rankings.npi import NPI

def audit_cornell():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    
    team = "Cornell"
    cornell_games = []
    
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == team:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            cornell_games.append({
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
            cornell_games.append({
                'Date': row['Date'],
                'Opponent': row['HomeTeam'],
                'Venue': 'Away',
                'Type': row['Type'],
                'Result': 'Win' if row['Result'] == 0.0 else ('Tie' if row['Result'] == 0.5 else 'Loss'),
                'IsOT': row.get('IsOT', False),
                'Pts': pts,
                'Wgt': wgt
            })
            
    df = pd.DataFrame(cornell_games)
    print("Cornell Game Audit:")
    print(df.to_string(index=False))
    
    total_pts = df['Pts'].sum()
    total_wgt = df['Wgt'].sum()
    raw_adjwp = (total_pts / total_wgt) * 100
    
    print(f"\nTotal Points: {total_pts:.4f}")
    print(f"Total Weight: {total_wgt:.4f}")
    print(f"Raw AdjWP (My Calc): {raw_adjwp:.4f}%")
    print(f"Target AdjWP: 70.465%")

if __name__ == "__main__":
    audit_cornell()
