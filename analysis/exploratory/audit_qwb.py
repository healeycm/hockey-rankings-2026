import pandas as pd
from src.rankings.npi import NPI

def audit_qwb():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    npi.fit() # Run the iterations to get final NPIs
    
    targets = {
        "Michigan": 1.354,
        "Michigan State": 0.897
    }
    
    print(f"{'Team':<20} | {'Opponent':<20} | {'Opp NPI':<10} | {'Bonus Raw':<10}")
    print("-" * 70)
    
    for team in targets:
        details = npi.details[team]
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        
        # Weighted Raw SOS?
        # Sum(OppNPI * Wgt) / Sum(Wgt)
        sos_wgt_num = 0.0
        sos_wgt_den = 0.0
        
        total_bonus = 0.0
        total_bonus_wgt = 0.0
        # Check Wins
        wins = []
        for _, row in games.iterrows():
            is_home = row['HomeTeam'] == team
            res = row['Result']
            if not is_home: res = 1.0 - res if res != 0.5 else 0.5
            
            if res == 1.0: # Win
                opp = row['AwayTeam'] if is_home else row['HomeTeam']
                opp_npi = npi.details[opp]['npi']
                
                # Check QWB logic from npi.py:
                # bonus = max(0, (opp_npi - 51.0) * 0.5) ??
                # Current code in npi.py uses self.conf['qwb_base'] etc.
                # Let's verify what the code actually does by calculating it here manually
                # mirroring expected logic.
                
                # Formula: (OppNPI - 51) * Factor?
                # User said: "QWB - 51... QW Multiplier - 0.5"
                # But typically RPI QWB is slightly different. Let's see what fits.
                
                if opp_npi > 51.0:
                    bonus_raw = (opp_npi - 51.0) * 0.5
                    
                    # Calculate Win Weight
                    is_ot = row.get('IsOT', False)
                    if is_ot:
                        wgt = 1.0
                    else:
                        wgt = 0.8 if is_home else 1.2
                        
                    bonus_wgt = bonus_raw * wgt
                    
                    wins.append({
                        'Opponent': opp,
                        'OppNPI': opp_npi,
                        'Bonus': bonus_raw,
                        'Wgt': wgt,
                        'BonusWgt': bonus_wgt
                    })
                    total_bonus += bonus_raw
                    total_bonus_wgt += bonus_wgt

        # Sort wins by bonus
        wins.sort(key=lambda x: x['Bonus'], reverse=True)
        
        for w in wins:
            print(f"{team:<20} | {w['Opponent']:<20} | {w['OppNPI']:<10.4f} | {w['Bonus']:<10.4f} | {w['BonusWgt']:<10.4f}")
            
        # Denominator
        total_weight = 0.0
        for _, row in games.iterrows():
             is_home = row['HomeTeam'] == team
             res = row['Result']
             if not is_home: res = 1.0 - res if res != 0.5 else 0.5
             is_ot = row.get('IsOT', False)
             if is_ot: wgt = 1.0
             else:
                 if res == 1.0: wgt = 0.8 if is_home else 1.2
                 elif res == 0.0: wgt = 1.2 if is_home else 0.8
                 else: 
                     # Ties are weighted
                     # To be safe, re-derive multiplier or fix to 1.0? 
                     # Ties in NPI calc use 1.0 weight for QWB denom? 
                     # Let's stick to 1.0 for now.
                     wgt = 1.0
             
             total_weight += wgt
             
             opp = row['AwayTeam'] if row['HomeTeam'] == team else row['HomeTeam']
             opp_npi = npi.details[opp]['npi']
             sos_wgt_num += opp_npi * wgt
             sos_wgt_den += wgt
             
        if sos_wgt_den > 0:
            raw_sos_wgt = sos_wgt_num / sos_wgt_den
        else:
            raw_sos_wgt = 0.0
            
        # Calculate Raw SOS (Unweighted)
        all_opp_npis = []
        for _, row in games.iterrows():
            opp = row['AwayTeam'] if row['HomeTeam'] == team else row['HomeTeam']
            all_opp_npis.append(npi.details[opp]['npi'])
        raw_sos = sum(all_opp_npis) / len(all_opp_npis) if all_opp_npis else 0.0
            
        my_qwb = total_bonus / total_weight if total_weight > 0 else 0
        my_qwb_wgt = total_bonus_wgt / total_weight if total_weight > 0 else 0

        
        print(f"{team:<20} | Raw QWB: {my_qwb:.4f} | Wgt QWB: {my_qwb_wgt:.4f} | Target: {targets[team]}")
        print(f"SOS Analysis | Raw: {raw_sos:.4f} | Wgt: {raw_sos_wgt:.4f} | Current Optimized: {details['sos']:.4f} | Target SOS: {52.387 if team == 'Michigan' else 51.897}")
        print("-" * 70)

if __name__ == "__main__":
    audit_qwb()
