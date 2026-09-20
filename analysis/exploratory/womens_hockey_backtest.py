"""
5-year/20-split backtest of the full 6-model roster (Massey, HockeyBT,
KRACH, ELO, RPI, NPI) on women's D-I hockey data — re-run, not ported, per
reports/womens_hockey_import.md's plan. Every hyperparameter here is the
men's-tuned default EXCEPT NPI, which uses config.yaml's npi_women block
(women's-specific dials, verified against the NCAA's own official document
-- see research/womens_comparison/reports/p0_3_npi_validation.md); this
script's job is to check whether those defaults still make sense on a
structurally different competitive landscape, not to assume they do.

IMPORTANT: every model instantiation must happen inside a
`using_di_team_path(...)` block — see src/rankings/base_ranker.py's
docstring for why the usual overlap-based safety check can't catch a
men's/women's mixup (most school names are shared between the two
divisions, so the "wrong naming convention" heuristic doesn't fire).

Run from the project root as a module:
    python -m analysis.exploratory.womens_hockey_backtest

See reports/womens_hockey_import.md for the split-averaged results and
interpretation, and research/womens_comparison/PLAN.md's P0.2 for why the
paired significance testing below was added (BacktestEngine already
collected per-game predictions in self.all_predictions; it just never
persisted or paired-tested them for women's data the way
analysis/exploratory/hockey_bt_backtest.py already does for men's).
NPI was added to this backtest 2026-09-20 (W2) now that P0.3 has validated
its women's-specific dials -- this is the FIRST time NPI has been included
in a women's-hockey accuracy/Brier/LogLoss backtest; every prior claim
about NPI on this project's public site was carried over from men's-only
evidence.
"""
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.base_ranker import using_di_team_path
from src.rankings.massey import Massey
from src.rankings.hockey_bt import HockeyBT
from src.rankings.krach import KRACH
from src.rankings.elo import ELO
from src.rankings.rpi import RPI
from src.validation.metrics import apply_ot_weighting

WOMENS_TEAM_INFO = Path('data/teams/team_info_women.csv')
SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
CUTOFFS = ['Jan1', 'Jan15', 'Feb1', 'Feb15']
BEST_MODEL = 'Massey'  # the incumbent-best on split-averaged means; every other model is paired-tested against it


def paired_tests(all_preds, best_model, other_models, ot_win_weight=0.6, ot_loss_weight=0.4):
    """
    Pools every held-out prediction across all 20 splits and runs the same
    paired t-test (Brier, LogLoss) / McNemar's test (accuracy) that
    analysis/exploratory/hockey_bt_backtest.py already runs for men's data,
    generalized to N models compared against one reference model instead of
    a single hardcoded pair. Returns a DataFrame, one row per comparison,
    for reproducibility (the men's script only ever printed this).
    """
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = all_preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = all_preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=ot_win_weight, ot_loss_weight=ot_loss_weight)
    y = res['WeightedResult'].values
    n = len(res)

    rows = []
    for model in other_models:
        p_best = res[best_model].values
        p_other = res[model].values
        b_best, b_other = (p_best - y) ** 2, (p_other - y) ** 2
        t_b, pval_b = stats.ttest_rel(b_best, b_other)

        mask = res['Result'] != 0.5
        yy = res.loc[mask, 'WeightedResult'].values
        pc_best = np.clip(p_best[mask], 1e-15, 1 - 1e-15)
        pc_other = np.clip(p_other[mask], 1e-15, 1 - 1e-15)
        ll_best = -(yy * np.log(pc_best) + (1 - yy) * np.log(1 - pc_best))
        ll_other = -(yy * np.log(pc_other) + (1 - yy) * np.log(1 - pc_other))
        t_l, pval_l = stats.ttest_rel(ll_best, ll_other)

        correct_best = np.round(pc_best) == np.round(yy)
        correct_other = np.round(pc_other) == np.round(yy)
        b01 = int(np.sum(correct_best & ~correct_other))
        b10 = int(np.sum(~correct_best & correct_other))
        mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0.0
        p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1)

        rows.append({
            'Model': model, 'N_paired': n, 'N_decisive': int(mask.sum()),
            f'{best_model}_Accuracy': round(float(correct_best.mean()), 4),
            f'{model}_Accuracy': round(float(correct_other.mean()), 4),
            'McNemar_b01': b01, 'McNemar_b10': b10, 'McNemar_p': round(float(p_mcnemar), 4),
            f'{best_model}_Brier': round(float(b_best.mean()), 5),
            f'{model}_Brier': round(float(b_other.mean()), 5),
            'Brier_diff': round(float(b_best.mean() - b_other.mean()), 6), 'Brier_ttest_p': pval_b,
            f'{best_model}_LogLoss': round(float(ll_best.mean()), 5),
            f'{model}_LogLoss': round(float(ll_other.mean()), 5),
            'LogLoss_diff': round(float(ll_best.mean() - ll_other.mean()), 6), 'LogLoss_ttest_p': pval_l,
        })

        print(f"\n--- {best_model} vs {model} (n={n} paired, {int(mask.sum())} decisive) ---")
        print(f"  Accuracy: {best_model}={correct_best.mean():.4f} {model}={correct_other.mean():.4f}  "
              f"({best_model}-right/{model}-wrong: {b01}, {best_model}-wrong/{model}-right: {b10}, "
              f"McNemar p={p_mcnemar:.4f})")
        print(f"  Brier:    {best_model}={b_best.mean():.5f} {model}={b_other.mean():.5f}  "
              f"diff={b_best.mean() - b_other.mean():+.6f}  paired-t p={pval_b:.2e}")
        print(f"  LogLoss:  {best_model}={ll_best.mean():.5f} {model}={ll_other.mean():.5f}  "
              f"diff={ll_best.mean() - ll_other.mean():+.6f}  paired-t p={pval_l:.2e}")

    return pd.DataFrame(rows)


