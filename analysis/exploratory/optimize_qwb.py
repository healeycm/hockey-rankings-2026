import pandas as pd
from src.rankings.npi_games import NPIGames

def run_experiment():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    configs = [
        {'name': 'Baseline (51/0.5)', 'quality_win_base': 51.0, 'quality_win_mult': 0.5, 'qwb_method': 'integrated'},
        {'name': 'High Bar (53/0.8)', 'quality_win_base': 53.0, 'quality_win_mult': 0.8, 'qwb_method': 'integrated'},
        {'name': 'Low Bar (49/0.3)', 'quality_win_base': 49.0, 'quality_win_mult': 0.3, 'qwb_method': 'integrated'},
        {'name': 'Additive (Simple Avg)', 'quality_win_base': 51.0, 'quality_win_mult': 0.5, 'qwb_method': 'additive'},
    ]
    
    results = {}
    
    for conf in configs:
        print(f"\nRunning {conf['name']}...")
        npi = NPIGames(season_df, config=conf)
        npi.fit()
        
        # Extract Rankings
        ranks = []
        for team, det in npi.details.items():
            ranks.append({'Team': team, 'NPI': det['npi']})
        
        df = pd.DataFrame(ranks).sort_values('NPI', ascending=False).reset_index(drop=True)
        df['Rank'] = df.index + 1
        results[conf['name']] = df
        
    # Compare
    baseline = results['Baseline (51/0.5)']
    print("\n--- Top 20 Comparison ---")
    
    # Merge all
    merged = baseline[['Team', 'Rank', 'NPI']].rename(columns={'Rank': 'Base_Rank', 'NPI': 'Base_NPI'})
    
    for conf in configs[1:]:
        name = conf['name']
        res = results[name][['Team', 'Rank', 'NPI']].rename(columns={'Rank': f"{name}_Rank", 'NPI': f"{name}_NPI"})
        merged = pd.merge(merged, res, on='Team')
        
    print(merged.head(20).to_string(index=False))
    
    # Highlights
    print("\n--- Major Movers (vs Baseline) ---")
    for conf in configs[1:]:
        name = conf['name']
        merged[f'{name}_Change'] = merged['Base_Rank'] - merged[f'{name}_Rank']
        
        print(f"\n{name} Movers:")
        movers = merged.iloc[:20].sort_values(f'{name}_Change', key=abs, ascending=False).head(5)
        print(movers[['Team', 'Base_Rank', f'{name}_Rank', f'{name}_Change']].to_string(index=False))

    # Save
    merged.to_csv('data/processed/qwb_experiment_results.csv', index=False)

if __name__ == "__main__":
    run_experiment()
