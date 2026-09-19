import pandas as pd
from src.rankings.npi import NPI

def reverse_engineer():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit()
    
    target = "Michigan"
    # Official Targets
    T_NPI = 60.386
    T_WP = 78.803
    T_SOS = 52.387
    T_QWB = 1.354
    
    ratings = npi.ratings
    team_games = []
    
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == target:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            opp = row['AwayTeam']
            is_win = row['Result'] == 1.0
            team_games.append({'opp': opp, 'pts': pts, 'wgt': wgt, 'is_win': is_win, 'opp_npi': ratings[opp]})
        elif row['AwayTeam'] == target:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            opp = row['HomeTeam']
            is_win = row['Result'] == 0.0
            team_games.append({'opp': opp, 'pts': pts, 'wgt': wgt, 'is_win': is_win, 'opp_npi': ratings[opp]})
            
    print(f"\n--- {target} Reverse Engineering ---")
    print(f"Games: {len(team_games)}")
    
    # 1. WP Check
    pts_sum = sum(g['pts'] for g in team_games)
    wgt_sum = sum(g['wgt'] for g in team_games)
    calc_wp = (pts_sum / wgt_sum) * 100
    print(f"Calc WP (All Games): {calc_wp:.3f} | Target: {T_WP}")
    if abs(calc_wp - T_WP) < 0.01:
        print(">> WP MATCHES ALL GAMES (No Removals Confirmed)")
    else:
        print(">> WP MISMATCH (Removals Active?)")
        
    # 2. QWB Reverse
    # T_QWB = Num / Denom
    # Denom = wgt_sum (All Games?)
    denom = wgt_sum
    required_num = T_QWB * denom
    print(f"\nQWB Analysis:")
    print(f"Target QWB: {T_QWB}")
    print(f"Denominator (All Wgt): {denom}")
    print(f"Required Numerator (Total Bonus): {required_num:.4f}")
    
    wins = [g for g in team_games if g['is_win']]
    bonus_wins = [g for g in wins if g['opp_npi'] > 51.0] # Assuming Base 51
    print(f"Wins > 51.0 NPI (Current): {len(bonus_wins)} / {len(wins)}")
    
    current_bonus_sum = 0
    # Using Standard Params
    BASE = 50.5
    MULT = 0.5
    for g in wins:
        if g['opp_npi'] > BASE:
            b = (g['opp_npi'] - BASE) * MULT * g['wgt']
            current_bonus_sum += b
            
    print(f"Current Calc Bonus ({BASE}/{MULT}): {current_bonus_sum:.4f}")
    print(f"Diff: {required_num - current_bonus_sum:.4f}")
    
    # 3. SOS Reverse
    print(f"\nSOS Analysis:")
    print(f"Target SOS: {T_SOS}")
    # Raw Avg All Games
    current_sos_raw = sum(g['opp_npi'] for g in team_games) / len(team_games)
    print(f"Current SOS (Raw All): {current_sos_raw:.4f}")
    print(f"Diff: {T_SOS - current_sos_raw:.4f}")
    
    # List Opponents to spot outliers
    print("\nOpponents (Current NPI):")
    sorted_opps = sorted(team_games, key=lambda x: x['opp_npi'], reverse=True)
    for g in sorted_opps:
        print(f"{g['opp']:<20} | NPI {g['opp_npi']:.2f}")

if __name__ == "__main__":
    reverse_engineer()
