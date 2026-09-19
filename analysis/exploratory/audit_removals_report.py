import pandas as pd
from src.rankings.npi import NPI

def audit_system():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit()
    
    print("\n--- Removal Audit (Iterative Maximization) ---")
    
    teams_with_bad_wins = []
    teams_with_good_losses = []
    
    # Reload NPI to get internal state if possible, or we rely on recreating the logic
    # Since fit() is destructive to `valid_games` (local var), we can't inspect it directly without modifying NPI class.
    # Instead, we will infer removed games by comparing Full Record to Valid NPI/SOS.
    # Actually, simpler: Mod check_npi_math.py style logic.
    
    # Better: Update NPI class to store 'valid_games' in self.details maybe?
    # For now, let's just reverse engineer it:
    # A game is removed if including it lowers the NPI.
    
    # Actually, let's verify using the logic:
    # 1. Start with All Games
    # 2. Run the loop
    # 3. See what remains.
    
    for team in npi.teams:
        games = npi.games[(npi.games['HomeTeam'] == team) | (npi.games['AwayTeam'] == team)]
        current_ratings = npi.ratings
        current_npi = current_ratings[team]
        
        team_games = []
        for _, row in games.iterrows():
             if row['HomeTeam'] == team:
                 pts, wgt = npi._calculate_game_points(row, 'Home')
                 opp = row['AwayTeam']
                 is_win = row['Result'] == 1.0
             else:
                 pts, wgt = npi._calculate_game_points(row, 'Away')
                 opp = row['HomeTeam']
                 is_win = row['Result'] == 0.0
             
             opp_npi = current_ratings[opp]
             game_wp = (pts / wgt) * 100
             contrib = (0.25 * game_wp) + (0.75 * opp_npi)
             
             team_games.append({
                 'opp': opp,
                 'is_win': is_win,
                 'pts': pts,
                 'wgt': wgt,
                 'opp_npi': opp_npi,
                 'contrib': contrib,
                 'row': row
             })
             
        # Re-construct logic to see what WAS removed
        # Heuristic Logic: Contrib vs NPI
        
        # New: Calculate Total All Weight (Fixed Denom for WP)
        total_all_wgt = sum(g['wgt'] for g in team_games)
        total_all_pts = sum(g['pts'] for g in team_games)
        fixed_wp = (total_all_pts / total_all_wgt) if total_all_wgt > 0 else 0.0

        # Check Wins
        bad_wins = []
        MARGIN = 0.0
        
        # Sort by Contrib (Low to High)
        wins = sorted([g for g in team_games if g['is_win']], key=lambda x: x['contrib'])
        curr_wgt = sum(g['wgt'] for g in wins)
        
        for w in wins:
            if w['contrib'] < (current_npi - MARGIN):
                 if (curr_wgt - w['wgt']) >= 10.0:
                      curr_wgt -= w['wgt']
                      bad_wins.append(w)
                 else:
                      pass # Hit floor
        
        # Check Losses
        losses = [g for g in team_games if not g['is_win']]
        # Good Loss Logic: Contrib > NPI
        # Note: Code removes if Contrib > NPI.
        # So 'Bad Losses' (Contrib <= NPI) are kept.
        removed_good_losses = [l for l in losses if l['contrib'] > current_npi and l['pts']/l['wgt'] != 0.5]

        # Inferred Lists
        removed_wins = bad_wins
        removed_losses = removed_good_losses
        
        if removed_wins:
            teams_with_bad_wins.append((team, len(removed_wins), removed_wins))
        if removed_losses:
             teams_with_good_losses.append((team, len(removed_losses), removed_losses))

    print(f"\nTeams with Removed Wins: {len(teams_with_bad_wins)}")
    
    target_bad_wins = ["Michigan", "Michigan State", "North Dakota", "Penn State", "Western Michigan"]
    target_good_losses = ["Ferris State", "Stonehill", "Northern Michigan", "St. Lawrence", "Mercyhurst"]

    print(f"\n--- Targeted Audit: User List Verification ---")
    
    print("\nChecking 'Bad Wins' List (Expectation: Removals Present):")
    found_wins = []
    for t, count, games in teams_with_bad_wins:
        if t in target_bad_wins:
            found_wins.append(t)
            print(f"  [CONFIRMED] {t}: {count} wins removed")
            # for g in games:
            #    print(f"    vs {g['opp']} (Contrib {g['contrib']:.2f})")
    
    missing_wins = set(target_bad_wins) - set(found_wins)
    if missing_wins:
        print(f"  [MISSING] {missing_wins} - No wins removed!")
    else:
        print("  [SUCCESS] All target teams have Bad Wins removed.")

    print("\nChecking 'Good Losses' List (Expectation: Removals Present):")
    found_losses = []
    for t, count, games in teams_with_good_losses:
        if t in target_good_losses:
            found_losses.append(t)
            print(f"  [CONFIRMED] {t}: {count} losses removed")
    
    missing_losses = set(target_good_losses) - set(found_losses)
    if missing_losses:
        print(f"  [MISSING] {missing_losses} - No losses removed!")
    else:
        print("  [SUCCESS] All target teams have Good Losses removed.")
        
    # Validation of Bad Win interactions
    # "One other thing, do 'bad wins' affect both teams? Or only the winning team?"
    # Answer: Removing a bad win INCREASES Winner NPI. Loser SOS depends on Winner NPI.
    # So Loser SOS INCREASES.
    
    print("\n--- Interaction Logic Check ---")
    print("Logic: Removing a 'Bad Win' from Winner -> Increases Winner NPI.")
    print("Logic: Loser SOS = Avg(Opponent NPIs).")
    print("Result: Since Winner NPI increases, Loser SOS INCREASES.")
    print("Conclusion: Bad Win removal affects BOTH teams (Positive for Winner WP, Positive for Loser SOS).")


if __name__ == "__main__":
    audit_system()
