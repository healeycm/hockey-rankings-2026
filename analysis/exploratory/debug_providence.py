import pandas as pd
from src.rankings.npi_games import NPIGames

def debug_providence():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi_system = NPIGames(season_df)
    npi_system.fit()
    
    team = 'Providence'
    details = npi_system.details[team]
    print(f"\n--- {team} Analysis ---")
    print(f"Final NPI: {details['npi']}")
    print(f"Dropped Losses: {details['dropped_losses']}")
    
    # We need to access the internal game list or reconstruct it
    # Rerun the loop logic for Providence using final ratings
    
    # Rebuild team games
    current_ratings = npi_system.ratings
    
    # Copy-paste logic from fit()
    h_games = season_df[season_df['HomeTeam'] == team]
    a_games = season_df[season_df['AwayTeam'] == team]
    
    games = []
    
    # Process Home Games
    for _, row in h_games.iterrows():
        opp = row['AwayTeam']
        h_pts, h_wgt = npi_system._calculate_game_points(row, 'Home')
        opp_npi = current_ratings.get(opp, 50)
        game_result_score = (h_pts / h_wgt) * 100 if h_wgt > 0 else 0
        bonus = 0.0
        if row['Result'] == 1.0 and opp_npi > 51.0:
            bonus = (opp_npi - 51.0) * 0.5
        
        game_npi = (game_result_score * 0.25) + (opp_npi * 0.75) + bonus
        games.append({
            'opponent': opp, 'result': row['Result'], 'is_win': row['Result']==1.0, 
            'pts': h_pts, 'wgt': h_wgt, 'game_result_score': game_result_score,
            'game_npi': game_npi, 'opp_npi': opp_npi
        })
        
    # Process Away Games
    for _, row in a_games.iterrows():
        opp = row['HomeTeam']
        a_pts, a_wgt = npi_system._calculate_game_points(row, 'Away')
        opp_npi = current_ratings.get(opp, 50)
        game_result_score = (a_pts / a_wgt) * 100 if a_wgt > 0 else 0
        bonus = 0.0
        # Away Win Result=0.0
        is_win = row['Result'] == 0.0
        if is_win and opp_npi > 51.0:
            bonus = (opp_npi - 51.0) * 0.5
            
        game_npi = (game_result_score * 0.25) + (opp_npi * 0.75) + bonus
        games.append({
            'opponent': opp, 'result': row['Result'], 'is_win': is_win, 
            'pts': a_pts, 'wgt': a_wgt, 'game_result_score': game_result_score,
            'game_npi': game_npi, 'opp_npi': opp_npi
        })

    losses = [g for g in games if not g['is_win']]
    
    print("\n--- Losses Analysis ---")
    for l in losses:
        flag = ""
        # Filter Logic Check
        # Check pure loss
        if l['game_result_score'] == 0 and l['game_npi'] > details['npi']:
            flag = " [DROPPED]"
        
        print(f"Vs {l['opponent']}: Score={l['game_result_score']:.1f}, OppNPI={l['opp_npi']:.4f}, GameNPI={l['game_npi']:.4f}{flag}")
        if flag:
            print(f"   -> Dropped because {l['game_npi']:.4f} > {details['npi']:.4f} and Score==0")
            print(f"   -> Math Check: ({l['game_result_score']}*0.25) + ({l['opp_npi']}*0.75) = {l['game_npi']}")

if __name__ == "__main__":
    debug_providence()
