# src/rankings/gw_lrmc.py

import numpy as np
import pandas as pd
from scipy.linalg import eig
from src.rankings.lrmc import LRMC


class gwLRMC(LRMC):
    def __init__(self, games_df, config=None, history_df=None):
        super().__init__(games_df, config, history_df)

        # Ensure default config for decay exists if not provided
        if 'time_decay_halflife' not in self.conf:
            self.conf['time_decay_halflife'] = 60  # Default to ~2 months

    def _calculate_game_weights(self, df):
        """
        Calculates time-decay weights for each game.
        Weight = 2 ^ -(days_ago / halflife)
        """
        halflife = self.conf.get('time_decay_halflife')
        if not halflife or halflife <= 0:
            return np.ones(len(df))

        if 'Date' not in df.columns:
            return np.ones(len(df))

        # Reference date is the last game played in the set
        max_date = df['Date'].max()

        # Calculate days ago
        days_ago = (max_date - df['Date']).dt.days

        # Apply Halflife formula
        weights = 2.0 ** -(days_ago / halflife)
        return weights.values

    def fit(self):
        """
        Builds the Weighted Markov Chain.
        Differences from Standard LRMC:
        1. Calculates 'Weight' for every game based on recency.
        2. When updating the P matrix, multiplies the vote probability by this Weight.
        3. Normalizes by 'Weighted Games Played' instead of raw count.
        """
        # 1. Preprocess (Calculates Probabilities & Margins using Parent Logic)
        processed_games = self._preprocess_game_values()

        # 2. Calculate Weights explicitly
        processed_games['Weight'] = self._calculate_game_weights(processed_games)

        n_teams = len(self.teams)
        team_map = {team: i for i, team in enumerate(self.teams)}

        P = np.zeros((n_teams, n_teams))

        # Track Weighted Games Played (The Denominator)
        # Instead of "1 game", a game 2 months ago might count as "0.5 games"
        weighted_games_played = np.zeros(n_teams)

        for _, row in processed_games.iterrows():
            idx_h = team_map[row['HomeTeam']]
            idx_a = team_map[row['AwayTeam']]

            p_h_better = row['prob_home_better']
            p_a_better = 1.0 - p_h_better

            w = row['Weight']

            # Weighted Voting:
            # The mass transferred is (Probability * Weight)
            # Home adds to Away's score (if Away is better)
            P[idx_h][idx_a] += p_a_better * w

            # Away adds to Home's score
            P[idx_a][idx_h] += p_h_better * w

            # Increment denominator
            weighted_games_played[idx_h] += w
            weighted_games_played[idx_a] += w

        # 3. Normalize Rows
        for i in range(n_teams):
            if weighted_games_played[i] > 0:
                P[i, :] /= weighted_games_played[i]

                # Self-loop fills the rest
                row_sum = np.sum(P[i, :])
                if row_sum > 1.0:
                    P[i, :] /= row_sum
                    P[i, i] = 0.0
                else:
                    P[i, i] = 1.0 - row_sum
            else:
                P[i, i] = 1.0

        # 4. Bayesian Adjustment (Optional)
        if 'bayesian' in self.conf.get('variant', '') or self.conf.get('prior_weight', 0) > 0:
            prior_weight = self.conf.get('prior_weight', 0.15)
            if prior_weight > 0:
                Prior = np.ones((n_teams, n_teams)) / n_teams
                P = (1 - prior_weight) * P + (prior_weight * Prior)

        self.transition_matrix = P

        # 5. Solve Eigenvector
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

        # Fit Ordinal Model if requested
        if self.conf.get('ordinal_prediction'):
            self._fit_ordinal_model(processed_games)