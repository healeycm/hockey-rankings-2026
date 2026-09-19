# src/rankings/krach.py

import numpy as np
from src.rankings.base_ranker import BaseRanker


class KRACH(BaseRanker):
    def fit(self, max_iterations=1000, tolerance=1e-9):
        """
        Iterative solver for KRACH.
        K_i = (Points Earned_i) / Sum( 1 / (K_i + K_j) ) for all opponents j
        Vectorized with NumPy for performance.
        """
        n = len(self.teams)
        team_idx = {t: i for i, t in enumerate(self.teams)}

        # 1. Points earned per team
        home_pts = self.games.groupby('HomeTeam')['Result'].sum()
        away_pts = self.games.groupby('AwayTeam')['Result'].apply(lambda x: (1.0 - x).sum())
        points = np.array([
            max(home_pts.get(t, 0) + away_pts.get(t, 0), 0.1)
            for t in self.teams
        ])

        # 2. Game indices (replaces iterrows matchup loop)
        h_idx = self.games['HomeTeam'].map(team_idx).values
        a_idx = self.games['AwayTeam'].map(team_idx).values

        # 3. Iteration
        ratings = np.full(n, 100.0)

        for _ in range(max_iterations):
            inv_sum = 1.0 / (ratings[h_idx] + ratings[a_idx])
            denom = np.zeros(n)
            np.add.at(denom, h_idx, inv_sum)
            np.add.at(denom, a_idx, inv_sum)

            new_ratings = np.where(denom == 0, 100.0, points / denom)
            new_ratings = new_ratings / new_ratings.mean() * 100.0

            max_diff = np.max(np.abs(new_ratings - ratings))
            ratings = new_ratings

            if max_diff < tolerance:
                break

        self.ratings = {t: ratings[i] for t, i in team_idx.items()}

    def predict(self, home_team, away_team, is_neutral=False):
        """
        KRACH formula: P(A beats B) = K_A / (K_A + K_B)
        Standard KRACH does not natively handle Home Ice Advantage.
        """
        k_home = self.ratings.get(home_team, 100)
        k_away = self.ratings.get(away_team, 100)

        # Avoid division by zero
        if k_home + k_away == 0:
            return 0.5

        prob = k_home / (k_home + k_away)
        return prob