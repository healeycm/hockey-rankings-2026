import pandas as pd
from src.rankings.npi import NPI

def audit_good_losses():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit()
    
    print(f"\n{'Team':<25} | {'NPI':<6} | {'Losses':<6} | {'Dropped':<7} | {'% Dropped':<9}")
    print("-" * 70)
    
    count_teams_with_drops = 0
    total_losses_dropped = 0
    
    sorted_teams = sorted(npi.teams, key=lambda x: npi.ratings.get(x, 0), reverse=True)
    
    for team in sorted_teams:
        team_npi = npi.ratings[team]
        
        # Re-run removal logic to see what happens
        # Note: We need to access the games list. npi.games is all games.
        # We need to filter for this team.
        
        team_games = []
        for idx, row in npi.games.iterrows():
            if row['HomeTeam'] == team:
                pts, wgt = npi._calculate_game_points(row, 'Home')
                opp = row['AwayTeam']
                is_win = row['Result'] == 1.0
            elif row['AwayTeam'] == team:
                pts, wgt = npi._calculate_game_points(row, 'Away')
                opp = row['HomeTeam']
                is_win = row['Result'] == 0.0
            else:
                 continue # Should not happen
            
            if not is_win and row['Result'] != 0.5: # Loss
                team_games.append({
                    'opponent': opp,
                    'pts': pts,
                    'wgt': wgt,
                    'opp_npi': npi.ratings.get(opp, 0)
                })

        num_losses = len(team_games)
        if num_losses == 0: continue
        
        dropped = 0
        for g in team_games:
            # Formula: (0.25 * WP) + (0.75 * OppNPI)
            # WP for Loss = 0.
            contrib = 0.75 * g['opp_npi']
            
            # Logic: Remove if Contrib > Team NPI
            if contrib > team_npi:
                dropped += 1
                # Print detail for first few
                if count_teams_with_drops < 5:
                    print(f"  [DROP] vs {g['opponent']} (NPI {g['opp_npi']:.2f}) -> Contrib {contrib:.2f} > {team_npi:.2f}")

        if dropped > 0:
            count_teams_with_drops += 1
            total_losses_dropped += dropped
            print(f"{team:<25} | {team_npi:<6.2f} | {num_losses:<6} | {dropped:<7} | {dropped/num_losses:<9.1%}")

    print("-" * 70)
    print(f"Total Teams with Good Losses Removed: {count_teams_with_drops}")
    print(f"Total Losses Dropped: {total_losses_dropped}")

if __name__ == "__main__":
    audit_good_losses()
