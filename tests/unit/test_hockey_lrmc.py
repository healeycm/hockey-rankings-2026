import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.hockey_lrmc import HockeyLRMC


@pytest.fixture
def sample_data():
    # Team A clearly stronger than Team B: wins both regulation meetings by
    # a comfortable margin. IsOT/NeutralSite/Date are required columns for
    # LRMC's margin/weight calculations.
    data = {
        'Season': [20252026, 20252026],
        'Date': pd.to_datetime(['2025-11-01', '2025-12-01']),
        'HomeTeam': ['Team A', 'Team B'],
        'AwayTeam': ['Team B', 'Team A'],
        'HomeGoals': [5, 1],
        'AwayGoals': [1, 4],
        'Result': [1.0, 0.0],  # Team A won both
        'IsOT': [False, False],
        'NeutralSite': [False, False],
    }
    return pd.DataFrame(data)


def test_hockey_lrmc_fit(sample_data):
    model = HockeyLRMC(sample_data)
    model.fit()
    rankings = model.get_rankings()

    assert 'Team A' in rankings['Team'].values
    assert 'Team B' in rankings['Team'].values
    rating_a = rankings[rankings['Team'] == 'Team A']['Rating'].iloc[0]
    rating_b = rankings[rankings['Team'] == 'Team B']['Rating'].iloc[0]
    assert rating_a > rating_b


def test_hockey_lrmc_predict(sample_data):
    model = HockeyLRMC(sample_data)
    model.fit()
    prob = model.predict('Team A', 'Team B')
    assert prob > 0.5


def test_hockey_lrmc_defaults_are_evidence_based():
    """
    Guards against silently re-enabling adaptations that backtesting showed
    did NOT help (see hockey_lrmc.py module docstring and
    reports/lrmc_hockey_adaptation.md / reports/lrmc_calibration.md) —
    should all stay off by default unless a future re-validation changes
    that.
    """
    model = HockeyLRMC(pd.DataFrame({
        'Season': [20252026], 'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'], 'HomeGoals': [3], 'AwayGoals': [1],
        'Result': [1.0], 'IsOT': [False], 'NeutralSite': [False],
    }))
    assert model.conf['empty_net_shrink'] is False
    assert model.conf['prior_weight'] == 0.0
    assert model.conf['calibrate_predictions'] is False
    assert model.conf['use_real_eng'] is False


def test_ot_games_get_fixed_low_confidence_vote():
    """
    An OT win should be scored as a small nudge above a coin flip
    (0.5 + ot_confidence), NOT run through the regulation margin logistic —
    this is the core hockey-specific adaptation validated in the backtest.
    """
    ot_confidence = 0.08
    data = pd.DataFrame({
        'Season': [20252026],
        'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'],
        'HomeGoals': [3], 'AwayGoals': [2],
        'Result': [1.0],  # Home (A) won
        'IsOT': [True],
        'NeutralSite': [False],
    })
    model = HockeyLRMC(data, config={'ot_confidence': ot_confidence})
    processed = model._preprocess_game_values()
    assert processed['prob_home_better'].iloc[0] == pytest.approx(0.5 + ot_confidence)


def test_real_eng_data_corrects_margin_before_capping():
    """
    When explicitly enabled (use_real_eng=True — it's off by default, see
    reports/lrmc_empty_net.md), a 6-1 home win with 2 real empty-net goals
    should be treated as a 3-1 game, with the correction applied to the raw
    margin BEFORE capping — not capped first and then corrected (which
    would lose the distinction entirely).
    """
    data = pd.DataFrame({
        'Season': [20252026], 'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'],
        'HomeGoals': [6], 'AwayGoals': [1],
        'Result': [1.0], 'IsOT': [False], 'NeutralSite': [False],
        'Home_ENG': [2], 'Away_ENG': [0],
    })
    # no cap, to isolate the ENG effect
    model = HockeyLRMC(data, config={'margin_cap': None, 'use_real_eng': True})
    margins = model._get_adjusted_margins_vectorized(model.games)
    assert margins[0] == pytest.approx(3.0)  # 6-1=5, minus 2 ENG = 3


