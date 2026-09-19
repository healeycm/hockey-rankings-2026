"""
Dixon-Coles vs. fixed Massey: prior_strength sweep, then the definitive
paired per-game significance test.

Run from the project root as a module:
    python -m analysis.exploratory.dixon_coles_backtest

See reports/dixon_coles_results.md for the results and interpretation.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.dixon_coles import DixonColes
from src.rankings.massey import Massey
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']


def run_kappa_sweep(history_df, out_dir):
    kappas = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
    models = {f"k{k}": DixonColes for k in kappas}
    configs = {f"k{k}": {'fit_home_ice': True, 'fit_rho': False, 'prior_strength': k} for k in kappas}
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    summary = pd.DataFrame(engine.results_summary)
    print("\n=== DixonColes prior_strength sweep (fit_home_ice=True, fit_rho=False) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex([f"k{k}" for k in kappas]))
    print("\n(Massey reference: ~64.9% / 0.172 / 0.632)")


def run_paired_test(history_df, out_dir):
    models = {"DixonColes": DixonColes, "Massey": Massey}
    configs = {
        "DixonColes": {'fit_home_ice': True, 'fit_rho': False, 'prior_strength': 3.0},
        "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
    }
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    engine.save_results()

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    y = res['WeightedResult'].values
    n = len(res)

    p_dc, p_m = res['DixonColes'].values, res['Massey'].values
    b_dc, b_m = (p_dc - y) ** 2, (p_m - y) ** 2
    _, pval_b = stats.ttest_rel(b_dc, b_m)

    mask = res['Result'] != 0.5
    yy = res.loc[mask, 'WeightedResult'].values
    pc_dc = np.clip(p_dc[mask], 1e-15, 1 - 1e-15)
    pc_m = np.clip(p_m[mask], 1e-15, 1 - 1e-15)
    ll_dc = -(yy * np.log(pc_dc) + (1 - yy) * np.log(1 - pc_dc))
    ll_m = -(yy * np.log(pc_m) + (1 - yy) * np.log(1 - pc_m))
    _, pval_l = stats.ttest_rel(ll_dc, ll_m)

    correct_dc = np.round(pc_dc) == np.round(yy)
    correct_m = np.round(pc_m) == np.round(yy)
    b01 = np.sum(correct_dc & ~correct_m)
    b10 = np.sum(~correct_dc & correct_m)
    mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

    print(f"\n=== DixonColes vs Massey (n={n}) ===")
    print(f"Accuracy: DC={correct_dc.mean():.4f} Massey={correct_m.mean():.4f}  "
          f"(DC-right/M-wrong: {b01}, DC-wrong/M-right: {b10}, McNemar p={p_mcnemar:.4f})")
    print(f"Brier:    DC={b_dc.mean():.5f} Massey={b_m.mean():.5f}  "
          f"diff={b_dc.mean() - b_m.mean():+.6f}  p={pval_b:.4f}")
    print(f"LogLoss:  DC={ll_dc.mean():.5f} Massey={ll_m.mean():.5f}  "
          f"diff={ll_dc.mean() - ll_m.mean():+.6f}  p={pval_l:.4f}")


def main():
    loader = DataLoader()
    history_df = loader.get_history()
    out_dir = Path('data/validation/backtest_results')

    run_kappa_sweep(history_df, out_dir)
    run_paired_test(history_df, out_dir)


if __name__ == "__main__":
    main()
