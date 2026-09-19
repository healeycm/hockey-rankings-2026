import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.hockey_bt import HockeyBT
from src.rankings.krach import KRACH


def _synthetic_games(n_pairs=20, seed=0):
    """A larger synthetic dataset than the 2-game KRACH fixture — needed
    because HockeyBT's optimizer has real free parameters (theta, nu) that
    need enough games to identify, unlike KRACH's closed-form iteration."""
    rng = np.random.default_rng(seed)
    teams = ['Team A', 'Team B', 'Team C', 'Team D']
    rows = []
    dates = pd.date_range('2025-10-01', periods=n_pairs * 6)
    di = 0
    for _ in range(n_pairs):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                # Team A/B are strong, C/D are weak, so there's real signal to fit.
                strength = {'Team A': 3, 'Team B': 2, 'Team C': -2, 'Team D': -3}
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


def test_hockey_bt_fit_and_rank(sample_data):
    model = HockeyBT(sample_data)
    model.fit()
    rankings = model.get_rankings()
    rank_a = rankings.loc[rankings['Team'] == 'Team A', 'Rating'].iloc[0]
    rank_d = rankings.loc[rankings['Team'] == 'Team D', 'Rating'].iloc[0]
    assert rank_a > rank_d


def test_hockey_bt_predict_range(sample_data):
    model = HockeyBT(sample_data)
    model.fit()
    p = model.predict('Team A', 'Team D')
    assert 0.5 < p <= 1.0
    p_rev = model.predict('Team D', 'Team A')
    assert p_rev < 0.5


def test_predict_outcomes_sums_to_one(sample_data):
    model = HockeyBT(sample_data, config={'fit_ties': True})
    model.fit()
    p_h, p_t, p_a = model.predict_outcomes('Team A', 'Team B')
    assert p_h > 0 and p_t >= 0 and p_a > 0
    assert p_h + p_t + p_a == pytest.approx(1.0)


def test_predict_matches_outcome_expectation(sample_data):
    """predict() must equal P(home win) + 0.5*P(tie), the same convention
    used everywhere else in this project for a 'HomeWinProb' scalar."""
    model = HockeyBT(sample_data, config={'fit_ties': True})
    model.fit()
    p = model.predict('Team A', 'Team C')
    p_h, p_t, p_a = model.predict_outcomes('Team A', 'Team C')
    assert p == pytest.approx(p_h + 0.5 * p_t)


def test_k0_reproduces_krach():
    """
    Correctness gate: with theta and nu both fixed off (K0), HockeyBT is
    exactly standard Bradley-Terry -- the same model KRACH's iterative
    solver computes. On real DI data the two should agree to within
    numerical-optimizer tolerance (verified in reports/hockey_bt_results.md
    at correlation 0.9999999995 / max abs diff ~0.01 on a mean-100 scale;
    this test uses a looser bound appropriate for a small synthetic fixture
    so it isn't flaky).
    """
    data = _synthetic_games(n_pairs=30, seed=1)
    krach = KRACH(data)
    krach.fit()
    bt = HockeyBT(data, config={'fit_home_ice': False, 'fit_ties': False, 'prior_strength': 0.0})
    bt.fit()

    assert bt.theta == pytest.approx(1.0)
    assert bt.nu == pytest.approx(0.0)

    k = pd.Series(krach.ratings)
    b = pd.Series(bt.ratings)[k.index]
    corr = np.corrcoef(k.values, b.values)[0, 1]
    assert corr > 0.999
    # Both are normalized to mean=100, so absolute-scale comparison is valid.
    assert np.abs(k.values - b.values).max() < 2.0


def test_home_ice_term_shifts_prediction_toward_home_team(sample_data):
    """
    Isolates the predict() mechanism directly: a theta>1 (home-ice edge)
    must raise P(home win) relative to a neutral-site prediction between
    the same two teams. Sets theta explicitly rather than relying on the
    fit recovering one, since the synthetic fixture's data-generating
    process has no true home-ice effect built in (result depends only on
    team strength) — a real fit on it could legitimately land on either
    side of 1.0 by chance. theta>1 being correctly fit from real data is
    already verified in reports/hockey_bt_results.md (theta consistently
    >1 across all 4 seasons tested there).
    """
    model = HockeyBT(sample_data, config={'fit_home_ice': True, 'fit_ties': False})
    model.fit()
    model.theta = 1.5  # override: isolate the mechanism, not the fit
    p_home = model.predict('Team B', 'Team C', is_neutral=False)
    p_neutral = model.predict('Team B', 'Team C', is_neutral=True)
    assert p_home > p_neutral


def test_home_ice_is_recovered_when_present_in_data():
    """Unlike the strength-only synthetic fixture, this dataset has a real,
    deliberate home-ice boost baked into the data-generating process — the
    fit should recover theta > 1."""
    rng = np.random.default_rng(3)
    teams = ['Team A', 'Team B', 'Team C', 'Team D']
    strength = {'Team A': 1.0, 'Team B': 0.5, 'Team C': -0.5, 'Team D': -1.0}
    rows = []
    dates = pd.date_range('2025-10-01', periods=300)
    di = 0
    for _ in range(40):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                z = (strength[h] - strength[a]) + 0.6  # deliberate home-ice bump
                p = 1 / (1 + np.exp(-z))
                result = 1.0 if rng.random() < p else 0.0
                rows.append({'Season': 20252026, 'Date': dates[di % len(dates)],
                             'HomeTeam': h, 'AwayTeam': a, 'Result': result,
                             'IsOT': False, 'NeutralSite': False})
                di += 1
    data = pd.DataFrame(rows)
    model = HockeyBT(data, config={'fit_home_ice': True, 'fit_ties': False})
    model.fit()
    assert model.theta > 1.1


def test_validated_defaults_are_shipped(sample_data):
    """
    Guards the evidence-based defaults documented in hockey_bt.py's module
    docstring / reports/hockey_bt_results.md — don't silently change these
    without re-running the 5-year backtest.
    """
    model = HockeyBT(sample_data)
    assert model.conf['fit_home_ice'] is True
    assert model.conf['fit_ties'] is True
    assert model.conf['prior_strength'] == 0.4
    assert model.conf['time_decay_halflife'] is None


def test_prior_shrinks_ratings_toward_mean():
    """A stronger MAP prior (kappa) should pull the spread of ratings in,
    directly targeting the calibration/overconfidence problem it was added
    to fix."""
    data = _synthetic_games(n_pairs=15, seed=2)
    m_weak = HockeyBT(data, config={'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.0})
    m_weak.fit()
    m_strong = HockeyBT(data, config={'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 2.0})
    m_strong.fit()

    spread_weak = np.std(np.log(list(m_weak.ratings.values())))
    spread_strong = np.std(np.log(list(m_strong.ratings.values())))
    assert spread_strong < spread_weak
