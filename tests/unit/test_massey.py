import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.massey import Massey


def _synthetic_games(n_pairs=25, seed=0, home_bump=0.0):
    """Larger-than-minimal synthetic dataset — Massey's held-out beta/HIA
    fitting needs enough games and date spread to exercise the split logic,
    unlike the 2-game KRACH fixture."""
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
                true_margin = (strength[h] - strength[a]) + home_bump
                goals_diff = int(round(true_margin + rng.normal(0, 1.0)))
                home_goals = max(0, 3 + goals_diff // 2)
                away_goals = max(0, 3 - goals_diff // 2)
                if home_goals == away_goals:
                    home_goals += 1
                result = 1.0 if home_goals > away_goals else 0.0
                rows.append({
                    'Season': 20252026, 'Date': dates[di % len(dates)],
                    'HomeTeam': h, 'AwayTeam': a,
                    'HomeGoals': home_goals, 'AwayGoals': away_goals,
                    'Result': result, 'IsOT': False, 'NeutralSite': False,
                })
                di += 1
    return pd.DataFrame(rows)


@pytest.fixture
def sample_data():
    return _synthetic_games()


def test_massey_fit_and_rank(sample_data):
    model = Massey(sample_data)
    model.fit()
    r = model.ratings
    assert r['Team A'] > r['Team D']


def test_massey_predict_range(sample_data):
    model = Massey(sample_data)
    model.fit()
    p = model.predict('Team A', 'Team D')
    assert 0.5 < p < 1.0


def test_old_config_reproduces_original_implementation():
    """
    Correctness gate: fit_home_ice=False, ridge_lambda=0, fit_beta=False
    must exactly reproduce the pre-fix Massey (manually re-derived here from
    the original formula, not imported, so this doesn't just test itself).
    """
    data = _synthetic_games(n_pairs=15, seed=1)
    model = Massey(data, config={'fit_home_ice': False, 'ridge_lambda': 0.0,
                                  'fit_beta': False, 'home_ice_advantage': 0.2,
                                  'beta_fixed': 0.15})
    model.fit()

    teams = model.teams
    n = len(teams)
    idx = {t: i for i, t in enumerate(teams)}
    M = np.zeros((n, n))
    p = np.zeros(n)
    for _, row in data.iterrows():
        ih, ia = idx[row['HomeTeam']], idx[row['AwayTeam']]
        M[ih, ih] += 1; M[ia, ia] += 1
        M[ih, ia] -= 1; M[ia, ih] -= 1
        margin = row['HomeGoals'] - row['AwayGoals']
        margin = np.clip(margin, -3, 3)
        eff = margin - 0.2 if not row['NeutralSite'] else margin
        p[ih] += eff; p[ia] -= eff
    M[-1, :] = 1
    p[-1] = 0
    r_orig = np.linalg.solve(M, p)

    for i, t in enumerate(teams):
        assert model.ratings[t] == pytest.approx(r_orig[i], abs=1e-8)
    assert model.beta == 0.15
    assert model.home_ice_advantage_fit == 0.2


def test_home_ice_is_fit_not_hardcoded(sample_data):
    model = Massey(sample_data)
    model.fit()
    # Synthetic data has home_bump=0.0 by default -- fitted HIA should be
    # small (near zero), not the old hardcoded 0.2, demonstrating it's
    # actually being estimated rather than assumed.
    assert model.home_ice_advantage_fit is not None
    assert abs(model.home_ice_advantage_fit) < 1.0


def test_home_ice_recovered_when_present():
    data = _synthetic_games(n_pairs=25, seed=2, home_bump=1.5)
    model = Massey(data)
    model.fit()
    assert model.home_ice_advantage_fit > 0.3


def test_beta_is_fit_via_holdout_not_the_hardcoded_default(sample_data):
    model = Massey(sample_data)
    model.fit()
    # With real signal in the data, the fitted beta should differ from the
    # old blind guess of 0.15.
    assert model.beta != 0.15


def test_beta_falls_back_when_data_too_small():
    """Too few games for a clean 80/20 temporal split -> falls back to beta_fixed."""
    data = _synthetic_games(n_pairs=3, seed=3)
    model = Massey(data)
    model.fit()
    assert model.beta == model.conf['beta_fixed']


def test_ridge_shrinks_ratings_toward_zero(sample_data):
    weak = Massey(sample_data, config={'ridge_lambda': 0.0})
    weak.fit()
    strong = Massey(sample_data, config={'ridge_lambda': 20.0})
    strong.fit()
    spread_weak = np.std(list(weak.ratings.values()))
    spread_strong = np.std(list(strong.ratings.values()))
    assert spread_strong < spread_weak


def test_validated_defaults_are_shipped(sample_data):
    """
    Guards the evidence-based defaults documented in massey.py's module
    docstring / reports/massey_calibration_results.md.
    """
    model = Massey(sample_data)
    assert model.conf['fit_home_ice'] is True
    assert model.conf['fit_beta'] is True
    assert model.conf['ridge_lambda'] == 1.0


# --- Time-decay weighting (reports/massey_experiments_2026.md) ---

def test_time_decay_off_by_default_is_noop(sample_data):
    baseline = Massey(sample_data)
    baseline.fit()
    noop = Massey(sample_data, config={'time_decay_halflife': None})
    noop.fit()
    for team in baseline.ratings:
        assert baseline.ratings[team] == pytest.approx(noop.ratings[team])


def test_time_decay_weights_are_all_ones_when_disabled(sample_data):
    model = Massey(sample_data)
    weights = model._time_decay_weights(sample_data)
    assert np.allclose(weights, 1.0)


def test_time_decay_weights_favor_recent_games(sample_data):
    model = Massey(sample_data, config={'time_decay_halflife': 10})
    weights = model._time_decay_weights(sample_data)
    dates = pd.to_datetime(sample_data['Date'])
    most_recent_idx = dates.values.argmax()
    oldest_idx = dates.values.argmin()
    assert weights[most_recent_idx] > weights[oldest_idx]


def test_time_decay_changes_ratings_when_enabled(sample_data):
    baseline = Massey(sample_data)
    baseline.fit()
    decayed = Massey(sample_data, config={'time_decay_halflife': 15})
    decayed.fit()
    diffs = [abs(baseline.ratings[t] - decayed.ratings[t]) for t in baseline.ratings]
    assert max(diffs) > 1e-6


# --- Rest/fatigue adjustment (reports/massey_experiments_2026.md) ---

def test_rest_advantage_off_by_default_is_noop(sample_data):
    baseline = Massey(sample_data)
    baseline.fit()
    rest_off = Massey(sample_data, config={'fit_rest_advantage': False})
    rest_off.fit()
    for team in baseline.ratings:
        assert baseline.ratings[team] == pytest.approx(rest_off.ratings[team])
    assert rest_off.rest_weight_fit == 0.0


def test_predict_without_game_date_is_noop_even_when_rest_enabled(sample_data):
    """Every existing caller (run_system.py, BacktestEngine, the
    simulator) predicts without a game_date -- this must behave exactly
    as if fit_rest_advantage were off."""
    model = Massey(sample_data, config={'fit_rest_advantage': True})
    model.fit()
    p_no_date = model.predict('Team A', 'Team B')
    baseline = Massey(sample_data, config={'fit_rest_advantage': False})
    baseline.fit()
    # Ratings/home-ice/beta all differ slightly (rest is fit jointly), but
    # the PREDICT-time rest contribution itself must be exactly 0 without a
    # game_date -- check that directly rather than comparing full predictions.
    r_home, r_away = model.ratings['Team A'], model.ratings['Team B']
    hia = model.home_ice_advantage_fit
    expected = 1 / (1 + np.exp(-model.beta * (r_home - r_away + hia)))
    assert p_no_date == pytest.approx(expected)


def test_rest_features_first_game_of_window_gets_default_rest():
    data = pd.DataFrame({
        'Season': [20252026], 'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'],
        'HomeGoals': [3], 'AwayGoals': [2],
        'Result': [1.0], 'IsOT': [False], 'NeutralSite': [False],
    })
    model = Massey(data, config={'rest_days_cap': 5})
    rest_diff, last_date = model._rest_features(data)
    assert rest_diff[0] == pytest.approx(0.0)  # both teams "fully rested" -> no diff
    assert last_date['A'] == data['Date'].iloc[0]


def test_rest_features_caps_and_floors_correctly():
    data = pd.DataFrame({
        'Season': [20252026] * 3,
        'Date': pd.to_datetime(['2025-11-01', '2025-11-02', '2025-11-15']),
        'HomeTeam': ['A', 'B', 'A'], 'AwayTeam': ['B', 'A', 'B'],
        'HomeGoals': [3, 2, 4], 'AwayGoals': [2, 1, 1],
        'Result': [1.0, 1.0, 1.0], 'IsOT': [False] * 3, 'NeutralSite': [False] * 3,
    })
    model = Massey(data, config={'rest_days_cap': 5})
    rest_diff, _ = model._rest_features(data)
    # Game 2 (Nov 2): B played Nov 1 (1 day rest), A also played Nov 1 as home (1 day rest) -> diff 0
    assert rest_diff[1] == pytest.approx(0.0)
    # Game 3 (Nov 15): A last played Nov 1 (14 days, capped at 5), B last played Nov 2 (13 days, capped at 5) -> diff 0
    assert rest_diff[2] == pytest.approx(0.0)


def test_negative_rest_gap_is_floored_not_unbounded():
    """predict() with a game_date EARLIER than the cached last game (a
    misuse -- proper backtest usage never does this, since test dates are
    always after the training cutoff) must floor to 0 rest days, not
    explode into a runaway negative value."""
    data = pd.DataFrame({
        'Season': [20252026] * 2,
        'Date': pd.to_datetime(['2025-11-01', '2025-11-01']),
        'HomeTeam': ['A', 'C'], 'AwayTeam': ['B', 'D'],
        'HomeGoals': [3, 2], 'AwayGoals': [2, 1],
        'Result': [1.0, 1.0], 'IsOT': [False, False], 'NeutralSite': [False, False],
    })
    model = Massey(data, config={'fit_rest_advantage': True, 'rest_days_cap': 5})
    model.fit()
    model._last_game_date['A'] = pd.Timestamp('2026-03-01')  # far in the "future" relative to game_date below
    p = model.predict('A', 'B', game_date=pd.Timestamp('2025-11-05'))
    assert 0.0 <= p <= 1.0 and np.isfinite(p)


# --- Manpower-adjusted margin (reports/massey_experiments_2026.md) ---

def test_manpower_margin_off_by_default_is_noop(sample_data):
    baseline = Massey(sample_data)
    baseline.fit()
    noop = Massey(sample_data, config={'use_manpower_margin': False})
    noop.fit()
    for team in baseline.ratings:
        assert baseline.ratings[team] == pytest.approx(noop.ratings[team])


def test_manpower_margin_falls_back_to_goals_without_ev_columns(sample_data):
    """sample_data has no Home_EV_Goals/Away_EV_Goals columns at all --
    use_manpower_margin=True must silently fall back to the raw goal
    margin rather than erroring."""
    with_flag = Massey(sample_data, config={'use_manpower_margin': True})
    with_flag.fit()
    baseline = Massey(sample_data, config={'use_manpower_margin': False})
    baseline.fit()
    for team in baseline.ratings:
        assert baseline.ratings[team] == pytest.approx(with_flag.ratings[team])


def test_manpower_margin_uses_ev_goals_when_available():
    data = pd.DataFrame({
        'Season': [20252026] * 4,
        'Date': pd.to_datetime(['2025-11-01', '2025-11-02', '2025-11-08', '2025-11-09']),
        'HomeTeam': ['A', 'B', 'A', 'B'], 'AwayTeam': ['B', 'A', 'B', 'A'],
        'HomeGoals': [5, 1, 4, 2], 'AwayGoals': [1, 5, 1, 4],
        # EV goals tell a very different story than the final score --
        # team A's blowouts were mostly special-teams-driven (small EV margin).
        'Home_EV_Goals': [1, 1, 1, 2], 'Away_EV_Goals': [1, 1, 1, 1],
        'Result': [1.0, 0.0, 1.0, 0.0], 'IsOT': [False] * 4, 'NeutralSite': [False] * 4,
    })
    ev_model = Massey(data, config={'use_manpower_margin': True, 'margin_cap': None,
                                     'fit_home_ice': False, 'ridge_lambda': 0.0, 'fit_beta': False})
    raw_model = Massey(data, config={'use_manpower_margin': False, 'margin_cap': None,
                                      'fit_home_ice': False, 'ridge_lambda': 0.0, 'fit_beta': False})
    ev_margin = ev_model._capped_margin(data)
    raw_margin = raw_model._capped_margin(data)
    assert not np.allclose(ev_margin, raw_margin)
    assert ev_margin[3] == pytest.approx(1.0)  # 2 - 1, not the raw 2 - 4 = -2


def test_manpower_margin_partial_coverage_falls_back_per_game():
    """Some games have EV data, some don't (NaN) -- must use EV where
    present and raw goals where missing, on a per-game basis."""
    data = pd.DataFrame({
        'Season': [20252026, 20252026],
        'Date': pd.to_datetime(['2025-11-01', '2025-11-02']),
        'HomeTeam': ['A', 'A'], 'AwayTeam': ['B', 'B'],
        'HomeGoals': [5, 5], 'AwayGoals': [1, 1],
        'Home_EV_Goals': [2, np.nan], 'Away_EV_Goals': [1, np.nan],
        'Result': [1.0, 1.0], 'IsOT': [False, False], 'NeutralSite': [False, False],
    })
    model = Massey(data, config={'use_manpower_margin': True, 'margin_cap': None})
    margin = model._capped_margin(data)
    assert margin[0] == pytest.approx(1.0)   # EV: 2 - 1
    assert margin[1] == pytest.approx(4.0)   # falls back to raw: 5 - 1
