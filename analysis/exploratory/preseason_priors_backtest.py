"""
Validates src/rankings/priors.py (see the plan in reports/preseason_priors_results.md's
own header, and config.yaml's `preseason:` block) -- does seeding ELO's
starting ratings and pulling Massey's ridge target toward a carryover of
last season's rating actually help EARLY in a season, without hurting once
enough real games have accumulated?

This CANNOT reuse BacktestEngine.run() unmodified: a prior varies by test
SEASON (fit from that season's own s-1/s-2 history), not by config, so
model_factory's plain ModelClass(train_df, config=...) has no way to
receive it. This script mirrors BacktestEngine's train/test split logic
(reusing its _get_cutoff_date, same pattern as tests/massey_rest_backtest.py)
but pre-computes each season's prior once (priors don't depend on the
cutoff, only on the season and the full history) and passes it directly
into the model constructor.

Design (pre-registered before running, per this repo's convention -- see
reports/massey_experiments_2026.md for the same pattern):
  - Expect a LARGE gain at Oct/Nov cutoffs (little/no in-season data yet,
    so the prior is most of the signal) and roughly ZERO gain by Jan
    (~2-3 months of real games should dominate both models' ridge/carryover
    weighting on their own).
  - If the prior actively HURTS at Jan cutoffs, that's a signal
    prior_lambda/elo_carryover_weight are set too high and should be
    turned down.
  - Uses config.yaml's current preseason.* values as the single candidate
    to test (r1=0.6, r2=0.15, massey_prior_lambda=2.0,
    elo_carryover_weight=0.6) -- NOT a hyperparameter sweep. If this
    shows a genuine win, those values ship as-is; if not, this is a
    starting point for retuning, not a finished search.

Run from the project root as a module:
    python -m analysis.exploratory.preseason_priors_backtest
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.elo import ELO
from src.rankings.massey import Massey
from src.rankings.priors import build_prior
from src.utils.config import load_config
from src.validation.metrics import apply_ot_weighting, calculate_accuracy, calculate_brier, calculate_log_loss

# 20172018 is excluded: its own s-1 (20162017) is a missing season in the
# raw archive, so build_prior() returns {} for it entirely -- prior_on and
# prior_off would be IDENTICAL for that season, which would just dilute
# the paired comparison rather than test anything.
TUNE_SEASONS = [20122013, 20132014, 20142015, 20152016, 20182019, 20192020, 20202021]
HOLDOUT_SEASONS = [20212022, 20222023, 20232024, 20242025, 20252026]
ALL_SEASONS = TUNE_SEASONS + HOLDOUT_SEASONS

CUTOFFS = ['Oct15', 'Nov1', 'Nov15', 'Dec1', 'Jan1']
TEST_WINDOW_DAYS = 14  # score only the 14 days after each cutoff -- see backtest_engine.py's test_window_days

OUT_DIR = Path('data/validation/backtest_results')
REPORT_PATH = Path('reports/preseason_priors_results.md')


def main():
    loader = DataLoader()
    history_df = loader.get_history()
    config = load_config()

    engine = BacktestEngine(history_df, OUT_DIR)  # only used for _get_cutoff_date

    # Priors don't depend on the cutoff, only on the season -- compute each
    # season's prior ONCE, up front, from full history (never truncated to
    # a cutoff date; s-1/s-2 are always fully-completed prior seasons, so
    # there's no leakage from doing this outside the per-cutoff loop).
    print("Building priors for each test season...")
    season_priors = {}
    for season in ALL_SEASONS:
        season_priors[season] = {
            "ELO": build_prior(history_df, season, "ELO", config)[0],
            "Massey": build_prior(history_df, season, "Massey", config)[0],
        }
        n_elo, n_massey = len(season_priors[season]["ELO"]), len(season_priors[season]["Massey"])
        print(f"  {season}: ELO prior for {n_elo} teams, Massey prior for {n_massey} teams")

    elo_conf = config['models'].get('elo', {})
    massey_conf = config['models'].get('massey', {})

    all_preds = []
    for season in ALL_SEASONS:
        season_df = history_df[history_df['Season'] == season].copy()
        if season_df.empty:
            continue
        for cutoff_name in CUTOFFS:
            cutoff_date = engine._get_cutoff_date(season, cutoff_name)
            train_df = season_df[season_df['Date'] < cutoff_date].copy()
            test_df = season_df[(season_df['Date'] >= cutoff_date) &
                                 (season_df['Date'] < cutoff_date + pd.Timedelta(days=TEST_WINDOW_DAYS))].copy()
            if train_df.empty or test_df.empty:
                continue

            elo_prior = season_priors[season]["ELO"]
            massey_prior = season_priors[season]["Massey"]

            models = {
                "ELO_off": ELO(train_df, config=elo_conf, prior=None),
                "ELO_on": ELO(train_df, config=elo_conf, prior=elo_prior),
                "Massey_off": Massey(train_df, config=massey_conf, prior=None),
                "Massey_on": Massey(train_df, config={**massey_conf, 'prior_lambda':
                                    config['models']['preseason'].get('massey_prior_lambda', 2.0)},
                                    prior=massey_prior),
            }
            for arm_name, model in models.items():
                model.fit()
                preds = []
                for _, row in test_df.iterrows():
                    prob = model.predict(row['HomeTeam'], row['AwayTeam'], row['NeutralSite'])
                    preds.append({
                        'Season': season, 'Cutoff': cutoff_name, 'Date': row['Date'],
                        'HomeTeam': row['HomeTeam'], 'AwayTeam': row['AwayTeam'],
                        'Result': row['Result'], 'IsOT': row.get('IsOT', False),
                        'HomeWinProb': prob, 'Arm': arm_name, 'TrainGames': len(train_df),
                    })
                all_preds.append(pd.DataFrame(preds))

    preds_df = pd.concat(all_preds, ignore_index=True)
    preds_df['WeightedResult'] = apply_ot_weighting(preds_df, ot_win_weight=0.6, ot_loss_weight=0.4)
    preds_df['Model'] = preds_df['Arm'].str.split('_').str[0]
    preds_df['PriorOn'] = preds_df['Arm'].str.endswith('_on')
    preds_df['SeasonSet'] = np.where(preds_df['Season'].isin(TUNE_SEASONS), 'tune', 'holdout')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preds_df.to_csv(OUT_DIR / 'preseason_priors_predictions.csv', index=False)

    report_lines = []
    report_lines.append("# Preseason priors: backtest results\n")
    report_lines.append(
        "Validates src/rankings/priors.py's carryover-based preseason prior for ELO and Massey "
        "(config.yaml's `preseason:` block) — see src/rankings/priors.py and tests/preseason_priors_backtest.py "
        "for how this was generated. Pre-registered expectation: a large gain at Oct/Nov cutoffs, "
        "shrinking toward zero by January, and NOT a regression at any cutoff.\n"
    )
    report_lines.append(
        f"Seasons: tune={TUNE_SEASONS}, holdout={HOLDOUT_SEASONS} (20172018 excluded — its own "
        "s-1 season, 20162017, is missing from the archive, so no prior could be built for it). "
        f"Cutoffs: {CUTOFFS}, each scored on the {TEST_WINDOW_DAYS} days immediately following "
        "(not the rest of the season — see backtest_engine.py's `test_window_days`).\n"
    )

    def summarize(df, season_set_label):
        report_lines.append(f"\n## {season_set_label.capitalize()} seasons\n")
        for model in ["ELO", "Massey"]:
            report_lines.append(f"\n### {model}\n")
            report_lines.append("| Cutoff | N games | Acc (off→on) | Brier (off→on) | LogLoss (off→on) | Brier p | LogLoss p | McNemar p |")
            report_lines.append("|---|---|---|---|---|---|---|---|")
            sub = df[df['Model'] == model]
            for cutoff in CUTOFFS:
                c = sub[sub['Cutoff'] == cutoff]
                off = c[~c['PriorOn']].set_index(['Season', 'Date', 'HomeTeam', 'AwayTeam'])
                on = c[c['PriorOn']].set_index(['Season', 'Date', 'HomeTeam', 'AwayTeam'])
                joined = off[['HomeWinProb', 'WeightedResult']].join(
                    on[['HomeWinProb']], lsuffix='_off', rsuffix='_on', how='inner')
                if joined.empty:
                    report_lines.append(f"| {cutoff} | 0 | n/a | n/a | n/a | n/a | n/a | n/a |")
                    continue
                y = joined['WeightedResult'].values
                p_off, p_on = joined['HomeWinProb_off'].values, joined['HomeWinProb_on'].values
                acc_off = calculate_accuracy(pd.DataFrame({'HomeWinProb': p_off, 'WeightedResult': y}), target_col='WeightedResult')
                acc_on = calculate_accuracy(pd.DataFrame({'HomeWinProb': p_on, 'WeightedResult': y}), target_col='WeightedResult')
                b_off_arr, b_on_arr = (p_off - y) ** 2, (p_on - y) ** 2
                brier_off, brier_on = b_off_arr.mean(), b_on_arr.mean()
                _, pval_b = stats.ttest_rel(b_on_arr, b_off_arr) if len(joined) > 1 else (None, np.nan)

                mask = y != 0.5
                yy = y[mask]
                pc_off = np.clip(p_off[mask], 1e-15, 1 - 1e-15)
                pc_on = np.clip(p_on[mask], 1e-15, 1 - 1e-15)
                ll_off_arr = -(yy * np.log(pc_off) + (1 - yy) * np.log(1 - pc_off))
                ll_on_arr = -(yy * np.log(pc_on) + (1 - yy) * np.log(1 - pc_on))
                ll_off, ll_on = ll_off_arr.mean(), ll_on_arr.mean()
                _, pval_l = stats.ttest_rel(ll_on_arr, ll_off_arr) if mask.sum() > 1 else (None, np.nan)

                correct_off = np.round(pc_off) == np.round(yy)
                correct_on = np.round(pc_on) == np.round(yy)
                b01, b10 = np.sum(correct_on & ~correct_off), np.sum(~correct_on & correct_off)
                mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
                p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1) if (b01 + b10) > 0 else np.nan

                report_lines.append(
                    f"| {cutoff} | {len(joined)} | {acc_off:.3f}→{acc_on:.3f} | "
                    f"{brier_off:.4f}→{brier_on:.4f} | {ll_off:.4f}→{ll_on:.4f} | "
                    f"{pval_b:.3g} | {pval_l:.3g} | {p_mcnemar:.3g} |"
                )

    summarize(preds_df[preds_df['SeasonSet'] == 'tune'], 'tune')
    summarize(preds_df[preds_df['SeasonSet'] == 'holdout'], 'holdout')

    report_lines.append(
        "\n\n*Brier/LogLoss columns show off→on (lower is better); a negative diff (on < off) is a win "
        "for the prior. p-values are paired t-tests (Brier/LogLoss) or McNemar's test (accuracy), "
        "same tests used throughout this project's other backtest reports.*\n"
    )
    report_lines.append(
        "\n**Status:** these numbers are what actually ran against the current "
        "`config.yaml` preseason.* values — see the top of this file for how they were produced, "
        "and treat any 'holdout' row as the honest read (the 'tune' rows are not disjoint validation)."
    )

    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
