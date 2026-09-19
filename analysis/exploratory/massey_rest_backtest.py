"""
Massey improvement #2 (of reports/massey_improvement_plan.md's "three
Massey options" — see reports/massey_experiments_2026.md for the writeup):
backtests `fit_rest_advantage` in src/rankings/massey.py, an extra fitted
covariate for schedule rest (days since each team's last game).

This CANNOT reuse BacktestEngine.run() unmodified: BacktestEngine calls
`model.predict(home, away, is_neutral)` with no game_date, and Massey's
rest term is exactly 0.0 without one (a deliberate no-op for every
existing caller — see massey.py's predict() docstring). This script
mirrors BacktestEngine's train/test cutoff logic exactly (reusing its
_get_cutoff_date helper) but calls predict(..., game_date=row['Date']),
which is the only way to actually exercise the feature.

Run from the project root as a module:
    python -m analysis.exploratory.massey_rest_backtest
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.massey import Massey
from src.validation.metrics import (
    apply_ot_weighting, calculate_accuracy, calculate_brier, calculate_log_loss,
)

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
BASE_CONFIG = {'margin_cap': 3, 'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True}
ARMS = {
    "rest_off": dict(BASE_CONFIG, fit_rest_advantage=False),
    "rest_on": dict(BASE_CONFIG, fit_rest_advantage=True),
}


def run_custom_backtest(history_df):
    engine = BacktestEngine(history_df, Path('.'))  # only used for _get_cutoff_date
    all_preds = []
    summary_rows = []

    for season in SEASONS:
        season_df = history_df[history_df['Season'] == season].copy()
        if season_df.empty:
            continue
        for cutoff_name in CUTOFFS:
            cutoff_date = engine._get_cutoff_date(season, cutoff_name)
            train_df = season_df[season_df['Date'] < cutoff_date].copy()
            test_df = season_df[season_df['Date'] >= cutoff_date].copy()
            if train_df.empty or test_df.empty:
                continue

            for arm_name, config in ARMS.items():
                model = Massey(train_df, config=config)
                model.fit()

                preds = []
                for _, row in test_df.iterrows():
                    prob = model.predict(row['HomeTeam'], row['AwayTeam'], row['NeutralSite'],
                                          game_date=row['Date'])
                    preds.append({
                        'Season': season, 'Cutoff': cutoff_name, 'Date': row['Date'],
                        'HomeTeam': row['HomeTeam'], 'AwayTeam': row['AwayTeam'],
                        'Result': row['Result'], 'IsOT': row.get('IsOT', False),
                        'HomeWinProb': prob, 'Model': arm_name,
                    })
                pred_df = pd.DataFrame(preds)
                pred_df['WeightedResult'] = apply_ot_weighting(pred_df, ot_win_weight=0.6, ot_loss_weight=0.4)
                summary_rows.append({
                    'Season': season, 'Cutoff': cutoff_name, 'Model': arm_name,
                    'Games_Test': len(pred_df),
                    'Accuracy': calculate_accuracy(pred_df, target_col='WeightedResult'),
                    'Brier': calculate_brier(pred_df, target_col='WeightedResult'),
                    'LogLoss': calculate_log_loss(pred_df, target_col='WeightedResult'),
                })
                all_preds.append(pred_df)

    return pd.DataFrame(summary_rows), pd.concat(all_preds, ignore_index=True)


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    summary, all_preds = run_custom_backtest(history_df)

    out_dir = Path('data/validation/backtest_results')
    summary.to_csv(out_dir / 'massey_rest_backtest.csv', index=False)
    print("=== Split-averaged means (20 splits): rest_off vs rest_on ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex(['rest_off', 'rest_on']))

    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)

    n = len(res)
    p_on, p_off, y = res['rest_on'].values, res['rest_off'].values, res['WeightedResult'].values
    b_on, b_off = (p_on - y) ** 2, (p_off - y) ** 2
    _, pval_b = stats.ttest_rel(b_on, b_off)

    mask = res['Result'] != 0.5
    yy = y[mask]
    pc_on, pc_off = np.clip(p_on[mask], 1e-15, 1 - 1e-15), np.clip(p_off[mask], 1e-15, 1 - 1e-15)
    ll_on = -(yy * np.log(pc_on) + (1 - yy) * np.log(1 - pc_on))
    ll_off = -(yy * np.log(pc_off) + (1 - yy) * np.log(1 - pc_off))
    _, pval_l = stats.ttest_rel(ll_on, ll_off)

    correct_on, correct_off = np.round(pc_on) == np.round(yy), np.round(pc_off) == np.round(yy)
    b01, b10 = np.sum(correct_on & ~correct_off), np.sum(~correct_on & correct_off)
    mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

    print(f"\n=== Pooled paired comparison, n={n} ===")
    print(f"  Accuracy: rest_on={correct_on.mean():.4f} rest_off={correct_off.mean():.4f} (McNemar p={p_mcnemar:.4f})")
    print(f"  Brier:    rest_on={b_on.mean():.5f} rest_off={b_off.mean():.5f} diff={b_on.mean() - b_off.mean():+.6f} (p={pval_b:.3g})")
    print(f"  LogLoss:  rest_on={ll_on.mean():.5f} rest_off={ll_off.mean():.5f} diff={ll_on.mean() - ll_off.mean():+.6f} (p={pval_l:.3g})")


if __name__ == "__main__":
    main()
