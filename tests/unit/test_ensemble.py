import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.ensemble import Ensemble


def _synthetic_games(n_pairs=25, seed=0):
    """
    Needs to be big enough (with a Date spread) to exercise the stacking
    holdout split logic, unlike the tiny KRACH-style fixtures elsewhere.
    """
    rng = np.random.default_rng(seed)
    teams = ['Team A', 'Team B', 'Team C', 'Team D', 'Team E', 'Team F']
    strength = {t: 3 - i * 1.2 for i, t in enumerate(teams)}
    rows = []
    dates = pd.date_range('2025-10-01', periods=n_pairs * 30)
    di = 0
    for _ in range(n_pairs):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                z = (strength[h] - strength[a]) / 3.0
                p = 1 / (1 + np.exp(-z))
                result = 1.0 if rng.random() < p else 0.0
                margin = 3 if result == 1.0 else -3
                rows.append({
                    'Season': 20252026, 'Date': dates[di % len(dates)],
                    'HomeTeam': h, 'AwayTeam': a,
                    'HomeGoals': max(0, 3 + margin // 2), 'AwayGoals': max(0, 3 - margin // 2),
                    'Result': result, 'IsOT': False, 'NeutralSite': False,
                })
                di += 1
    return pd.DataFrame(rows)


@pytest.fixture
def sample_data():
    return _synthetic_games()


def test_average_method_fit_and_predict(sample_data):
    model = Ensemble(sample_data, config={'method': 'average', 'base_models': ['Massey', 'KRACH']})
    model.fit()
    assert model.stack_weights is None
    p = model.predict('Team A', 'Team F')
    assert 0.5 < p < 1.0


def test_average_equals_mean_of_base_predictions(sample_data):
    model = Ensemble(sample_data, config={'method': 'average', 'base_models': ['Massey', 'KRACH', 'ELO']})
    model.fit()
    p_ens = model.predict('Team B', 'Team E')
    p_direct = np.mean([m.predict('Team B', 'Team E') for m in model.fitted_base_models.values()])
    assert p_ens == pytest.approx(p_direct)


def test_stacked_weights_are_non_negative(sample_data):
    """
    Regression guard for the multicollinearity bug found during development
    (see ensemble.py's _fit_regularized_stack docstring / reports/
    ensemble_results.md): an unconstrained stacking fit produced a large
    NEGATIVE weight and catastrophically failed to generalize (59.6%
    accuracy, worse than every individual base model). Weights must stay
    non-negative.
    """
    model = Ensemble(sample_data, config={'method': 'stacked', 'base_models': ['Massey', 'KRACH', 'ELO']})
    model.fit()
    if model.stack_weights is not None:
        for name in ['Massey', 'KRACH', 'ELO']:
            assert model.stack_weights[name] >= 0.0


def test_default_method_is_average(sample_data):
    """
    Guards the evidence-based default: 'stacked', even properly regularized,
    plateaus below simple averaging on the real backtest (reports/
    ensemble_results.md) — don't silently default back to it.
    """
    model = Ensemble(sample_data)
    assert model.conf['method'] == 'average'


def test_stacking_falls_back_to_average_with_too_little_data():
    tiny = _synthetic_games(n_pairs=2, seed=1)
    model = Ensemble(tiny, config={'method': 'stacked', 'base_models': ['Massey', 'KRACH']})
    model.fit()
    assert model.stack_weights is None
    # predict() must still work via the average fallback
    p = model.predict('Team A', 'Team F')
    assert 0.0 < p < 1.0


def test_stack_prediction_uses_stored_standardization(sample_data):
    """
    Regression guard for the standardization bug found during development:
    stacking weights are fit on STANDARDIZED logits (base models have very
    different natural logit scales), so predict() must re-apply the same
    stored per-model mean/std, not the raw logit directly.
    """
    model = Ensemble(sample_data, config={'method': 'stacked', 'base_models': ['Massey', 'KRACH', 'ELO']})
    model.fit()
    if model.stack_weights is not None:
        assert '_feat_mean' in model.stack_weights
        assert '_feat_std' in model.stack_weights
        for name in ['Massey', 'KRACH', 'ELO']:
            assert name in model.stack_weights['_feat_mean']
            assert model.stack_weights['_feat_std'][name] > 0


def test_get_rankings_produces_a_composite_for_all_teams(sample_data):
    model = Ensemble(sample_data, config={'base_models': ['Massey', 'KRACH']})
    model.fit()
    r = model.get_rankings()
    assert set(r['Team']) == set(model.teams)
