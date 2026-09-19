"""
Massey improvement #1 (of reports/massey_improvement_plan.md's "three
Massey options" — see reports/massey_experiments_2026.md for the writeup):
backtests `time_decay_halflife` in src/rankings/massey.py, a recency
weighting on training games (no new data needed -- pure reuse of the
existing Date column).

Sweeps halflife in {None (=off, baseline), 90, 45, 30, 15} against the
standard 5-year/20-split protocol.

Run from the project root as a module:
    python -m analysis.exploratory.massey_time_decay_backtest
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.massey import Massey
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
HALFLIVES = [None, 90, 45, 30, 15]
BASE_CONFIG = {'margin_cap': 3, 'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True}


def _key(h):
    return f"halflife_{h}"


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

    models = {_key(h): Massey for h in HALFLIVES}
    configs = {_key(h): dict(BASE_CONFIG, time_decay_halflife=h) for h in HALFLIVES}

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'massey_time_decay_backtest.csv', index=False)
    print("=== Split-averaged means (20 splits) by halflife ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex([_key(h) for h in HALFLIVES]))

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)

    print(f"\n=== Pooled paired comparisons vs halflife_None (=off, current default) baseline, n={len(res)} ===")
    for h in HALFLIVES[1:]:
        paired_report(res, _key(h), _key(None), f"halflife={h}")


if __name__ == "__main__":
    main()
