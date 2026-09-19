"""
Sweeps HockeyLRMC's `calibration_shrinkage` (0.0 = ignore the in-sample
Platt-scaling fit entirely, 1.0 = trust it fully) across the 5-year backtest
to check whether prediction calibration helps.

Run from the project root as a module:
    python -m analysis.exploratory.lrmc_calibration_sweep

Result (see reports/lrmc_calibration.md for the full writeup): LogLoss gets
monotonically WORSE with any nonzero shrinkage; Brier improves marginally up
to ~0.2-0.3 before also reversing. Shipped default is
calibrate_predictions=False (equivalent to shrinkage=0.0) in
src/rankings/hockey_lrmc.py.
"""
import pandas as pd
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.hockey_lrmc import HockeyLRMC


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    shrink_levels = [0.0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0]
    models = {f"shrink_{s}": HockeyLRMC for s in shrink_levels}
    configs = {
        f"shrink_{s}": {
            'auto_fit': True, 'fit_source': 'history',
            'calibrate_predictions': True, 'calibration_shrinkage': s,
        }
        for s in shrink_levels
    }

    seasons = [20212022, 20222023, 20232024, 20242025, 20252026]
    cutoffs = ['Jan1', 'Jan15', 'Feb1', 'Feb15']

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=seasons, cutoffs=cutoffs, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'lrmc_calibration_sweep.csv', index=False)

    print("\n=== Calibration Shrinkage Sweep (5-year, 20 splits) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean()
          .reindex([f"shrink_{s}" for s in shrink_levels]))


if __name__ == "__main__":
    main()
