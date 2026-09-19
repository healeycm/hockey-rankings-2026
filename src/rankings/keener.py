# src/rankings/keener.py
"""
Keener's method (Keener 1993, "The Perron-Frobenius Theorem and the Ranking
of Football Teams") — a genuinely different eigenvector structure from
Markov/LRMC already in this codebase. Where Markov/LRMC build a
column-stochastic transition matrix (each team's outgoing mass sums to 1)
and take its stationary distribution, Keener's method builds an
unnormalized positive matrix from a SKEWED score-share statistic and takes
its Perron eigenvector directly — no stochastic normalization at all.

Construction, for each pair of teams (i, j) that have played:
    s_i = i's goals in the game + 1   (the "+1" is Keener's own convention:
                                        credit for showing up / avoids a
                                        0-in-numerator degenerate ratio)
    s_j = j's goals in the game + 1
    r_ij = s_i / (s_i + s_j)          (i's share of adjusted scoring)
    h(r) = 1/2 + sign(r - 1/2) * sqrt(|2r - 1|) / 2   ("skew" function)
A_ij accumulates h(r_ij) (weight-averaged) across all games between i and j.
The skew function is the key idea: it's concave near the extremes and
convex near 1/2 (via the sqrt), which COMPRESSES blowout score shares (a
10-1 win and a 5-1 win end up close together after skewing) while staying
sensitive to close games — directly addressing the same "margin is noisy in
a low-scoring sport" concern this project's LRMC work identified, but via a
bounded nonlinear transform rather than a hard cap.

A small uniform perturbation `epsilon` is added to every off-diagonal entry
so the matrix is strictly positive — required for the Perron-Frobenius
theorem to guarantee a unique, positive dominant eigenvector (this also
naturally "connects" otherwise-disconnected parts of the schedule graph,
similar in spirit to HockeyBT's MAP prior, but structurally built into the
matrix rather than the likelihood).

predict() fits a home-ice term and a log-ratio scale via a genuinely
held-out temporal split — same discipline as Massey's beta and RPI's beta
(NOT the in-sample recalibration that overfit for HockeyLRMC — see
reports/lrmc_calibration.md).
"""
import numpy as np
from scipy.optimize import minimize_scalar

from src.rankings.base_ranker import BaseRanker


