"""
Fixed Massey vs. original Massey (ridge_lambda sweep), then a definitive
paired per-game significance test against HockeyBT, ELO, and KRACH.

Run from the project root as a module:
    python -m analysis.exploratory.massey_backtest

See reports/massey_calibration_results.md for the results and interpretation.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.massey import Massey
from src.rankings.hockey_bt import HockeyBT
from src.rankings.elo import ELO
from src.rankings.krach import KRACH
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']


def run_ridge_sweep(history_df, out_dir):
    lambdas = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]
    models = {"Massey_orig": Massey, **{f"Massey_L{l}": Massey for l in lambdas}}
    configs = {"Massey_orig": {'fit_home_ice': False, 'ridge_lambda': 0.0, 'fit_beta': False}}
    configs.update({f"Massey_L{l}": {'fit_home_ice': True, 'ridge_lambda': l, 'fit_beta': True} for l in lambdas})

    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'massey_fix_sweep.csv', index=False)
    print("\n=== Massey fix + ridge sweep (5-year, 20 splits) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean()
          .reindex(["Massey_orig"] + [f"Massey_L{l}" for l in lambdas]))


def run_paired_test(history_df, out_dir):
    models = {"Massey": Massey, "HockeyBT": HockeyBT, "ELO": ELO, "KRACH": KRACH}
    configs = {
        "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
        "HockeyBT": {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4},
        "ELO": {}, "KRACH": {},
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
    print(f"\n=== Pooled paired-comparison games: {n} ===")

    for model in ['HockeyBT', 'ELO', 'KRACH']:
        p_m, p_o = res['Massey'].values, res[model].values
        b_m, b_o = (p_m - y) ** 2, (p_o - y) ** 2
        _, pval_b = stats.ttest_rel(b_m, b_o)

        mask = res['Result'] != 0.5
        yy = res.loc[mask, 'WeightedResult'].values
        pc_m = np.clip(p_m[mask], 1e-15, 1 - 1e-15)
        pc_o = np.clip(p_o[mask], 1e-15, 1 - 1e-15)
        ll_m = -(yy * np.log(pc_m) + (1 - yy) * np.log(1 - pc_m))
        ll_o = -(yy * np.log(pc_o) + (1 - yy) * np.log(1 - pc_o))
        _, pval_l = stats.ttest_rel(ll_m, ll_o)

        correct_m = np.round(pc_m) == np.round(yy)
        correct_o = np.round(pc_o) == np.round(yy)
        b01 = np.sum(correct_m & ~correct_o)
        b10 = np.sum(~correct_m & correct_o)
        mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
        p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

        print(f"\n--- Massey vs {model} (n={n}) ---")
        print(f"  Accuracy: Massey={correct_m.mean():.4f} {model}={correct_o.mean():.4f}  "
              f"(M-right/other-wrong: {b01}, M-wrong/other-right: {b10}, McNemar p={p_mcnemar:.4f})")
        print(f"  Brier:    Massey={b_m.mean():.5f} {model}={b_o.mean():.5f}  "
              f"diff={b_m.mean() - b_o.mean():+.6f}  p={pval_b:.2e}")
        print(f"  LogLoss:  Massey={ll_m.mean():.5f} {model}={ll_o.mean():.5f}  "
              f"diff={ll_m.mean() - ll_o.mean():+.6f}  p={pval_l:.2e}")


def main():
    loader = DataLoader()
    history_df = loader.get_history()
    out_dir = Path('data/validation/backtest_results')

    run_ridge_sweep(history_df, out_dir)
    run_paired_test(history_df, out_dir)


if __name__ == "__main__":
    main()
