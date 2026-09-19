import pandas as pd
from src.rankings.npi import NPI

def audit_targets():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    
    targets = {
        "Michigan": 78.803,
        "Denver": 58.841,
        "Augustana": 66.942,
        "St. Cloud State": 53.023,
        "St. Thomas": 66.917,
        "Cornell": 70.465
    }
    
    print(f"{'Team':<20} | {'My AdjWP':<10} | {'Target':<10} | {'Diff':<10}")
    print("-" * 60)
    
    for team, target in targets.items():
        team_games = []
        for idx, row in npi.games.iterrows():
            if row['HomeTeam'] == team:
                pts, wgt = npi._calculate_game_points(row, 'Home')
                team_games.append({'Pts': pts, 'Wgt': wgt})
            elif row['AwayTeam'] == team:
                pts, wgt = npi._calculate_game_points(row, 'Away')
                team_games.append({'Pts': pts, 'Wgt': wgt})
        
        if not team_games:
            print(f"{team:<20} | {'N/A':<10} | {target:<10} | N/A")
            continue
            
        total_pts = sum(g['Pts'] for g in team_games)
        total_wgt = sum(g['Wgt'] for g in team_games)
        my_wp = (total_pts / total_wgt) * 100
        diff = my_wp - target
        
        print(f"{team:<20} | {my_wp:<10.4f} | {target:<10.3f} | {diff:<10.4f}")

if __name__ == "__main__":
    audit_targets()
