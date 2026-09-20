# research/womens_comparison/experiments/p0_4_power_analysis.py
"""
P0.4 — minimum detectable effect (MDE) for the paired significance tests
this comparison relies on, computed from REAL per-game variance in the
pooled women's backtest predictions (not an assumed/textbook sd), at
alpha=0.05 and 80% power. Per PLAN.md: "a null is reported as 'no
difference detected, MDE = X' -- never as 'no difference'", and this
script is what produces that X for every later report.

Two things this answers:
  1. Paired t-test (Brier, LogLoss): given n and the OBSERVED sd of the
     per-game paired difference, what mean difference could we reliably
     detect?
  2. McNemar's test (Accuracy): given the OBSERVED number of discordant
     games (one model right, the other wrong), what imbalance between the
     two directions would reach significance?
  3. The men's/women's power gap (C2 in PLAN.md): the same two
     computations at the men's-hockey pooled n (8,371 games, from
     paper/draft.md's abstract) under women's-observed variance, to make
     concrete how much less power the women's backtest has.

Run from the project root as a module:
    python -m research.womens_comparison.experiments.p0_4_power_analysis

Requires research/womens_comparison/experiments/../reports/p0_2_paired_significance.md's
prerequisite artifact: data/validation/backtest_results/backtest_predictions.csv
(written by analysis/exploratory/womens_hockey_backtest.py's save_predictions()
call -- run that first if this file doesn't exist).
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

from src.validation.metrics import apply_ot_weighting
from research.womens_comparison.harness.paths import report_path, results_path

PREDICTIONS_PATH = Path('data/validation/backtest_results/backtest_predictions.csv')
ALPHA = 0.05
POWER = 0.80
MEN_POOLED_N = 8371  # paper/draft.md abstract: "8,371 held-out games, 20 walk-forward train/test splits"


def mde_paired_t(sd_diff, n, alpha=ALPHA, power=POWER):
    """Minimum detectable mean paired difference for a two-sided paired
    t-test, using the normal approximation (valid at these sample sizes):
    MDE = (z_{alpha/2} + z_{power}) * sd_diff / sqrt(n)."""
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_power = stats.norm.ppf(power)
    return (z_alpha + z_power) * sd_diff / np.sqrt(n)


def mde_mcnemar(n_discordant, alpha=ALPHA, power=POWER):
    """Minimum |b01 - b10| detectable by McNemar's (continuity-corrected)
    test given a total discordant-pair count, found by inverting the test
    statistic (b01+b10) rather than a closed-form power formula, since the
    continuity correction has no clean algebraic inverse. Returns the
    corresponding minimum detectable proportion of discordant pairs
    favoring one model (0.5 = balanced/no effect)."""
    if n_discordant <= 0:
        return None, None
    # Solve chi2 = ((|d| - 1)^2) / n_discordant = chi2_crit for |d|, then
    # also report power at that |d| to confirm (McNemar's power depends on
    # both alpha and the true discordant proportion, not just alpha -- the
    # simple algebraic solve below gives the ALPHA-only threshold; we
    # report it as the "detectable at p<0.05" boundary rather than a true
    # 80%-power MDE, and note this distinction in the report).
    chi2_crit = stats.chi2.ppf(1 - alpha, df=1)
    d_min = 1 + np.sqrt(chi2_crit * n_discordant)
    frac_min = 0.5 + (d_min / 2) / n_discordant
    return d_min, frac_min


def main():
    if not PREDICTIONS_PATH.exists():
        raise SystemExit(
            f"{PREDICTIONS_PATH} not found -- run "
            f"`python -m analysis.exploratory.womens_hockey_backtest` first "
            f"(see this script's docstring)."
        )

    preds = pd.read_csv(PREDICTIONS_PATH)
    key = ['Season', 'Cutoff', 'Date', 'HomeTeam', 'AwayTeam']
    piv = preds.pivot_table(index=key, columns='Model', values='HomeWinProb').reset_index()
    res = preds.drop_duplicates(subset=key)[key + ['Result', 'IsOT']].merge(piv, on=key)
    res['WeightedResult'] = apply_ot_weighting(res, ot_win_weight=0.6, ot_loss_weight=0.4)
    y = res['WeightedResult'].values
    n_women = len(res)
    models = [m for m in ['Massey', 'HockeyBT', 'KRACH', 'ELO', 'RPI'] if m in res.columns]

    print(f"Pooled women's paired games: n={n_women}")
    print(f"Reference men's pooled n (paper/draft.md): {MEN_POOLED_N}")

    rows = []
    for i, m1 in enumerate(models):
        for m2 in models[i + 1:]:
            p1, p2 = res[m1].values, res[m2].values
            brier_diff = (p1 - y) ** 2 - (p2 - y) ** 2
            mask = res['Result'] != 0.5
            yy = res.loc[mask, 'WeightedResult'].values
            pc1 = np.clip(p1[mask], 1e-15, 1 - 1e-15)
            pc2 = np.clip(p2[mask], 1e-15, 1 - 1e-15)
            ll1 = -(yy * np.log(pc1) + (1 - yy) * np.log(1 - pc1))
            ll2 = -(yy * np.log(pc2) + (1 - yy) * np.log(1 - pc2))
            ll_diff = ll1 - ll2

            correct1 = np.round(pc1) == np.round(yy)
            correct2 = np.round(pc2) == np.round(yy)
            n_discordant = int(np.sum(correct1 != correct2))

            sd_brier, sd_ll = brier_diff.std(ddof=1), ll_diff.std(ddof=1)
            mde_brier_women = mde_paired_t(sd_brier, n_women)
            mde_ll_women = mde_paired_t(sd_ll, len(yy))
            mde_brier_men = mde_paired_t(sd_brier, MEN_POOLED_N)
            mde_ll_men = mde_paired_t(sd_ll, MEN_POOLED_N)
            d_min, frac_min = mde_mcnemar(n_discordant)

            rows.append({
                'Pair': f"{m1} vs {m2}",
                'n_decisive': int(mask.sum()),
                'sd_Brier_diff': round(float(sd_brier), 5),
                'MDE_Brier_women_n': round(float(mde_brier_women), 6),
                'MDE_Brier_men_n': round(float(mde_brier_men), 6),
                'sd_LogLoss_diff': round(float(sd_ll), 5),
                'MDE_LogLoss_women_n': round(float(mde_ll_women), 5),
                'MDE_LogLoss_men_n': round(float(mde_ll_men), 5),
                'n_discordant': n_discordant,
                'McNemar_min_|b01-b10|_p05': round(float(d_min), 1) if d_min else None,
                'McNemar_min_detectable_frac': round(float(frac_min), 4) if frac_min else None,
            })

    out = pd.DataFrame(rows)
    print("\n=== Minimum detectable effect, women's backtest (alpha=0.05, power=0.80) ===")
    print(out.to_string(index=False))

    out_path = results_path('p0_4_power_analysis', 'mde_by_pair.csv')
    out.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")
    return out


if __name__ == "__main__":
    main()
