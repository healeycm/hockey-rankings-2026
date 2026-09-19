import numpy as np
import pandas as pd
from src.rankings.base_ranker import BaseRanker


class Colley(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)
        self.conf = {}
        if config:
            self.conf.update(config)

    def fit(self):
        n_teams = len(self.teams)
        team_map = {team: i for i, team in enumerate(self.teams)}

        # Initialize Matrix C and Vector b
        # C diagonals start at 2, b starts at 1
        C = np.diag(2 * np.ones(n_teams))
        b = np.ones(n_teams)

        for _, row in self.games.iterrows():
            idx_h = team_map[row['HomeTeam']]
            idx_a = team_map[row['AwayTeam']]

            # Update C Matrix (Schedule info)
            # Add 1 to diagonal (Total Games)
            C[idx_h, idx_h] += 1
            C[idx_a, idx_a] += 1

            # Subtract 1 from off-diagonal (Games between i and j)
            C[idx_h, idx_a] -= 1
            C[idx_a, idx_h] -= 1

            # Update b Vector (Win/Loss info)
            # Result is 1.0 (Home Win), 0.5 (Tie), 0.0 (Away Win)
            # Colley formula for b update: +0.5 for win, -0.5 for loss, 0 for tie

            # Calculate Home "Colley Credit"
            # Win (1.0) -> +0.5
            # Loss (0.0) -> -0.5
            # Tie (0.5) -> 0.0
            val = row['Result'] - 0.5

            b[idx_h] += val
            b[idx_a] -= val  # Away result is inverse

        # Solve Linear System Cr = b
        try:
            r = np.linalg.solve(C, b)
        except np.linalg.LinAlgError:
            # Fallback for singular matrix (rare in Colley unless 0 games)
            r = np.ones(n_teams) * 0.5

        self.ratings = {self.teams[i]: r[i] for i in range(n_teams)}

    def predict(self, home, away, is_neutral=False):
        """
        Colley prediction: P(A > B) = 0.5 + (r_A - r_B)
        Note: Colley ratings usually sum to N/2 or average 0.5.
        """
        r_home = self.ratings.get(home, 0.5)
        r_away = self.ratings.get(away, 0.5)

        # Basic Colley prediction is linear
        prob = 0.5 + (r_home - r_away)

        # Add slight home edge? Colley usually handles this by adjusting b,
        # but for simple prediction we can bump probability.
        # Let's keep it pure for now, or clamp it.

        return max(0.01, min(0.99, prob))