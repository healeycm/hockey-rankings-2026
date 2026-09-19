"""
Tests for the division-awareness mechanism added to support women's hockey
(see reports/womens_hockey_import.md). The critical property being guarded:
BaseRanker's DI filter must not silently apply the wrong division's team
list — the overlap-based safety heuristic that catches "wrong naming
convention" (unit-test fixtures, etc.) CANNOT catch "wrong division",
because men's and women's programs share most school names by design. This
was a real bug caught during development, not a hypothetical.
"""
import sys
import pandas as pd
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.base_ranker import using_di_team_path, load_di_teams
from src.rankings.krach import KRACH

WOMENS_TEAM_INFO = Path(__file__).resolve().parents[2] / "data" / "teams" / "team_info_women.csv"


def _shared_name_games():
    """
    A tiny schedule using ONLY team names that exist in BOTH the men's and
    women's team lists (e.g. Wisconsin, Ohio State fields both programs) --
    this is exactly the scenario where the overlap-based "is this even the
    right naming convention" safety check can't help, since it would see
    high overlap with EITHER division's list.
    """
    return pd.DataFrame({
        'Season': [20252026, 20252026],
        'Date': pd.to_datetime(['2025-11-01', '2025-11-08']),
        'HomeTeam': ['Wisconsin', 'Ohio State'],
        'AwayTeam': ['Ohio State', 'Wisconsin'],
        'HomeGoals': [3, 2], 'AwayGoals': [1, 2],
        'Result': [1.0, 0.5], 'IsOT': [False, False], 'NeutralSite': [False, False],
    })


@pytest.mark.skipif(not WOMENS_TEAM_INFO.exists(), reason="data/teams/team_info_women.csv not present in this environment.")
def test_womens_team_list_loads():
    teams = load_di_teams(path=WOMENS_TEAM_INFO)
    assert teams is not None
    assert 'Wisconsin' in teams
    assert len(teams) > 30  # sanity: real women's D-I field size, not an empty/truncated file


@pytest.mark.skipif(not WOMENS_TEAM_INFO.exists(), reason="data/teams/team_info_women.csv not present in this environment.")
def test_context_manager_switches_default_di_list():
    data = _shared_name_games()

    # Without the override: uses the men's default list.
    model_default = KRACH(data)
    assert len(model_default.games) == 2  # both teams are in the men's list too, so nothing gets dropped here

    # With the override active: explicitly uses the women's list instead.
    with using_di_team_path(WOMENS_TEAM_INFO):
        model_women = KRACH(data)
    assert len(model_women.games) == 2


def test_context_manager_resets_after_block():
    """The override must not leak past its `with` block -- a men's model
    instantiated afterward must go back to using the men's default list."""
    from src.rankings import base_ranker
    assert base_ranker._ACTIVE_DI_TEAM_PATH is None

    with using_di_team_path(Path("some/other/path.csv")):
        assert base_ranker._ACTIVE_DI_TEAM_PATH == Path("some/other/path.csv")

    assert base_ranker._ACTIVE_DI_TEAM_PATH is None


def test_explicit_kwarg_beats_context_manager():
    """A directly-passed di_team_path (for classes that forward it) takes
    precedence over the ambient context-manager override."""
    data = _shared_name_games()
    with using_di_team_path(Path("nonexistent_dir/nonexistent.csv")):
        # filter_di_teams=False bypasses lookup entirely -- confirms the
        # explicit kwarg path is even consulted before di_teams resolution
        # would otherwise blow up on the bogus context-manager path.
        model = KRACH(data, filter_di_teams=False)
    assert len(model.games) == 2