def main():
    loader = DataLoader(data_dir='data/raw/women')
    history_df = loader.get_history()
    print(f"Women's D-I historical games loaded: {len(history_df)}")
    print(history_df['Season'].value_counts().sort_index())

    # NPI added 2026-09-20 (W2, research/womens_comparison/PLAN.md) now that
    # P0.3 has validated the women's-specific dials -- see config.yaml's
    # npi_women block and research/womens_comparison/reports/
    # p0_3_npi_validation.md. Without this config override NPI() would use
    # its constructor default (men's dials), silently reproducing the exact
    # bug P0.3 found and fixed.
    from src.rankings.npi import NPI
    from src.utils.config import load_config
    npi_women_config = load_config()['models']['npi_women']

    models = {"Massey": Massey, "HockeyBT": HockeyBT, "KRACH": KRACH, "ELO": ELO, "RPI": RPI, "NPI": NPI}
    configs = {
        "Massey": {'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': True},
        "HockeyBT": {'fit_home_ice': True, 'fit_ties': True, 'prior_strength': 0.4},
        "KRACH": {}, "ELO": {}, "RPI": {}, "NPI": npi_women_config,
    }

    out_dir = Path('data/validation/backtest_results')
    with using_di_team_path(WOMENS_TEAM_INFO):
        engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
        engine.run(seasons=SEASONS, cutoffs=CUTOFFS, model_factory=models, model_configs=configs)

    summary = pd.DataFrame(engine.results_summary)
    summary.to_csv(out_dir / 'womens_hockey_backtest.csv', index=False)
    print("\n=== Women's hockey: split-averaged means (men's-tuned defaults) ===")
    cols = ['Accuracy', 'Brier', 'LogLoss', 'ECE', 'Reliability', 'Resolution']
    print(summary.groupby('Model')[cols].mean().reindex(['Massey', 'HockeyBT', 'KRACH', 'ELO', 'RPI', 'NPI']))

    # P0.2: persist per-game predictions and run the same paired
    # significance tests the men's-hockey scripts already run.
    preds_df = engine.save_predictions()
    other_models = [m for m in models if m != BEST_MODEL]
    print(f"\n=== Pooled paired-comparison tests: {BEST_MODEL} vs. every other model ===")
    sig_df = paired_tests(preds_df, BEST_MODEL, other_models,
                           ot_win_weight=0.6, ot_loss_weight=0.4)
    sig_path = out_dir / 'womens_hockey_backtest_significance.csv'
    sig_df.to_csv(sig_path, index=False)
    print(f"\nSaved paired-significance results to {sig_path}")


if __name__ == "__main__":
    main()
