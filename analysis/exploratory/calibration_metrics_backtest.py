"""
Runs the 5-year/20-split backtest for the core model roster and reports the
newly-added calibration metrics (ECE, Brier decomposition) alongside
Accuracy/Brier/LogLoss, plus RPS for HockeyBT (the one model in this set
exposing native 3-outcome predict_outcomes()).

Run from the project root as a module:
    python -m analysis.exploratory.calibration_metrics_backtest

See reports/calibration_metrics.md for the results and interpretation.
"""
import pandas as pd
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.massey import Massey
from src.rankings.hockey_bt import HockeyBT
from src.rankings.krach import KRACH
from src.rankings.elo import ELO
from src.rankings.rpi import RPI
from src.validation.metrics import get_calibration_table

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    models = {"Massey": Massey, "HockeyBT": HockeyBT, "KRACH": KRACH, "ELO": ELO, "RPI": RPI}
    configs = {
        "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
        "HockeyBT": {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4},
        "KRACH": {}, "ELO": {}, "RPI": {},
    }
    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    engine.save_results()

    summary = pd.DataFrame(engine.results_summary)
    print("\n=== Full metric suite, split-averaged (20 splits) ===")
    cols = ['Accuracy', 'Brier', 'LogLoss', 'ECE', 'Reliability', 'Resolution', 'Uncertainty']
    if 'RPS' in summary.columns:
        cols.append('RPS')
    print(summary.groupby('Model')[cols].mean().reindex(['Massey', 'ELO', 'RPI', 'HockeyBT', 'KRACH']))

    # Pooled calibration table for the two extremes (Massey, KRACH)
    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    from src.validation.metrics import apply_ot_weighting
    all_preds['WeightedResult'] = apply_ot_weighting(all_preds, ot_win_weight=0.6, ot_loss_weight=0.4)

    for name in ['Massey', 'KRACH']:
        sub = all_preds[all_preds['Model'] == name]
        table = get_calibration_table(sub, target_col='WeightedResult', n_bins=10)
        print(f"\n=== Calibration table: {name} (n={len(sub)}) ===")
        print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
