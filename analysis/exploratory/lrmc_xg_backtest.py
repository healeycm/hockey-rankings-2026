"""
LRMC option #1 (of the "experiment with all LRMC options" pass — see
reports/lrmc_experiments_2026.md): backtests the already-wired but never-
validated `use_xg` toggle in src/rankings/lrmc.py. The question: does using
expected-goals margin (a puck-luck-adjusted signal) instead of actual goal
margin improve LRMC's predictions?

IMPORTANT CAVEAT, checked before running anything: real per-game xG
coverage (Home_xG/Away_xG) is 0% for every season before 2024-25 (0/1173 in
2023-24, 0/1089 in 2021-22, etc.) and only 90%/46% for 2024-25/2025-26
respectively (the latter because the season is still in progress as of this
scrape). With `fallback_to_goals=True`, LRMC_xG is BYTE-IDENTICAL to
LRMC_Classic on every game outside that window, which mechanically dilutes
any pooled 5-year effect toward zero regardless of whether xG actually
helps. This script reports BOTH the standard 5-year/20-split pooled result
(for comparability with every other backtest in this project) AND a
separate breakdown restricted to the 2024-25/2025-26 seasons where xG
coverage is real, since that's the only place an effect could possibly show
up.

Every OTHER config knob (margin_cap, auto_fit, fit_source, time_decay) is
held IDENTICAL between the two arms -- config.yaml's existing LRMC_xG block
also flips on time_decay_halflife=60, which would confound this ablation,
so it's deliberately not used here.

Run from the project root as a module:
    python -m analysis.exploratory.lrmc_xg_backtest
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.lrmc import LRMC
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
XG_COVERED_SEASONS = [20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']

BASE_CONFIG = {
    'variant': 'classic', 'margin_cap': 3, 'auto_fit': True, 'fit_source': 'history',
    'time_decay_halflife': None,
}


def paired_report(res, y_col, model_a, model_b, label):
    n = len(res)
    p_a = res[model_a].values
    p_b = res[model_b].values
    y = res[y_col].values

    b_a, b_b = (p_a - y) ** 2, (p_b - y) ** 2
    t_b, pval_b = stats.ttest_rel(b_a, b_b)

    mask = res['Result'] != 0.5
    yy = y[mask]
    pc_a = np.clip(p_a[mask], 1e-15, 1 - 1e-15)
    pc_b = np.clip(p_b[mask], 1e-15, 1 - 1e-15)
    ll_a = -(yy * np.log(pc_a) + (1 - yy) * np.log(1 - pc_a))
    ll_b = -(yy * np.log(pc_b) + (1 - yy) * np.log(1 - pc_b))
    t_l, pval_l = stats.ttest_rel(ll_a, ll_b)

    correct_a = np.round(pc_a) == np.round(yy)
    correct_b = np.round(pc_b) == np.round(yy)
    b01 = np.sum(correct_a & ~correct_b)
    b10 = np.sum(~correct_a & correct_b)
    mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

    print(f"\n--- {label}: {model_a} vs {model_b} (n={n}) ---")
    print(f"  Accuracy: {model_a}={correct_a.mean():.4f} {model_b}={correct_b.mean():.4f}  "
          f"({model_a}-right/{model_b}-wrong: {b01}, reverse: {b10}, McNemar p={p_mcnemar:.4f})")
    print(f"  Brier:    {model_a}={b_a.mean():.5f} {model_b}={b_b.mean():.5f}  "
          f"diff={b_a.mean() - b_b.mean():+.6f}  paired-t p={pval_b:.2e}")
    print(f"  LogLoss:  {model_a}={ll_a.mean():.5f} {model_b}={ll_b.mean():.5f}  "
          f"diff={ll_a.mean() - ll_b.mean():+.6f}  paired-t p={pval_l:.2e}")


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    models = {"LRMC_Classic": LRMC, "LRMC_xG": LRMC}
    configs = {
        "LRMC_Classic": dict(BASE_CONFIG, use_xg=False),
        "LRMC_xG": dict(BASE_CONFIG, use_xg=True, fallback_to_goals=True),
    }

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'lrmc_xg_backtest.csv', index=False)
    print("=== Split-averaged means, ALL 5 seasons (standard protocol) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean())

    print("\n=== Split-averaged means, xG-COVERED seasons only (2024-25, 2025-26) ===")
    covered = summary[summary['Season'].isin(XG_COVERED_SEASONS)]
    print(covered.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean())

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)

    paired_report(res, 'WeightedResult', 'LRMC_xG', 'LRMC_Classic', "ALL 5 seasons pooled")

    res_covered = res[res['Season'].isin(XG_COVERED_SEASONS)]
    paired_report(res_covered, 'WeightedResult', 'LRMC_xG', 'LRMC_Classic', "xG-covered seasons only")

    n_diff = int((res_covered['LRMC_xG'] != res_covered['LRMC_Classic']).sum())
    print(f"\nOf {len(res_covered)} test games in xG-covered seasons, LRMC_xG and LRMC_Classic "
          f"produced a DIFFERENT prediction on {n_diff} ({n_diff / len(res_covered):.1%}) -- "
          f"this is the actual fraction of games where xG could have changed anything.")


if __name__ == "__main__":
    main()
