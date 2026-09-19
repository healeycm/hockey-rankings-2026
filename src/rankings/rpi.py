# src/rankings/rpi.py
"""
RPI (Ratings Percentage Index): the direct historical predecessor to NPI for
NCAA hockey tournament selection (RPI -> Pairwise Rankings (PWR) -> NPI).
Built to answer a direct question about this project's own NPI investigation:
did replacing RPI/PWR with NPI's committee-tuned weights (weight_wp=0.25,
weight_sos=0.75, quality-win bonus, bad-wins filter) actually improve
anything, or was the older, simpler system already competitive?

Classic three-component formula:
    RPI = weight_wp * WP + weight_owp * OWP + weight_oowp * OOWP
      WP   = team's own (weighted) win percentage
      OWP  = average, over the team's own games, of that game's opponent's
             win percentage -- computed EXCLUDING games between the team and
             that specific opponent (the standard RPI convention; omitting
             this exclusion is a well-known RPI implementation bug because a
             team's own record would otherwise leak into its opponents'
             calculated strength, inflating SOS for teams with good records
             against common opponents)
      OOWP = average of the team's opponents' OWP (no further exclusion,
             matching typical RPI implementations)

Win-percentage weighting uses the same home/away multiplier convention as
NPI (0.8 home-win / 1.2 away-win) -- an NCAA-hockey-specific RPI convention,
not the generic multi-sport RPI formula, so RPI and NPI are being compared
on equal footing rather than RPI using a cruder win-pct calculation.

Unlike NPI, this class does NOT implement the "bad wins" filter (outcome-
based game removal) or a quality-win bonus -- keeping this a faithful
implementation of RPI proper, not RPI-plus-NPI's-extra-mechanisms. That
comparison (does the filter/QWB actually help, independent of the weight
choice) is exactly what comparing RPI vs NPI is meant to isolate.

predict() uses a logistic sigmoid fit via a genuinely held-out temporal
split, same discipline as Massey's beta calibration (see
reports/massey_calibration_results.md) -- NOT naive in-sample recalibration.
"""
import numpy as np
from scipy.optimize import minimize_scalar

from src.rankings.base_ranker import BaseRanker


