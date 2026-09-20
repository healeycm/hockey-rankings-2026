# research/womens_comparison/harness/women_npi.py
"""
Women's-data equivalents of src/analysis/npi_vs_krach.py's core fitting
helpers (load_games, get_di_teams, filter_season, fit_npi, fit_krach,
get_ranks) -- that module is hardcoded to men's paths and isn't
division-aware, so it can't be imported and reused directly. Re-implemented
here rather than modified in place, since npi_vs_krach.py is production
code this workspace only reads, never edits (see README.md's isolation
rules).

Every NPI fit here uses the CORRECTED women's dials (config.yaml's
npi_women block -- see research/womens_comparison/reports/
p0_3_npi_validation.md), not the men's defaults NPI's constructor would
otherwise use.
"""
from pathlib import Path
import pandas as pd

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.base_ranker import using_di_team_path
from src.utils.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WOMENS_GAMES = PROJECT_ROOT / "data" / "processed" / "women" / "games_archive.csv"
WOMENS_TEAM_INFO = PROJECT_ROOT / "data" / "teams" / "team_info_women.csv"
WOMENS_COLLEGE_TEAMS = PROJECT_ROOT / "data" / "teams" / "college_hockey_teams_women.csv"

# 2021-22 through 2025-26 -- every complete women's D-I season this project
# has scraped (see reports/womens_hockey_import.md). No exclusions needed
# (unlike men's 2016-17, which has no raw file at all).
BACKTEST_SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]

_NPI_WOMEN_CONFIG = None


def npi_women_config():
    """The corrected women's NPI dials from config.yaml's npi_women block,
    cached after first load."""
    global _NPI_WOMEN_CONFIG
    if _NPI_WOMEN_CONFIG is None:
        cfg = load_config()
        _NPI_WOMEN_CONFIG = dict(cfg['models']['npi_women'])
    return _NPI_WOMEN_CONFIG


def load_games() -> pd.DataFrame:
    df = pd.read_csv(WOMENS_GAMES)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def get_di_teams() -> set:
    """Women's D-I roster, keyed the same way team_info_women.csv stores
    it (USCHO_Name), mirroring get_di_teams()'s men's convention."""
    return set(pd.read_csv(WOMENS_TEAM_INFO)["USCHO_Name"].unique())


def filter_season(df: pd.DataFrame, season: int, di_teams: set = None) -> pd.DataFrame:
    sdf = df[df["Season"] == season].copy()
    if "Is_Exhibition" in sdf.columns:
        sdf = sdf[~sdf["Is_Exhibition"].isin([True, "True", 1, "1"])]
    if di_teams:
        sdf = sdf[sdf["HomeTeam"].isin(di_teams) & sdf["AwayTeam"].isin(di_teams)]
    return sdf


def get_ranks(ratings: dict) -> dict:
    sorted_teams = sorted(ratings, key=lambda t: ratings[t], reverse=True)
    return {t: i + 1 for i, t in enumerate(sorted_teams)}


def fit_npi(games_df: pd.DataFrame, config: dict = None) -> NPI:
    """Fits NPI with the women's-corrected dials by default -- pass an
    explicit `config` to override (e.g. for a dial-sensitivity sweep)."""
    cfg = config if config is not None else npi_women_config()
    with using_di_team_path(WOMENS_TEAM_INFO):
        m = NPI(games_df, config=cfg)
        m.fit()
    return m


def fit_krach(games_df: pd.DataFrame) -> KRACH:
    with using_di_team_path(WOMENS_TEAM_INFO):
        m = KRACH(games_df)
        m.fit()
    return m


def fit_massey(games_df: pd.DataFrame) -> Massey:
    with using_di_team_path(WOMENS_TEAM_INFO):
        m = Massey(games_df, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True})
        m.fit()
    return m
