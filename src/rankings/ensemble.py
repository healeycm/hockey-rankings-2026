# src/rankings/ensemble.py
"""
Ensemble: combines predictions from multiple base ranking models.

Motivation: checked pairwise error correlation across the project's
strongest models (Massey, HockeyBT, KRACH, ELO, RPI) on the pooled 5-year
backtest before building this — see reports/ensemble_results.md. Error
correlations range 0.94-0.99 across ALL pairs, meaning these models extract
very similar signal from the same games (they differ mainly in functional
form, not in what information they use — Massey is the only one that uses
goal margin rather than win/loss/tie alone). This sets a modest expectation
going in: ensembling headroom is limited when base models are this
correlated, unlike the classic ensembling case of genuinely diverse,
weakly-correlated models.

Two combination methods:
  'average' — unweighted mean of predicted probabilities. Zero free
      parameters, cannot overfit.
  'stacked' — logistic regression of the outcome on each base model's
      LOGIT-transformed prediction, giving each model a learned weight
      (+ intercept). Has real degrees of freedom, so — learning directly
      from this project's repeated experience with in-sample calibration
      overfitting (reports/lrmc_calibration.md) — the stacking weights are
      fit on a genuinely HELD-OUT temporal split within the training
      window, exactly like Massey's beta and RPI's beta: base models are
      fit on the first ~(1-frac) of training games by date, their
      out-of-sample predictions on the remaining holdout are used to fit
      the stacking weights, and separately the DEPLOYED base models are
      refit on the full training window for actual prediction.
"""
import numpy as np
import pandas as pd

from src.rankings.base_ranker import BaseRanker
from src.rankings.massey import Massey
from src.rankings.hockey_bt import HockeyBT
from src.rankings.krach import KRACH
from src.rankings.elo import ELO
from src.rankings.rpi import RPI
from src.rankings.npi import NPI
from src.rankings.dixon_coles import DixonColes

_MODEL_REGISTRY = {
    'Massey': (Massey, {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True}),
    'HockeyBT': (HockeyBT, {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4}),
    'KRACH': (KRACH, {}),
    'ELO': (ELO, {}),
    'RPI': (RPI, {}),
    'NPI': (NPI, {}),
    'DixonColes': (DixonColes, {'fit_home_ice': True, 'fit_rho': False, 'prior_strength': 3.0}),
}

_EPS = 1e-6


