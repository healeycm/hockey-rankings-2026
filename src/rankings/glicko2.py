# src/rankings/glicko2.py
"""
Glicko-2 (Glickman 2001) — a genuinely different paradigm from every other
model in this codebase: sequential Bayesian-filtering updates (one game at
a time, in chronological order) rather than a batch MLE/eigenvector/least-
squares solve over the whole schedule at once. Unlike plain ELO (already
implemented), each team carries THREE state variables, not one:
    rating (mu)       -- the usual skill estimate
    RD (phi)           -- rating deviation: how UNCERTAIN that estimate is
    volatility (sigma) -- how erratically the team's true strength itself
                          seems to be changing over time
This gives genuine per-team uncertainty quantification (e.g. "ranked 14th,
but with a wide RD because they've played few common opponents") that
nothing else in this codebase provides, and RD naturally decays connectivity
problems: a team with few/no games has high RD, which correctly makes it
contribute little "vote" against well-established opponents.

Standard Glicko-2 processes discrete RATING PERIODS (batches of games).
College hockey doesn't have a natural period the way chess tournaments do,
so — following common practice when adapting Glicko-2 to a continuous
stream of individual games — each single game is treated as its own rating
period per team, processed strictly in chronological order (same
chronological-sequential-update pattern already used by this codebase's
ELO implementation).

Algorithm (Glickman's published Glicko-2 specification):
    Internal scale: mu = (r - 1500)/173.7178, phi = RD/173.7178
    g(phi_j)  = 1 / sqrt(1 + 3*phi_j^2/pi^2)
    E(mu, mu_j, phi_j) = 1 / (1 + exp(-g(phi_j)*(mu - mu_j)))
    v         = [ g(phi_j)^2 * E*(1-E) ]^-1                (estimated variance)
    Delta     = v * g(phi_j) * (s - E)                      (estimated improvement)
    New volatility solved via the Illinois algorithm (a bracketed
        regula-falsi variant) on Glickman's f(x) root equation -- the one
        genuinely nontrivial numerical step in the whole algorithm.
    phi*      = sqrt(phi^2 + sigma'^2)
    phi'      = 1 / sqrt(1/phi*^2 + 1/v)
    mu'       = mu + phi'^2 * g(phi_j) * (s - E)
A team that doesn't play in a period only has its RD grow (uncertainty
increases the longer a team goes unobserved) -- not modeled explicitly here
since every game updates both participants immediately; this matters mainly
for teams with long gaps between games, which is left as a known
simplification (see module-level "Open items" in
reports/keener_and_glicko2_results.md).
"""
import numpy as np

from src.rankings.base_ranker import BaseRanker

_SCALE = 173.7178
_BASE_RATING = 1500.0
_BASE_RD = 350.0
_BASE_VOL = 0.06