def test_real_eng_correction_is_off_by_default():
    """Same game as above, but with default config: ENG data present but deliberately unused."""
    data = pd.DataFrame({
        'Season': [20252026], 'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'],
        'HomeGoals': [6], 'AwayGoals': [1],
        'Result': [1.0], 'IsOT': [False], 'NeutralSite': [False],
        'Home_ENG': [2], 'Away_ENG': [0],
    })
    model = HockeyLRMC(data, config={'margin_cap': None})
    margins = model._get_adjusted_margins_vectorized(model.games)
    assert margins[0] == pytest.approx(5.0)  # uncorrected 6-1


def test_missing_eng_data_leaves_margin_unchanged_by_default():
    """Rows without real ENG data get no correction unless the legacy proxy is explicitly enabled."""
    data = pd.DataFrame({
        'Season': [20252026], 'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'],
        'HomeGoals': [3], 'AwayGoals': [1],
        'Result': [1.0], 'IsOT': [False], 'NeutralSite': [False],
    })
    model = HockeyLRMC(data, config={'margin_cap': None})
    margins = model._get_adjusted_margins_vectorized(model.games)
    assert margins[0] == pytest.approx(2.0)


def test_calibration_disabled_by_default_matches_uncalibrated_baseline():
    """calibrate_predictions=False (the default) should leave calib_scale/hia at the pre-calibration baseline."""
    data = pd.DataFrame({
        'Season': [20252026, 20252026], 'Date': pd.to_datetime(['2025-11-01', '2025-11-08']),
        'HomeTeam': ['Team A', 'Team B'], 'AwayTeam': ['Team B', 'Team A'],
        'HomeGoals': [4, 1], 'AwayGoals': [1, 3],
        'Result': [1.0, 0.0], 'IsOT': [False, False], 'NeutralSite': [False, False],
    })
    model = HockeyLRMC(data)
    model.fit()
    assert model.calib_scale == 1.0
    assert model.calib_hia == pytest.approx(abs(model.alpha))


def test_calibration_shrinkage_zero_equals_no_calibration():
    """calibration_shrinkage=0.0 should fully discard the fitted correction, matching the disabled baseline."""
    data = pd.DataFrame({
        'Season': [20252026] * 40,
        'Date': pd.to_datetime(['2025-11-01', '2025-11-08'] * 20),
        'HomeTeam': ['Team A', 'Team B'] * 20, 'AwayTeam': ['Team B', 'Team A'] * 20,
        'HomeGoals': [4, 1] * 20, 'AwayGoals': [1, 3] * 20,
        'Result': [1.0, 0.0] * 20, 'IsOT': [False] * 40, 'NeutralSite': [False] * 40,
    })
    model = HockeyLRMC(data, config={'calibrate_predictions': True, 'calibration_shrinkage': 0.0})
    model.fit()
    assert model.calib_scale == pytest.approx(1.0)
    assert model.calib_hia == pytest.approx(abs(model.alpha))


# --- Graduated OT confidence (reports/lrmc_experiments_2026.md) ---

def test_graduated_ot_confidence_off_by_default():
    data = pd.DataFrame({
        'Season': [20252026] * 4,
        'Date': pd.to_datetime(['2025-11-01', '2025-11-02', '2025-11-08', '2025-11-09']),
        'HomeTeam': ['A', 'B', 'A', 'B'], 'AwayTeam': ['B', 'A', 'B', 'A'],
        'HomeGoals': [3, 2, 4, 1], 'AwayGoals': [2, 3, 3, 2],
        'Result': [1.0, 0.0, 1.0, 0.0], 'IsOT': [True, True, True, True],
        'OT_Info': ['OT', '3OT', '2OT', '5OT'],
        'NeutralSite': [False] * 4,
    })
    model = HockeyLRMC(data)
    conf = model._ot_confidence_for_games(data)
    # Default: scalar, same for every row regardless of period count.
    assert not isinstance(conf, np.ndarray)
    assert conf == model.conf['ot_confidence']


