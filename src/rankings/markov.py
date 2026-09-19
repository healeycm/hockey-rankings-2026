import numpy as np
import pandas as pd
from scipy.linalg import eig
from src.rankings.base_ranker import BaseRanker


class Markov(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)
        self.conf = {
            'method': 'score_ratio',  # 'binary' or 'score_ratio'
            'damping_factor': 0.85,  # PageRank damping
            'margin_cap': 3,
            'home_bonus': 0.0
        }
        if config:
            self.conf.update(config)

    def fit(self):
        n_teams = len(self.teams)
        team_map = {team: i for i, team in enumerate(self.teams)}

        # S[i][j] = Probability of moving from Team i to Team j
        S = np.zeros((n_teams, n_teams))

        # Track Games Played (The Denominator)
        games_played = np.zeros(n_teams)

        for _, row in self.games.iterrows():
            idx_h = team_map[row['HomeTeam']]
            idx_a = team_map[row['AwayTeam']]

            games_played[idx_h] += 1
            games_played[idx_a] += 1

            # 1. Determine Weight of the Vote
            if self.conf['method'] == 'binary':
                res = row['Result']
                vote_for_home = res
                vote_for_away = 1.0 - res

            else:
                # 'score_ratio'
                h_goals = row['HomeGoals'] + self.conf['home_bonus']
                a_goals = row['AwayGoals']

                diff = h_goals - a_goals
                cap = self.conf['margin_cap']
                if abs(diff) > cap:
                    if diff > 0:
                        h_goals = a_goals + cap
                    else:
                        a_goals = h_goals + cap

                total_goals = h_goals + a_goals
                if total_goals == 0: total_goals = 1

                vote_for_home = h_goals / total_goals
                vote_for_away = a_goals / total_goals

            # 2. Update Matrix (Loser/Giver -> Winner/Receiver)
            # The value is added to the numerator.
            # Later we divide by games_played to get the average.
            S[idx_a][idx_h] += vote_for_home
            S[idx_h][idx_a] += vote_for_away

        # 3. Normalize Rows by Games Played (Create Self-Loop)
        for i in range(n_teams):
            if games_played[i] > 0:
                # Average the outgoing votes over the number of games
                S[i, :] /= games_played[i]

                # Calculate Self-Loop (Retention)
                # This effectively encodes Winning % (or Vote Retention %) into the diagonal
                # If a team wins every game, off-diagonals are 0, Self-Loop is 1.0.
                row_sum = np.sum(S[i, :])

                # Handle slight float precision errors
                if row_sum > 1.0:
                    S[i, :] /= row_sum
                    S[i, i] = 0.0
                else:
                    S[i, i] = 1.0 - row_sum
            else:
                # Disconnected / No games
                S[i, i] = 1.0

        # 4. Apply Damping
        d = self.conf['damping_factor']
        U = np.ones((n_teams, n_teams)) / n_teams
        M = (d * S) + ((1 - d) * U)

        # 5. Solve Eigenvector
        try:
            vals, vecs = eig(M.T)
            idx = np.argmin(np.abs(vals - 1))
            ratings = np.real(vecs[:, idx])

            # Enforce positive
            ratings = np.abs(ratings)

            # Normalize to sum to N*100 (Average Rating = 100)
            ratings = ratings / np.sum(ratings) * n_teams * 100

        except Exception:
            # Fallback
            ratings = np.ones(n_teams) * 100

        self.ratings = {self.teams[i]: ratings[i] for i in range(n_teams)}

    def predict(self, home, away, is_neutral=False):
        r_home = self.ratings.get(home, 0)
        r_away = self.ratings.get(away, 0)
        if r_home + r_away == 0: return 0.5
        return r_home / (r_home + r_away)