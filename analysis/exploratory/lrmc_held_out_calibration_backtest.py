"""
LRMC option #3 (of the "experiment with all LRMC options" pass — see
reports/lrmc_experiments_2026.md): backtests `held_out_calibration` in
src/rankings/hockey_lrmc.py, a genuinely held-out version of the
calibration attempt that failed in reports/lrmc_calibration.md (that
attempt calibrated against the SAME games used to fit the ratings; this one
fits ratings on an earlier temporal slice and calibrates only against the
later slice's actual outcomes, mirroring Massey's held-out beta fit).

Sweeps held_out_calibration_shrinkage in {0.0 (=off, baseline), 0.25, 0.5,
0.75, 1.0 (full fit)} against the standard 5-year/20-split protocol.

Run from the project root as a module:
    python -m analysis.exploratory.lrmc_held_out_calibration_backtest
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.hockey_lrmc import HockeyLRMC
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
SHRINKAGES = [0.0, 0.25, 0.5, 0.75, 1.0]


def paired_report(res, model_a, model_b, label):
    n = len(res)
    p_a, p_b, y = res[model_a].values, res[model_b].values, res['WeightedResult'].values

    b_a, b_b = (p_a - y) ** 2, (p_b - y) ** 2
    _, pval_b = stats.ttest_rel(b_a, b_b)

    mask = res['Result'] != 0.5
    yy = y[mask]
    pc_a, pc_b = np.clip(p_a[mask], 1e-15, 1 - 1e-15), np.clip(p_b[mask], 1e-15, 1 - 1e-15)
    ll_a = -(yy * np.log(pc_a) + (1 - yy) * np.log(1 - pc_a))
    ll_b = -(yy * np.log(pc_b) + (1 - yy) * np.log(1 - pc_b))
    _, pval_l = stats.ttest_rel(ll_a, ll_b)

    correct_a, correct_b = np.round(pc_a) == np.round(yy), np.round(pc_b) == np.round(yy)
    b01, b10 = np.sum(correct_a & ~correct_b), np.sum(~correct_a & correct_b)
    mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

    print(f"  {label}: n={n}  Acc {correct_a.mean():.4f} vs {correct_b.mean():.4f} (McNemar p={p_mcnemar:.4f})  "
          f"Brier diff={b_a.mean() - b_b.mean():+.6f} (p={pval_b:.3g})  "
          f"LogLoss diff={ll_a.mean() - ll_b.mean():+.6f} (p={pval_l:.3g})")


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    models = {f"shrink_{s}": HockeyLRMC for s in SHRINKAGES}
    configs = {
        f"shrink_{s}": {'auto_fit': True, 'fit_source': 'history',
                         'held_out_calibration': True, 'held_out_calibration_shrinkage': s}
        for s in SHRINKAGES
    }

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'lrmc_held_out_calibration_backtest.csv', index=False)
    print("=== Split-averaged means (20 splits) by shrinkage ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex([f"shrink_{s}" for s in SHRINKAGES]))

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)

    print(f"\n=== Pooled paired comparisons vs shrink_0.0 (=off, current default) baseline, n={len(res)} ===")
    for s in SHRINKAGES[1:]:
        paired_report(res, f"shrink_{s}", "shrink_0.0", f"shrink={s}")


if __name__ == "__main__":
    main()
