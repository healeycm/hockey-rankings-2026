"""
Regression tests for RankInterpreter.compute_all_impacts() -- the batched,
game-level Leave-One-Out sensitivity analysis that replaced run_system.py's
old per-(team, game) loop (see reports/in_season_revamp_plan.md). The
critical property: batching by game instead of by team must produce
EXACTLY the same per-team impact numbers as the old approach, just with
roughly half as many model refits (each dropped game updates both of its
teams' ratings at once, instead of being refit once per team that played
in it).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import pytest
from src.analysis.interpreter import RankInterpreter


def _toy_history():
    # A small round-robin so every team has several LOO-eligible games.
    teams = ['A', 'B', 'C', 'D']
    rows = []
    dates = pd.date_range('2025-11-01', periods=12, freq='3D')
    pairs = [('A', 'B'), ('C', 'D'), ('A', 'C'), ('B', 'D'), ('A', 'D'), ('B', 'C')] * 2
    results = [1.0, 0.0, 0.5, 1.0, 0.0, 1.0, 1.0, 0.5, 0.0, 1.0, 1.0, 0.0]
    for i, ((h, a), res, d) in enumerate(zip(pairs, results, dates)):
        rows.append({
            'Season': 20252026, 'Date': d, 'HomeTeam': h, 'AwayTeam': a,
            'HomeGoals': 3 if res >= 0.5 else 2, 'AwayGoals': 2 if res >= 0.5 else 3,
            'Result': res, 'IsOT': False, 'NeutralSite': False,
        })
    return pd.DataFrame(rows)


@pytest.mark.parametrize("model_name,config", [
    ("KRACH", {}),
    ("Massey", {"margin_cap": 3, "fit_home_ice": True, "ridge_lambda": 1.0, "fit_beta": False}),
    ("ELO", {}),
])
def test_batched_matches_per_team_loo(model_name, config):
    history = _toy_history()
    interp = RankInterpreter(history, 20252026)

    batched = interp.compute_all_impacts(model_name=model_name, model_config=config, n_jobs=1)

    for team in ['A', 'B', 'C', 'D']:
        old = interp.find_impact_games(team, model_name=model_name, model_config=config)
        new = batched[team]

        old_sorted = old.sort_values(['Date', 'Opponent']).reset_index(drop=True)
        new_sorted = new.sort_values(['Date', 'Opponent']).reset_index(drop=True)

        assert len(old_sorted) == len(new_sorted), f"{model_name}/{team}: row count mismatch"
        assert old_sorted['Rating Impact'].round(9).tolist() == new_sorted['Rating Impact'].round(9).tolist(), \
            f"{model_name}/{team}: impact values diverged between batched and per-team LOO"
        assert old_sorted['Result'].tolist() == new_sorted['Result'].tolist()


def test_compute_all_impacts_unknown_model_raises():
    interp = RankInterpreter(_toy_history(), 20252026)
    with pytest.raises(KeyError):
        interp.compute_all_impacts(model_name="NotARealModel")
