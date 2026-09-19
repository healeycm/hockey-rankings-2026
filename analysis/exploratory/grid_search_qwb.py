import pandas as pd
import numpy as np
from src.rankings.npi_games import NPIGames

def grid_search():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    
    # Finer Grid
    # Hotspot 1 (around 50.5 / 0.45)
    floors = [50.4, 50.5, 50.6, 50.9, 51.0, 51.1]
    mults = [0.44, 0.45, 0.46, 0.54, 0.55, 0.56]
    
    results = []
    
    print(f"\n--- Running Grid Search ({len(floors)*len(mults)} Runs) ---")
    print(f"{'Floor':<6} | {'Mult':<6} | {'MAE':<8} | {'Bias':<8}")
    
    for f in floors:
        for m in mults:
            conf = {'quality_win_base': f, 'quality_win_mult': m, 'qwb_method': 'integrated'}
            npi = NPIGames(season_df, config=conf)
            npi.fit()
            
            # Calc MAE
            calc_data = []
            for team, det in npi.details.items():
                calc_data.append({'Team': team, 'Calc_NPI': det['npi']})
            calc_df = pd.DataFrame(calc_data)
            
            merged = pd.merge(calc_df, ref_df[['Team', 'NPI']], on='Team')
            merged['Diff'] = merged['Calc_NPI'] - merged['NPI']
            mae = merged['Diff'].abs().mean()
            bias = merged['Diff'].mean()
            
            results.append({'floor': f, 'mult': m, 'mae': mae, 'bias': bias})
            print(f"{f:<6.1f} | {m:<6.2f} | {mae:<8.4f} | {bias:<8.4f}")
            
    # Best
    best = sorted(results, key=lambda x: x['mae'])[0]
    print(f"\nBEST CONFIG: Floor {best['floor']}, Mult {best['mult']} -> MAE {best['mae']:.4f}")

if __name__ == "__main__":
    grid_search()
