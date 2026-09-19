"""
Regression test for a real latent bug found and fixed while optimizing
MonteCarloSimulator (see reports/in_season_revamp_plan.md): simulated
future games' 'Date' field was built as pd.Timestamp, while
current_games_df's 'Date' column (as loaded from CSV) stays a plain
string -- concatenating the two left a mixed-dtype 'Date' column that any
model sorting by Date (e.g. Massey's fit_beta, which builds a temporal
holdout split via df.sort_values('Date')) crashed on with
`TypeError: '<' not supported between instances of 'Timestamp' and 'str'`.
This was silently swallowed by run_system.py's broad per-model
except-and-continue with no record of which models it affected -- it took
adding the run manifest (Phase 4) to even notice it was happening.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from src.analysis.simulator import MonteCarloSimulator
from src.rankings.massey import Massey


def _current_games_with_string_dates():
    # Date as plain strings, exactly as pd.read_csv would load them --
    # this is what actually triggers the bug (a DataFrame built directly
    # with pd.Timestamp objects wouldn't reproduce it).
    return pd.DataFrame({
        'Season': [20252026] * 6,
        'Date': ['2025-11-01', '2025-11-02', '2025-11-08', '2025-11-09', '2025-11-15', '2025-11-16'],
        'HomeTeam': ['A', 'B', 'A', 'C', 'B', 'C'],
        'AwayTeam': ['B', 'A', 'C', 'A', 'C', 'B'],
        'HomeGoals': [3, 2, 4, 1, 3, 2], 'AwayGoals': [1, 2, 2, 3, 1, 2],
        'Result': [1.0, 0.5, 1.0, 0.0, 1.0, 0.5],
        'IsOT': [False] * 6, 'NeutralSite': [False] * 6,
    })


def _upcoming_schedule():
    return pd.DataFrame({
        'Season': [20252026, 20252026],
        'Date': pd.to_datetime(['2025-11-22', '2025-11-23']),
        'HomeTeam': ['A', 'B'],
        'AwayTeam': ['C', 'C'],
        'NeutralSite': [False, False],
    })


def test_simulator_survives_string_dated_current_games():
    """Reproduces the exact bug scenario: current_games_df with string
    Date values, a model (Massey with fit_beta) that sorts by Date. Before
    the fix, sim.run() raised TypeError on the very first iteration."""
    current_games = _current_games_with_string_dates()
    schedule = _upcoming_schedule()
    config = {"margin_cap": 3, "fit_home_ice": True, "ridge_lambda": 1.0, "fit_beta": True}

    sim = MonteCarloSimulator(
        model_class=Massey, model_config=config,
        current_games_df=current_games, upcoming_schedule_df=schedule,
    )
    sim.run(num_iterations=5, n_jobs=1)  # must not raise

    assert all(len(ranks) == 5 for ranks in sim.rank_history.values())


def test_simulator_normalizes_current_games_date_dtype():
    current_games = _current_games_with_string_dates()
    schedule = _upcoming_schedule()
    sim = MonteCarloSimulator(
        model_class=Massey, model_config={},
        current_games_df=current_games, upcoming_schedule_df=schedule,
    )
    assert pd.api.types.is_datetime64_any_dtype(sim.current_games_df['Date'])
