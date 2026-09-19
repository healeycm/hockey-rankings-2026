"""
LRMC option #4 (of the "experiment with all LRMC options" pass — see
reports/lrmc_experiments_2026.md): backtests `iterative_fit` in
src/rankings/hockey_lrmc.py, a self-consistent version of LRMC that
iteratively blends the original margin-based per-game probability with the
Bradley-Terry-implied probability from the CURRENT iteration's ratings,
rebuilding the transition matrix each round until ratings converge.

Sweeps iterative_blend in {0.0 (=off, baseline), 0.25, 0.5, 0.75, 1.0 (fully
self-consistent, margin evidence only informs iteration 0)} against the
standard 5-year/20-split protocol.

Run from the project root as a module:
    python -m analysis.exploratory.lrmc_iterative_backtest
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
BLENDS = [0.0, 0.25, 0.5, 0.75, 1.0]


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

    models = {f"blend_{b}": HockeyLRMC for b in BLENDS}
    configs = {
        f"blend_{b}": {'auto_fit': True, 'fit_source': 'history',
                        'iterative_fit': True, 'iterative_blend': b}
        for b in BLENDS
    }

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'lrmc_iterative_backtest.csv', index=False)
    print("=== Split-averaged means (20 splits) by blend ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex([f"blend_{b}" for b in BLENDS]))

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)

    print(f"\n=== Pooled paired comparisons vs blend_0.0 (=off, current default) baseline, n={len(res)} ===")
    for b in BLENDS[1:]:
        paired_report(res, f"blend_{b}", "blend_0.0", f"blend={b}")


if __name__ == "__main__":
    main()
