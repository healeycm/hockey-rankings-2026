import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.dixon_coles import DixonColes


def _synthetic_games(n_pairs=20, seed=0, home_bump=0.0):
    rng = np.random.default_rng(seed)
    teams = ['Team A', 'Team B', 'Team C', 'Team D']
    attack = {'Team A': 0.4, 'Team B': 0.1, 'Team C': -0.1, 'Team D': -0.4}
    defense = {'Team A': 0.3, 'Team B': 0.0, 'Team C': 0.0, 'Team D': -0.3}
    rows = []
    dates = pd.date_range('2025-10-01', periods=n_pairs * 6)
    di = 0
    for _ in range(n_pairs):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                lam_h = np.exp(1.0 + attack[h] - defense[a] + home_bump)
                lam_a = np.exp(1.0 + attack[a] - defense[h])
                hg = rng.poisson(lam_h)
                ag = rng.poisson(lam_a)
                result = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
                rows.append({
                    'Season': 20252026, 'Date': dates[di % len(dates)],
                    'HomeTeam': h, 'AwayTeam': a,
                    'HomeGoals': hg, 'AwayGoals': ag,
                    'Result': result, 'IsOT': False, 'NeutralSite': False,
                })
                di += 1
    return pd.DataFrame(rows)


@pytest.fixture
def sample_data():
    return _synthetic_games()


def test_fit_and_rank(sample_data):
    model = DixonColes(sample_data)
    model.fit()
    r = model.get_rankings()
    rank_a = r.loc[r['Team'] == 'Team A', 'Rating'].iloc[0]
    rank_d = r.loc[r['Team'] == 'Team D', 'Rating'].iloc[0]
    assert rank_a > rank_d


def test_predict_outcomes_sum_to_one(sample_data):
    """
    Without rho (default: fit_rho=False, see the evidence-based-defaults
    test below), there's no renormalization step, so the sum is 1.0 minus
    whatever Poisson mass falls beyond `max_goals` -- negligible (<1e-3)
    for realistic hockey scoring rates, not exact to floating-point.
    """
    model = DixonColes(sample_data)
    model.fit()
    p_h, p_t, p_a = model.predict_outcomes('Team A', 'Team D')
    assert p_h > 0 and p_t > 0 and p_a > 0
    assert (p_h + p_t + p_a) == pytest.approx(1.0, abs=1e-3)


def test_predict_matches_outcome_expectation(sample_data):
    model = DixonColes(sample_data)
    model.fit()
    p = model.predict('Team A', 'Team C')
    p_h, p_t, _ = model.predict_outcomes('Team A', 'Team C')
    assert p == pytest.approx(p_h + 0.5 * p_t)


def test_stronger_attacker_favored(sample_data):
    model = DixonColes(sample_data)
    model.fit()
    assert model.predict('Team A', 'Team D') > 0.5
    assert model.predict('Team D', 'Team A') < 0.5


def test_staged_fit_is_properly_nested(sample_data):
    """
    D2 (eta+rho) evaluated at [D1's (eta-only) solution, rho=0] must exactly
    recover D1's likelihood -- this is the nesting property that was
    violated by optimizer non-convergence on cold-started fits (caught on
    the 2025-26 season; see dixon_coles.py's fit() docstring) and fixed via
    staged warm-starting. This test guards against that regression.
    """
    d1 = DixonColes(sample_data, config={'fit_home_ice': True, 'fit_rho': False})
    d1.fit()
    d2 = DixonColes(sample_data, config={'fit_home_ice': True, 'fit_rho': True})
    d2.fit()
    # D2's fitted likelihood must be at least as good (nll at least as low) as D1's.
    assert d2.fit_result_.fun <= d1.fit_result_.fun + 1e-6


def test_home_ice_is_recovered_when_present():
    data = _synthetic_games(n_pairs=25, seed=1, home_bump=0.5)
    model = DixonColes(data, config={'fit_home_ice': True, 'fit_rho': False})
    model.fit()
    assert model.eta > 0.1


def test_d0_disables_home_ice_and_rho(sample_data):
    model = DixonColes(sample_data, config={'fit_home_ice': False, 'fit_rho': False})
    model.fit()
    assert model.eta == 0.0
    assert model.rho == 0.0


def test_validated_defaults_are_shipped(sample_data):
    """
    Guards the evidence-based defaults documented in dixon_coles.py's
    module docstring / reports/dixon_coles_results.md — fit_rho was tested
    and found not to help out-of-sample despite often being in-sample
    LR-significant (same lesson as HockeyBT's rejected silo prior); don't
    silently flip it back on without re-validating.
    """
    model = DixonColes(sample_data)
    assert model.conf['fit_home_ice'] is True
    assert model.conf['fit_rho'] is False
    assert model.conf['prior_strength'] == 3.0


def test_prior_shrinks_attack_defense_toward_zero(sample_data):
    weak = DixonColes(sample_data, config={'fit_home_ice': True, 'fit_rho': True, 'prior_strength': 0.0})
    weak.fit()
    strong = DixonColes(sample_data, config={'fit_home_ice': True, 'fit_rho': True, 'prior_strength': 2.0})
    strong.fit()
    spread_weak = np.std(list(weak.attack.values()) + list(weak.defense.values()))
    spread_strong = np.std(list(strong.attack.values()) + list(strong.defense.values()))
    assert spread_strong < spread_weak