class Glicko2(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)
        self.conf = {
            'tau': 0.5,              # system constant controlling volatility change (Glickman recommends 0.3-1.2)
            'base_rating': _BASE_RATING,
            'base_rd': _BASE_RD,
            'base_volatility': _BASE_VOL,
            'home_advantage': 0.0,   # additive on the internal mu scale; 0 = unfit default, see fit_home_advantage
            'fit_home_advantage': True,
            'calib_holdout_frac': 0.2,
        }
        if config:
            self.conf.update(config)

        self.rd = {}       # team -> current RD (display scale)
        self.volatility = {}

    @staticmethod
    def _g(phi):
        return 1.0 / np.sqrt(1.0 + 3.0 * phi ** 2 / np.pi ** 2)

    @staticmethod
    def _E(mu, mu_j, phi_j):
        return 1.0 / (1.0 + np.exp(-Glicko2._g(phi_j) * (mu - mu_j)))

    def _new_volatility(self, phi, sigma, v, delta, tau):
        """Illinois algorithm (bracketed regula-falsi) for Glickman's volatility root equation."""
        a = np.log(sigma ** 2)

        def f(x):
            ex = np.exp(x)
            num = ex * (delta ** 2 - phi ** 2 - v - ex)
            den = 2 * (phi ** 2 + v + ex) ** 2
            return (num / den) - (x - a) / (tau ** 2)

        A = a
        if delta ** 2 > phi ** 2 + v:
            B = np.log(delta ** 2 - phi ** 2 - v)
        else:
            k = 1
            while f(a - k * tau) < 0:
                k += 1
                if k > 100:  # safety valve; shouldn't happen for realistic inputs
                    return sigma
            B = a - k * tau

        fA, fB = f(A), f(B)
        for _ in range(100):
            if abs(B - A) <= 1e-6:
                break
            C = A + (A - B) * fA / (fB - fA)
            fC = f(C)
            if fC * fB < 0:
                A, fA = B, fB
            else:
                fA = fA / 2.0
            B, fB = C, fC

        return np.exp(A / 2.0)

    def _update_one_side(self, mu, phi, sigma, mu_j, phi_j, s, tau):
        """One player's update from a single game against one opponent (their own single-game 'rating period')."""
        g_j = self._g(phi_j)
        E_j = self._E(mu, mu_j, phi_j)
        v = 1.0 / (g_j ** 2 * E_j * (1 - E_j) + 1e-12)
        delta = v * g_j * (s - E_j)

        sigma_new = self._new_volatility(phi, sigma, v, delta, tau)
        phi_star = np.sqrt(phi ** 2 + sigma_new ** 2)
        phi_new = 1.0 / np.sqrt(1.0 / phi_star ** 2 + 1.0 / v)
        mu_new = mu + phi_new ** 2 * g_j * (s - E_j)

        return mu_new, phi_new, sigma_new

    def _run_sequential(self, df, home_advantage):
        """Runs the full chronological sequential update, returning final per-team (mu, phi, sigma) on the internal scale."""
        base_r, base_rd, base_sigma = self.conf['base_rating'], self.conf['base_rd'], self.conf['base_volatility']
        tau = self.conf['tau']

        mu = {t: (base_r - _BASE_RATING) / _SCALE for t in self.teams}
        phi = {t: base_rd / _SCALE for t in self.teams}
        sigma = {t: base_sigma for t in self.teams}

        df_sorted = df.sort_values('Date') if 'Date' in df.columns else df

        for _, row in df_sorted.iterrows():
            h, a = row['HomeTeam'], row['AwayTeam']
            if h not in mu or a not in mu:
                continue
            result = row['Result']
            is_neutral = bool(row['NeutralSite'])
            hia = 0.0 if is_neutral else home_advantage

            mu_h, phi_h, sig_h = mu[h], phi[h], sigma[h]
            mu_a, phi_a, sig_a = mu[a], phi[a], sigma[a]

            s_h = 1.0 if result == 1.0 else (0.0 if result == 0.0 else 0.5)
            s_a = 1.0 - s_h

            # Home advantage enters as a symmetric shift applied only when
            # computing each side's view of the OTHER's effective rating.
            mu_h_new, phi_h_new, sig_h_new = self._update_one_side(mu_h, phi_h, sig_h, mu_a - hia, phi_a, s_h, tau)
            mu_a_new, phi_a_new, sig_a_new = self._update_one_side(mu_a, phi_a, sig_a, mu_h + hia, phi_h, s_a, tau)

            mu[h], phi[h], sigma[h] = mu_h_new, phi_h_new, sig_h_new
            mu[a], phi[a], sigma[a] = mu_a_new, phi_a_new, sig_a_new

        return mu, phi, sigma

    def _fit_home_advantage(self, df):
        if not self.conf.get('fit_home_advantage', True) or 'Date' not in df.columns:
            return self.conf.get('home_advantage', 0.0)

        frac = self.conf.get('calib_holdout_frac', 0.2)
        df_sorted = df.sort_values('Date')
        n_games = len(df_sorted)
        split = int(n_games * (1 - frac))
        if split < 200 or (n_games - split) < 50:
            return self.conf.get('home_advantage', 0.0)

        inner_train = df_sorted.iloc[:split]
        inner_holdout = df_sorted.iloc[split:]

        from scipy.optimize import minimize_scalar

        def nll(hia):
            mu, phi, _ = self._run_sequential(inner_train, hia)
            preds, ys = [], []
            for _, row in inner_holdout.iterrows():
                h, a = row['HomeTeam'], row['AwayTeam']
                if h not in mu or a not in mu or row['Result'] == 0.5:
                    continue
                is_neutral = bool(row['NeutralSite'])
                eff_hia = 0.0 if is_neutral else hia
                z = self._g(phi[a]) * (mu[h] + eff_hia - mu[a])
                p = 1 / (1 + np.exp(-z))
                preds.append(np.clip(p, 1e-12, 1 - 1e-12))
                ys.append(1.0 if row['Result'] == 1.0 else 0.0)
            if len(ys) < 20:
                return 1e6
            preds, ys = np.array(preds), np.array(ys)
            return -np.mean(ys * np.log(preds) + (1 - ys) * np.log(1 - preds))

        res = minimize_scalar(nll, bounds=(-1.0, 1.0), method='bounded')
        return float(res.x) if res.success else self.conf.get('home_advantage', 0.0)

    def fit(self):
        df = self.games
        home_advantage = self._fit_home_advantage(df)
        self.conf['home_advantage'] = home_advantage

        mu, phi, sigma = self._run_sequential(df, home_advantage)

        # Store both internal (for predict()) and display-scale ratings.
        self._mu, self._phi = mu, phi
        self.volatility = sigma
        self.rd = {t: phi[t] * _SCALE for t in self.teams}
        self.ratings = {t: mu[t] * _SCALE + _BASE_RATING for t in self.teams}

    def predict(self, home_team, away_team, is_neutral=False):
        mu_h = self._mu.get(home_team, 0.0)
        mu_a = self._mu.get(away_team, 0.0)
        phi_a = self._phi.get(away_team, self.conf['base_rd'] / _SCALE)
        hia = 0.0 if is_neutral else self.conf.get('home_advantage', 0.0)

        z = self._g(phi_a) * (mu_h + hia - mu_a)
        return float(1 / (1 + np.exp(-z)))
