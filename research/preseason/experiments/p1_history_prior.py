# research/preseason/experiments/p1_history_prior.py
"""
PLAN.md P1: sweep the history-only prior for ELO and Massey (Arm A: the
existing prior-CONSTRUCTION shape, r1=0.6/r2=0.15, held fixed at
production's validated values -- only the per-model APPLICATION strength
is swept: Massey's prior_lambda, ELO's carryover/prior_weight), and compare
against a 538-style continuous Elo that never resets between seasons
(Arm B: research/preseason/models/continuous_elo.py).

PRE-REGISTRATION (written before this script's first run, left unedited
after):
  - Expect Arm A's swept strength to land STRONGER than production's
    current values (massey_prior_lambda=2.0, elo_carryover_weight=0.6),
    because reports/preseason_priors_results.md found the current prior
    still helping at Jan1 on holdout -- a prior that's still helping
    that late is a sign it was under-weighted, not over-weighted.
  - Expect Arm B (continuous Elo) to be AT LEAST competitive with Arm A's
    refit-blend at early cutoffs (Oct/Nov), since it's a more direct
    implementation of the same "long-run program strength" idea 538 uses,
    with no manual r1/r2/lambda blend needed.
  - Ship gate: whichever arm wins per model must beat "no prior" and
    production's current values on HOLDOUT Brier/LogLoss at every cutoff,
    with no reversal, before being proposed for promotion to production.

Scope narrowed for this pass (documented, not silent): r1/r2 (the prior's
CONSTRUCTION) are held at production's values, not swept -- only each
model's APPLICATION strength is. Feb1/Mar1 fade-point cutoffs and Massey
fade-schedule variants (originally sketched in PLAN.md) are deferred to a
follow-up if this pass's results warrant it.

Run from the project root (takes several minutes -- ~2000 model fits):
    python -m research.preseason.experiments.p1_history_prior
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtesting.backtest_engine import BacktestEngine  # noqa: E402
from src.rankings.elo import ELO  # noqa: E402
from src.rankings.massey import Massey  # noqa: E402
from src.utils.config import load_config  # noqa: E402

from research.preseason.harness.paths import research_path  # noqa: E402
from research.preseason.harness.eval import weighted_result, paired_comparison, holm_correct  # noqa: E402
from research.preseason.models.priors_research import build_prior_research  # noqa: E402
from research.preseason.models.continuous_elo import ContinuousElo  # noqa: E402

EXPERIMENT = "p1_history_prior"
CUTOFFS = ['Oct1', 'Oct15', 'Nov1', 'Nov15', 'Dec1', 'Jan1']
TEST_WINDOW_DAYS = 14

MASSEY_LAMBDAS = [1, 2, 4, 8, 16]
ELO_WEIGHTS = [0.3, 0.5, 0.7, 0.9, 1.0]
CONTINUOUS_ELO_GRID = [(rev, k) for rev in (0.15, 0.25, 0.33, 0.5) for k in (15, 20, 30)]

R1, R2 = 0.6, 0.15  # prior construction, held fixed at production's validated values


def load_archive():
    path = PROJECT_ROOT / "research" / "preseason" / "data" / "extended_archive.csv"
    df = pd.read_csv(path)
    df['Date'] = pd.to_datetime(df['Date'])
    return df


def season_splits(all_seasons):
    all_seasons = sorted(all_seasons)
    holdout = [s for s in all_seasons if s >= 20212022]
    tune = [s for s in all_seasons if s not in holdout]
    return tune, holdout


def precompute_history_priors(history_df, seasons, models_config):
    """{season: {'ELO': prior_dict, 'Massey': prior_dict}} -- built ONCE per
    (season, model) since r1/r2 are fixed across the whole strength sweep."""
    out = {}
    for season in seasons:
        out[season] = {}
        for model_key in ("ELO", "Massey"):
            prior, meta = build_prior_research(history_df, season, model_key, models_config, r1=R1, r2=R2)
            out[season][model_key] = prior
        print(f"  priors built for {season}: "
              f"ELO={len(out[season]['ELO'])} teams, Massey={len(out[season]['Massey'])} teams")
    return out


def precompute_continuous_elo(history_df, cutoff_dates):
    """{(rev, k): {cutoff_date: {team: rating}}} -- one chronological pass
    per (reversion_frac, k) combo across ALL cutoffs at once."""
    out = {}
    for rev, k in CONTINUOUS_ELO_GRID:
        model = ContinuousElo(config={'reversion_frac': rev, 'k_factor': k})
        out[(rev, k)] = model.snapshots_at_cutoffs(history_df, cutoff_dates)
        print(f"  continuous Elo snapshots built for reversion_frac={rev}, k={k}")
    return out


def main():
    print("Loading extended archive...")
    history_df = load_archive()
    all_seasons = history_df['Season'].unique().tolist()
    tune_seasons, holdout_seasons = season_splits(all_seasons)
    print(f"Tune seasons ({len(tune_seasons)}): {sorted(tune_seasons)}")
    print(f"Holdout seasons ({len(holdout_seasons)}): {sorted(holdout_seasons)}")

    config = load_config()
    models_config = config['models']
    elo_base_conf = models_config.get('elo', {})
    massey_base_conf = models_config.get('massey', {})

    engine = BacktestEngine(history_df, research_path("results", EXPERIMENT, "_scratch.csv").parent)

    print("\nBuilding history priors (one build per season, reused across the whole strength sweep)...")
    priors_by_season = precompute_history_priors(history_df, tune_seasons + holdout_seasons, models_config)

    print("\nResolving cutoff dates and running continuous-Elo pre-pass...")
    cutoff_date_map = {}  # (season, cutoff_name) -> Timestamp
    for season in tune_seasons + holdout_seasons:
        for cutoff_name in CUTOFFS:
            cutoff_date_map[(season, cutoff_name)] = engine._get_cutoff_date(season, cutoff_name)
    all_cutoff_dates = sorted(set(cutoff_date_map.values()))
    continuous_elo_snapshots = precompute_continuous_elo(history_df, all_cutoff_dates)
    continuous_elo_model = ContinuousElo()  # only used for predict_from_ratings (stateless)

    def massey_arms(prior):
        arms = {'Massey_none': dict(massey_base_conf, prior_lambda=0.0)}
        arms['Massey_prodprior'] = dict(massey_base_conf, prior_lambda=2.0)
        for lam in MASSEY_LAMBDAS:
            arms[f'Massey_lambda{lam}'] = dict(massey_base_conf, prior_lambda=float(lam))
        return arms

    def elo_arms():
        arms = {'ELO_none': dict(elo_base_conf, prior_weight=0.0)}
        arms['ELO_prodprior'] = dict(elo_base_conf, prior_weight=0.6)
        for w in ELO_WEIGHTS:
            arms[f'ELO_weight{w}'] = dict(elo_base_conf, prior_weight=w)
        return arms

    print("\nRunning main sweep (this is the slow part)...")
    all_preds = []
    for season in tune_seasons + holdout_seasons:
        season_df = history_df[history_df['Season'] == season].copy()
        if season_df.empty:
            continue
        massey_prior = priors_by_season[season]['Massey']
        elo_prior = priors_by_season[season]['ELO']

        for cutoff_name in CUTOFFS:
            cutoff_date = cutoff_date_map[(season, cutoff_name)]
            train_df = season_df[season_df['Date'] < cutoff_date].copy()
            test_df = season_df[(season_df['Date'] >= cutoff_date) &
                                 (season_df['Date'] < cutoff_date + pd.Timedelta(days=TEST_WINDOW_DAYS))].copy()
            if train_df.empty or test_df.empty:
                continue

            arm_predictions = {}

            for arm_name, conf in massey_arms(massey_prior).items():
                model = Massey(train_df, config=conf, prior=massey_prior if conf.get('prior_lambda', 0) > 0 else None)
                model.fit()
                arm_predictions[arm_name] = [model.predict(r['HomeTeam'], r['AwayTeam'], r['NeutralSite'])
                                              for _, r in test_df.iterrows()]

            for arm_name, conf in elo_arms().items():
                model = ELO(train_df, config=conf, prior=elo_prior if conf.get('prior_weight', 0) > 0 else None)
                model.fit()
                arm_predictions[arm_name] = [model.predict(r['HomeTeam'], r['AwayTeam'], r['NeutralSite'])
                                              for _, r in test_df.iterrows()]

            for (rev, k), snaps in continuous_elo_snapshots.items():
                ratings = snaps.get(cutoff_date, {})
                arm_name = f'ContinuousElo_rev{rev}_k{k}'
                arm_predictions[arm_name] = [continuous_elo_model.predict_from_ratings(ratings, r['HomeTeam'], r['AwayTeam'], r['NeutralSite'])
                                              for _, r in test_df.iterrows()]

            base_cols = test_df[['Date', 'HomeTeam', 'AwayTeam', 'Result', 'IsOT']].reset_index(drop=True)
            for arm_name, preds in arm_predictions.items():
                d = base_cols.copy()
                d['Season'] = season
                d['Cutoff'] = cutoff_name
                d['Arm'] = arm_name
                d['HomeWinProb'] = preds
                all_preds.append(d)

        print(f"  {season}: done")

    preds_df = pd.concat(all_preds, ignore_index=True)
    preds_df['WeightedResult'] = weighted_result(preds_df)
    preds_df['SeasonSet'] = np.where(preds_df['Season'].isin(tune_seasons), 'tune', 'holdout')

    out_path = research_path("results", EXPERIMENT, "predictions.csv")
    preds_df.to_csv(out_path, index=False)
    print(f"\nSaved {len(preds_df)} predictions to {out_path}")

    write_report(preds_df, tune_seasons, holdout_seasons)


def _select_best_arm(preds_df, model_prefix, exclude_suffixes, tune_seasons):
    """Picks the arm (within one model family) with the lowest mean Brier
    on tune seasons, excluding baseline arms from the "best" selection."""
    tune = preds_df[(preds_df['Season'].isin(tune_seasons)) & (preds_df['Arm'].str.startswith(model_prefix))]
    tune = tune[~tune['Arm'].isin(exclude_suffixes)]
    tune = tune.copy()
    tune['sq_err'] = (tune['HomeWinProb'] - tune['WeightedResult']) ** 2
    means = tune.groupby('Arm')['sq_err'].mean().sort_values()
    return means.index[0], means


def write_report(preds_df, tune_seasons, holdout_seasons):
    report = []
    report.append("# P1: history-only priors (538 continuous Elo vs. refit-blend strength sweep)\n")
    report.append(
        "See this experiment's module docstring (`research/preseason/experiments/p1_history_prior.py`) "
        "for the full pre-registration. Summary: r1/r2 (prior construction) held at production's "
        "validated 0.6/0.15; swept each model's APPLICATION strength (Massey prior_lambda, ELO "
        "prior_weight), and compared against a 538-style continuous Elo that never resets between "
        f"seasons. Tune seasons ({len(tune_seasons)}): {sorted(tune_seasons)}. "
        f"Holdout seasons ({len(holdout_seasons)}): {sorted(holdout_seasons)} (unchanged from "
        "reports/preseason_priors_results.md).\n"
    )

    massey_best, massey_tune_means = _select_best_arm(
        preds_df, 'Massey_', {'Massey_none', 'Massey_prodprior'}, tune_seasons)
    elo_best, elo_tune_means = _select_best_arm(
        preds_df, 'ELO_', {'ELO_none', 'ELO_prodprior'}, tune_seasons)
    continuous_best, continuous_tune_means = _select_best_arm(
        preds_df, 'ContinuousElo_', set(), tune_seasons)

    report.append(f"**Selected on tune seasons (lowest mean Brier):** Massey -> `{massey_best}`, "
                  f"ELO -> `{elo_best}`, continuous Elo -> `{continuous_best}`.\n")
    report.append("Full tune-season Brier by arm:\n")
    report.append("```\nMassey:\n" + massey_tune_means.to_string() +
                  "\n\nELO:\n" + elo_tune_means.to_string() +
                  "\n\nContinuous Elo:\n" + continuous_tune_means.to_string() + "\n```\n")

    def holdout_table(model_label, baseline_arm, candidate_arms):
        report.append(f"\n## {model_label}: holdout comparison vs. `{baseline_arm}`\n")
        report.append("| Candidate | Cutoff | N | Acc (base->cand) | Brier (base->cand) | LogLoss (base->cand) | Brier p | LogLoss p | McNemar p |")
        report.append("|---|---|---|---|---|---|---|---|---|")
        pvals = []
        rows = []
        for cand in candidate_arms:
            for cutoff in CUTOFFS:
                base = preds_df[(preds_df['SeasonSet'] == 'holdout') & (preds_df['Arm'] == baseline_arm) & (preds_df['Cutoff'] == cutoff)]
                cand_df = preds_df[(preds_df['SeasonSet'] == 'holdout') & (preds_df['Arm'] == cand) & (preds_df['Cutoff'] == cutoff)]
                key = ['Season', 'Date', 'HomeTeam', 'AwayTeam']
                joined = base.set_index(key)[['HomeWinProb', 'WeightedResult']].join(
                    cand_df.set_index(key)[['HomeWinProb']], lsuffix='_base', rsuffix='_cand', how='inner')
                if joined.empty:
                    continue
                res = paired_comparison(joined['HomeWinProb_base'].values, joined['HomeWinProb_cand'].values,
                                         joined['WeightedResult'].values)
                rows.append((cand, cutoff, res))
                pvals.append(res['p_brier'])

        adj_pvals = holm_correct(pvals)
        for (cand, cutoff, res), p_adj in zip(rows, adj_pvals):
            report.append(
                f"| {cand} | {cutoff} | {res['n']} | {res['acc_off']:.3f}->{res['acc_on']:.3f} | "
                f"{res['brier_off']:.4f}->{res['brier_on']:.4f} | {res['logloss_off']:.4f}->{res['logloss_on']:.4f} | "
                f"{res['p_brier']:.3g} (Holm {p_adj:.3g}) | {res['p_logloss']:.3g} | {res['p_mcnemar']:.3g} |"
            )

    holdout_table("Massey", "Massey_none", ["Massey_prodprior", massey_best])
    holdout_table("ELO", "ELO_none", ["ELO_prodprior", elo_best])
    holdout_table("ELO vs. continuous Elo", "ELO_prodprior", [continuous_best])

    report.append(
        "\n\n*Brier/LogLoss columns show baseline->candidate (lower is better). Holm-adjusted p-value "
        "shown alongside the raw Brier p-value, corrected across every row in each table.*"
    )
    report.append(
        "\n\n**Status:** pre-registration and gate are at the top of this file's generating script "
        "(`research/preseason/experiments/p1_history_prior.py`). This report only presents what ran; "
        "the ship/no-ship call against that gate is left to a human reading the holdout tables above, "
        "not made automatically here."
    )

    out_path = research_path("reports", f"{EXPERIMENT}.md")
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
