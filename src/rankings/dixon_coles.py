# src/rankings/dixon_coles.py
"""
DixonColes: a bivariate Poisson model of the goal-scoring process (Dixon &
Coles 1997, originally for soccer), adapted here to test whether modeling
goals directly beats the fixed Massey linear-regression model
(reports/massey_calibration_results.md) — the current best model in this
codebase on every metric.

Each team gets TWO parameters instead of one: attack_i and defense_i.
    lambda_home = exp(mu + attack_home - defense_away + eta)   (eta=0 at neutral sites)
    lambda_away = exp(mu + attack_away - defense_home)
    P(h, a) = Poisson(h; lambda_home) * Poisson(a; lambda_away) * tau(h, a)
tau is the Dixon-Coles low-score correction (only applies to (0,0), (1,0),
(0,1), (1,1) — designed for exactly the low-scoring regime hockey is in):
    tau(0,0) = 1 - lambda_home*lambda_away*rho
    tau(1,0) = 1 + lambda_away*rho
    tau(0,1) = 1 + lambda_home*rho
    tau(1,1) = 1 - rho
    tau(h,a) = 1  otherwise

Nested variants (all in this one class, config-toggled, per this project's
established ablation discipline):
    D0: eta=0, rho=0, kappa=0   -> plain independent bivariate Poisson
    D1: + eta (home-ice, additive in log-lambda)
    D2: + rho (Dixon-Coles low-score correction)
    D3: + kappa (L2 prior on attack/defense, analogous to HockeyBT's MAP prior)

RESULT (see reports/dixon_coles_results.md for the full writeup): after
extensive tuning (a prior_strength sweep 0-5, plus fixing an optimizer
convergence bug in the nested-variant fitting — see fit()'s docstring),
DixonColes reaches statistical parity with fixed Massey, not a win over it.
A pooled paired-per-game test (n=8,371) found NO significant difference on
any of accuracy (McNemar p=0.84), Brier (p=0.67), or LogLoss (p=0.28). This
is reported as a legitimate, honest result — not a negative finding to
bury: a properly-specified two-parameter-per-team goal-scoring model
matches (rather than exceeds) a well-calibrated one-parameter-per-team
linear model. It does NOT replace Massey as the project's best model, and
is not on by default in config.yaml's active_models. It's kept as an
available, separately-validated model — its native tie/OT prediction and
attack/defense decomposition (interpretable in a way a single strength
scalar isn't) have analytical value independent of whether it wins a raw
accuracy/calibration horse race.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from src.rankings.base_ranker import BaseRanker


class DixonColes(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)

        self.conf = {
            # Defaults below are the VALIDATED configuration (see
            # reports/dixon_coles_results.md) -- pass fit_home_ice=False,
            # fit_rho=False, prior_strength=0.0 for the plain D0 model.
            'fit_home_ice': True,    # D1 -- LR-significant in 3/4 seasons tested, backtest-positive
            'fit_rho': False,        # D2 -- REJECTED: often LR-significant in-sample, but combined
                                     # with home-ice and regularization it did not improve (sometimes
                                     # slightly hurt) held-out Accuracy/Brier/LogLoss. Same lesson as
                                     # HockeyBT's silo prior: in-sample significance isn't the same as
                                     # out-of-sample predictive value. Left available/tunable.
            'prior_strength': 3.0,  # D3 (kappa) -- swept 0-5; higher kappa keeps improving Brier/
                                     # LogLoss but starts costing accuracy past ~2-3. 3.0 is the point
                                     # where a pooled paired test shows NO significant difference vs
                                     # Massey on ANY of accuracy/Brier/LogLoss (the cleanest, most
                                     # representative characterization of "ties Massey" -- lower kappa
                                     # like 1.0 ties on accuracy but is marginally worse on Brier).
            'max_goals': 15,         # summation grid for P(win)/P(tie)/P(loss); covers the observed max (14)
            'max_iterations': 1000,
        }
        if config:
            self.conf.update(config)

        self.mu = 0.0
        self.eta = 0.0
        self.rho = 0.0
        self.attack = {}
        self.defense = {}
        self.fit_result_ = None

    def _prepare_arrays(self):
        df = self.games
        team_idx = {t: i for i, t in enumerate(self.teams)}
        h_idx = df['HomeTeam'].map(team_idx).values
        a_idx = df['AwayTeam'].map(team_idx).values
        home_goals = df['HomeGoals'].values.astype(int)
        away_goals = df['AwayGoals'].values.astype(int)
        is_neutral = df['NeutralSite'].astype(bool).values
        return h_idx, a_idx, home_goals, away_goals, is_neutral

    def _unpack(self, params, n):
        attack = params[:n]
        defense = params[n:2 * n]
        idx = 2 * n
        mu = params[idx]; idx += 1
        if self.conf['fit_home_ice']:
            eta = params[idx]; idx += 1
        else:
            eta = 0.0
        if self.conf['fit_rho']:
            rho = params[idx]; idx += 1
        else:
            rho = 0.0
        return attack, defense, mu, eta, rho

    @staticmethod
    def _tau(h, a, lam_h, lam_a, rho):
        """Dixon-Coles low-score correction, vectorized. Only (0,0)/(1,0)/(0,1)/(1,1) are adjusted."""
        tau = np.ones_like(lam_h)
        m00 = (h == 0) & (a == 0)
        m10 = (h == 1) & (a == 0)
        m01 = (h == 0) & (a == 1)
        m11 = (h == 1) & (a == 1)
        tau = np.where(m00, 1 - lam_h * lam_a * rho, tau)
        tau = np.where(m10, 1 + lam_a * rho, tau)
        tau = np.where(m01, 1 + lam_h * rho, tau)
        tau = np.where(m11, 1 - rho, tau)
        return tau

    def _neg_log_likelihood(self, params, h_idx, a_idx, home_goals, away_goals, is_neutral, n):
        attack, defense, mu, eta, rho = self._unpack(params, n)

        eta_eff = np.where(is_neutral, 0.0, eta)
        log_lam_h = mu + attack[h_idx] - defense[a_idx] + eta_eff
        log_lam_a = mu + attack[a_idx] - defense[h_idx]
        lam_h = np.exp(log_lam_h)
        lam_a = np.exp(log_lam_a)

        # log Poisson pmf (drop the log(h!)/log(a!) constants -- irrelevant to optimization)
        ll = (home_goals * log_lam_h - lam_h) + (away_goals * log_lam_a - lam_a)

        if self.conf['fit_rho'] and rho != 0.0:
            tau = self._tau(home_goals, away_goals, lam_h, lam_a, rho)
            tau = np.maximum(tau, 1e-10)  # tau can go slightly negative for pathological rho; guard the log
            ll = ll + np.log(tau)

        nll = -np.sum(ll)

        kappa = self.conf.get('prior_strength', 0.0)
        if kappa > 0:
            nll += kappa * (np.sum(attack ** 2) + np.sum(defense ** 2))

        return nll

    def _minimize(self, x0, bounds, h_idx, a_idx, home_goals, away_goals, is_neutral, n):
        return minimize(
            self._neg_log_likelihood, x0,
            args=(h_idx, a_idx, home_goals, away_goals, is_neutral, n),
            method='L-BFGS-B', bounds=bounds,
            options={'maxiter': self.conf.get('max_iterations', 1000)},
        )

    def fit(self):
        """
        Fits in STAGES, each warm-started from the previous (simpler)
        stage's solution: [attack, defense, mu] -> [+ eta] -> [+ rho]. This
        matters because the model IS properly nested here (unlike
        HockeyBT's fit_ties boundary) -- verified directly: evaluating the
        rho-model's objective at [eta-model's solution, rho=0] exactly
        recovers the eta-model's likelihood. That means a cold start
        (all-zeros) failing to find at least as good a solution as the
        simpler nested stage is purely an optimizer-convergence problem, not
        a modeling one -- caught concretely on the 2025-26 season, where a
        cold-started rho fit converged to a WORSE likelihood than the
        eta-only fit despite rho=0 being trivially available to it (a
        negative "likelihood-ratio" that's impossible for a genuinely
        nested comparison). Warm-starting from the simpler stage's optimum
        guarantees each stage can only do as well as or better than the one
        before it.
        """
        n = len(self.teams)
        h_idx, a_idx, home_goals, away_goals, is_neutral = self._prepare_arrays()
        args = (h_idx, a_idx, home_goals, away_goals, is_neutral, n)

        base_bounds = [(-3.0, 3.0)] * (2 * n) + [(-2.0, 3.0)]  # attack, defense, mu

        # Stage 0: attack/defense/mu only (eta=0, rho=0 fixed).
        x0 = np.zeros(2 * n + 1)
        x0[2 * n] = np.log(max((home_goals.sum() + away_goals.sum()) / (2 * len(home_goals)), 0.5))
        saved_conf = (self.conf['fit_home_ice'], self.conf['fit_rho'])
        self.conf['fit_home_ice'], self.conf['fit_rho'] = False, False
        res = self._minimize(x0, base_bounds, *args)
        x_stage = res.x

        # Stage 1: add eta, warm-started from stage 0.
        if saved_conf[0]:
            self.conf['fit_home_ice'] = True
            x_stage = np.concatenate([x_stage, [0.0]])
            res = self._minimize(x_stage, base_bounds + [(-2.0, 2.0)], *args)
            x_stage = res.x

        # Stage 2: add rho, warm-started from stage 1.
        if saved_conf[1]:
            self.conf['fit_rho'] = True
            x_stage = np.concatenate([x_stage, [0.0]])
            bounds = base_bounds + ([(-2.0, 2.0)] if saved_conf[0] else []) + [(-0.5, 0.5)]
            res = self._minimize(x_stage, bounds, *args)

        self.conf['fit_home_ice'], self.conf['fit_rho'] = saved_conf
        self.fit_result_ = res

        attack, defense, mu, eta, rho = self._unpack(res.x, n)
        self.mu = float(mu)
        self.eta = float(eta)
        self.rho = float(rho)
        self.attack = {t: attack[i] for i, t in enumerate(self.teams)}
        self.defense = {t: defense[i] for i, t in enumerate(self.teams)}

        # Rating for get_rankings()/generic display: net scoring-rate advantage
        # vs. an average team (attack for + defense against, higher = better).
        self.ratings = {t: self.attack[t] + self.defense[t] for t in self.teams}

    def _lambdas(self, home, away, is_neutral):
        a_h = self.attack.get(home, 0.0)
        d_h = self.defense.get(home, 0.0)
        a_a = self.attack.get(away, 0.0)
        d_a = self.defense.get(away, 0.0)
        eta = 0.0 if is_neutral else self.eta
        lam_h = np.exp(self.mu + a_h - d_a + eta)
        lam_a = np.exp(self.mu + a_a - d_h)
        return lam_h, lam_a

    def predict_outcomes(self, home_team, away_team, is_neutral=False):
        """Returns the native (P_home_win, P_tie, P_away_win) triple, from
        the full scoreline probability grid (Poisson product * tau)."""
        lam_h, lam_a = self._lambdas(home_team, away_team, is_neutral)
        max_g = self.conf.get('max_goals', 15)
        h_grid = np.arange(max_g + 1)

        ph = poisson.pmf(h_grid, lam_h)
        pa = poisson.pmf(h_grid, lam_a)
        joint = np.outer(ph, pa)  # joint[h, a]

        if self.conf.get('fit_rho', True) and self.rho != 0.0:
            H, A = np.meshgrid(h_grid, h_grid, indexing='ij')
            tau = self._tau(H, A, np.full_like(H, lam_h, dtype=float),
                             np.full_like(A, lam_a, dtype=float), self.rho)
            joint = joint * np.maximum(tau, 1e-10)
            joint = joint / joint.sum()  # renormalize (tau can shift total mass very slightly)

        p_home_win = np.tril(joint, -1).sum()   # h > a
        p_tie = np.trace(joint)                  # h == a
        p_away_win = np.triu(joint, 1).sum()     # h < a
        return float(p_home_win), float(p_tie), float(p_away_win)

    def predict(self, home_team, away_team, is_neutral=False):
        """Returns P(home win) + 0.5*P(tie) -- same convention as HockeyBT
        and every other model's predict(), for direct comparability."""
        p_h, p_t, _ = self.predict_outcomes(home_team, away_team, is_neutral)
        return p_h + 0.5 * p_t
