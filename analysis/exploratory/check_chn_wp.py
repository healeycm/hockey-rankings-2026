import pandas as pd
import numpy as np
from src.rankings.npi import NPI

def check_rankings():
    # Load local games
    games_df = pd.read_csv('data/processed/games_archive.csv')
    
    # Run NPI for current season
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)
    npi.fit()
    
    # Extract details
    results = []
    
    # Pre-calculate records for display
    # (Since NPI object has games, we can iterate them)
    records = {}
    for team in npi.teams:
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        wins = 0
        losses = 0
        ties = 0
        ot_wins = 0
        ot_losses = 0
        
        for _, row in games.iterrows():
             is_home = row['HomeTeam'] == team
             res = row['Result']
             if not is_home: res = 1.0 - res if res != 0.5 else 0.5
             
             is_ot = row.get('IsOT', False)
             
             if res == 1.0:
                 wins += 1
                 if is_ot: ot_wins += 1
             elif res == 0.0:
                 losses += 1
                 if is_ot: ot_losses += 1
             else:
                 ties += 1
                 
        rec_str = f"{wins}-{losses}-{ties}"
        if ot_wins > 0 or ot_losses > 0:
            rec_str += f" ({ot_wins}-{ot_losses})"
        records[team] = rec_str

    for team, details in npi.details.items():
        results.append({
            'Team': team,
            'Record': records.get(team, "0-0-0"),
            'NPI': details['npi'],
            'WP': details.get('raw_adj_wp', details['adj_wp']), # Request asks for Weighted Win %. Display Raw.
            'SOS': details['sos'],
            'QWB': details['qwb']
        })
    
    df = pd.DataFrame(results).sort_values('NPI', ascending=False)
    
    # Reorder columns
    df = df[['Team', 'Record', 'NPI', 'WP', 'SOS', 'QWB']]
    
    print("NPI Rankings and Components (Top 20):")
    # Format for readability
    pd.options.display.float_format = '{:,.4f}'.format
    pd.options.display.max_columns = 10
    pd.options.display.width = 1000
    print(df.head(20).to_string(index=False))
    
    print("\nTarget Team Verification:")
    targets = ["Michigan", "Michigan State", "North Dakota", "Cornell"]
    target_df = df[df['Team'].isin(targets)]
    print(target_df.to_string(index=False))
    
    print("\nManual Verification Steps:")
    print("1. Compare columns with CHN: https://www.collegehockeynews.com/ratings/npi")


if __name__ == "__main__":
    check_rankings()
