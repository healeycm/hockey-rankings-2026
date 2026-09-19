import pandas as pd
from src.rankings.npi_games import NPIGames

def debug_quinnipiac():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi_system = NPIGames(season_df)
    npi_system.fit()
    
    team = 'Quinnipiac'
    details = npi_system.details[team]
    print(f"\n--- {team} Analysis ---")
    print(f"Final NPI: {details['npi']}")
    print(f"Dropped Wins: {details['dropped_wins']}")
    
    current_ratings = npi_system.ratings
    
    # Reconstruct Game List for QU
    h_games = season_df[season_df['HomeTeam'] == team]
    a_games = season_df[season_df['AwayTeam'] == team]
    
    games = []
    
    for _, row in h_games.iterrows():
        opp = row['AwayTeam']
        h_pts, h_wgt = npi_system._calculate_game_points(row, 'Home')
        opp_npi = current_ratings.get(opp, 50)
        game_result_score = (h_pts / h_wgt) * 100 if h_wgt > 0 else 0
        bonus = 0.0
        if row['Result'] == 1.0 and opp_npi > 51.0:
            bonus = (opp_npi - 51.0) * 0.5
        game_npi = (game_result_score * 0.25) + (opp_npi * 0.75) + bonus
        games.append({'opp': opp, 'is_win': row['Result']==1.0, 'game_npi': game_npi, 'opp_npi': opp_npi})
        
    for _, row in a_games.iterrows():
        opp = row['HomeTeam']
        a_pts, a_wgt = npi_system._calculate_game_points(row, 'Away')
        opp_npi = current_ratings.get(opp, 50)
        is_win = row['Result'] == 0.0
        game_result_score = (a_pts / a_wgt) * 100 if a_wgt > 0 else 0
        bonus = 0.0
        if is_win and opp_npi > 51.0:
            bonus = (opp_npi - 51.0) * 0.5
        game_npi = (game_result_score * 0.25) + (opp_npi * 0.75) + bonus
        games.append({'opp': opp, 'is_win': is_win, 'game_npi': game_npi, 'opp_npi': opp_npi})
        
    wins = sorted([g for g in games if g['is_win']], key=lambda x: x['game_npi'], reverse=True)
    
    print(f"\nTotal Wins: {len(wins)}")
    print(f"Quinnipiac NPI: {details['npi']:.4f}")
    print("\n--- All Wins (Sorted) ---")
    for i, w in enumerate(wins):
        status = "KEPT"
        if w['game_npi'] < details['npi']:
            status = "BELOW AVG (Risk)"
        # Note: Actual drop logic is iterative.
        # But generally, anything significantly below NPI is dropped if > 12 wins.
        print(f"{i+1}. vs {w['opp']}: GameNPI={w['game_npi']:.4f} (OppNPI={w['opp_npi']:.4f}) - {status}")

if __name__ == "__main__":
    debug_quinnipiac()
