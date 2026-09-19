"""
5-year/20-split backtest of the core model roster (Massey, HockeyBT, KRACH,
ELO, RPI) on women's D-I hockey data — re-run, not ported, per
reports/womens_hockey_import.md's plan. Every hyperparameter here is the
men's-tuned default; this script's job is to check whether those defaults
still make sense on a structurally different competitive landscape, not to
assume they do.

IMPORTANT: every model instantiation must happen inside a
`using_di_team_path(...)` block — see src/rankings/base_ranker.py's
docstring for why the usual overlap-based safety check can't catch a
men's/women's mixup (most school names are shared between the two
divisions, so the "wrong naming convention" heuristic doesn't fire).

Run from the project root as a module:
    python -m analysis.exploratory.womens_hockey_backtest

See reports/womens_hockey_import.md for the results and interpretation.
"""
import pandas as pd
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.base_ranker import using_di_team_path
from src.rankings.massey import Massey
from src.rankings.hockey_bt import HockeyBT
from src.rankings.krach import KRACH
from src.rankings.elo import ELO
from src.rankings.rpi import RPI

WOMENS_TEAM_INFO = Path('data/teams/team_info_women.csv')
SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']


def main():
    loader = DataLoader(data_dir='data/raw/women')
    history_df = loader.get_history()
    print(f"Women's D-I historical games loaded: {len(history_df)}")
    print(history_df['Season'].value_counts().sort_index())

    models = {"Massey": Massey, "HockeyBT": HockeyBT, "KRACH": KRACH, "ELO": ELO, "RPI": RPI}
    configs = {
        "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
        "HockeyBT": {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4},
        "KRACH": {}, "ELO": {}, "RPI": {},
    }

    out_dir = Path('data/validation/backtest_results')
    with using_di_team_path(WOMENS_TEAM_INFO):
        engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
        engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'womens_hockey_backtest.csv', index=False)
    print("\n=== Women's hockey: split-averaged means (men's-tuned defaults) ===")
    cols = ['Accuracy', 'Brier', 'LogLoss', 'ECE', 'Reliability', 'Resolution']
    print(summary.groupby('Model')[cols].mean().reindex(['Massey', 'HockeyBT', 'KRACH', 'ELO', 'RPI']))


if __name__ == "__main__":
    main()
