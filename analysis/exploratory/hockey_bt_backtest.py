"""
Definitive HockeyBT vs. KRACH vs. NPI comparison: runs the 5-year/20-split
backtest (via BacktestEngine, so history is leak-free per-cutoff) and then
does a PAIRED per-game significance test on the pooled predictions, not just
split-averaged means — split-averaged and pooled views can disagree (see
reports/lrmc_empty_net.md's ENG ablation for a concrete case where they did).

Run from the project root as a module:
    python -m analysis.exploratory.hockey_bt_backtest

See reports/hockey_bt_results.md for the results and interpretation.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.krach import KRACH
from src.rankings.npi import NPI
from src.rankings.hockey_bt import HockeyBT
from src.validation.metrics import apply_ot_weighting


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    models = {"KRACH": KRACH, "NPI": NPI, "HockeyBT": HockeyBT}
    configs = {
        "HockeyBT": {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4},
        "NPI": {}, "KRACH": {},
    }

    seasons = [20212022, 20222023, 20232024, 20242025, 20252026]
    cutoffs = ['Jan1', 'Jan15', 'Feb1', 'Feb15']

    out_dir = Path('data/validation/backtest_results')
    engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
    engine.run(seasons=seasons, cutoffs=cutoffs, model_factory=models, model_configs=configs)
    engine.save_results()

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'hockey_bt_backtest.csv', index=False)
    print("\n=== Split-averaged means (20 splits) ===")
    print(summary.groupby('Model')[['Accuracy', 'Brier', 'LogLoss']].mean().reindex(['KRACH', 'NPI', 'HockeyBT']))

    # Pool ALL per-game predictions across every split for paired testing
    all_preds = pd.concat(engine.all_predictions, ignore_index=True)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    y = res['WeightedResult'].values
    n = len(res)
    print(f"\n=== Pooled paired-comparison games: {n} ===")

    for model in ['KRACH', 'NPI']:
        p_bt = res['HockeyBT'].values
        p_other = res[model].values
        b_bt, b_other = (p_bt - y) ** 2, (p_other - y) ** 2
        t_b, pval_b = stats.ttest_rel(b_bt, b_other)

        mask = res['Result'] != 0.5
        yy = res.loc[mask, 'WeightedResult'].values
        pc_bt = np.clip(p_bt[mask], 1e-15, 1 - 1e-15)
        pc_other = np.clip(p_other[mask], 1e-15, 1 - 1e-15)
        ll_bt = -(yy * np.log(pc_bt) + (1 - yy) * np.log(1 - pc_bt))
        ll_other = -(yy * np.log(pc_other) + (1 - yy) * np.log(1 - pc_other))
        t_l, pval_l = stats.ttest_rel(ll_bt, ll_other)

        correct_bt = np.round(pc_bt) == np.round(yy)
        correct_other = np.round(pc_other) == np.round(yy)
        b01 = np.sum(correct_bt & ~correct_other)
        b10 = np.sum(~correct_bt & correct_other)
        mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
        p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

        print(f"\n--- HockeyBT vs {model} (n={n}) ---")
        print(f"  Accuracy: BT={correct_bt.mean():.4f} {model}={correct_other.mean():.4f}  "
              f"(BT-right/other-wrong: {b01}, BT-wrong/other-right: {b10}, McNemar p={p_mcnemar:.4f})")
        print(f"  Brier:    BT={b_bt.mean():.5f} {model}={b_other.mean():.5f}  "
              f"diff={b_bt.mean() - b_other.mean():+.6f}  paired-t p={pval_b:.2e}")
        print(f"  LogLoss:  BT={ll_bt.mean():.5f} {model}={ll_other.mean():.5f}  "
              f"diff={ll_bt.mean() - ll_other.mean():+.6f}  paired-t p={pval_l:.2e}")


if __name__ == "__main__":
    main()
