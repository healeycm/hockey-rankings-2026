import pandas as pd
from src.rankings.npi import NPI

def test_weighted_sos():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    npi.fit()
    
    targets = {
        'Michigan': 52.387,
        'Michigan State': 51.897,
        'North Dakota': 52.793, # Target from CHN
        'Penn State': 52.261,
        'Denver': 53.644
    }
    
    print(f"{'Team':<20} | {'Raw SOS':<8} | {'Wgt SOS':<8} | {'Target':<8} | {'Diff Raw':<8} | {'Diff Wgt':<8}")
    print("-" * 80)
    
    for team, target in targets.items():
        if team not in npi.teams: continue
        
        # Get Valid Games (Optimized Subset)
        # Note: fit() stores 'sos' in details. 
        # But we want to check if that 'sos' (which I implemented as Unweighted recently?) 
        # matches the Target if we calculate it Weighted.
        # Or if we calculate Weighted SOS on ALL games?
        
        # Let's check both:
        # 1. Weighted SOS of Optimized Games.
        # 2. Weighted SOS of All Games.
        
        # Re-construct games lists
        # We need to access npi.details or re-run removal logic?
        # fit() has finished. npi.details['sos'] is the value from the last iteration.
        # Currently npi.py uses Unweighted SOS.
        
        # Let's manually calculate Weighted/Unweighted for ALL games first.
        
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        opp_npis = []
        weights = []
        
        for _, row in games.iterrows():
            opp = row['AwayTeam'] if row['HomeTeam'] == team else row['HomeTeam']
            opp_npi = npi.details[opp]['npi']
            
            is_home = row['HomeTeam'] == team
            res = row['Result'] # 1.0, 0.0, 0.5
            if not is_home: res = 1.0 - res if res != 0.5 else 0.5
            is_ot = row.get('IsOT', False)
            
            wgt = 1.0
            if is_ot: wgt = 1.0
            else:
                if res == 1.0: wgt = 0.8 if is_home else 1.2
                elif res == 0.0: wgt = 1.2 if is_home else 0.8
                else: wgt = 1.0
                
            opp_npis.append(opp_npi)
            weights.append(wgt)
            
        raw_sos = sum(opp_npis) / len(opp_npis)
        wgt_sos = sum(n * w for n, w in zip(opp_npis, weights)) / sum(weights)
        
        print(f"{team:<20} | {raw_sos:<8.4f} | {wgt_sos:<8.4f} | {target:<8.4f} | {raw_sos-target:<8.4f} | {wgt_sos-target:<8.4f}")

if __name__ == "__main__":
    test_weighted_sos()
