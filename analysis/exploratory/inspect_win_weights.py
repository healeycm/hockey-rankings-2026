import pandas as pd
from src.rankings.npi import NPI

def inspect_weights():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    npi.fit()
    
    # List of teams to check (Top 10ish)
    targets = [
        "Michigan", "Michigan State", "North Dakota", "Penn State", "Western Michigan", # Should remove
        "Quinnipiac", "Minnesota Duluth", "Providence", "Cornell", "Wisconsin" # Should NOT remove?
    ]
    
    print(f"{'Team':<20} | {'RawWins':<8} | {'WgtWins':<8} | {'AvgWgt':<8}")
    print("-" * 60)
    
    for team in targets:
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        
        wins = []
        for _, row in games.iterrows():
            is_home = row['HomeTeam'] == team
            res = row['Result']
            if not is_home: res = 1.0 - res if res != 0.5 else 0.5
            is_ot = row.get('IsOT', False)
            
            if res == 1.0: # Win
                if is_ot: wgt = 1.0
                else: wgt = 0.8 if is_home else 1.2
                wins.append(wgt)
                
        tot_wgt = sum(wins)
        count = len(wins)
        avg = tot_wgt / count if count > 0 else 0
        
        print(f"{team:<20} | {count:<8} | {tot_wgt:<8.4f} | {avg:<8.4f}")

if __name__ == "__main__":
    inspect_weights()
