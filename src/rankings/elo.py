# src/rankings/elo.py
import numpy as np
import math
import pandas as pd
from src.rankings.base_ranker import BaseRanker


class ELO(BaseRanker):
    def __init__(self, games_df, config=None, prior=None):
        super().__init__(games_df)

        self.conf = {
            'k_factor': 20,
            'home_advantage': 50,  # Added to Home Rating before calculating expected win prob
            'mov_multiplier': True,
            'start_rating': 1000,
            'prior_weight': 0.6,  # see config.yaml preseason.elo_carryover_weight
        }
        if config:
            self.conf.update(config)

        # `prior`: optional {team: prior_rating} from src/rankings/priors.py,
        # on ELO's own rating scale (mean ~= start_rating). Blended toward
        # start_rating by prior_weight rather than used verbatim, so a bad
        # prior estimate doesn't fully override the flat default; weight=1.0
        # reproduces plain carryover, weight=0 (or prior=None) reproduces
        # today's flat-start behavior exactly.
        self.prior = prior or {}

    def fit(self):
        """
        Iterates through games chronologically to update ELO ratings.
        """
        # Ensure Date is datetime
        if 'Date' in self.games.columns:
            self.games['Date'] = pd.to_datetime(self.games['Date'])
            
        # Sort by date
        sorted_games = self.games.sort_values('Date')

        # Initialize Ratings -- blend the preseason prior (if any) toward
        # start_rating by prior_weight; teams with no prior entry just get
        # the flat start_rating, unchanged from before priors existed.
        pw = self.conf.get('prior_weight', 0.0)
        start = self.conf['start_rating']
        self.ratings = {
            team: (start + pw * (self.prior[team] - start)) if team in self.prior else start
            for team in self.teams
        }

        for _, row in sorted_games.iterrows():
            home, away = row['HomeTeam'], row['AwayTeam']
            result = row['Result']  # 1.0 (Home Win), 0.5 (Tie), 0.0 (Away Win)
            is_neutral = row['NeutralSite']
            margin = abs(row['HomeGoals'] - row['AwayGoals'])

            r_home = self.ratings.get(home, self.conf['start_rating'])
            r_away = self.ratings.get(away, self.conf['start_rating'])

            # 1. Calculate Expected Result
            # E_home = 1 / (1 + 10^((R_away - R_home - HIA) / 400))
            hia = self.conf['home_advantage'] if not is_neutral else 0
            diff = r_away - r_home - hia
            e_home = 1.0 / (1.0 + (10 ** (diff / 400.0)))

            # 2. Calculate Multiplier (Margin of Victory)
            # K_mult = ln(|margin| + 1)
            k = self.conf['k_factor']
            if self.conf['mov_multiplier']:
                mult = math.log(margin + 1)
                # Correction to prevent autocorrelation scaling issues?
                # Standard Elo implementations often use: K * mult * (Result - Expected)
                k = k * mult

            # 3. Update Ratings
            # New = Old + K * (Actual - Expected)
            change = k * (result - e_home)

            self.ratings[home] = r_home + change
            self.ratings[away] = r_away - change

    def predict(self, home, away, is_neutral=False):
        r_home = self.ratings.get(home, self.conf['start_rating'])
        r_away = self.ratings.get(away, self.conf['start_rating'])
        hia = self.conf['home_advantage'] if not is_neutral else 0

        diff = r_away - r_home - hia
        prob_home = 1.0 / (1.0 + (10 ** (diff / 400.0)))
        return prob_home