def test_graduated_ot_confidence_decays_with_periods():
    data = pd.DataFrame({
        'Season': [20252026] * 4,
        'Date': pd.to_datetime(['2025-11-01'] * 4),
        'HomeTeam': ['A'] * 4, 'AwayTeam': ['B'] * 4,
        'HomeGoals': [3] * 4, 'AwayGoals': [2] * 4,
        'Result': [1.0] * 4, 'IsOT': [True] * 4,
        'OT_Info': ['OT', '2OT', '3OT', '5OT'],
        'NeutralSite': [False] * 4,
    })
    model = HockeyLRMC(data, config={
        'graduated_ot_confidence': True, 'ot_confidence_decay': 0.5, 'ot_confidence': 0.08,
    })
    conf = model._ot_confidence_for_games(data)
    assert conf == pytest.approx([0.08, 0.04, 0.02, 0.005])


def test_graduated_ot_confidence_decay_one_matches_fixed_baseline():
    """decay=1.0 must reproduce the pre-existing fixed-vote behavior exactly
    (decay^n == 1 for all n) -- a strict generalization, not a change."""
    data = pd.DataFrame({
        'Season': [20252026] * 3,
        'Date': pd.to_datetime(['2025-11-01'] * 3),
        'HomeTeam': ['A'] * 3, 'AwayTeam': ['B'] * 3,
        'HomeGoals': [3] * 3, 'AwayGoals': [2] * 3,
        'Result': [1.0] * 3, 'IsOT': [True] * 3,
        'OT_Info': ['OT', '2OT', '5OT'],
        'NeutralSite': [False] * 3,
    })
    graduated = HockeyLRMC(data, config={
        'graduated_ot_confidence': True, 'ot_confidence_decay': 1.0, 'ot_confidence': 0.08,
    })
    fixed = HockeyLRMC(data, config={'ot_confidence': 0.08})
    conf_graduated = graduated._ot_confidence_for_games(data)
    conf_fixed = fixed._ot_confidence_for_games(data)
    assert np.allclose(conf_graduated, conf_fixed)


def test_ot_periods_missing_column_defaults_to_one():
    data = pd.DataFrame({
        'Season': [20252026], 'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['A'], 'AwayTeam': ['B'],
        'HomeGoals': [3], 'AwayGoals': [2],
        'Result': [1.0], 'IsOT': [True], 'NeutralSite': [False],
        # no OT_Info column at all -- e.g. a synthetic Monte Carlo game.
    })
    model = HockeyLRMC(data)
    periods = model._parse_ot_periods(data)
    assert periods.tolist() == [1.0]


# --- Held-out calibration (reports/lrmc_experiments_2026.md) ---

def _bigger_season(n_pairs=60):
    """A larger synthetic season (enough games to clear the held-out
    calibration guard rails: split >= 100, holdout >= 30 games)."""
    teams = [f"Team{i}" for i in range(8)]
    rows = []
    dates = pd.date_range('2025-10-15', periods=n_pairs * 2, freq='2D')
    rng = np.random.default_rng(0)
    for i in range(n_pairs * 2):
        h, a = rng.choice(teams, size=2, replace=False)
        margin = rng.integers(-3, 4)
        result = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
        hg = max(1, 2 + margin)
        ag = max(1, 2 - margin)
        rows.append({
            'Season': 20252026, 'Date': dates[i], 'HomeTeam': h, 'AwayTeam': a,
            'HomeGoals': hg, 'AwayGoals': ag, 'Result': result,
            'IsOT': False, 'NeutralSite': False,
        })
    return pd.DataFrame(rows)


def test_held_out_calibration_off_by_default():
    data = _bigger_season()
    model = HockeyLRMC(data, config={'auto_fit': True, 'fit_source': 'season'})
    model.fit()
    assert model.calib_scale == 1.0
    assert model.calib_hia == pytest.approx(abs(model.alpha))


def test_held_out_calibration_shrinkage_zero_equals_baseline():
    data = _bigger_season()
    model = HockeyLRMC(data, config={
        'auto_fit': True, 'fit_source': 'season',
        'held_out_calibration': True, 'held_out_calibration_shrinkage': 0.0,
    })
    model.fit()
    assert model.calib_scale == pytest.approx(1.0)
    assert model.calib_hia == pytest.approx(abs(model.alpha))


