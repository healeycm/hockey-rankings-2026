"""
RPI vs. NPI vs. Massey: does NPI's added complexity (75% SOS weight,
quality-win bonus, outcome-based bad-wins filter) actually improve on the
simpler RPI system it replaced? Runs the 5-year/20-split backtest, then a
paired per-game significance test on the pooled predictions.

Run from the project root as a module:
    python -m analysis.exploratory.rpi_backtest

See reports/rpi_results.md for the results and interpretation.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.rpi import RPI
from src.rankings.massey import Massey
from src.rankings.npi import NPI
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    models = {"RPI": RPI, "Massey": Massey, "NPI": NPI}
    configs = {
        "RPI": {}, "NPI": {},
        "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
    }
    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    engine.save_results()

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'rpi_backtest.csv', index=False)
    print("\n=== Split-averaged means (20 splits) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex(['Massey', 'RPI', 'NPI']))

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    y = res['WeightedResult'].values
    n = len(res)
    print(f"\n=== Pooled paired-comparison games: {n} ===")

    for model in ['NPI', 'Massey']:
        p_r, p_o = res['RPI'].values, res[model].values
        b_r, b_o = (p_r - y) ** 2, (p_o - y) ** 2
        _, pval_b = stats.ttest_rel(b_r, b_o)

        mask = res['Result'] != 0.5
        yy = res.loc[mask, 'WeightedResult'].values
        pc_r = np.clip(p_r[mask], 1e-15, 1 - 1e-15)
        pc_o = np.clip(p_o[mask], 1e-15, 1 - 1e-15)
        ll_r = -(yy * np.log(pc_r) + (1 - yy) * np.log(1 - pc_r))
        ll_o = -(yy * np.log(pc_o) + (1 - yy) * np.log(1 - pc_o))
        _, pval_l = stats.ttest_rel(ll_r, ll_o)

        correct_r = np.round(pc_r) == np.round(yy)
        correct_o = np.round(pc_o) == np.round(yy)
        b01 = np.sum(correct_r & ~correct_o)
        b10 = np.sum(~correct_r & correct_o)
        mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
        p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

        print(f"\n--- RPI vs {model} (n={n}) ---")
        print(f"  Accuracy: RPI={correct_r.mean():.4f} {model}={correct_o.mean():.4f}  (McNemar p={p_mcnemar:.4f})")
        print(f"  Brier:    RPI={b_r.mean():.5f} {model}={b_o.mean():.5f}  "
              f"diff={b_r.mean() - b_o.mean():+.6f}  p={pval_b:.2e}")
        print(f"  LogLoss:  RPI={ll_r.mean():.5f} {model}={ll_o.mean():.5f}  "
              f"diff={ll_r.mean() - ll_o.mean():+.6f}  p={pval_l:.2e}")


if __name__ == "__main__":
    main()
