import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.keener import Keener


def _synthetic_games(n_pairs=25, seed=0):
    rng = np.random.default_rng(seed)
    teams = ['Team A', 'Team B', 'Team C', 'Team D']
    strength = {'Team A': 3.0, 'Team B': 1.0, 'Team C': -1.0, 'Team D': -3.0}
    rows = []
    dates = pd.date_range('2025-10-01', periods=n_pairs * 6)
    di = 0
    for _ in range(n_pairs):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                diff = strength[h] - strength[a]
                hg = max(0, int(round(3 + diff / 2 + rng.normal(0, 0.5))))
                ag = max(0, int(round(3 - diff / 2 + rng.normal(0, 0.5))))
                if hg == ag:
                    hg += 1
                result = 1.0 if hg > ag else 0.0
                rows.append({
                    'Season': 20252026, 'Date': dates[di % len(dates)],
                    'HomeTeam': h, 'AwayTeam': a, 'HomeGoals': hg, 'AwayGoals': ag,
                    'Result': result, 'IsOT': False, 'NeutralSite': False,
                })
                di += 1
    return pd.DataFrame(rows)


@pytest.fixture
def sample_data():
    return _synthetic_games()


def test_fit_and_rank(sample_data):
    model = Keener(sample_data)
    model.fit()
    assert model.ratings['Team A'] > model.ratings['Team D']


def test_ratings_all_strictly_positive(sample_data):
    """Perron-Frobenius guarantee: with the positivity perturbation, the
    dominant eigenvector must be strictly positive for every team."""
    model = Keener(sample_data)
    model.fit()
    assert all(v > 0 for v in model.ratings.values())


def test_predict_range(sample_data):
    model = Keener(sample_data)
    model.fit()
    p = model.predict('Team A', 'Team D')
    assert 0.5 < p < 1.0


def test_skew_function_is_identity_at_half():
    assert Keener._skew(np.array([0.5]))[0] == pytest.approx(0.5)


def test_skew_function_compresses_extremes():
    """
    The skew function should map a moderate ratio (e.g. 0.7) further from
    0.5 than a linear map would, and an extreme ratio (0.95) should NOT be
    proportionally as far from 0.5 as the raw ratio suggests -- this is the
    blowout-compression property the whole model is built around.
    """
    moderate = Keener._skew(np.array([0.7]))[0] - 0.5
    extreme = Keener._skew(np.array([0.95]))[0] - 0.5
    # Raw ratio distances from 0.5 are 0.2 and 0.45 (ratio 2.25x);
    # skewed distances should compress that ratio.
    raw_ratio = 0.45 / 0.2
    skewed_ratio = extreme / moderate
    assert skewed_ratio < raw_ratio


def test_validated_defaults_are_shipped(sample_data):
    model = Keener(sample_data)
    assert model.conf['epsilon'] == 0.1
