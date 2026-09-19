# src/rankings/massey.py
"""
Massey ratings from goal differential, via a regularized linear system.

Original implementation used three hardcoded, never-validated constants:
`margin_cap=3` (reasonable, kept), `home_ice_advantage=0.2` (a guess, now
fit jointly with team ratings by least squares), and `beta=0.15` in
predict()'s margin-to-probability sigmoid (an outright guess — the comment
literally said "generic hockey slope beta ~ 0.15"). Since classification
accuracy depends only on the SIGN of the predicted margin, that guess never
hurt accuracy at all, which is exactly why Massey topped the roster on
accuracy (see reports/goal_based_ranking_plan.md) while having mediocre
Brier/LogLoss — a calibration bug, not a modeling weakness.

Fixes (see reports/massey_calibration_results.md for the validation):
  1. Home-ice advantage is now fit jointly with team ratings by ridge
     regression (an extra column in the design matrix), not hardcoded.
  2. beta is fit via a genuinely HELD-OUT temporal split within the
     training window (fit ratings on the first ~80% of training games by
     date, fit beta against those ratings' OUT-OF-SAMPLE predictions on the
     remaining ~20%). This is deliberately NOT a naive in-sample refit —
     HockeyLRMC's calibration attempt (reports/lrmc_calibration.md) showed
     that fitting a probability-scale parameter on the SAME games used to
     fit the ratings overfits and makes LogLoss worse, not better. This
     class does the held-out version of that fix instead of skipping it.
  3. Ridge regularization (`ridge_lambda`) on team ratings, both for
     numerical stability (handles the classic Massey rank-deficiency —
     shifting every rating by the same constant doesn't change any
     predicted margin — via minimum-norm least squares, no manual
     sum-to-zero constraint row needed) and as a tunable analogous to
     HockeyBT's MAP prior.

Setting fit_home_ice=False, ridge_lambda=0, fit_beta=False reproduces the
original (buggy) Massey behavior exactly — used as this class's own
correctness gate.

Two further experiments added (2026, see reports/massey_improvement_plan.md
and reports/massey_experiments_2026.md for the plan and results):
  4. `time_decay_halflife`: optional recency weighting on training games,
     the same weighted-least-squares treatment LRMC already has (weight =
     2^-(days_ago/halflife), games closer to the fit's reference date count
     more). DEFAULT OFF (None = every game weighted equally, unchanged from
     before this was added).
  5. `fit_rest_advantage`: optional extra fitted covariate for schedule
     rest (days since each team's last game, capped and normalized),
     fit jointly with team ratings/home-ice the same way home-ice itself
     is. Requires `predict()`'s new optional `game_date` kwarg to have any
     effect on a specific future prediction — every existing caller that
     doesn't pass it gets a rest contribution of exactly 0.0, i.e. IDENTICAL
     behavior to before this existed. DEFAULT OFF.
  6. `use_manpower_margin`: optional alternative fitting target — the
     margin is computed from even-manpower goals only (excludes power-play/
     short-handed/empty-net goals; see
     src/data/advanced_metrics_scraper.py's extract_even_manpower_goals())
     instead of the raw final-score margin, isolating how a team performed
     when neither side had a man advantage. Falls back to the raw margin
     per-game when Home_EV_Goals/Away_EV_Goals aren't available (older
     seasons/games not covered by the CHN scrape), same fallback pattern as
     LRMC's use_xg/fallback_to_goals. DEFAULT OFF.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from src.rankings.base_ranker import BaseRanker


class Massey(BaseRanker):
    def __init__(self, games_df, config=None, prior=None):
        super().__init__(games_df)
        self.conf = {
            'margin_cap': 3,
            'fit_home_ice': True,       # False -> use the fixed `home_ice_advantage` below instead
            'home_ice_advantage': 0.2,  # only used when fit_home_ice=False
            'ridge_lambda': 1.0,        # 0 = original unregularized Massey (via minimum-norm lstsq)
            'fit_beta': True,           # False -> use the fixed `beta_fixed` below instead
            'beta_fixed': 0.15,         # the original hardcoded guess; fallback only
            'beta_calib_holdout_frac': 0.2,

            # Preseason prior pull (see src/rankings/priors.py and
            # config.yaml's preseason.massey_prior_lambda). A SECOND ridge
            # augmentation, independent of ridge_lambda above: ridge_lambda
            # pulls every rating toward 0 for numerical stability;
            # prior_lambda pulls toward the supplied prior rating instead.
            # 0 (or no prior) reproduces today's behavior exactly -- the
            # prior's pull is in units of "pseudo-games" and fades on its
            # own as real games accumulate (n_games grows, the prior rows
            # don't), so no explicit decay schedule is needed.
            'prior_lambda': 0.0,

            # Recency weighting (see module docstring, item 4). None = no
            # decay, every game weighted equally -- unchanged default.
            'time_decay_halflife': None,

            # Rest/fatigue adjustment (see module docstring, item 5).
            'fit_rest_advantage': False,
            'rest_days_cap': 5,          # rest beyond this many days is treated the same as this many
            'default_rest_days': None,  # None -> uses rest_days_cap (a team's first game of the
                                         # season/window is treated as "fully rested", not penalized
                                         # for lacking a prior game to measure from)

            # Manpower-adjusted margin (see module docstring, item 6).
            'use_manpower_margin': False,
        }
        if config:
            self.conf.update(config)
        if self.conf.get('default_rest_days') is None:
            self.conf['default_rest_days'] = self.conf['rest_days_cap']

        self.home_ice_advantage_fit = None
        self.rest_weight_fit = 0.0
        self.beta = self.conf['beta_fixed']
        self._last_game_date = {}  # team -> most recent game date seen during fit(); used by predict()
        self.prior = prior or {}  # {team: prior_rating}, on Massey's own rating scale (see priors.py)

    def _capped_margin(self, df):
        margin = (df['HomeGoals'].astype(float) - df['AwayGoals'].astype(float)).values

        if self.conf.get('use_manpower_margin', False):
            has_ev = 'Home_EV_Goals' in df.columns and 'Away_EV_Goals' in df.columns
            if has_ev:
                ev_valid = df['Home_EV_Goals'].notna() & df['Away_EV_Goals'].notna()
                ev_margin = (df['Home_EV_Goals'].astype(float) - df['Away_EV_Goals'].astype(float)).values
                # Fall back to the raw goal margin per-game where EV data
                # isn't available (older/uncovered seasons) -- same pattern
                # as LRMC's use_xg/fallback_to_goals.
                margin = np.where(ev_valid.values, ev_margin, margin)

        cap = self.conf.get('margin_cap')
        if cap and cap > 0:
            margin = np.clip(margin, -cap, cap)
        return margin

    def _time_decay_weights(self, df):
        """
        Recency weighting (module docstring item 4), mirroring LRMC's
        `_calculate_game_weights`: weight = 2^-(days_ago/halflife), where
        days_ago is measured from THIS df's own latest game date (so it
        works the same whether df is the full training window or the
        `_fit_beta` inner_train sub-window). Returns an all-ones array when
        disabled (halflife falsy) -- the identity weighting, so this is a
        strict generalization of the pre-existing unweighted fit.
        """
        halflife = self.conf.get('time_decay_halflife')
        if not halflife or halflife <= 0 or 'Date' not in df.columns:
            return np.ones(len(df))
        dates = pd.to_datetime(df['Date'])
        max_date = dates.max()
        days_ago = (max_date - dates).dt.days.values
        return 2.0 ** (-(days_ago / halflife))

    def _rest_features(self, df):
        """
        Rest/fatigue adjustment (module docstring item 5). For each game,
        computes how many days each side has had since ITS previous game
        within this df (chronological; resets naturally at the start of
        whatever window df covers -- a team's first game in df is treated
        as `default_rest_days`, i.e. fully rested, not penalized for having
        no prior game to measure from within this window).

        Returns (rest_diff, last_game_date): rest_diff is a per-game array
        in roughly [-1, 1] ((home_rest - away_rest) / rest_days_cap, each
        side's rest capped at rest_days_cap first); last_game_date is the
        {team: latest date seen} map built along the way, reused by
        predict() to compute rest for a genuinely future game date.
        """
        cap = self.conf.get('rest_days_cap', 5)
        default_days = self.conf.get('default_rest_days', cap)

        dates = pd.to_datetime(df['Date']).values
        homes = df['HomeTeam'].values
        aways = df['AwayTeam'].values
        order = np.argsort(dates, kind='stable')

        n = len(df)
        home_rest = np.empty(n)
        away_rest = np.empty(n)
        last_date = {}
        for i in order:
            h, a, d = homes[i], aways[i], dates[i]
            h_prev = last_date.get(h)
            a_prev = last_date.get(a)
            home_rest[i] = min(max((d - h_prev) / np.timedelta64(1, 'D'), 0), cap) if h_prev is not None else default_days
            away_rest[i] = min(max((d - a_prev) / np.timedelta64(1, 'D'), 0), cap) if a_prev is not None else default_days
            last_date[h] = d
            last_date[a] = d

        rest_diff = (home_rest - away_rest) / cap
        return rest_diff, last_date

    def _fit_ratings(self, h_idx, a_idx, margin, is_neutral, n, weights=None, rest_diff=None, prior_vec=None):
        """
        Solves for team ratings (and, if fit_home_ice/fit_rest_advantage, a
        joint home-ice/rest term) via ridge-regularized, optionally
        recency-weighted least squares. Ridge is implemented as augmented
        pseudo-observations rather than explicit normal equations (more
        numerically stable, and np.linalg.lstsq's minimum-norm SVD solution
        handles the classic rank-1 Massey degeneracy automatically when
        ridge_lambda=0, replacing the old manual "overwrite the last row
        with a sum-to-zero constraint" hack). Recency weighting is applied
        as standard weighted least squares (scale each row/target by
        sqrt(weight) before solving) -- the ridge pseudo-observation rows
        are left unweighted (weight=1), matching how they're unaffected by
        any other per-game covariate here.

        `prior_vec` (optional, length n, aligned to self.teams): a SECOND,
        independent set of ridge pseudo-observations pulling each team's
        rating toward prior_vec[i] instead of 0, weighted by
        conf['prior_lambda']. Teams with no prior (prior_vec[i]==0 and
        prior_lambda==0) behave exactly as before this existed.
        """
        n_games = len(margin)
        fit_hia = self.conf.get('fit_home_ice', True)
        fit_rest = self.conf.get('fit_rest_advantage', False) and rest_diff is not None
        n_cols = n + int(fit_hia) + int(fit_rest)

        A = np.zeros((n_games, n_cols))
        rows = np.arange(n_games)
        A[rows, h_idx] += 1
        A[rows, a_idx] -= 1

        y = margin.copy()
        col = n
        if fit_hia:
            A[:, col] = (~is_neutral).astype(float)
            col += 1
        else:
            # Old behavior: subtract the fixed HIA from the target before
            # regressing on team ratings only (no free HIA column).
            hia = self.conf.get('home_ice_advantage', 0.2)
            y = np.where(is_neutral, y, y - hia)

        if fit_rest:
            A[:, col] = rest_diff
            col += 1

        if weights is not None:
            sqrt_w = np.sqrt(weights)
            A = A * sqrt_w[:, None]
            y = y * sqrt_w

        lam = self.conf.get('ridge_lambda', 0.0)
        if lam > 0:
            # Penalize only the team-rating columns, not the home-ice/rest columns.
            aug = np.eye(n, n_cols) * np.sqrt(lam)
            A = np.vstack([A, aug])
            y = np.concatenate([y, np.zeros(n)])

        prior_lambda = self.conf.get('prior_lambda', 0.0)
        if prior_lambda > 0 and prior_vec is not None:
            aug = np.eye(n, n_cols) * np.sqrt(prior_lambda)
            A = np.vstack([A, aug])
            y = np.concatenate([y, prior_vec])

        x, *_ = np.linalg.lstsq(A, y, rcond=None)
        ratings = x[:n]
        idx = n
        home_effect = x[idx] if fit_hia else self.conf.get('home_ice_advantage', 0.2)
        idx += int(fit_hia)
        rest_weight = x[idx] if fit_rest else 0.0
        return home_effect, rest_weight, ratings

    def _fit_beta(self, df, team_idx, n):
        if not self.conf.get('fit_beta', True):
            return self.conf.get('beta_fixed', 0.15)

        if 'Date' not in df.columns:
            return self.conf.get('beta_fixed', 0.15)

        frac = self.conf.get('beta_calib_holdout_frac', 0.2)
        df_sorted = df.sort_values('Date').reset_index(drop=True)
        n_games = len(df_sorted)
        split = int(n_games * (1 - frac))

        # Guard rails: don't attempt a noisy calibration fit on too little data.
        if split < 100 or (n_games - split) < 30:
            return self.conf.get('beta_fixed', 0.15)

        # Rest features computed on the FULL sorted window (not just
        # inner_train) so a team's rest going into a holdout game correctly
        # reflects its last game in inner_train, not an artificial reset at
        # the split boundary.
        fit_rest = self.conf.get('fit_rest_advantage', False)
        rest_diff_full, _ = self._rest_features(df_sorted) if fit_rest else (None, None)

        inner_train = df_sorted.iloc[:split]
        inner_holdout = df_sorted.iloc[split:]

        h_tr = inner_train['HomeTeam'].map(team_idx).values
        a_tr = inner_train['AwayTeam'].map(team_idx).values
        neutral_tr = inner_train['NeutralSite'].astype(bool).values
        margin_tr = self._capped_margin(inner_train)
        weights_tr = self._time_decay_weights(inner_train)
        rest_tr = rest_diff_full[:split] if fit_rest else None
        home_effect, rest_weight, ratings = self._fit_ratings(
            h_tr, a_tr, margin_tr, neutral_tr, n, weights=weights_tr, rest_diff=rest_tr
        )

        h_ho = inner_holdout['HomeTeam'].map(team_idx).values
        a_ho = inner_holdout['AwayTeam'].map(team_idx).values
        neutral_ho = inner_holdout['NeutralSite'].astype(bool).values
        # Genuinely out-of-sample: these ratings never saw the holdout games.
        exp_margin_ho = ratings[h_ho] - ratings[a_ho] + np.where(neutral_ho, 0.0, home_effect)
        if fit_rest:
            rest_ho = rest_diff_full[split:]
            exp_margin_ho = exp_margin_ho + rest_weight * rest_ho
        result_ho = inner_holdout['Result'].values

        valid = result_ho != 0.5
        y = (result_ho[valid] == 1.0).astype(float)
        x = exp_margin_ho[valid]
        if len(y) < 20 or len(set(y)) < 2:
            return self.conf.get('beta_fixed', 0.15)

        def nll(beta):
            p = np.clip(1 / (1 + np.exp(-beta * x)), 1e-12, 1 - 1e-12)
            return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

        res = minimize_scalar(nll, bounds=(0.01, 5.0), method='bounded')
        return float(res.x) if res.success else self.conf.get('beta_fixed', 0.15)

    def fit(self):
        n = len(self.teams)
        team_idx = {team: i for i, team in enumerate(self.teams)}
        df = self.games

        h_idx = df['HomeTeam'].map(team_idx).values
        a_idx = df['AwayTeam'].map(team_idx).values
        is_neutral = df['NeutralSite'].astype(bool).values
        margin = self._capped_margin(df)
        weights = self._time_decay_weights(df)

        rest_diff = None
        if self.conf.get('fit_rest_advantage', False):
            rest_diff, self._last_game_date = self._rest_features(df)

        prior_vec = None
        if self.conf.get('prior_lambda', 0.0) > 0 and self.prior:
            prior_vec = np.array([self.prior.get(team, 0.0) for team in self.teams])

        # Final deployed ratings use ALL available training games.
        home_effect, rest_weight, ratings = self._fit_ratings(
            h_idx, a_idx, margin, is_neutral, n, weights=weights, rest_diff=rest_diff, prior_vec=prior_vec
        )
        self.home_ice_advantage_fit = home_effect
        self.rest_weight_fit = rest_weight
        self.ratings = {self.teams[i]: ratings[i] for i in range(n)}

        # beta is calibrated on a held-out split (see _fit_beta docstring) —
        # NOT refit against the same games used for the ratings above.
        self.beta = self._fit_beta(df, team_idx, n)

    def predict(self, home, away, is_neutral=False, game_date=None):
        """
        `game_date` is optional and defaults to None, in which case the
        rest/fatigue term is exactly 0.0 regardless of `fit_rest_advantage`
        -- every EXISTING caller (run_system.py, MonteCarloSimulator,
        BacktestEngine, RankInterpreter) predicts without passing it, so
        this is a strict behavioral no-op for all of them. Pass the
        upcoming game's actual scheduled date to get a rest-adjusted
        prediction (see reports/massey_experiments_2026.md's validation
        script for the pattern).
        """
        r_home = self.ratings.get(home, 0.0)
        r_away = self.ratings.get(away, 0.0)
        hia = 0.0 if is_neutral else (self.home_ice_advantage_fit or 0.0)

        rest_term = 0.0
        if self.conf.get('fit_rest_advantage', False) and game_date is not None:
            cap = self.conf.get('rest_days_cap', 5)
            default_days = self.conf.get('default_rest_days', cap)
            gd = pd.Timestamp(game_date)
            h_prev = self._last_game_date.get(home)
            a_prev = self._last_game_date.get(away)
            h_rest = min(max((gd - h_prev) / np.timedelta64(1, 'D'), 0), cap) if h_prev is not None else default_days
            a_rest = min(max((gd - a_prev) / np.timedelta64(1, 'D'), 0), cap) if a_prev is not None else default_days
            rest_term = self.rest_weight_fit * ((h_rest - a_rest) / cap)

        exp_margin = r_home - r_away + hia + rest_term
        prob = 1 / (1 + np.exp(-self.beta * exp_margin))
        return prob
