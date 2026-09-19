import pandas as pd
from src.rankings.npi import NPI

def audit_removals():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    npi = NPI(season_df)
    npi.fit()
    
    # We need to hook into the removal logic or re-calculate it to count.
    # Since fit() already ran, 'npi.details[team]['sos']' is based on valid games.
    # But npi.details doesn't store the counts of removed games directly unless we modify npi.py.
    # So we will re-simulate the removal logic here.
    
    print(f"{'Team':<25} | {'NPI':<8} | {'TotWins':<8} | {'KeptWins':<8} | {'BadWinsRemoved':<14} | {'TotLoss':<8} | {'KeptLoss':<8} | {'GoodLossRemoved':<15}")
    print("-" * 120)
    
    stats = []
    
    for team in npi.teams:
        rating = npi.details[team]['npi']
        
        # Re-calc games
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        wins = []
        losses = []
        
        for _, row in games.iterrows():
            is_home = row['HomeTeam'] == team
            res = row['Result']
            if not is_home: res = 1.0 - res if res != 0.5 else 0.5
            is_ot = row.get('IsOT', False)
            
            # Wgt logic
            if is_ot: wgt = 1.0
            else:
                if res == 1.0: wgt = 0.8 if is_home else 1.2
                elif res == 0.0: wgt = 1.2 if is_home else 0.8
                else: 
                     # Weighted ties
                     mult = 0.8 if is_home else 1.2
                     wgt = 1.0 
            
            # Pts logic for sorting (contrib)
            opp = row['AwayTeam'] if is_home else row['HomeTeam']
            opp_npi = npi.details[opp]['npi']
            
            # Tie logic?
            # Contrib = Pts / Wgt? No.
            # Contrib = "Equivalent NPI" of the game result.
            # Win Contrib = Opp NPI?
            # Loss Contrib = Opp NPI?
            # No, Contrib is usually just Opp NPI for removal purposes?
            # CHN: "if a team's victory would otherwise lower its NPI...".
            # This implies comparing (New NPI with game) vs (NPI without game).
            # Approx: GameValue vs Current NPI.
            # GameValue = Opp NPI. (For Wins).
            # For Losses? GameValue = Opp NPI.
            
            # Win Removal: Remove if OppNPI < TeamNPI.
            # Loss Removal: Remove if OppNPI > TeamNPI (Good Loss).
            
            # Let's use simple logic:
            
            item = {
                'opp_npi': opp_npi,
                'wgt': wgt,
                'is_win': res == 1.0,
                'is_loss': res == 0.0,
                'is_tie': res == 0.5
            }
            
            if item['is_win']: wins.append(item)
            if item['is_loss']: losses.append(item)
            
        # Simulate Removal
        kept_losses = [l for l in losses if l['opp_npi'] <= rating] # Keep Bad Losses (Opp <= NPI)
        good_losses_removed = len(losses) - len(kept_losses)
        
        # Wins
        # Sort wins by NPI (low to high is worst)
        wins.sort(key=lambda x: x['opp_npi']) 
        
        total_weighted_wins = sum(w['wgt'] for w in wins)
        current_weighted_wins = total_weighted_wins
        FLOOR = 10.0
        
        removed_count = 0
        
        for w in wins:
            if w['opp_npi'] < rating:
                # Candidate
                if (current_weighted_wins - w['wgt']) >= FLOOR:
                    current_weighted_wins -= w['wgt']
                    removed_count += 1
                    continue
            # Else kept
            
        stats.append({
            'Team': team,
            'NPI': rating,
            'TotWins': len(wins),
            'KeptWins': len(wins) - removed_count,
            'BadWinsRemoved': removed_count,
            'TotLoss': len(losses),
            'KeptLoss': len(kept_losses),
            'GoodLossRemoved': good_losses_removed
        })
        
    # Sort by removals? Or NPI?
    stats.sort(key=lambda x: x['NPI'], reverse=True)
    
    for s in stats:
        if s['BadWinsRemoved'] > 0 or s['GoodLossRemoved'] > 0:
            print(f"{s['Team']:<25} | {s['NPI']:<8.4f} | {s['TotWins']:<8} | {s['KeptWins']:<8} | {s['BadWinsRemoved']:<14} | {s['TotLoss']:<8} | {s['KeptLoss']:<8} | {s['GoodLossRemoved']:<15}")

if __name__ == "__main__":
    audit_removals()
