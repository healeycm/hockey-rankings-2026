"""
5-year, Jan/Feb-cutoff comparison of KRACH, NPI, LRMC_Classic, and HockeyLRMC.

Run from the project root as a module (needed for the `src.*` imports):
    python -m analysis.exploratory.five_year_backtest

Design notes:
- 5 seasons: excludes the COVID-shortened 2020-21 and the missing-data
  2016-17 (data/raw/games_2016_2017.csv doesn't exist), consistent with the
  precedent already set in src/analysis/npi_vs_krach.py's BACKTEST_SEASONS.
- 4 cutoffs per season (Jan1/Jan15/Feb1/Feb15), deliberately dropping the
  December cutoff used in earlier backtests: with too little training data,
  the Markov-chain-based models (LRMC family) can produce degenerate,
  near-zero ratings for thinly-connected teams, which then blow up
  predict()'s log(r_home/r_away) into a near-0/near-1 probability — see the
  LRMC_Zero investigation (Assumption/Saint Anselm, 2024-25 season) that
  motivated the centralized DI-team filter in base_ranker.py. Jan-on cutoffs
  give the ratings enough games to stabilize while still keeping most of the
  season as a test set. 5 seasons x 4 cutoffs = 20 independent splits, ~8.4k
  test games total per model — a much larger sample than the original
  4-season x 3-cutoff (12-split) backtests used earlier in this project.

See reports/five_year_backtest_and_di_filter.md for the results and analysis.
"""
import pandas as pd
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.krach import KRACH
from src.rankings.npi import NPI
from src.rankings.lrmc import LRMC
from src.rankings.hockey_lrmc import HockeyLRMC


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    models = {
        "KRACH": KRACH,
        "NPI": NPI,
        "LRMC_Classic": LRMC,
        "HockeyLRMC": HockeyLRMC,
    }
    configs = {
        "LRMC_Classic": {'variant': 'classic', 'margin_cap': 3, 'auto_fit': True, 'fit_source': 'history'},
        "HockeyLRMC": {'auto_fit': True, 'fit_source': 'history'},
        "NPI": {}, "KRACH": {},
    }

    seasons = [20212022, 20222023, 20232024, 20242025, 20252026]
    cutoffs = ['Jan1', 'Jan15', 'Feb1', 'Feb15']

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=seasons, cutoffs=cutoffs, model_factory=models, model_configs=configs)
    engine.save_results()

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'five_year_summary.csv', index=False)

    print("\n=== Per-Model Overall Means (all seasons x cutoffs) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().sort_values('Accuracy', ascending=False))
    print(f"\nTotal (season x cutoff) splits: {summary[['Season', 'Cutoff']].drop_duplicates().shape[0]}")
    print(f"Total test games across all splits: {summary.groupby('Model')['Games_Test'].sum().iloc[0]}")


if __name__ == "__main__":
    main()
