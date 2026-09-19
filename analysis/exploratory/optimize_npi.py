import pandas as pd
import numpy as np
from src.rankings.npi import NPI
from analysis.exploratory.calibration_targets import TARGETS

class ConfigurableNPI(NPI):
    def __init__(self, games_df, calibration_config):
        super().__init__(games_df)
        self.cal_config = calibration_config
    
    def fit(self, max_iterations=100, tolerance=1e-5):
        # Configuration Dials
        SOS_METHOD = self.cal_config.get('sos_method', 'weighted') # 'weighted', 'raw'
        REMOVAL_LOGIC = self.cal_config.get('removal_logic', 'margin') # 'margin', 'loo_max'
        QWB_DENOM = self.cal_config.get('qwb_denom', 'valid') # 'valid', 'all', 'all_weighted'
        MARGIN = -4.0
        FLOOR = 10.0

        team_games = {t: [] for t in self.teams}
        for idx, row in self.games.iterrows():
            h, a = row['HomeTeam'], row['AwayTeam']
            h_pts, h_wgt = self._calculate_game_points(row, 'Home')
            a_pts, a_wgt = self._calculate_game_points(row, 'Away')
            h_is_win = row['Result'] == 1.0
            a_is_win = row['Result'] == 0.0
            team_games[h].append({'opponent': a, 'pts': h_pts, 'wgt': h_wgt, 'is_win': h_is_win})
            team_games[a].append({'opponent': h, 'pts': a_pts, 'wgt': a_wgt, 'is_win': a_is_win})

        current_ratings = {}
        raw_wps = {}
        for team, games in team_games.items():
            pts = sum(g['pts'] for g in games)
            wgt = sum(g['wgt'] for g in games)
            rating = (pts / wgt * 100) if wgt > 0 else 50.0
            current_ratings[team] = rating
            raw_wps[team] = rating # Store initial Raw WP

        if not hasattr(self, 'details'): self.details = {}
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            max_diff = 0.0
            next_ratings = {}
            
            for team in self.teams:
                current_npi = current_ratings[team]
                games = team_games[team]
                
                # --- REMOVAL LOGIC ---
                valid_games = []
                
                if REMOVAL_LOGIC == 'margin':
                     # Current Implementation
                    temp_games = []
                    for g in games:
                        opp_npi = current_ratings[g['opponent']]
                        game_wp = (g['pts'] / g['wgt']) * 100
                        contrib = (0.25 * game_wp) + (0.75 * opp_npi)
                        temp_games.append({**g, 'contrib': contrib, 'opp_npi': opp_npi})

                    losses = [g for g in temp_games if not g['is_win']]
                    kept_losses = [l for l in losses if l['contrib'] <= current_npi or l['pts']/l['wgt'] == 0.5]
                    
                    wins = sorted([g for g in temp_games if g['is_win']], key=lambda x: x['contrib'])
                    kept_wins = []
                    current_weighted_wins = sum(g['wgt'] for g in wins)
                    for w in wins:
                        if w['contrib'] < (current_npi - MARGIN):
                            if (current_weighted_wins - w['wgt']) >= FLOOR:
                                current_weighted_wins -= w['wgt']
                                continue
                        kept_wins.append(w)
                    valid_games = kept_wins + kept_losses

                elif REMOVAL_LOGIC == 'loo_max':
                    # Leave One Out Maximization (Approximate)
                    # We accept games only if they improve NPI? Or drop those that hurt?
                    # "Optimized NPI" usually means removing bad results.
                    # We will calculate "contribution" and remove strict negatives.
                    # Strict Negative: removing it RAISES the score.
                    # This is iterative inside the loop? Or a separate sub-loop?
                    # Let's stick to simple LOO check:
                    # Calculate Base Score (using all games).
                    # For each game, Calc Score Without It.
                    # If Without > With, Drop it.
                    # Constraint: Floor 10.
                    # NOTE: This effectively mimics "Contrib < Current NPI".
                    # Let's try explicit "Contrib < Current NPI" without margin.
                    
                    temp_games = []
                    for g in games:
                        opp_npi = current_ratings[g['opponent']]
                        game_wp = (g['pts'] / g['wgt']) * 100
                        contrib = (0.25 * game_wp) + (0.75 * opp_npi)
                        temp_games.append({**g, 'contrib': contrib})
                        
                    kept = []
                    win_wgt = sum(g['wgt'] for g in temp_games if g['is_win'])
                    
                    # Sort by contrib (lowest first) to drop worst first
                    temp_games.sort(key=lambda x: x['contrib'])
                    
                    for g in temp_games:
                         # Win Floor Check
                         if g['is_win']:
                             if (win_wgt - g['wgt']) < FLOOR:
                                 kept.append(g)
                                 continue
                                 
                         # Maximization Check
                         # If Contrib < Current NPI, dropping it raises average.
                         # (Strictly true for simple averages, approx for weighted NPI).
                         if g['contrib'] < current_npi:
                             if g['is_win']: win_wgt -= g['wgt']
                             continue # Drop bad game
                         kept.append(g)
                    valid_games = kept

                if not valid_games:
                    next_ratings[team] = current_ratings[team]
                    continue

                total_pts = sum(g['pts'] for g in valid_games)
                total_wgt = sum(g['wgt'] for g in valid_games)
                
                adj_wp = (total_pts / total_wgt)
                raw_adj_wp = raw_wps[team] / 100.0

                # --- SOS CALCULATION ---
                valid_opp_npis = [current_ratings[g['opponent']] for g in valid_games]
                
                if SOS_METHOD == 'weighted':
                    valid_opp_weights = [g['wgt'] for g in valid_games]
                    sos = sum(n * w for n, w in zip(valid_opp_npis, valid_opp_weights)) / sum(valid_opp_weights)
                elif SOS_METHOD == 'raw':
                    sos = sum(valid_opp_npis) / len(valid_opp_npis)
                else: # 'raw_all' - use all games? (Unlikely for "Optimized SOS")
                    sos = sum(valid_opp_npis) / len(valid_opp_npis)

                # --- QWB CALCULATION ---
                qwb_sum = 0.0
                qwb_denom = 0.0
                
                # Bonus earned on Wins (Weighted by Game Weight)
                # Base 51, Factor 0.5 (Fixed)
                
                # Denominator Source
                if QWB_DENOM == 'all_weighted':
                    qwb_denom = sum(g['wgt'] for g in games)
                elif QWB_DENOM == 'all':
                    qwb_denom = len(games)
                elif QWB_DENOM == 'valid':
                    qwb_denom = total_wgt # Sum of weights of VALID games
                
                # QWB Parameters from Config
                QWB_BASE = self.cal_config.get('qwb_base', 51.0)
                QWB_MULT = self.cal_config.get('qwb_mult', 0.5)

                for g in games:
                     if g['is_win']:
                         opp_npi = current_ratings[g['opponent']] 
                         if opp_npi > QWB_BASE:
                             bonus = (opp_npi - QWB_BASE) * QWB_MULT 
                             qwb_sum += bonus * g['wgt']
                
                qwb = qwb_sum / qwb_denom if qwb_denom > 0 else 0.0
                
                new_npi = (raw_adj_wp * 100 * 0.25) + (sos * 0.75) + qwb
                
                # Update Details
                if team not in self.details: self.details[team] = {}
                self.details[team].update({
                    'npi': new_npi,
                    'sos': sos,
                    'qwb': qwb
                })

                max_diff = max(max_diff, abs(new_npi - current_ratings[team]))
                next_ratings[team] = new_npi

            current_ratings = next_ratings
            if max_diff < tolerance:
                break
        self.ratings = current_ratings

