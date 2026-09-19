"""
Regression test for a real bug found and fixed during the 2026-27 season
rollover (see reports/season_2026_27_rollover_audit.md):
DataLoader.get_schedule() used to return every Is_Final=False row across
ALL seasons in the raw archive, with no season filter at all. A game that
never got marked final for any reason (a scraper miss, a postponement, an
unresolved NCAA tournament bracket placeholder) stayed in "upcoming"
forever, regardless of season -- confirmed on disk as stray 2013-14/
2014-15/2023-24/2025-26 rows sitting in data/processed/upcoming_schedule.csv
alongside the real 2026-27 schedule.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from src.data.loader import DataLoader


def _write_raw_season_file(tmp_path, season, filename, rows):
    """Writes a minimal raw-format season CSV (the columns _load_all_raw()
    expects before renaming) -- one row per (Date, Home_Team, Visitor_Team,
    Is_Final) tuple in `rows`."""
    df = pd.DataFrame({
        'Day': ['Fri'] * len(rows),
        'Date': [r[0] for r in rows],
        'Time': ['7:00'] * len(rows),
        'Visitor_Team': [r[2] for r in rows],
        'Visitor_Score': [2] * len(rows),
        'Location_Indicator': ['H'] * len(rows),
        'Home_Team': [r[1] for r in rows],
        'Home_Score': [3] * len(rows),
        'OT_Info': [None] * len(rows),
        'Notes': [None] * len(rows),
        'Type': ['REG'] * len(rows),
        'Is_Final': [r[3] for r in rows],
        'Is_Neutral': [False] * len(rows),
        'Is_Exhibition': [False] * len(rows),
        'Is_OT': [False] * len(rows),
        'Season': [season] * len(rows),
    })
    df.to_csv(tmp_path / filename, index=False)


def test_get_schedule_excludes_stray_rows_from_older_seasons(tmp_path):
    # An older season with one game that never got marked final (the exact
    # failure mode found in production -- a stale/orphaned row, not a
    # genuine future game anyone cares about anymore).
    _write_raw_season_file(tmp_path, 20142015, "games_2014_2015.csv", [
        ("2014-12-13", "Princeton", "Minnesota State", False),
        ("2014-10-01", "Princeton", "Yale", True),
    ])
    # The current/newest season, with real upcoming games.
    _write_raw_season_file(tmp_path, 20262027, "games_2026_2027.csv", [
        ("2026-10-02", "Niagara", "RIT", False),
        ("2026-10-03", "Denver", "Colorado College", False),
    ])

    loader = DataLoader(data_dir=tmp_path)
    schedule = loader.get_schedule()

    assert set(schedule['Season'].unique()) == {20262027}
    assert len(schedule) == 2
    assert "Minnesota State" not in schedule['AwayTeam'].values


def test_get_schedule_defaults_to_newest_season_present(tmp_path):
    _write_raw_season_file(tmp_path, 20242025, "games_2024_2025.csv", [
        ("2024-11-01", "A", "B", False),
    ])
    _write_raw_season_file(tmp_path, 20252026, "games_2025_2026.csv", [
        ("2025-11-01", "C", "D", False),
    ])

    loader = DataLoader(data_dir=tmp_path)
    schedule = loader.get_schedule()

    assert set(schedule['Season'].unique()) == {20252026}


def test_get_schedule_accepts_explicit_target_season(tmp_path):
    _write_raw_season_file(tmp_path, 20242025, "games_2024_2025.csv", [
        ("2024-11-01", "A", "B", False),
    ])
    _write_raw_season_file(tmp_path, 20252026, "games_2025_2026.csv", [
        ("2025-11-01", "C", "D", False),
    ])

    loader = DataLoader(data_dir=tmp_path)
    schedule = loader.get_schedule(target_season=20242025)

    assert set(schedule['Season'].unique()) == {20242025}


def test_get_schedule_excludes_final_games():
    """Sanity check the pre-existing Is_Final filter still works alongside
    the new season filter (not just replaced by it)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp_path = Path(d)
        _write_raw_season_file(tmp_path, 20262027, "games_2026_2027.csv", [
            ("2026-10-02", "Niagara", "RIT", True),   # already played
            ("2026-10-03", "Denver", "Colorado College", False),  # upcoming
        ])
        loader = DataLoader(data_dir=tmp_path)
        schedule = loader.get_schedule()
        assert len(schedule) == 1
        assert schedule.iloc[0]['HomeTeam'] == 'Denver'


def test_get_history_drops_exact_duplicate_raw_rows(tmp_path):
    """
    Regression test for a real data-quality bug found 2026-09-13 while
    researching preseason priors (research/preseason/reports/
    probe_pre2011_scrape.md): every raw season file from 2011-12 through
    2020-21 contained a consistent ~3% rate of fully-identical duplicate
    rows (confirmed on disk), silently double-counting those games in
    every ranking model fit on them since this project began. Fixed in
    DataLoader._load_all_raw() via a conservative full-row drop_duplicates
    (not a Date/Home/Away subset match, which risks conflating two
    genuinely different games -- e.g. the same game listed once as an
    exhibition and once as a real game, which differs in Is_Exhibition/Type
    and must NOT be collapsed by this step).
    """
    _write_raw_season_file(tmp_path, 20152016, "games_2015_2016.csv", [
        ("2015-10-03", "Denver", "Colorado College", True),
        ("2015-10-03", "Denver", "Colorado College", True),  # exact duplicate row
        ("2015-10-04", "Michigan", "Ohio State", True),
    ])
    loader = DataLoader(data_dir=tmp_path)
    history = loader.get_history()

    assert len(history) == 2
    assert history['HomeTeam'].tolist() == ['Denver', 'Michigan']


def test_get_history_keeps_rows_that_only_differ_in_exhibition_status(tmp_path):
    """The near-duplicate case a naive Date+HomeTeam+AwayTeam dedup would
    wrongly collapse: two rows for the "same" game, one flagged as an
    exhibition and one not. Both must survive _load_all_raw()'s
    full-row dedup (they aren't identical rows) -- the exhibition one is
    then correctly removed by the existing _filter_exhibition() step,
    not by the dedup fix."""
    df = pd.DataFrame({
        'Day': ['Sat', 'Sat'], 'Date': ["2015-10-03", "2015-10-03"], 'Time': ['7:00', '7:00'],
        'Visitor_Team': ['Colorado College', 'Colorado College'], 'Visitor_Score': [2, 2],
        'Location_Indicator': ['H', 'H'], 'Home_Team': ['Denver', 'Denver'], 'Home_Score': [3, 3],
        'OT_Info': [None, None], 'Notes': [None, None], 'Type': ['ex', 'REG'],
        'Is_Final': [True, True], 'Is_Neutral': [False, False],
        'Is_Exhibition': [True, False], 'Is_OT': [False, False],
        'Season': [20152016, 20152016],
    })
    df.to_csv(tmp_path / "games_2015_2016.csv", index=False)

    loader = DataLoader(data_dir=tmp_path)
    history = loader.get_history()

    # Both rows survive the dedup step (they differ), and the exhibition
    # filter removes exactly the one marked as an exhibition.
    assert len(history) == 1
    assert history.iloc[0]['HomeTeam'] == 'Denver'
