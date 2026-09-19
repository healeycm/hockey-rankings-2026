import pandas as pd
from src.rankings.npi import NPI

def print_standings():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    print(f"Loaded {len(games_df)} games total.")
    if 'Is_Exhibition' in games_df.columns:
        print(f"Is_Exhibition values: {games_df['Is_Exhibition'].unique()}")
    print(f"Result values: {games_df['Result'].unique()} Type: {games_df['Result'].dtype}")
    
    season_df = games_df[games_df['Season'] == 20252026].copy()
    print(f"Filtered {len(season_df)} games for 20252026.")
    
    npi = NPI(season_df)
    npi.fit()
    
    # Get rankings
    rankings = npi.get_rankings() 
    print(f"Rankings items: {len(rankings)}")
    if hasattr(rankings, 'head'):
        print(f"Rankings Head:\n{rankings.head()}")
    else:
        print(f"Rankings (first 5): {list(rankings.items())[:5]}")
    
    print(f"Details keys: {len(npi.details)}")
    if npi.details:
        sample_key = list(npi.details.keys())[0]
        print(f"Sample key: {sample_key}")
        print(f"Sample details: {npi.details[sample_key]}")
    
    print(f"\n{'Rank':<4} | {'Team':<25} | {'NPI':<8} | {'Record':<10} | {'AdjWP':<8} | {'SOS':<8} | {'QWB':<8}")
    print("-" * 100)
    
    # Check if rankings is DataFrame
    if hasattr(rankings, 'iterrows'):
        params = rankings.iterrows()
    else:
        # dict
        params = enumerate(rankings.items(), 1)
        
    for idx, data in params:
        if hasattr(rankings, 'iterrows'):
            rank = idx
            team = data['Team']
            rating = data['Rating']
        else:
            rank = idx
            team = data[0]
            rating = data[1]

        if team in ['Team', 'Rating'] or '/' in team: continue 
        details = npi.details.get(team)
        if not details: continue
        
        # Calculate Record
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        wins = 0
        losses = 0
        ties = 0
        for _, row in games.iterrows():
            is_home = row['HomeTeam'] == team
            res = row['Result']
            if not is_home: res = 1.0 - res if res != 0.5 else 0.5
            
            if res == 1.0: wins += 1
            elif res == 0.0: losses += 1
            else: ties += 1
        
        record = f"{wins}-{losses}-{ties}"
        
        # Details
        val_npi = details.get('npi', 0.0)
        val_wp = details.get('raw_adj_wp', 0.0) # Show Raw WP? Or Adjusted? NPI uses Valid WP.
                                                # CHN shows "Win %". Usually Raw.
                                                # But let's show Valid WP as 'AdjWP' for transparency.
                                                # details['adj_wp'] is stored x100 in npi.py.
        val_sos = details.get('sos', 0.0)
        val_qwb = details.get('qwb', 0.0)
        
        print(f"{rank:<4} | {team:<25} | {val_npi:<8.4f} | {record:<10} | {val_wp:<8.4f} | {val_sos:<8.4f} | {val_qwb:<8.4f}")

if __name__ == "__main__":
    print_standings()
