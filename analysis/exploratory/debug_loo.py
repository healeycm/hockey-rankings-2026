import pandas as pd
from src.rankings.npi import NPI

def debug_loo():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit()
    
    target = "Michigan"
    # Get current state
    current_npi = npi.ratings[target]
    print(f"\n--- {target} Baseline ---")
    print(f"Current NPI: {current_npi:.4f}")
    
    team_games = []
    # Identify games
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == target:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            opp = row['AwayTeam']
            is_win = row['Result'] == 1.0
            team_games.append({'opp': opp, 'pts': pts, 'wgt': wgt, 'is_win': is_win, 'opp_npi': npi.ratings[opp]})
        elif row['AwayTeam'] == target:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            opp = row['HomeTeam']
            is_win = row['Result'] == 0.0
            team_games.append({'opp': opp, 'pts': pts, 'wgt': wgt, 'is_win': is_win, 'opp_npi': npi.ratings[opp]})

    print(f"Total Games: {len(team_games)}")
    
    # 1. Calculate All Games Metrics
    all_pts = sum(g['pts'] for g in team_games)
    all_wgt = sum(g['wgt'] for g in team_games)
    all_wp = (all_pts / all_wgt) * 100
    all_sos_raw = sum(g['opp_npi'] for g in team_games) / len(team_games)
    all_sos_wgt = sum(g['opp_npi'] * g['wgt'] for g in team_games) / all_wgt
    
    print(f"\n[All Games Config]")
    print(f"  WP: {all_wp:.4f} (Target 78.803)")
    print(f"  SOS (Raw): {all_sos_raw:.4f} (Target 52.387)")
    print(f"  SOS (Wgt): {all_sos_wgt:.4f}")
    
    # 2. LOO Analysis
    # "Does removing this game improve NPI?"
    # We assume SOS is Raw Avg of VALID games (to test user hypothesis)
    # And QWB uses All Weighted (Fixed).
    
    qwb_denom = all_wgt 
    qwb_sum = 0
    for g in team_games:
        if g['is_win'] and g['opp_npi'] > 51.0:
            qwb_sum += (g['opp_npi'] - 51.0) * 0.5 * g['wgt']
    base_qwb = qwb_sum / qwb_denom
    
    print("\n--- Leave-One-Out Analysis (Hypothesis: Maximize NPI) ---")
    print(f"{'Opponent':<20} | {'Res':<4} | {'OppNPI':<6} | {'NPI_With':<8} | {'NPI_Wo':<8} | {'Delta':<8} | {'Action'}")
    
    # We calculate Base NPI using All Games
    base_npi = (0.25 * all_wp) + (0.75 * all_sos_raw) + base_qwb
    
    sorted_games = sorted(team_games, key=lambda x: x['opp_npi'])
    
    kept_games = team_games[:]
    
    for g in sorted_games:
        # Calculate metrics without this game
        subset = [x for x in team_games if x != g]
        if not subset: continue
        
        sub_pts = sum(x['pts'] for x in subset)
        sub_wgt = sum(x['wgt'] for x in subset)
        sub_wp = (sub_pts / sub_wgt) * 100
        
        # SOS (Raw)
        sub_sos = sum(x['opp_npi'] for x in subset) / len(subset)
        
        # QWB (Fixed based on All Games)
        sub_npi = (0.25 * sub_wp) + (0.75 * sub_sos) + base_qwb
        
        delta = sub_npi - base_npi
        action = "DROP" if delta > 0 else "KEEP"
        
        if abs(delta) > 0.001:
             print(f"{g['opp']:<20} | {'W' if g['is_win'] else 'L'}    | {g['opp_npi']:<6.2f} | {base_npi:<8.4f} | {sub_npi:<8.4f} | {delta:<8.4f} | {action}")

if __name__ == "__main__":
    debug_loo()
