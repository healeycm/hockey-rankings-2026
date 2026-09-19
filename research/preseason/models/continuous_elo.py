# research/preseason/models/continuous_elo.py
"""
538-style continuous Elo (research-only, PLAN.md P1 Arm B): unlike
production's src/rankings/elo.py (which refits from a flat/prior-seeded
start EVERY season), this runs Elo continuously across every season in the
archive and only pulls ratings toward the mean by a fixed fraction at each
season boundary -- the prior emerges naturally from the long-run rating
rather than being built as a separate step. Same update rule as
production's ELO (margin-of-victory multiplier, home-ice term), so this is
a fair comparison of "how the prior is constructed", not a different Elo
formula.

One pass over the FULL chronological game history produces a ratings
snapshot at every requested cutoff date, which is far cheaper than
re-fitting from scratch per cutoff (season boundaries are crossed once,
not once per cutoff test).
"""
import math
import pandas as pd


class ContinuousElo:
    def __init__(self, config=None):
        self.conf = {
            'k_factor': 20,
            'home_advantage': 50,
            'mov_multiplier': True,
            'start_rating': 1000,
            'reversion_frac': 0.3,  # fraction pulled back toward the mean at each offseason
        }
        if config:
            self.conf.update(config)

    def snapshots_at_cutoffs(self, full_history_df, cutoff_dates):
        """
        Runs one continuous Elo pass over every game in full_history_df
        (regardless of season) and returns {cutoff_date: {team: rating}},
        one ratings snapshot per requested cutoff -- each snapshot reflects
        every game strictly BEFORE that cutoff (same train/test boundary
        convention as BacktestEngine._get_cutoff_date's train_df).
        """
        df = full_history_df.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)

        cutoffs_sorted = sorted(cutoff_dates)
        snapshots = {}
        cutoff_ptr = 0

        ratings = {}
        current_season = None
        k = self.conf['k_factor']
        hia = self.conf['home_advantage']
        start = self.conf['start_rating']
        reversion = self.conf['reversion_frac']

        for _, row in df.iterrows():
            game_date = row['Date']

            # Snapshot for every pending cutoff this game's date has now
            # reached or passed (handles cutoffs that fall in a gap with no
            # games, e.g. a season not yet started, or the 2016-17 gap).
            while cutoff_ptr < len(cutoffs_sorted) and game_date >= cutoffs_sorted[cutoff_ptr]:
                snapshots[cutoffs_sorted[cutoff_ptr]] = dict(ratings)
                cutoff_ptr += 1

            season = row['Season']
            if current_season is not None and season != current_season:
                # Offseason reversion: pull every rated team back toward
                # the global mean of currently-rated teams (538's approach)
                # -- applied once per season boundary crossed, not per game.
                if ratings:
                    mu = sum(ratings.values()) / len(ratings)
                    ratings = {t: r + reversion * (mu - r) for t, r in ratings.items()}
            current_season = season

            home, away = row['HomeTeam'], row['AwayTeam']
            result = row['Result']
            is_neutral = row.get('NeutralSite', False)
            margin = abs(row['HomeGoals'] - row['AwayGoals'])

            r_home = ratings.setdefault(home, start)
            r_away = ratings.setdefault(away, start)

            eff_hia = hia if not is_neutral else 0
            diff = r_away - r_home - eff_hia
            e_home = 1.0 / (1.0 + (10 ** (diff / 400.0)))

            mult = math.log(margin + 1) if self.conf['mov_multiplier'] else 1.0
            change = (k * mult) * (result - e_home)

            ratings[home] = r_home + change
            ratings[away] = r_away - change

        # Any remaining cutoffs are after the last game in the data (e.g. a
        # future/not-yet-started season) -- snapshot the final state.
        while cutoff_ptr < len(cutoffs_sorted):
            snapshots[cutoffs_sorted[cutoff_ptr]] = dict(ratings)
            cutoff_ptr += 1

        return snapshots

    def predict_from_ratings(self, ratings, home, away, is_neutral=False):
        start = self.conf['start_rating']
        r_home = ratings.get(home, start)
        r_away = ratings.get(away, start)
        hia = self.conf['home_advantage'] if not is_neutral else 0
        diff = r_away - r_home - hia
        return 1.0 / (1.0 + (10 ** (diff / 400.0)))
