# src/rankings/lrmc.py

import numpy as np
import pandas as pd
import warnings
from scipy.linalg import eig
import statsmodels.api as sm
from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationWarning
from collections import defaultdict

from src.rankings.base_ranker import BaseRanker


class LRMC(BaseRanker):
    def __init__(self, games_df, config=None, history_df=None):
        super().__init__(games_df)
        self.history_df = history_df

        # Default Configuration
        self.conf = {
            'variant': 'classic',
            'margin_cap': 3,
            'margin_power': 1.0,
            'home_ice_advantage': 0.2,

            'auto_fit': False,
            'fit_source': 'season',

            'use_xg': False,
            'fallback_to_goals': True,

            # --- NEW: Time Decay ---
            'time_decay_halflife': None,  # Number of days for weight to drop to 50%. None = No decay.

            'prior_weight': 0.0,
            'ordinal_prediction': False,
            'use_ncaa_weights': False,
            'min_common_opponents': 1
        }

        if config:
            self.conf.update(config)

        # Defaults (Generic Hockey)
        self.beta = 0.15
        self.hia_goals = self.conf['home_ice_advantage']
        self.alpha = self.beta * self.hia_goals

        self.transition_matrix = None
        self.ordinal_model = None

    def _get_adjusted_margin(self, row):
        """Returns Goal Margin with Cap, Power Scaling, and xG logic."""
        use_xg = self.conf.get('use_xg', False)

        has_xg = 'Home_xG' in row.index and 'Away_xG' in row.index and \
                 pd.notna(row['Home_xG']) and pd.notna(row['Away_xG'])

        if use_xg and has_xg:
            try:
                margin = float(row['Home_xG']) - float(row['Away_xG'])
            except ValueError:
                margin = float(row['HomeGoals']) - float(row['AwayGoals'])
        else:
            if use_xg and not self.conf.get('fallback_to_goals', True):
                return 0.0
            margin = float(row['HomeGoals']) - float(row['AwayGoals'])

        # Cap
        cap = self.conf.get('margin_cap')
        if cap and cap > 0:
            if abs(margin) > cap:
                margin = cap if margin > 0 else -cap

        # Power
        power = self.conf.get('margin_power', 1.0)
        if power != 1.0:
            sign = 1 if margin >= 0 else -1
            margin = sign * (abs(margin) ** power)

        return margin

    def _get_adjusted_margins_vectorized(self, df):
        """Vectorized version of _get_adjusted_margin operating on a full DataFrame."""
        use_xg = self.conf.get('use_xg', False)
        has_xg_cols = 'Home_xG' in df.columns and 'Away_xG' in df.columns

        if use_xg and has_xg_cols:
            xg_valid = df['Home_xG'].notna() & df['Away_xG'].notna()
            xg_margin = df['Home_xG'].astype(float).values - df['Away_xG'].astype(float).values
            goal_margin = df['HomeGoals'].astype(float).values - df['AwayGoals'].astype(float).values
            fallback = goal_margin if self.conf.get('fallback_to_goals', True) else np.zeros(len(df))
            margin = np.where(xg_valid.values, xg_margin, fallback)
        else:
            margin = df['HomeGoals'].astype(float).values - df['AwayGoals'].astype(float).values

        cap = self.conf.get('margin_cap')
        if cap and cap > 0:
            margin = np.clip(margin, -cap, cap)

        power = self.conf.get('margin_power', 1.0)
        if power != 1.0:
            margin = np.sign(margin) * (np.abs(margin) ** power)

        return margin

    def _fit_logit_safe(self, y, X, max_abs_param=5.0):
        """
        `max_abs_param` guards against a genuinely runaway/near-separated
        fit (coefficients diverging toward infinity), not against any
        specific numeric value — the default of 5.0 was chosen for
        _learn_params_home_and_home's margin-fit use case. Held-out
        calibration (see HockeyLRMC._calibrate_predictions_held_out) passes
        a higher threshold deliberately: that use case's raw log-ratio is
        known (reports/lrmc_calibration.md, reports/lrmc_experiments_2026.md)
        to need roughly a 4-5x scale correction to match KRACH's probability
        spread, so a fitted scale in that neighborhood is the expected
        signal, not a sign of instability.
        """
        if len(set(y)) < 2: return None, False
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=PerfectSeparationWarning)
                warnings.filterwarnings("ignore", category=ConvergenceWarning)
                model = sm.Logit(y, X).fit(disp=0, method='bfgs', maxiter=200)
                if np.any(np.abs(model.params) > max_abs_param): return None, False
                return model.params, True
        except Exception:
            return None, False

    def _learn_params_home_and_home(self, df):
        """Learns Alpha/Beta using Home-and-Home series."""
        valid = df[~df['NeutralSite'].astype(bool)].copy()
        if valid.empty:
            return

        valid['_Margin'] = self._get_adjusted_margins_vectorized(valid)
        valid['_VisWin'] = (valid['Result'] < 0.5).astype(int)

        # Find home-and-home pairs: (Season, A, B) where A hosted B AND A visited B
        home_df = valid[['Season', 'HomeTeam', 'AwayTeam', '_Margin']]
        away_df = valid[['Season', 'HomeTeam', 'AwayTeam', '_VisWin']].rename(
            columns={'HomeTeam': 'AwayTeam', 'AwayTeam': 'HomeTeam'}
        )
        # Merge creates cross-product when multiple games per direction, matching original behavior
        merged = home_df.merge(away_df, on=['Season', 'HomeTeam', 'AwayTeam'])

        if len(merged) < 50:
            return

        X_arr = sm.add_constant(merged['_Margin'].values)
        params, success = self._fit_logit_safe(merged['_VisWin'].values, X_arr)

        if success:
            self.alpha = params[0]
            self.beta = params[1]
            if abs(self.beta) > 0.001:
                self.hia_goals = np.abs(self.alpha) / (2 * self.beta)
                self.conf['home_ice_advantage'] = self.hia_goals

    def _train_flrmc_params(self):
        """F-LRMC Logic."""
        hia_goals = self.conf['home_ice_advantage']
        df = self.games.copy()
        margins = self._get_adjusted_margins_vectorized(df)
        df['_HomePerf'] = margins - hia_goals
        df['_AwayPerf'] = -(margins - hia_goals)

        # Build mean performance lookup via groupby (replaces first iterrows)
        home_records = df[['HomeTeam', 'AwayTeam', '_HomePerf']].rename(
            columns={'HomeTeam': 'Team', 'AwayTeam': 'Opponent', '_HomePerf': 'Perf'})
        away_records = df[['AwayTeam', 'HomeTeam', '_AwayPerf']].rename(
            columns={'AwayTeam': 'Team', 'HomeTeam': 'Opponent', '_AwayPerf': 'Perf'})
        all_records = pd.concat([home_records, away_records], ignore_index=True)
        mean_perfs_series = all_records.groupby(['Team', 'Opponent'])['Perf'].mean()

        mean_perfs = defaultdict(dict)
        for (team, opp), val in mean_perfs_series.items():
            mean_perfs[team][opp] = val
        opps = {team: set(d.keys()) for team, d in mean_perfs.items()}

        X, y = [], []
        min_common = self.conf['min_common_opponents']
        for i, row in enumerate(df.itertuples(index=False)):
            A, B = row.HomeTeam, row.AwayTeam
            common = opps.get(A, set()) & opps.get(B, set())
            if len(common) < min_common:
                continue

            mp_A, mp_B = mean_perfs[A], mean_perfs[B]
            votes_A = sum(1 for C in common if mp_A[C] > mp_B[C])
            votes_B = sum(1 for C in common if mp_B[C] > mp_A[C])

            if votes_A > votes_B:
                X.append(margins[i])
                y.append(1)
            elif votes_B > votes_A:
                X.append(margins[i])
                y.append(0)

        if len(X) < 20:
            return
        X_arr = sm.add_constant(np.array(X))
        params, success = self._fit_logit_safe(y, X_arr)
        if success:
            self.alpha = params[0]
            self.beta = params[1]

    def _calculate_game_weights(self, df):
        """
        Calculates time-decay weights for each game.
        Weight = 2 ^ -(days_ago / halflife)
        """
        halflife = self.conf.get('time_decay_halflife')
        if not halflife or halflife <= 0:
            return np.ones(len(df))

        # Ensure we have dates
        if 'Date' not in df.columns:
            return np.ones(len(df))

        # Reference date is the last game played in the set
        max_date = df['Date'].max()

        # Calculate days ago
        days_ago = (max_date - df['Date']).dt.days

        # Apply Halflife formula
        # If days_ago == halflife, weight is 0.5
        weights = 2.0 ** -(days_ago / halflife)
        return weights.values

    def _preprocess_game_values(self):
        df = self.games.copy()

        # 1. Calc Margins
        df['ProcessedMargin'] = self._get_adjusted_margins_vectorized(df)

        # 2. Calc Time Weights (NEW)
        df['Weight'] = self._calculate_game_weights(df)

        # 3. Logic Selection
        if self.conf['variant'] == 'zero':
            if self.conf['use_ncaa_weights']:
                conditions = [(df['Result'] > 0.5), (df['Result'] < 0.5), (df['Result'] == 0.5)]
                choices = [1.0, 0.0, 0.5]
                df['prob_home_better'] = np.select(conditions, choices, default=0.5)
            else:
                df['prob_home_better'] = np.where(df['Result'] > 0.5, 1.0, 0.0)
                df.loc[df['Result'] == 0.5, 'prob_home_better'] = 0.5

        else:
            # MARGIN BASED
            should_fit = self.conf.get('auto_fit')
            if should_fit:
                fit_data = self.games
                if self.conf.get('fit_source') == 'history' and self.history_df is not None:
                    fit_data = self.history_df
                self._learn_params_home_and_home(fit_data)

            if self.conf['variant'] == 'flrmc' and self.transition_matrix is None:
                self._train_flrmc_params()

            z_full = self.alpha + self.beta * df['ProcessedMargin']
            z_neut = self.beta * df['ProcessedMargin']
            df['z'] = np.where(df['NeutralSite'], z_neut, z_full)
            df['prob_home_better'] = 1 / (1 + np.exp(-df['z']))

        return df

    def fit(self):
        processed_games = self._preprocess_game_values()

        n_teams = len(self.teams)
        team_map = {team: i for i, team in enumerate(self.teams)}

        P = np.zeros((n_teams, n_teams))

        # Track Weighted Games Played
        # This is the sum of weights of all games a team participated in
        weighted_games_played = np.zeros(n_teams)

        h_idx = processed_games['HomeTeam'].map(team_map).values
        a_idx = processed_games['AwayTeam'].map(team_map).values
        p_h = processed_games['prob_home_better'].values
        w = processed_games['Weight'].values

        np.add.at(P, (h_idx, a_idx), (1.0 - p_h) * w)
        np.add.at(P, (a_idx, h_idx), p_h * w)
        np.add.at(weighted_games_played, h_idx, w)
        np.add.at(weighted_games_played, a_idx, w)

        # Normalize Rows
        for i in range(n_teams):
            if weighted_games_played[i] > 0:
                P[i, :] /= weighted_games_played[i]
                # Self-loop fills the rest
                row_sum = np.sum(P[i, :])
                # Precision errors can make row_sum > 1.0 slightly
                if row_sum > 1.0:
                    P[i, :] /= row_sum
                    P[i, i] = 0.0
                else:
                    P[i, i] = 1.0 - row_sum
            else:
                P[i, i] = 1.0

        if 'bayesian' in self.conf.get('variant', '') or self.conf.get('prior_weight', 0) > 0:
            prior_weight = self.conf.get('prior_weight', 0.15)
            if prior_weight > 0:
                Prior = np.ones((n_teams, n_teams)) / n_teams
                P = (1 - prior_weight) * P + (prior_weight * Prior)

        self.transition_matrix = P

        try:
            vals, vecs = eig(P.T)
            idx = np.argmin(np.abs(vals - 1))
            ratings = np.real(vecs[:, idx])
            if np.all(ratings < 0): ratings = -ratings
            ratings = np.abs(ratings)
            ratings = ratings / np.sum(ratings) * n_teams * 100
        except:
            ratings = np.ones(n_teams) * 100

        self.ratings = {self.teams[i]: ratings[i] for i in range(n_teams)}

        if self.conf.get('ordinal_prediction'):
            self._fit_ordinal_model(processed_games)

    def _fit_ordinal_model(self, df):
        # ... (Same as before) ...
        pass

    def predict(self, home, away, is_neutral=False):
        """
        Predicts the probability of the home team winning using the
        logistic (exponential) function and home-ice advantage.
        """
        # 1. Get ratings (default to 1.0 to avoid log(0) if team not found)
        r_home = self.ratings.get(home, 1.0)
        r_away = self.ratings.get(away, 1.0)

        # 2. Determine the Home Ice Advantage (HIA)
        # self.alpha is the logit-scale intercept learned during _preprocess_game_values
        hia = 0.0 if is_neutral else np.abs(self.alpha)

        # 3. Calculate the log-ratio of the ratings
        # This transforms the stationary distribution mass into a logit-scale performance gap
        # If r_home == r_away, log_ratio is 0.
        log_ratio = np.log(r_home / r_away)

        # 4. Combine HIA and Rating Difference
        z = hia + log_ratio

        # 5. Apply the Logistic (Exponential) Function
        # Prob = 1 / (1 + e^-z)
        prob = 1 / (1 + np.exp(-z))

        return prob