class RPI(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)
        self.conf = {
            'weight_wp': 0.25,
            'weight_owp': 0.50,
            'weight_oowp': 0.25,
            'home_multiplier': 0.8,
            'away_multiplier': 1.2,
            'fit_beta': True,
            'beta_calib_holdout_frac': 0.2,
            'beta_fixed': 8.0,  # RPI lives on a 0-1 scale, needs a much larger beta than margin-based models
        }
        if config:
            self.conf.update(config)
        self.beta = self.conf['beta_fixed']
        self.wp_ = {}
        self.owp_ = {}
        self.oowp_ = {}

    def _game_points_long(self, df):
        """
        Returns a long-format frame, one row per (team, game) side, with
        each side's weighted points/weight for that game, PLUS the game
        index so the opponent's own pts/weight for that exact game can be
        looked up later (needed for OWP's head-to-head exclusion).
        """
        HM, AM = self.conf['home_multiplier'], self.conf['away_multiplier']
        is_neutral = df['NeutralSite'].astype(bool).values
        result = df['Result'].values

        h_win_mult = np.where(is_neutral, 1.0, HM)
        h_loss_mult = np.where(is_neutral, 1.0, AM)
        h_is_win, h_is_loss = result == 1.0, result == 0.0
        h_pts = np.where(h_is_win, h_win_mult, np.where(h_is_loss, 0.0, 0.5 * h_win_mult))
        h_wgt = np.where(h_is_win, h_win_mult, np.where(h_is_loss, h_loss_mult, 1.0))

        a_win_mult = np.where(is_neutral, 1.0, AM)
        a_loss_mult = np.where(is_neutral, 1.0, HM)
        a_is_win, a_is_loss = result == 0.0, result == 1.0
        a_pts = np.where(a_is_win, a_win_mult, np.where(a_is_loss, 0.0, 0.5 * a_win_mult))
        a_wgt = np.where(a_is_win, a_win_mult, np.where(a_is_loss, a_loss_mult, 1.0))

        game_id = np.arange(len(df))
        home = np.column_stack([game_id, df['HomeTeam'].values, df['AwayTeam'].values, h_pts, h_wgt])
        away = np.column_stack([game_id, df['AwayTeam'].values, df['HomeTeam'].values, a_pts, a_wgt])
        import pandas as pd
        cols = ['GameID', 'Team', 'Opponent', 'Pts', 'Wgt']
        long_df = pd.concat([pd.DataFrame(home, columns=cols), pd.DataFrame(away, columns=cols)],
                             ignore_index=True)
        long_df['Pts'] = long_df['Pts'].astype(float)
        long_df['Wgt'] = long_df['Wgt'].astype(float)
        long_df['GameID'] = long_df['GameID'].astype(int)
        return long_df

    def _compute_rpi(self, df, teams):
        """Computes WP, OWP, OOWP, and the combined RPI for every team in `teams`."""
        long_df = self._game_points_long(df)

        team_totals = long_df.groupby('Team')[['Pts', 'Wgt']].sum()
        wp = (team_totals['Pts'] / team_totals['Wgt']).reindex(teams).fillna(0.5)

        # Self-merge each row with its game's OTHER side, to get the
        # opponent's own pts/wgt in that exact matchup (needed to exclude
        # head-to-head from the opponent's win pct).
        merged = long_df.merge(long_df, on='GameID', suffixes=('', '_opp'))
        merged = merged[merged['Team'] != merged['Team_opp']]  # drop self-joins

        opp_totals = merged['Opponent'].map(team_totals['Pts']).values
        opp_totals_wgt = merged['Opponent'].map(team_totals['Wgt']).values
        excl_pts = opp_totals - merged['Pts_opp'].values
        excl_wgt = opp_totals_wgt - merged['Wgt_opp'].values
        # np.where evaluates both branches eagerly, so guard the division
        # itself (not just the selection) to avoid a spurious 0/0 warning
        # for a team whose entire record was against the excluded opponent.
        safe_wgt = np.where(excl_wgt > 0, excl_wgt, 1.0)
        merged['OppWP_excl'] = np.where(excl_wgt > 0, excl_pts / safe_wgt, 0.5)

        owp = merged.groupby('Team')['OppWP_excl'].mean().reindex(teams).fillna(0.5)

        oowp_raw = merged.copy()
        oowp_raw['OppOWP'] = oowp_raw['Opponent'].map(owp)
        oowp = oowp_raw.groupby('Team')['OppOWP'].mean().reindex(teams).fillna(0.5)

        w_wp = self.conf['weight_wp']
        w_owp = self.conf['weight_owp']
        w_oowp = self.conf['weight_oowp']
        rpi = w_wp * wp + w_owp * owp + w_oowp * oowp

        return wp, owp, oowp, rpi

    def _fit_beta(self, df, teams):
        if not self.conf.get('fit_beta', True):
            return self.conf.get('beta_fixed', 8.0)
        if 'Date' not in df.columns:
            return self.conf.get('beta_fixed', 8.0)

        frac = self.conf.get('beta_calib_holdout_frac', 0.2)
        df_sorted = df.sort_values('Date')
        n_games = len(df_sorted)
        split = int(n_games * (1 - frac))
        if split < 100 or (n_games - split) < 30:
            return self.conf.get('beta_fixed', 8.0)

        inner_train = df_sorted.iloc[:split]
        inner_holdout = df_sorted.iloc[split:]

        inner_teams = sorted(set(inner_train['HomeTeam']) | set(inner_train['AwayTeam']))
        _, _, _, rpi_inner = self._compute_rpi(inner_train, inner_teams)

        h_rpi = inner_holdout['HomeTeam'].map(rpi_inner).fillna(0.5).values
        a_rpi = inner_holdout['AwayTeam'].map(rpi_inner).fillna(0.5).values
        diff = h_rpi - a_rpi
        result = inner_holdout['Result'].values

        valid = result != 0.5
        y = (result[valid] == 1.0).astype(float)
        x = diff[valid]
        if len(y) < 20 or len(set(y)) < 2:
            return self.conf.get('beta_fixed', 8.0)

        def nll(beta):
            p = np.clip(1 / (1 + np.exp(-beta * x)), 1e-12, 1 - 1e-12)
            return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

        res = minimize_scalar(nll, bounds=(0.5, 40.0), method='bounded')
        return float(res.x) if res.success else self.conf.get('beta_fixed', 8.0)

    def fit(self):
        df = self.games
        wp, owp, oowp, rpi = self._compute_rpi(df, self.teams)
        self.wp_ = wp.to_dict()
        self.owp_ = owp.to_dict()
        self.oowp_ = oowp.to_dict()
        self.ratings = rpi.to_dict()

        self.beta = self._fit_beta(df, self.teams)

    def predict(self, home, away, is_neutral=False):
        r_home = self.ratings.get(home, 0.5)
        r_away = self.ratings.get(away, 0.5)
        diff = r_home - r_away
        return 1 / (1 + np.exp(-self.beta * diff))