def _logit(p):
    p = np.clip(p, _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


class Ensemble(BaseRanker):
    def __init__(self, games_df, config=None):
        super().__init__(games_df)
        self.conf = {
            # DEFAULT method is 'average', not 'stacked' -- see
            # reports/ensemble_results.md. Base models here are extremely
            # correlated (pairwise prediction correlation 0.83-0.98), so
            # stacking has little real diversity to exploit; even after
            # fixing two real bugs found during development (unconstrained
            # weights overfitting catastrophically to 59.6% accuracy from
            # multicollinearity; then a wrong regularization target that
            # degenerated toward a constant prediction instead of the
            # sensible average), properly-regularized stacking still
            # plateaus BELOW simple averaging on the 5-year backtest.
            # Neither method beats Massey (paired test: no significant
            # difference on any metric, p=0.30-0.52) -- ensembling adds
            # complexity here without adding predictive value.
            'base_models': ['Massey', 'HockeyBT', 'KRACH', 'ELO', 'RPI'],
            'method': 'average',  # 'average' or 'stacked'
            'stack_holdout_frac': 0.2,
            'stack_ridge': 1.0,  # kappa; shrinks stacking weights toward the equal-weight (average) prior
            'base_configs': {},  # optional per-model config overrides, keyed by name
        }
        if config:
            self.conf.update(config)

        self.fitted_base_models = {}
        self.stack_weights = None  # None = simple average (either by choice or fallback)

    def _make_model(self, name, df):
        cls, default_cfg = _MODEL_REGISTRY[name]
        cfg = {**default_cfg, **self.conf.get('base_configs', {}).get(name, {})}
        try:
            m = cls(df, config=cfg)
        except TypeError:
            m = cls(df)
        m.fit()
        return m

    def _fit_stack_weights(self, df, names):
        if 'Date' not in df.columns:
            return None

        frac = self.conf.get('stack_holdout_frac', 0.2)
        df_sorted = df.sort_values('Date')
        n_games = len(df_sorted)
        split = int(n_games * (1 - frac))
        if split < 200 or (n_games - split) < 50:
            return None  # not enough data for a clean holdout split

        inner_train = df_sorted.iloc[:split]
        inner_holdout = df_sorted.iloc[split:]

        inner_models = {name: self._make_model(name, inner_train) for name in names}

        rows = []
        for _, row in inner_holdout.iterrows():
            if row['Result'] == 0.5:
                continue
            feats = []
            for name in names:
                try:
                    p = inner_models[name].predict(row['HomeTeam'], row['AwayTeam'], row['NeutralSite'])
                except Exception:
                    p = 0.5
                feats.append(_logit(p))
            rows.append((feats, 1.0 if row['Result'] == 1.0 else 0.0))

        if len(rows) < 30:
            return None
        X = np.array([r[0] for r in rows])
        y = np.array([r[1] for r in rows])
        if len(set(y)) < 2:
            return None

        return self._fit_regularized_stack(X, y, names)

    def _fit_regularized_stack(self, X, y, names):
        """
        L2-regularized logistic stacking on STANDARDIZED logit features, fit
        via scipy rather than unconstrained sm.Logit MLE.

        Two things had to be fixed to make this generalize at all, both
        confirmed empirically via backtest, not assumed:

        1. Regularization: base models here are extremely correlated
           (pairwise prediction correlation 0.83-0.98 — see
           reports/ensemble_results.md's error-correlation check). An
           unconstrained fit is a classic multicollinearity failure,
           confirmed empirically (backtested to 59.6% accuracy, worse than
           every individual base model, driven by a large NEGATIVE
           coefficient on a genuinely decent model). Weights are also
           constrained non-negative — a negative weight on a base model
           that performs reasonably well alone is itself a symptom of
           overfitting to the calibration-holdout's noise, not a real
           complementary correction.
        2. Feature standardization: raw logits from different base models
           have very different natural scales (e.g. KRACH's wide rating
           spread produces far more extreme logits than ELO's) — applying
           one ridge penalty strength to weights multiplying differently-
           scaled inputs isn't a fair regularization. Stats (mean/std)
           computed on this same calibration holdout, stored, and
           re-applied identically at prediction time.
        3. The regularization TARGET matters, not just its strength — this
           was a real bug, not just under-tuning. Standard ridge penalizes
           ||weights||^2, shrinking weights toward ZERO. But zero weights
           on standardized features means predictions collapse toward the
           intercept alone (a near-constant, uninformative prediction) —
           confirmed empirically: increasing kappa made results
           monotonically WORSE even after fixing (2) above, converging
           toward a degenerate constant rather than anything sensible.
           What's actually wanted is shrinkage toward the SIMPLE-AVERAGE
           ensemble (equal weight 1/n_models on every model) as the
           sensible fallback prior, not toward all-zero. Penalizing
           ||weights - 1/n_models||^2 instead fixes this: at kappa=0 it's
           the free (overfit-prone) MLE, and as kappa -> infinity it
           converges exactly to simple averaging rather than to nothing.
        """
        from scipy.optimize import minimize

        n_models = X.shape[1]
        kappa = self.conf.get('stack_ridge', 1.0)
        prior_weight = 1.0 / n_models

        feat_mean = X.mean(axis=0)
        feat_std = X.std(axis=0)
        feat_std = np.where(feat_std > 1e-8, feat_std, 1.0)
        Xs = (X - feat_mean) / feat_std

        def nll(params):
            intercept, weights = params[0], params[1:]
            z = intercept + Xs @ weights
            p = np.clip(1 / (1 + np.exp(-z)), _EPS, 1 - _EPS)
            loss = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
            loss += kappa * np.sum((weights - prior_weight) ** 2)
            return loss

        x0 = np.concatenate([[0.0], np.full(n_models, 1.0 / n_models)])
        bounds = [(-3.0, 3.0)] + [(0.0, 5.0)] * n_models  # weights constrained non-negative
        res = minimize(nll, x0, method='L-BFGS-B', bounds=bounds)
        if not res.success:
            return None

        weights = {'intercept': float(res.x[0])}
        weights.update({name: float(res.x[i + 1]) for i, name in enumerate(names)})
        weights['_feat_mean'] = dict(zip(names, feat_mean.tolist()))
        weights['_feat_std'] = dict(zip(names, feat_std.tolist()))
        return weights

    def fit(self):
        df = self.games
        names = self.conf['base_models']

        # Deployed base models: fit on the FULL training window.
        self.fitted_base_models = {name: self._make_model(name, df) for name in names}

        if self.conf.get('method') == 'stacked':
            self.stack_weights = self._fit_stack_weights(df, names)
        else:
            self.stack_weights = None

        # Composite rating for get_rankings()/display: z-score each base
        # model's ratings (they're on incompatible scales) and average.
        # Not used by predict() -- that always re-derives from each base
        # model's own predict(), which is properly calibrated per-model.
        composite = pd.Series(0.0, index=self.teams)
        n_contributing = pd.Series(0, index=self.teams)
        for name, model in self.fitted_base_models.items():
            r = pd.Series(model.ratings).reindex(self.teams)
            if r.std() > 0:
                z = (r - r.mean()) / r.std()
                composite = composite.add(z.fillna(0), fill_value=0)
                n_contributing += r.notna().astype(int)
        self.ratings = composite.to_dict()

    def predict(self, home_team, away_team, is_neutral=False):
        names = self.conf['base_models']
        preds = {}
        for name in names:
            try:
                preds[name] = self.fitted_base_models[name].predict(home_team, away_team, is_neutral)
            except Exception:
                preds[name] = 0.5

        if self.stack_weights is None:
            return float(np.mean(list(preds.values())))

        feat_mean = self.stack_weights['_feat_mean']
        feat_std = self.stack_weights['_feat_std']
        z = self.stack_weights['intercept']
        for name in names:
            standardized = (_logit(preds[name]) - feat_mean[name]) / feat_std[name]
            z += self.stack_weights[name] * standardized
        return float(1 / (1 + np.exp(-z)))
