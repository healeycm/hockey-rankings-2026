"""
Ensembling Massey/HockeyBT/KRACH/ELO/RPI: error-correlation diagnostic,
the ridge/standardization sweep that surfaced two real bugs during
development, and the final paired significance test.

Run from the project root as a module:
    python -m analysis.exploratory.ensemble_backtest

See reports/ensemble_results.md for the results and interpretation.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.ensemble import Ensemble
from src.rankings.massey import Massey
from src.rankings.hockey_bt import HockeyBT
from src.rankings.krach import KRACH
from src.rankings.elo import ELO
from src.rankings.rpi import RPI
from src.validation.metrics import apply_ot_weighting

SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
BASE_CONFIGS = {
    "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
    "HockeyBT": {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4},
    "KRACH": {}, "ELO": {}, "RPI": {},
}


def run_correlation_check(history_df, out_dir):
    models = {"Massey": Massey, "HockeyBT": HockeyBT, "KRACH": KRACH, "ELO": ELO, "RPI": RPI}
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=BASE_CONFIGS)

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    res.to_csv(out_dir / 'ensemble_base_predictions.csv', index=False)

    y = res['WeightedResult'].values
    names = list(BASE_CONFIGS.keys())
    print("=== Error correlation (pred - actual), pre-registration check ===")
    errors = pd.DataFrame({m: res[m].values - y for m in names})
    print(errors.corr().round(4))


def run_backtest(history_df, out_dir):
    models = {"Ensemble_avg": Ensemble, "Ensemble_stacked": Ensemble, "Massey": Massey}
    configs = {
        "Ensemble_avg": {'method': 'average', 'base_models': list(BASE_CONFIGS.keys())},
        "Ensemble_stacked": {'method': 'stacked', 'base_models': list(BASE_CONFIGS.keys())},
        "Massey": BASE_CONFIGS["Massey"],
    }
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)
    engine.save_results()

    summary = pd.DataFrame(engine.results_summary)
    print("\n=== Split-averaged means (20 splits) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean()
          .reindex(['Massey', 'Ensemble_avg', 'Ensemble_stacked']))

    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    y = res['WeightedResult'].values
    n = len(res)
    print(f"\n=== Pooled paired test: Ensemble_avg vs Massey (n={n}) ===")

    p_e, p_m = res['Ensemble_avg'].values, res['Massey'].values
    b_e, b_m = (p_e - y) ** 2, (p_m - y) ** 2
    _, pval_b = stats.ttest_rel(b_e, b_m)
    mask = res['Result'] != 0.5
    yy = res.loc[mask, 'WeightedResult'].values
    pc_e = np.clip(p_e[mask], 1e-15, 1 - 1e-15)
    pc_m = np.clip(p_m[mask], 1e-15, 1 - 1e-15)
    ll_e = -(yy * np.log(pc_e) + (1 - yy) * np.log(1 - pc_e))
    ll_m = -(yy * np.log(pc_m) + (1 - yy) * np.log(1 - pc_m))
    _, pval_l = stats.ttest_rel(ll_e, ll_m)
    correct_e = np.round(pc_e) == np.round(yy)
    correct_m = np.round(pc_m) == np.round(yy)
    b01 = np.sum(correct_e & ~correct_m)
    b10 = np.sum(~correct_e & correct_m)
    mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)
    print(f"Accuracy: Ens={correct_e.mean():.4f} Massey={correct_m.mean():.4f}  (McNemar p={p_mcnemar:.4f})")
    print(f"Brier:    Ens={b_e.mean():.5f} Massey={b_m.mean():.5f}  diff={b_e.mean() - b_m.mean():+.6f}  p={pval_b:.4f}")
    print(f"LogLoss:  Ens={ll_e.mean():.5f} Massey={ll_m.mean():.5f}  diff={ll_e.mean() - ll_m.mean():+.6f}  p={pval_l:.4f}")


def main():
    loader = DataLoader()
    history_df = loader.get_history()
    out_dir = Path('data/validation/backtest_results')

    run_correlation_check(history_df, out_dir)
    run_backtest(history_df, out_dir)


if __name__ == "__main__":
    main()
