# src/utils/season.py
"""
Single source of truth for season-derived values that used to be hardcoded
per-season throughout the codebase (e.g. `pd.Timestamp('2026-03-01')` for the
start of conference tournaments). A season code like `20262027` encodes both
the starting and ending calendar year; everything else (conference-tournament
cutoff, default fallback dates, etc.) should be derived from it rather than
re-hardcoded each year.
"""
import datetime
import pandas as pd


def season_start_year(season: int) -> int:
    """20262027 -> 2026"""
    return int(str(season)[:4])


def season_end_year(season: int) -> int:
    """20262027 -> 2027"""
    return int(str(season)[4:8])


def conf_tourney_cutoff(season: int) -> pd.Timestamp:
    """
    First of March in the season's ending year. Games on/after this date
    between two teams from the same conference are treated as conference
    tournament (postseason) games for NPI purposes.
    """
    return pd.Timestamp(f"{season_end_year(season)}-03-01")

def default_season_end_date(season: int) -> pd.Timestamp:
    """
    Approximate end-of-season date (national championship is typically early
    April). Used as a fallback timestamp only when a real scheduled date
    isn't available (e.g. a Monte Carlo simulated game with no Date field).
    """
    return pd.Timestamp(f"{season_end_year(season)}-04-15")


def get_current_season_code(today: datetime.date = None) -> int:
    """
    Calculates the season code (e.g. 20262027) based on a calendar date.
    Mirrors src.data.scraper.get_current_season_code(), but returns an int
    matching the 'Season' column / config.yaml 'system.season' format
    instead of a string, and accepts an explicit date for testability.

    If month is roughly Aug-Dec, the season started this year.
    If Jan-July, the season started last year.
    """
    today = today or datetime.date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    return int(f"{start_year}{start_year + 1}")
