import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.rpi import RPI


def _synthetic_games(n_pairs=25, seed=0):
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
                    'HomeTeam': h, 'AwayTeam': a, 'HomeGoals': 3, 'AwayGoals': 1,
                    'Result': result, 'IsOT': False, 'NeutralSite': False,
                })
                di += 1
    return pd.DataFrame(rows)


@pytest.fixture
def sample_data():
    return _synthetic_games()


def test_fit_and_rank(sample_data):
    model = RPI(sample_data)
    model.fit()
    assert model.ratings['Team A'] > model.ratings['Team D']


def test_predict_range(sample_data):
    model = RPI(sample_data)
    model.fit()
    p = model.predict('Team A', 'Team D')
    assert 0.5 < p < 1.0


def test_rpi_formula_matches_components(sample_data):
    """RPI = weight_wp*WP + weight_owp*OWP + weight_oowp*OOWP, exactly."""
    model = RPI(sample_data)
    model.fit()
    for t in model.teams:
        expected = (model.conf['weight_wp'] * model.wp_[t]
                    + model.conf['weight_owp'] * model.owp_[t]
                    + model.conf['weight_oowp'] * model.oowp_[t])
        assert model.ratings[t] == pytest.approx(expected)


def test_owp_excludes_head_to_head():
    """
    Hand-checkable toy case: A beat B once; B beat C twice; C beat D once.
    B's overall record is 2-1, but excluding the A-B game (B's only loss),
    B's record vs everyone else is 2-0 -- so OWP_A (built only from B) must
    be 1.0, not B's unadjusted win pct of 2/3. This is the textbook RPI
    head-to-head exclusion bug if implemented naively.
    """
    data = pd.DataFrame({
        'Season': [20252026] * 4,
        'Date': pd.to_datetime(['2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04']),
        'HomeTeam': ['A', 'B', 'B', 'C'], 'AwayTeam': ['B', 'C', 'C', 'D'],
        'HomeGoals': [3, 3, 3, 3], 'AwayGoals': [1, 1, 1, 1],
        'Result': [1.0, 1.0, 1.0, 1.0], 'IsOT': [False] * 4, 'NeutralSite': [False] * 4,
    })
    model = RPI(data, config={'fit_beta': False, 'home_multiplier': 1.0, 'away_multiplier': 1.0})
    model.fit()
    assert model.owp_['A'] == pytest.approx(1.0)


def test_beta_fit_via_holdout_not_hardcoded(sample_data):
    model = RPI(sample_data)
    model.fit()
    assert model.beta != model.conf['beta_fixed']


def test_beta_falls_back_when_data_too_small():
    data = _synthetic_games(n_pairs=3, seed=1)
    model = RPI(data)
    model.fit()
    assert model.beta == model.conf['beta_fixed']


def test_validated_defaults_are_shipped(sample_data):
    model = RPI(sample_data)
    assert model.conf['weight_wp'] == 0.25
    assert model.conf['weight_owp'] == 0.50
    assert model.conf['weight_oowp'] == 0.25
    assert model.conf['fit_beta'] is True