def run_optimization():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    
    # Filter Exhibition
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
    
    configs = []
    bases = [54.0, 55.0, 56.0, 57.0]
    factors = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    for b in bases:
        for f in factors:
            configs.append({'qwb_base': b, 'qwb_mult': f})
            
    results = []
    
    print(f"Running Grid Search on {len(configs)} configurations...")
    print("-" * 60)
    
    for conf in configs:
        model = ConfigurableNPI(season_df, {
            'sos_method': 'raw', 
            'removal_logic': 'margin', 
            'qwb_denom': 'all_weighted',
            **conf # Inject QWB params
        })
        model.fit()
        
        # Calculate Error
        total_error = 0.0
        n_teams = 0
        for team, targets in TARGETS.items():
            if team not in model.details: continue
            
            actual = model.details[team]
            err_npi = (actual['npi'] - targets['NPI']) ** 2
            # SOS and QWB will move too, but NPI is the anchor.
            
            total_error += err_npi
            n_teams += 1
            
        rmse = np.sqrt(total_error / n_teams)
        
        res_entry = {**conf, 'rmse': rmse, 'MichNPI': model.details['Michigan']['npi']}
        results.append(res_entry)
        
        # Print rapid feedback
        print(f"Base={conf['qwb_base']} | Mult={conf['qwb_mult']} | RMSE: {rmse:.4f} | Mich: {model.details['Michigan']['npi']:.2f}")

    print("-" * 60)
    print("Top 3 Configurations:")
    sorted_res = sorted(results, key=lambda x: x['rmse'])
    for i, res in enumerate(sorted_res[:3]):
        print(f"{i+1}. RMSE {res['rmse']:.4f} | {res}")

if __name__ == "__main__":
    run_optimization()
