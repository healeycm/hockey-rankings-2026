import pandas as pd
import numpy as np
from src.rankings.npi import NPI

def analyze_margins():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    # Run simple fit first to serve as baseline? 
    # Actually we need to hook into the iterative process or simulate it.
    # Simulating based on final NPIs is easiest approximation.
    
    npi = NPI(season_df)
    npi.fit()
    ratings = npi.ratings
    
    removed_wins_deltas = []
    removed_losses_deltas = []
    
    print("\n--- Removal Margin Analysis ---")
    
    for team in npi.teams:
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        current_npi = ratings[team]
        
        team_games = []
        for _, row in games.iterrows():
             if row['HomeTeam'] == team:
                 pts, wgt = npi._calculate_game_points(row, 'Home')
                 opp = row['AwayTeam']
                 is_win = row['Result'] == 1.0
             else:
                 pts, wgt = npi._calculate_game_points(row, 'Away')
                 opp = row['HomeTeam']
                 is_win = row['Result'] == 0.0
             
             opp_npi = ratings[opp]
             game_wp = (pts / wgt) * 100
             contrib = (0.25 * game_wp) + (0.75 * opp_npi)
             
             delta = contrib - current_npi # Positive = Good Game, Negative = Bad Game
             
             if is_win:
                 # Current Logic: Remove if Contrib < NPI (Delta < 0)
                 if delta < 0:
                     removed_wins_deltas.append(delta)
             else:
                 # LOSS
                 # Current Logic: Remove if Contrib > NPI (Delta > 0)
                 # Wait, logic in npi.py is "kept_losses = [l for l in losses if l['contrib'] <= current_npi]"
                 # So we REMOVE if contrib > current_npi (Delta > 0)
                 if delta > 0:
                     removed_losses_deltas.append(delta)

    # Analyze Wins
    wins_df = pd.DataFrame(removed_wins_deltas, columns=['delta'])
    print(f"\nTotal Bad Wins Removed (Strict 0.0 Margin): {len(wins_df)}")
    print("Distribution of how 'Bad' these wins were (NPI points below average):")
    print(f"  Start Range: {wins_df['delta'].max():.2f} (Closest to keeping)")
    print(f"  End Range:   {wins_df['delta'].min():.2f} (Worst win)")
    
    thresholds = [-0.5, -1.0, -2.0, -3.0, -4.0, -5.0]
    for t in thresholds:
        # If we set margin to T (e.g. -2.0), we only remove if Delta < -2.0.
        # So we SAVE games where Delta >= -2.0
        saved = len(wins_df[wins_df['delta'] >= t])
        pct = (saved / len(wins_df)) * 100 if len(wins_df) > 0 else 0
        print(f"  Margin {t}: Would SAVE {saved} wins ({pct:.1f}%)")

    # Analyze Losses
    losses_df = pd.DataFrame(removed_losses_deltas, columns=['delta'])
    print(f"\nTotal Good Losses Removed (Strict 0.0 Margin): {len(losses_df)}")
    print("Distribution of how 'Good' these losses were (NPI points above average):")
    if not losses_df.empty:
        print(f"  Start Range: {losses_df['delta'].min():.2f} (Closest to keeping)")
        print(f"  End Range:   {losses_df['delta'].max():.2f} (Best loss)")
    
    thresholds = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    for t in thresholds:
        # If we set margin to T (e.g. 2.0), we only remove if Delta > 2.0.
        # So we SAVE games where Delta <= 2.0
        saved = len(losses_df[losses_df['delta'] <= t])
        pct = (saved / len(losses_df)) * 100 if len(losses_df) > 0 else 0
        print(f"  Margin {t}: Would SAVE {saved} losses ({pct:.1f}%)")

if __name__ == "__main__":
    analyze_margins()
