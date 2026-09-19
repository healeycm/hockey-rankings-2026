import pandas as pd
import numpy as np
from src.rankings.npi_games import NPIGames

def test_seeds():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    
    # 1. Calculate Adj WP for Seeding
    print("Calculating initial Adjusted WP...")
    # Instantiate just to use helper methods
    helper = NPIGames(season_df)
    
    adj_wps = {}
    for team in helper.teams:
        # Get team games
        team_rows_h = season_df[season_df['HomeTeam'] == team]
        team_rows_a = season_df[season_df['AwayTeam'] == team]
        
        total_pts = 0
        total_wgt = 0
        
        for _, row in team_rows_h.iterrows():
            p, w = helper._calculate_game_points(row, 'Home')
            total_pts += p
            total_wgt += w
            
        for _, row in team_rows_a.iterrows():
            p, w = helper._calculate_game_points(row, 'Away')
            total_pts += p
            total_wgt += w
            
        wp = (total_pts / total_wgt * 100) if total_wgt > 0 else 50.0
        adj_wps[team] = wp
        
    print(f"Calculated Adj WP for {len(adj_wps)} teams.")
    
    # 2. Run with Seed = Adj WP
    print("\n--- Running Seed: Adjusted WP ---")
    npi_wp = NPIGames(season_df)
    npi_wp.fit(initial_ratings=adj_wps)
    
    # Compare
    metrics_wp = evaluate(npi_wp, ref_df)
    print(f"Seed=AdjWP -> MAE: {metrics_wp['mae']:.4f}, RMSE: {metrics_wp['rmse']:.4f}")
    
    # 3. Run with Seed = 51.0
    print("\n--- Running Seed: Flat 51.0 ---")
    npi_51 = NPIGames(season_df)
    npi_51.fit(initial_ratings=51.0)
    
    metrics_51 = evaluate(npi_51, ref_df)
    print(f"Seed=51.0  -> MAE: {metrics_51['mae']:.4f}, RMSE: {metrics_51['rmse']:.4f}")
    
    # 4. Run with Seed = 50.0 (Baseline)
    print("\n--- Running Seed: Flat 50.0 (Baseline) ---")
    npi_50 = NPIGames(season_df)
    npi_50.fit(initial_ratings=50.0)
    
    metrics_50 = evaluate(npi_50, ref_df)
    print(f"Seed=50.0  -> MAE: {metrics_50['mae']:.4f}, RMSE: {metrics_50['rmse']:.4f}")

    # 5. Output Comparison details for Best
    best_npi = npi_wp # Placeholder
    if metrics_51['mae'] < metrics_wp['mae']: best_npi = npi_51
    
    # Print specific diffs for the best one to see if the "RPI bias (-0.44)" is fixed
    print("\nCheck RPI with Best Seed:")
    rpi_val = best_npi.details['RPI']['npi']
    ref_rpi = ref_df[ref_df['Team'] == 'RPI']['NPI'].values[0]
    print(f"RPI: Calc={rpi_val:.4f}, Ref={ref_rpi}, Diff={rpi_val - ref_rpi:.4f}")

def evaluate(model, ref_df):
    results = []
    for team, details in model.details.items():
        results.append({'Team': team, 'Calc_NPI': details['npi']})
    
    df = pd.DataFrame(results)
    merged = pd.merge(df, ref_df, on='Team', how='inner')
    merged['Diff'] = merged['Calc_NPI'] - merged['NPI']
    mae = merged['Diff'].abs().mean()
    rmse = np.sqrt((merged['Diff'] ** 2).mean())
    return {'mae': mae, 'rmse': rmse, 'merged': merged}

if __name__ == "__main__":
    test_seeds()
