import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.glicko2 import Glicko2


def _synthetic_games(n_pairs=20, seed=0):
    rng = np.random.default_rng(seed)
    teams = ['Team A', 'Team B', 'Team C', 'Team D']
    strength = {'Team A': 3, 'Team B': 1, 'Team C': -1, 'Team D': -3}
    rows = []
    dates = pd.date_range('2025-10-01', periods=n_pairs * 6)
    di = 0
    for _ in range(n_pairs):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                z = (strength[h] - strength[a]) / 3.0
                p = 1 / (1 + np.exp(-z))
                result = 1.0 if rng.random() < p else 0.0
                rows.append({
                    'Season': 20252026, 'Date': dates[di % len(dates)],
                    'HomeTeam': h, 'AwayTeam': a, 'Result': result,
                    'IsOT': False, 'NeutralSite': False,
                })
                di += 1
    return pd.DataFrame(rows)


@pytest.fixture
def sample_data():
    return _synthetic_games()


def test_fit_and_rank(sample_data):
    model = Glicko2(sample_data, config={'fit_home_advantage': False})
    model.fit()
    assert model.ratings['Team A'] > model.ratings['Team D']


def test_predict_range(sample_data):
    model = Glicko2(sample_data, config={'fit_home_advantage': False})
    model.fit()
    p = model.predict('Team A', 'Team D')
    assert 0.5 < p < 1.0


def test_rd_shrinks_with_more_games():
    """RD (uncertainty) should decrease as a team accumulates more games,
    the core Glicko-2 property that distinguishes it from ELO."""
    few_games = _synthetic_games(n_pairs=2, seed=1)
    many_games = _synthetic_games(n_pairs=30, seed=1)
    m_few = Glicko2(few_games, config={'fit_home_advantage': False})
    m_few.fit()
    m_many = Glicko2(many_games, config={'fit_home_advantage': False})
    m_many.fit()
    assert m_many.rd['Team A'] < m_few.rd['Team A']


def test_no_nan_or_inf_in_output(sample_data):
    model = Glicko2(sample_data)
    model.fit()
    ratings = pd.Series(model.ratings)
    rds = pd.Series(model.rd)
    vols = pd.Series(model.volatility)
    assert not ratings.isna().any() and np.isfinite(ratings).all()
    assert not rds.isna().any() and np.isfinite(rds).all()
    assert not vols.isna().any() and np.isfinite(vols).all()


def test_volatility_stays_near_base_for_stable_synthetic_data(sample_data):
    """Synthetic teams here have constant (non-drifting) strength, so
    volatility should stay close to its starting value, not blow up."""
    model = Glicko2(sample_data, config={'fit_home_advantage': False})
    model.fit()
    for v in model.volatility.values():
        assert 0.01 < v < 0.2


def test_home_advantage_recovered_when_present():
    rng = np.random.default_rng(2)
    teams = ['Team A', 'Team B', 'Team C', 'Team D']
    strength = {'Team A': 1.0, 'Team B': 0.5, 'Team C': -0.5, 'Team D': -1.0}
    rows = []
    dates = pd.date_range('2025-10-01', periods=300)
    di = 0
    for _ in range(30):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                z = (strength[h] - strength[a]) + 1.0  # deliberate strong home bump
                p = 1 / (1 + np.exp(-z))
                result = 1.0 if rng.random() < p else 0.0
                rows.append({'Season': 20252026, 'Date': dates[di % len(dates)],
                             'HomeTeam': h, 'AwayTeam': a, 'Result': result,
                             'IsOT': False, 'NeutralSite': False})
                di += 1
    data = pd.DataFrame(rows)
    model = Glicko2(data, config={'fit_home_advantage': True})
    model.fit()
    assert model.conf['home_advantage'] > 0.1
