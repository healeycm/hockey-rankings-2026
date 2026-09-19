# research/preseason/experiments/p1b_continuous_elo_power.py
"""
Follow-up to P1 (research/preseason/reports/p1_history_prior.md), addressing
its two open items:

  1. That report only compared continuous Elo against `ELO_prodprior` (one
     hop removed). This adds a DIRECT comparison against `ELO_none` (no
     prior at all) -- the more fundamental question: does letting Elo run
     continuously across seasons, with offseason reversion, beat starting
     fresh every season with no prior whatsoever?
  2. That report's significance tests paired individual GAMES, which
     treats games within the same season as independent observations when
     they aren't (they share the same two models' ratings, the same
     season-specific noise). This adds a season-level paired bootstrap:
     the unit of observation is one (model, season, cutoff) mean Brier/
     LogLoss, resampled with replacement across seasons. This is a more
     honest (if necessarily wider) uncertainty estimate than the per-game
     test, not a way to manufacture significance.

Reuses predictions already computed by p1_history_prior.py (no new model
fitting) -- pure re-analysis of research/preseason/results/p1_history_prior/
predictions.csv.

PRE-REGISTRATION: P1 found continuous Elo (`rev0.33_k20`, the tune-selected
config) beat `ELO_prodprior` at 5/5 holdout cutoffs with no reversal, but
none of those held up under Holm correction on a per-game basis. Expect:
(a) the direct comparison against `ELO_none` to show an even larger, more
likely significant gap, since `ELO_none` is the weaker baseline; (b) the
season-level bootstrap to produce WIDER intervals than the per-game test
implied (that's the point -- it's not a bug in this follow-up if the
per-game test's apparent significance doesn't survive), especially on only
5 holdout seasons. A season-level result that's still directionally
consistent and has most of its bootstrap mass on one side, even without
holdout significance, is the most honest signal available given how few
truly-held-out seasons exist (5) -- that is a hard limit of the data, not
something a better test can fix.

Run from the project root:
    python -m research.preseason.experiments.p1b_continuous_elo_power
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from research.preseason.harness.paths import research_path  # noqa: E402

EXPERIMENT = "p1b_continuous_elo_power"
BEST_CONTINUOUS_ARM = "ContinuousElo_rev0.33_k20"
CUTOFFS = ['Oct1', 'Oct15', 'Nov1', 'Nov15', 'Dec1', 'Jan1']
N_BOOTSTRAP = 10000
RNG_SEED = 20260913


def load_predictions():
    path = research_path("results", "p1_history_prior", "predictions.csv", mkdir_parent=False)
    df = pd.read_csv(path)
    return df


def per_season_means(preds_df, arm, season_set, cutoff):
    sub = preds_df[(preds_df['Arm'] == arm) & (preds_df['SeasonSet'] == season_set) & (preds_df['Cutoff'] == cutoff)].copy()
    sub['sq_err'] = (sub['HomeWinProb'] - sub['WeightedResult']) ** 2
    y = sub['WeightedResult'].values
    p = np.clip(sub['HomeWinProb'].values, 1e-15, 1 - 1e-15)
    mask = y != 0.5
    sub.loc[mask, 'log_loss'] = -(y[mask] * np.log(p[mask]) + (1 - y[mask]) * np.log(1 - p[mask]))
    return sub.groupby('Season').agg(brier=('sq_err', 'mean'), logloss=('log_loss', 'mean'), n=('sq_err', 'size'))


def season_level_bootstrap(base_means, cand_means, rng):
    """Both inputs: pd.Series indexed by Season (brier or logloss, one
    metric at a time), aligned to the SAME seasons. Returns
    (mean_diff, ci_low, ci_high, p_two_sided) for cand - base (negative =
    candidate is better)."""
    common = base_means.index.intersection(cand_means.index)
    diffs = (cand_means.loc[common] - base_means.loc[common]).values
    n = len(diffs)
    if n < 2:
        return np.nan, np.nan, np.nan, np.nan, n

    observed_mean = diffs.mean()
    boot_means = np.array([rng.choice(diffs, size=n, replace=True).mean() for _ in range(N_BOOTSTRAP)])
    ci_low, ci_high = np.percentile(boot_means, [2.5, 97.5])
    # Two-sided bootstrap p-value: fraction of resamples on the opposite
    # side of zero from the observed direction, doubled.
    if observed_mean <= 0:
        p = 2 * (boot_means > 0).mean()
    else:
        p = 2 * (boot_means < 0).mean()
    p = min(p, 1.0)
    return observed_mean, ci_low, ci_high, p, n


def main():
    preds_df = load_predictions()
    rng = np.random.default_rng(RNG_SEED)

    comparisons = [
        ("ELO_none", "no prior at all"),
        ("ELO_prodprior", "today's shipped prior (r1=0.6/r2=0.15, weight=0.6)"),
    ]

    report = []
    report.append("# P1b: continuous Elo vs. no-prior, with season-level power\n")
    report.append(
        "Follow-up to `research/preseason/reports/p1_history_prior.md` -- see this script's "
        "docstring for the full pre-registration. Re-analyzes P1's existing predictions (no new "
        f"model fits). Candidate: `{BEST_CONTINUOUS_ARM}` (P1's tune-selected continuous-Elo config).\n"
    )

    for season_set_label, season_set in [("Holdout (5 seasons -- the honest test)", "holdout"),
                                           ("All 23 seasons (descriptive only -- tune seasons were used "
                                            "to SELECT this config, so this pool isn't a clean significance "
                                            "test, just a larger-sample sanity check)", "tune_and_holdout")]:
        report.append(f"\n## {season_set_label}\n")

        for base_arm, base_label in comparisons:
            report.append(f"\n### vs. `{base_arm}` ({base_label})\n")
            report.append("**Per-game test (P1's original method, repeated here for direct comparison):**\n")
            report.append("| Cutoff | N games | Brier (base->cand) | Season-level mean diff | 95% bootstrap CI | Bootstrap p |")
            report.append("|---|---|---|---|---|---|")

            for cutoff in CUTOFFS:
                if season_set == "tune_and_holdout":
                    base_all = preds_df[(preds_df['Arm'] == base_arm) & (preds_df['Cutoff'] == cutoff)]
                    cand_all = preds_df[(preds_df['Arm'] == BEST_CONTINUOUS_ARM) & (preds_df['Cutoff'] == cutoff)]
                else:
                    base_all = preds_df[(preds_df['Arm'] == base_arm) & (preds_df['SeasonSet'] == 'holdout') & (preds_df['Cutoff'] == cutoff)]
                    cand_all = preds_df[(preds_df['Arm'] == BEST_CONTINUOUS_ARM) & (preds_df['SeasonSet'] == 'holdout') & (preds_df['Cutoff'] == cutoff)]

                if base_all.empty or cand_all.empty:
                    continue

                key = ['Season', 'Date', 'HomeTeam', 'AwayTeam']
                joined = base_all.set_index(key)[['HomeWinProb', 'WeightedResult']].join(
                    cand_all.set_index(key)[['HomeWinProb']], lsuffix='_base', rsuffix='_cand', how='inner')
                n_games = len(joined)
                brier_base = ((joined['HomeWinProb_base'] - joined['WeightedResult']) ** 2).mean()
                brier_cand = ((joined['HomeWinProb_cand'] - joined['WeightedResult']) ** 2).mean()

                seasons_to_use = 'holdout' if season_set != 'tune_and_holdout' else None
                base_seasons = per_season_means(preds_df, base_arm, seasons_to_use, cutoff) if seasons_to_use \
                    else pd.concat([per_season_means(preds_df, base_arm, s, cutoff) for s in ('tune', 'holdout')])
                cand_seasons = per_season_means(preds_df, BEST_CONTINUOUS_ARM, seasons_to_use, cutoff) if seasons_to_use \
                    else pd.concat([per_season_means(preds_df, BEST_CONTINUOUS_ARM, s, cutoff) for s in ('tune', 'holdout')])

                mean_diff, ci_low, ci_high, p_boot, n_seasons = season_level_bootstrap(
                    base_seasons['brier'], cand_seasons['brier'], rng)

                report.append(
                    f"| {cutoff} | {n_games} | {brier_base:.4f}->{brier_cand:.4f} | "
                    f"{mean_diff:+.4f} (n={n_seasons} seasons) | [{ci_low:+.4f}, {ci_high:+.4f}] | {p_boot:.3g} |"
                )

    report.append(
        "\n\n*Season-level mean diff = mean(candidate season Brier - baseline season Brier); negative "
        "means the candidate (continuous Elo) is better. The bootstrap resamples SEASONS (not games) "
        "with replacement, so its CI reflects season-to-season variability, which per-game pairing "
        "cannot see. A CI that straddles zero, even with a consistently negative point estimate, means "
        "the direction is plausible but not yet demonstrated at conventional significance with this few "
        "holdout seasons -- that's an honest report of a real data limitation (5 holdout seasons total), "
        "not a flaw in the bootstrap.*"
    )

    out_path = research_path("reports", f"{EXPERIMENT}.md")
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Report written to {out_path}")
    print("\n".join(report))


if __name__ == "__main__":
    main()
