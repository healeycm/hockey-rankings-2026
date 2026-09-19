# src/rankings/base_ranker.py

import contextlib
from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd

_TEAMS_DIR = Path(__file__).resolve().parents[2] / "data" / "teams"
_TEAM_INFO_PATH = _TEAMS_DIR / "team_info.csv"  # default: men's, unchanged from before division support existed
_DI_TEAMS_CACHE = {}  # keyed by resolved path, so men's and women's lists never collide
_ACTIVE_DI_TEAM_PATH = None  # None = use the men's default _TEAM_INFO_PATH; see using_di_team_path() below


@contextlib.contextmanager
def using_di_team_path(path):
    """
    Temporarily changes which team_info-style CSV every ranker's DI filter
    uses BY DEFAULT for any model instantiated inside this block —
    without needing to plumb a di_team_path kwarg through every model
    subclass's __init__ (most of them call `super().__init__(games_df)`
    without forwarding extra kwargs today, so a constructor-argument
    approach would mean touching all ~13 ranker files). Use this to run a
    whole analysis (a backtest, a single fit, an entire script) against a
    different division's team list:

        with using_di_team_path(TEAMS_DIR / "team_info_women.csv"):
            model = Massey(womens_games_df)
            model.fit()

    An explicit `di_team_path` passed directly to a model's constructor
    (for classes that do forward it) still takes precedence over this.
    """
    global _ACTIVE_DI_TEAM_PATH
    previous = _ACTIVE_DI_TEAM_PATH
    _ACTIVE_DI_TEAM_PATH = Path(path)
    try:
        yield
    finally:
        _ACTIVE_DI_TEAM_PATH = previous


def load_di_teams(path=None):
    """
    Loads (and process-caches, per path) the set of USCHO Division-I team
    names from a team_info-style CSV (default: data/teams/team_info.csv,
    the men's list — unchanged behavior from before women's hockey support
    was added). Pass `path` to load a different division's list, e.g.
    data/teams/team_info_women.csv. Returns None if the file can't be read,
    so callers can distinguish "no filter available" from "empty filter".
    """
    resolved = Path(path) if path else _TEAM_INFO_PATH
    if resolved not in _DI_TEAMS_CACHE:
        try:
            team_info = pd.read_csv(resolved)
            _DI_TEAMS_CACHE[resolved] = set(team_info['USCHO_Name'].unique())
        except Exception as e:
            print(f"Warning: could not load DI team list from {resolved}: {e}")
            _DI_TEAMS_CACHE[resolved] = None
    return _DI_TEAMS_CACHE[resolved]


class BaseRanker(ABC):
    def __init__(self, games_df, **kwargs):
        """
        Initialize the ranking system.

        Args:
            games_df (pd.DataFrame): Must contain 'HomeTeam', 'AwayTeam',
                                     'Result' (1.0, 0.5, 0.0), and 'NeutralSite'.
        """
        self.config = kwargs.get('config', {})
        self.games = games_df.copy()

        self._apply_di_filter(
            filter_di_teams=kwargs.get('filter_di_teams', True),
            di_team_path=kwargs.get('di_team_path'),
        )

        self.ratings = {}  # Dictionary {TeamName: RatingValue}
        self.teams = sorted(list(set(self.games['HomeTeam']).union(set(self.games['AwayTeam']))))

        # Validation
        required_cols = ['HomeTeam', 'AwayTeam', 'Result']
        missing = [c for c in required_cols if c not in self.games.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required columns: {missing}")

    def _apply_di_filter(self, filter_di_teams=True, di_team_path=None):
        """
        Filters self.games to only games where BOTH teams are Division I,
        using data/teams/team_info.csv by default (the same list NPI/
        NPIGames already used internally) — pass `di_team_path` to use a
        different division's list (e.g. data/teams/team_info_women.csv;
        see reports/womens_hockey_import.md). A non-DI opponent slipping
        into a "counting"
        (non-exhibition) game creates a near-isolated/winless node for
        win-loss- and Markov-chain-based models (KRACH, LRMC, Colley,
        Massey, Markov). For LRMC's eigenvector-based ratings this can
        degenerate to a literal ~0 rating, which then sends predict()'s
        log(r_home/r_away) to +-infinity — a near-0/near-1 probability
        that's catastrophic if wrong (concrete case: Assumption/Saint
        Anselm, 2024-25 season — see reports/lrmc_hockey_adaptation.md).
        Centralizing this here means every ranker gets the same protection
        NPI already had, instead of each subclass having to remember it.

        Only applied when it's actually meaningful: if fewer than half the
        input teams match the DI list, this probably isn't USCHO-named
        production data (e.g. synthetic unit-test fixtures, or a different
        naming convention) — skip rather than silently filtering the
        dataset down to nothing. Below that threshold but still nonzero
        overlap, warn rather than silently doing something surprising.
        """
        if not filter_di_teams:
            return
        if 'HomeTeam' not in self.games.columns or 'AwayTeam' not in self.games.columns or self.games.empty:
            return

        effective_path = di_team_path or _ACTIVE_DI_TEAM_PATH
        di_teams = load_di_teams(path=effective_path)
        if not di_teams:
            return

        all_teams = set(self.games['HomeTeam']).union(set(self.games['AwayTeam']))
        if not all_teams:
            return
        overlap = len(all_teams & di_teams) / len(all_teams)

        if overlap == 0:
            return  # Not DI-named data at all (e.g. unit-test fixtures); nothing to filter.
        if overlap < 0.5:
            print(f"Warning: only {overlap:.0%} of teams in this dataset matched the DI team "
                  f"list; skipping the DI filter (data may use a different naming convention).")
            return

        before = len(self.games)
        self.games = self.games[
            self.games['HomeTeam'].isin(di_teams) & self.games['AwayTeam'].isin(di_teams)
        ].copy()
        self.di_filter_dropped_games = before - len(self.games)

    @abstractmethod
    def fit(self):
        """
        Calculate ratings based on the provided games.
        Must populate self.ratings.
        """
        pass

    @abstractmethod
    def predict(self, home_team, away_team, is_neutral=False):
        """
        Predict the probability of the Home Team winning.

        Returns:
            float: Probability (0.0 to 1.0)
        """
        pass

    def get_rankings(self, ascending=False):
        """
        Returns a formatted DataFrame of the current rankings.

        Args:
            ascending (bool): False for "Higher is Better" (KRACH/LRMC/ELO) -> Sorts Descending
                              True for "Lower is Better" (Pairwise/RPI ranks) -> Sorts Ascending
        """
        if not self.ratings:
            print("Warning: Ratings are empty. Did you run fit()?")
            return pd.DataFrame()

        df = pd.DataFrame(list(self.ratings.items()), columns=['Team', 'Rating'])

        # FIX: Removed 'not'.
        # If ascending=False (Higher is Better), we want pandas to sort descending (ascending=False).
        df = df.sort_values('Rating', ascending=ascending).reset_index(drop=True)

        df.index += 1  # 1-based rank
        return df