class Keener(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)
        self.conf = {
            # RESULT (reports/keener_and_glicko2_results.md): Keener trails
            # Massey decisively (accuracy 61.7-62.0% vs Massey's 64.9% across
            # an epsilon sweep 0.01-0.3; paired test vs Massey p<1e-20 on
            # Brier/LogLoss, p<1e-4 on accuracy). epsilon itself is nearly
            # flat across that whole range -- not a tuning problem, a real
            # gap. NOT in active_models by default. eps=0.1 was the
            # best-scoring point in the sweep, kept as the default since
            # this model isn't being recommended anyway.
            'epsilon': 0.1,        # positivity perturbation, standard Keener range 0.02-0.1
            'score_offset': 1.0,   # the "+1" credit-for-playing adjustment
            'fit_calibration': True,
            'calib_holdout_frac': 0.2,
            'beta_fixed': 3.0,
            'home_effect_fixed': 0.2,
        }
        if config:
            self.conf.update(config)

        self.beta = self.conf['beta_fixed']
        self.home_effect = self.conf['home_effect_fixed']

    @staticmethod
    def _skew(r):
        r = np.clip(r, 0.0, 1.0)
        return 0.5 + np.sign(r - 0.5) * np.sqrt(np.abs(2 * r - 1)) / 2.0

    def _build_matrix(self, df, teams):
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}
        A_sum = np.zeros((n, n))
        A_wgt = np.zeros((n, n))

        offset = self.conf['score_offset']
        hg = df['HomeGoals'].values.astype(float) + offset
        ag = df['AwayGoals'].values.astype(float) + offset
        h_idx = df['HomeTeam'].map(idx).values
        a_idx = df['AwayTeam'].map(idx).values

        r_home = hg / (hg + ag)
        h_home = self._skew(r_home)
        h_away = 1.0 - h_home  # symmetric by construction (skew is an odd function around 0.5)

        np.add.at(A_sum, (h_idx, a_idx), h_home)
        np.add.at(A_wgt, (h_idx, a_idx), 1.0)
        np.add.at(A_sum, (a_idx, h_idx), h_away)
        np.add.at(A_wgt, (a_idx, h_idx), 1.0)

        A = np.divide(A_sum, A_wgt, out=np.zeros_like(A_sum), where=A_wgt > 0)

        eps = self.conf['epsilon']
        # Perturb only the entries that could plausibly be a "game" (off-diagonal),
        # towards a neutral 0.5 share, guaranteeing strict positivity everywhere.
        A_perturbed = (1 - eps) * A + eps * 0.5
        np.fill_diagonal(A_perturbed, 0.0)

        return A_perturbed

    def _compute_ratings(self, df, teams):
        n = len(teams)
        A = self._build_matrix(df, teams)

        # Perron eigenvector: dominant eigenvalue of a strictly positive
        # matrix is guaranteed real, positive, and simple (Perron-Frobenius).
        vals, vecs = np.linalg.eig(A)
        idx = np.argmax(vals.real)
        vec = np.real(vecs[:, idx])
        if np.all(vec < 0):
            vec = -vec
        vec = np.abs(vec)
        vec = vec / vec.sum() * n  # normalize to mean 1, matching a comparable scale to other eigenvector models

        return dict(zip(teams, vec))

    def _fit_calibration(self, df, teams):
        if not self.conf.get('fit_calibration', True) or 'Date' not in df.columns:
            return self.conf['beta_fixed'], self.conf['home_effect_fixed']

        frac = self.conf.get('calib_holdout_frac', 0.2)
        df_sorted = df.sort_values('Date')
        n_games = len(df_sorted)
        split = int(n_games * (1 - frac))
        if split < 100 or (n_games - split) < 30:
            return self.conf['beta_fixed'], self.conf['home_effect_fixed']

        inner_train = df_sorted.iloc[:split]
        inner_holdout = df_sorted.iloc[split:]
        inner_teams = sorted(set(inner_train['HomeTeam']) | set(inner_train['AwayTeam']))
        inner_ratings = self._compute_ratings(inner_train, inner_teams)

        h_r = inner_holdout['HomeTeam'].map(inner_ratings).values
        a_r = inner_holdout['AwayTeam'].map(inner_ratings).values
        valid_mask = ~(np.isnan(h_r) | np.isnan(a_r))
        h_r, a_r = h_r[valid_mask], a_r[valid_mask]
        is_neutral = inner_holdout['NeutralSite'].astype(bool).values[valid_mask]
        result = inner_holdout['Result'].values[valid_mask]

        eps = 1e-6
        log_ratio = np.log(np.clip(h_r, eps, None) / np.clip(a_r, eps, None))
        decisive = result != 0.5
        y = (result[decisive] == 1.0).astype(float)
        x_ratio = log_ratio[decisive]
        x_home = (~is_neutral[decisive]).astype(float)
        if len(y) < 20 or len(set(y)) < 2:
            return self.conf['beta_fixed'], self.conf['home_effect_fixed']

        def nll(params):
            beta, home_eff = params
            z = home_eff * x_home + beta * x_ratio
            p = np.clip(1 / (1 + np.exp(-z)), 1e-12, 1 - 1e-12)
            return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

        from scipy.optimize import minimize
        res = minimize(nll, x0=[self.conf['beta_fixed'], self.conf['home_effect_fixed']],
                        method='Nelder-Mead')
        if res.success and np.all(np.abs(res.x) < 20):
            return float(res.x[0]), float(res.x[1])
        return self.conf['beta_fixed'], self.conf['home_effect_fixed']

    def fit(self):
        df = self.games
        self.ratings = self._compute_ratings(df, self.teams)
        self.beta, self.home_effect = self._fit_calibration(df, self.teams)

    def predict(self, home_team, away_team, is_neutral=False):
        r_home = self.ratings.get(home_team, 1.0)
        r_away = self.ratings.get(away_team, 1.0)
        eps = 1e-6
        log_ratio = np.log(max(r_home, eps) / max(r_away, eps))
        home_term = 0.0 if is_neutral else self.home_effect
        z = home_term + self.beta * log_ratio
        return 1 / (1 + np.exp(-z))
