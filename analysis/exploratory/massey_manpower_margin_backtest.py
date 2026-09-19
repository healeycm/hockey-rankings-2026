"""
Massey improvement #3 (of reports/massey_improvement_plan.md's "three
Massey options" — see reports/massey_experiments_2026.md for the writeup):
backtests `use_manpower_margin` in src/rankings/massey.py, fitting ratings
against even-manpower-only goal margin (excludes power-play/short-handed/
empty-net goals) instead of the raw final-score margin.

CAVEAT, same as the xG experiment: even-manpower data (Home_EV_Goals/
Away_EV_Goals) only exists for 2024-25 and 2025-26 (the two CHN-covered
seasons). With per-game fallback to the raw margin when unavailable, this
mechanically dilutes any pooled 5-year effect toward zero, so results are
reported both pooled (all 5 seasons) and restricted to the two covered
seasons.

Run from the project root as a module:
    python -m analysis.exploratory.massey_manpower_margin_backtest
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
EV_COVERED_SEASONS = [20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
BASE_CONFIG = {'margin_cap': 3, 'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True,
               'fit_rest_advantage': True, 'rest_days_cap': 5}


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
    print(f"Home_EV_Goals coverage: {history_df['Home_EV_Goals'].notna().sum()} / {len(history_df)} games")

    models = {"Massey_raw": Massey, "Massey_manpower": Massey}
    configs = {
        "Massey_raw": dict(BASE_CONFIG, use_manpower_margin=False),
        "Massey_manpower": dict(BASE_CONFIG, use_manpower_margin=True),
    }

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'massey_manpower_margin_backtest.csv', index=False)
    print("\n=== Split-averaged means, ALL 5 seasons (standard protocol) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean())

    print("\n=== Split-averaged means, EV-COVERED seasons only (2024-25, 2025-26) ===")
    covered = summary[summary['Season'].isin(EV_COVERED_SEASONS)]
    print(covered.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean())

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)

    paired_report(res, 'Massey_manpower', 'Massey_raw', "ALL 5 seasons pooled")

    res_covered = res[res['Season'].isin(EV_COVERED_SEASONS)]
    paired_report(res_covered, 'Massey_manpower', 'Massey_raw', "EV-covered seasons only")

    n_diff = int((res_covered['Massey_manpower'] != res_covered['Massey_raw']).sum())
    print(f"\nOf {len(res_covered)} test games in EV-covered seasons, Massey_manpower and Massey_raw "
          f"produced a DIFFERENT prediction on {n_diff} ({n_diff / len(res_covered):.1%}).")


if __name__ == "__main__":
    main()
