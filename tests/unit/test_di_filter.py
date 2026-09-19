import sys
import pandas as pd
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.base_ranker import load_di_teams
from src.rankings.krach import KRACH
from src.rankings.lrmc import LRMC


def _di_data_available():
    return load_di_teams() is not None


@pytest.mark.skipif(not _di_data_available(), reason="data/teams/team_info.csv not present in this environment.")
def test_non_di_opponent_is_dropped():
    """
    A real DI team plus a game against a non-DI opponent: the non-DI game
    should be filtered out by every ranker (not just NPI), since it's now
    centralized in BaseRanker. Uses two teams (Michigan, Cornell) known to
    be in team_info.csv, plus a fictional non-DI name.
    """
    data = pd.DataFrame({
        'Season': [20252026, 20252026],
        'Date': pd.to_datetime(['2025-11-01', '2025-11-08']),
        'HomeTeam': ['Michigan', 'Michigan'],
        'AwayTeam': ['Cornell', 'Definitely Not A DI School'],
        'HomeGoals': [3, 5],
        'AwayGoals': [1, 0],
        'Result': [1.0, 1.0],
        'IsOT': [False, False],
        'NeutralSite': [False, False],
    })
    model = KRACH(data)
    assert 'Definitely Not A DI School' not in model.teams
    assert len(model.games) == 1
    assert model.di_filter_dropped_games == 1


def test_synthetic_test_data_is_not_filtered_to_empty():
    """
    Unit-test-style synthetic team names (no overlap with the real DI list)
    must NOT be silently filtered down to nothing — this is the guard that
    keeps test_models.py / test_hockey_lrmc.py's 'Team A'/'Team B' fixtures
    working now that DI filtering is on by default in BaseRanker.
    """
    data = pd.DataFrame({
        'Season': [20252026, 20252026],
        'HomeTeam': ['Team A', 'Team B'],
        'AwayTeam': ['Team B', 'Team A'],
        'Result': [1.0, 0.0],
        'IsOT': [False, False],
    })
    model = KRACH(data)
    assert len(model.games) == 2
    assert 'Team A' in model.teams and 'Team B' in model.teams


def test_filter_di_teams_can_be_explicitly_disabled():
    data = pd.DataFrame({
        'Season': [20252026],
        'Date': pd.to_datetime(['2025-11-01']),
        'HomeTeam': ['Michigan'],
        'AwayTeam': ['Definitely Not A DI School'],
        'HomeGoals': [5], 'AwayGoals': [0],
        'Result': [1.0], 'IsOT': [False], 'NeutralSite': [False],
    })
    model = KRACH(data, filter_di_teams=False)
    assert len(model.games) == 1
    assert 'Definitely Not A DI School' in model.teams