def test_held_out_calibration_too_little_data_falls_back_to_baseline():
    """Guard rails (split < 100 or holdout < 30) should fall back cleanly,
    not crash, on a small dataset like this project's other tiny fixtures."""
    data = pd.DataFrame({
        'Season': [20252026, 20252026], 'Date': pd.to_datetime(['2025-11-01', '2025-12-01']),
        'HomeTeam': ['Team A', 'Team B'], 'AwayTeam': ['Team B', 'Team A'],
        'HomeGoals': [4, 1], 'AwayGoals': [1, 3],
        'Result': [1.0, 0.0], 'IsOT': [False, False], 'NeutralSite': [False, False],
    })
    model = HockeyLRMC(data, config={'held_out_calibration': True})
    model.fit()  # must not raise
    assert model.calib_scale == 1.0
    assert model.calib_hia == pytest.approx(abs(model.alpha))


def test_held_out_calibration_produces_nondegenerate_fit_on_real_data():
    """Regression guard for the max_abs_param bug found while building this:
    the raw log-ratio's known ~4-5x scale need was being rejected by
    _fit_logit_safe's default max_abs_param=5.0 guard (meant for a
    different use case), silently falling back to baseline every time. This
    checks calibration actually fires (doesn't silently no-op) given enough
    real, non-synthetic data."""
    df = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "processed" / "games_archive.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    season = df[df['Season'] == 20252026].copy()

    model = HockeyLRMC(season, config={
        'auto_fit': True, 'fit_source': 'season', 'held_out_calibration': True,
    })
    model.fit()
    assert model.calib_scale != 1.0, "held-out calibration silently fell back to the uncalibrated baseline"


# --- Self-consistent iterative fit (reports/lrmc_experiments_2026.md) ---

def test_iterative_fit_off_by_default(sample_data):
    model = HockeyLRMC(sample_data)
    assert model.conf['iterative_fit'] is False


def test_iterative_blend_zero_matches_noniterative_baseline():
    df = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "processed" / "games_archive.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    season = df[df['Season'] == 20252026].copy()

    baseline = HockeyLRMC(season, config={'auto_fit': True, 'fit_source': 'season'})
    baseline.fit()

    iterative = HockeyLRMC(season, config={
        'auto_fit': True, 'fit_source': 'season', 'iterative_fit': True, 'iterative_blend': 0.0,
    })
    iterative.fit()

    for team in baseline.ratings:
        assert baseline.ratings[team] == pytest.approx(iterative.ratings[team], abs=1e-9), \
            f"iterative_blend=0.0 should reproduce the non-iterative baseline exactly (team={team})"
    assert iterative.iterations_run == 1


def test_iterative_fit_converges_within_max_iter():
    df = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "processed" / "games_archive.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    season = df[df['Season'] == 20252026].copy()

    model = HockeyLRMC(season, config={
        'auto_fit': True, 'fit_source': 'season', 'iterative_fit': True,
        'iterative_blend': 0.5, 'iterative_max_iter': 25, 'iterative_tol': 1e-4,
    })
    model.fit()
    assert model.iterations_run < 25, "should converge before exhausting max_iter at these settings"
    assert all(np.isfinite(v) for v in model.ratings.values())


def test_iterative_fit_changes_ratings_when_blend_positive():
    """A sanity check that the mechanism actually does something -- not a
    quality claim, just that blend>0 perturbs ratings from the baseline."""
    df = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "processed" / "games_archive.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    season = df[df['Season'] == 20252026].copy()

    baseline = HockeyLRMC(season, config={'auto_fit': True, 'fit_source': 'season'})
    baseline.fit()
    iterative = HockeyLRMC(season, config={
        'auto_fit': True, 'fit_source': 'season', 'iterative_fit': True, 'iterative_blend': 0.5,
    })
    iterative.fit()

    diffs = [abs(baseline.ratings[t] - iterative.ratings[t]) for t in baseline.ratings]
    assert max(diffs) > 0.01
