"""
Keener's method and Glicko-2 vs. Massey (and ELO for Glicko-2, its closest
relative). Hyperparameter sweeps (epsilon for Keener, tau for Glicko-2)
followed by paired significance tests.

Run from the project root as a module:
    python -m analysis.exploratory.keener_glicko2_backtest

See reports/keener_and_glicko2_results.md for the results and interpretation.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.keener import Keener
from src.rankings.glicko2 import Glicko2
from src.rankings.massey import Massey
from src.rankings.elo import ELO
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
MASSEY_CFG = {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True}


def _paired_test(res, y, name_a, name_b):
    p_a, p_b = res[name_a].values, res[name_b].values
    b_a, b_b = (p_a - y) ** 2, (p_b - y) ** 2
    _, pval_b = stats.ttest_rel(b_a, b_b)
    mask = res['Result'] != 0.5
    yy = res.loc[mask, 'WeightedResult'].values
    pc_a = np.clip(p_a[mask], 1e-15, 1 - 1e-15)
    pc_b = np.clip(p_b[mask], 1e-15, 1 - 1e-15)
    ll_a = -(yy * np.log(pc_a) + (1 - yy) * np.log(1 - pc_a))
    ll_b = -(yy * np.log(pc_b) + (1 - yy) * np.log(1 - pc_b))
    _, pval_l = stats.ttest_rel(ll_a, ll_b)
    correct_a = np.round(pc_a) == np.round(yy)
    correct_b = np.round(pc_b) == np.round(yy)
    ab = np.sum(correct_a & ~correct_b)
    ba = np.sum(~correct_a & correct_b)
    mcnemar = (abs(ab - ba) - 1) ** 2 / (ab + ba) if (ab + ba) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)
    print(f"--- {name_a} vs {name_b} (n={len(res)}) ---")
    print(f"  Accuracy: {name_a}={correct_a.mean():.4f} {name_b}={correct_b.mean():.4f}  (McNemar p={p_mcnemar:.4f})")
    print(f"  Brier:    {name_a}={b_a.mean():.5f} {name_b}={b_b.mean():.5f}  p={pval_b:.2e}")
    print(f"  LogLoss:  {name_a}={ll_a.mean():.5f} {name_b}={ll_b.mean():.5f}  p={pval_l:.2e}")


def run_keener(history_df, out_dir):
    epsilons = [0.01, 0.02, 0.05, 0.1, 0.2, 0.3]
    models = {f"eps{e}": Keener for e in epsilons}
    models["Massey"] = Massey
    configs = {f"eps{e}": {'epsilon': e} for e in epsilons}
    configs["Massey"] = MASSEY_CFG
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    summary = pd.DataFrame(engine.results_summary)
    print("=== Keener epsilon sweep ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean()
          .reindex(['Massey'] + [f"eps{e}" for e in epsilons]))

    models2 = {"Keener": Keener, "Massey": Massey}
    configs2 = {"Keener": {'epsilon': 0.1}, "Massey": MASSEY_CFG}
    engine2 = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine2.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models2, model_configs=configs2)
    all_preds = pd.concat(engine2.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    print()
    _paired_test(res, res['WeightedResult'].values, 'Keener', 'Massey')


def run_glicko2(history_df, out_dir):
    taus = [0.2, 0.3, 0.5, 0.8, 1.0]
    models = {f"tau{t}": Glicko2 for t in taus}
    configs = {f"tau{t}": {'tau': t} for t in taus}
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    summary = pd.DataFrame(engine.results_summary)
    print("\n=== Glicko-2 tau sweep ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex([f"tau{t}" for t in taus]))

    models2 = {"Glicko2": Glicko2, "Massey": Massey, "ELO": ELO}
    configs2 = {"Glicko2": {}, "Massey": MASSEY_CFG, "ELO": {}}
    engine2 = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine2.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models2, model_configs=configs2)
    engine2.save_results()
    all_preds = pd.concat(engine2.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    y = res['WeightedResult'].values
    print()
    _paired_test(res, y, 'Glicko2', 'Massey')
    print()
    _paired_test(res, y, 'Glicko2', 'ELO')


def main():
    loader = DataLoader()
    history_df = loader.get_history()
    out_dir = Path('data/validation/backtest_results')

    run_keener(history_df, out_dir)
    run_glicko2(history_df, out_dir)


if __name__ == "__main__":
    main()
