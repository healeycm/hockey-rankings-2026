import numpy as np
from src.rankings.base_ranker import BaseRanker


class NPIGames(BaseRanker):
    def __init__(self, games_df, config=None):
        # BaseRanker.__init__ already filters to Division I opponents only —
        # see base_ranker.py's _apply_di_filter docstring. Previously
        # duplicated here with its own try/except; now centralized.
        super().__init__(games_df)

        # Default NCAA DI dials, set for 2025-26 season; carried forward until
        # re-tuned/re-validated against a newer official NPI snapshot.
        self.conf = {
            'home_multiplier': 0.8,
            'away_multiplier': 1.2,
            'quality_win_base': 50.5,
            'quality_win_mult': 0.45
        }
        if config:
            self.conf.update(config)

        # Filter Exhibition Games
        if 'Is_Exhibition' in self.games.columns:
             self.games = self.games[~self.games['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
             self.teams = sorted(list(set(self.games['HomeTeam']).union(set(self.games['AwayTeam']))))

    def _calculate_game_points(self, row, team_role):
        """
        Calculates weighted points for a single team in a game.
        """
        is_ot = row.get('IsOT', False)
        is_postseason = row['Type'].upper() in ['POST', 'NCAA']
        
        is_winner = (team_role == 'Home' and row['Result'] == 1.0) or \
                    (team_role == 'Away' and row['Result'] == 0.0)
        is_loser = (team_role == 'Home' and row['Result'] == 0.0) or \
                   (team_role == 'Away' and row['Result'] == 1.0)
        is_tie = row['Result'] == 0.5

        # Determine Multiplier
        mult = 1.0
        if not row['NeutralSite'] and not is_postseason:
            if is_winner:
                mult = self.conf['away_multiplier'] if team_role == 'Away' else self.conf['home_multiplier']
            elif is_loser:
                mult = self.conf['away_multiplier'] if team_role == 'Home' else self.conf['home_multiplier']
            else:
                mult = 1.0

        if not is_ot:
            if row['NeutralSite'] or is_postseason:
                win_mult = 1.0
                loss_mult = 1.0
            else:
                win_mult = self.conf['home_multiplier'] if team_role == 'Home' else self.conf['away_multiplier'] 
                loss_mult = self.conf['away_multiplier'] if team_role == 'Home' else self.conf['home_multiplier'] 
            
            if is_winner:
               weight = win_mult
               pts = weight
            elif is_loser:
               weight = loss_mult
               pts = 0.0
            else:
               # Tie
               weight = 1.0
               pts = 0.5 * win_mult
        else:
            if is_postseason:
                weight = 1.0
                pts = 1.0 if is_winner else 0.0
            else:
                weight = 1.0 
                if is_winner:
                     pts = (0.4 * mult) + 0.2
                elif is_loser:
                     opp_role = 'Away' if team_role == 'Home' else 'Home'
                     opp_mult = self.conf['away_multiplier'] if opp_role == 'Away' else self.conf['home_multiplier']
                     winner_pts = (0.4 * opp_mult) + 0.2
                     pts = weight - winner_pts
                else:
                     tie_mult = self.conf['home_multiplier'] if team_role == 'Home' else self.conf['away_multiplier']
                     pts = 0.5 * tie_mult
                     weight = 1.0

        return pts, weight

    def fit(self, max_iterations=100, tolerance=1e-5, initial_ratings=None):
        team_games = {t: [] for t in self.teams}
        for idx, row in self.games.iterrows():
            h, a = row['HomeTeam'], row['AwayTeam']
            h_pts, h_wgt = self._calculate_game_points(row, 'Home')
            a_pts, a_wgt = self._calculate_game_points(row, 'Away')
            h_is_win = row['Result'] == 1.0
            a_is_win = row['Result'] == 0.0
            h_is_loss = row['Result'] == 0.0
            a_is_loss = row['Result'] == 1.0
            
            # Additional metadata for filtering
            team_games[h].append({'opponent': a, 'pts': h_pts, 'wgt': h_wgt, 'is_win': h_is_win, 'is_loss': h_is_loss, 'result': row['Result']})
            team_games[a].append({'opponent': h, 'pts': a_pts, 'wgt': a_wgt, 'is_win': a_is_win, 'is_loss': a_is_loss, 'result': 1.0 - row['Result']})

        # Initial ratings
        if initial_ratings:
             if isinstance(initial_ratings, dict):
                 print(f"Seeding NPI with provided dictionary ({len(initial_ratings)} teams).")
                 current_ratings = {t: 50.0 for t in self.teams}
                 current_ratings.update(initial_ratings)
             elif isinstance(initial_ratings, (int, float)):
                 print(f"Seeding NPI with flat value: {initial_ratings}")
                 current_ratings = {t: float(initial_ratings) for t in self.teams}
        else:
             current_ratings = {t: 50.0 for t in self.teams}
            
        if not hasattr(self, 'details'): self.details = {}
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            max_diff = 0.0
            next_ratings = {}
            
            for team in self.teams:
                # 1. Calculate Game NPI for all games
                games = []
                for g in team_games[team]:
                    opp_npi = current_ratings[g['opponent']]
                    
                    # Game Result Score (0-100)
                    # Use pts/wgt * 100 to capture Weighted Win Pct equivalent
                    game_result_score = (g['pts'] / g['wgt']) * 100 if g['wgt'] > 0 else 0
                    
                    # Bonus Logic
                    bonus = 0.0
                    qwb_base = self.conf.get('quality_win_base', 51.0)
                    qwb_mult = self.conf.get('quality_win_mult', 0.5)
                    
                    if g['is_win'] and opp_npi > qwb_base:
                              bonus = (opp_npi - qwb_base) * qwb_mult
                    
                    # Game NPI Formula
                    # (Result * 25%) + (OppNPI * 75%) + Bonus
                    game_npi = (game_result_score * 0.25) + (opp_npi * 0.75) + bonus
                    
                    games.append({**g, 'game_npi': game_npi, 'opp_npi': opp_npi, 'game_result_score': game_result_score})

                # 2. Filter Games (Bad Wins and Good Losses)
                
                # Separate wins/losses
                all_wins = [g for g in games if g['is_win']]
                losses = [g for g in games if not g['is_win']]
                
                # Split Wins into Regulation (Subject to Drop) and OT (Mandatory)
                regulation_wins = []
                ot_wins = []
                for w in all_wins:
                    if w['game_result_score'] >= 99.0:
                         regulation_wins.append(w)
                    else:
                         ot_wins.append(w)
                
                # Regulation Wins are the only ones sorted and potentially dropped
                regulation_wins = sorted(regulation_wins, key=lambda x: x['game_npi'], reverse=True)
                
                # Good Loss Filter
                mandatory_losses = []
                for l in losses:
                    if l['game_npi'] > current_ratings[team] and l['game_result_score'] == 0:
                        pass # Drop
                    else:
                        mandatory_losses.append(l)
                
                mandatory_set = mandatory_losses + ot_wins + regulation_wins[:12]
                optional_set = regulation_wins[12:]
                
                # Helper to calculate average based on Method
                method = self.conf.get('qwb_method', 'integrated')
                
                def calc_team_npi(game_set):
                    if not game_set: return 0.0
                    
                    if method == 'integrated':
                        # Current Logic: Weighted Average of (Base + Bonus)
                        sum_npi_wgt = sum(g['game_npi'] * g['wgt'] for g in game_set)
                        sum_wgt = sum(g['wgt'] for g in game_set)
                        return sum_npi_wgt / sum_wgt if sum_wgt > 0 else 0.0
                    else:
                        # Additive Logic: Weighted Base + Simple Bonus
                        # Re-calculate Base NPI (remove bonus from game_npi for the weighted part)
                        # Actually simpler: track base_npi in games list? 
                        # Or just subtract bonus back out?
                        # Let's subtract bonus.
                        sum_base_wgt = 0
                        sum_wgt = 0
                        total_bonus = 0
                        for g in game_set:
                            # Reconstruct Base
                            # Bonus was: (Opp - Floor) * Mult if win
                            # Or we can just store 'base_npi' earlier.
                            # For now, back-calc:
                            g_bonus = 0.0
                            if g['is_win'] and g['opp_npi'] > self.conf['quality_win_base']:
                                 g_bonus = (g['opp_npi'] - self.conf['quality_win_base']) * self.conf['quality_win_mult']
                            
                            base_val = g['game_npi'] - g_bonus
                            sum_base_wgt += base_val * g['wgt']
                            sum_wgt += g['wgt']
                            total_bonus += g_bonus
                            
                        base_avg = sum_base_wgt / sum_wgt if sum_wgt > 0 else 0.0
                        bonus_avg = total_bonus / len(game_set)
                        return base_avg + bonus_avg

                curr_npi = calc_team_npi(mandatory_set)
                
                # Iteratively add Optional Wins
                final_games = list(mandatory_set)
                
                for opt_game in optional_set:
                    test_games = final_games + [opt_game]
                    test_avg = calc_team_npi(test_games)
                    
                    if test_avg > curr_npi:
                        curr_npi = test_avg
                        final_games = test_games
                    else:
                        break
                        
                # 3. Calculate Team NPI
                new_npi = curr_npi
                
                # 4. SOS Calculation (All Games Played — NOT just games surviving the
                # bad-wins filter. Verified against 2026-01-27 reference NPI data:
                # computing SOS over the filtered/surviving set alone nearly doubles
                # the error vs. computing it over the full schedule.)
                all_opp_npis = [g['opp_npi'] for g in games]
                sos = sum(all_opp_npis) / len(all_opp_npis) if all_opp_npis else 0.0
                
                # QWB for display
                valid_bonuses = []
                for g in final_games:
                    if g['is_win'] and g['opp_npi'] > self.conf['quality_win_base']:
                        valid_bonuses.append((g['opp_npi'] - self.conf['quality_win_base']) * self.conf['quality_win_mult'])
                qwb_val = sum(valid_bonuses) / len(final_games) if final_games else 0.0
                
                # Count Dropped Games
                dropped_wins = len(all_wins) - sum(1 for g in final_games if g['is_win'])
                dropped_losses = len(losses) - len(mandatory_losses) 
                
                # Store Details
                if team not in self.details: self.details[team] = {}
                self.details[team].update({
                    'npi': new_npi,
                    'sos': sos,
                    'qwb': qwb_val,
                    # Wgt W% is also reported over the full schedule (same rationale as SOS above).
                    'wp': (sum(g['pts'] for g in games)/sum(g['wgt'] for g in games)*100) if games else 0,
                    'dropped_wins': dropped_wins,
                    'dropped_losses': dropped_losses
                })
                
                max_diff = max(max_diff, abs(new_npi - current_ratings[team]))
                next_ratings[team] = new_npi

            current_ratings = next_ratings
            if max_diff < tolerance:
                print(f"Converged after {iteration} iterations.")
                break
        self.ratings = current_ratings

    def predict(self, home, away, is_neutral=False):
        r_home = self.ratings.get(home, 50)
        r_away = self.ratings.get(away, 50)
        scale = 15.0
        diff = r_home - r_away + (5.0 if not is_neutral else 0)
        return 1.0 / (1.0 + np.exp(-diff / scale))
