# research/womens_comparison/experiments/w6_dial_sensitivity.py
"""
W6 (PLAN.md) -- how sensitive are women's NPI rankings to the dial
settings themselves? Direct extension of P0.3's finding (the NCAA applies
DIFFERENT dials to men's vs. women's D-I hockey with no published
sensitivity analysis for either): if the sensible region of the dial
surface differs by division, then at most one division's dials can be
well-justified, and neither committee has published a rationale.

IMPORTANT discovery made while building this (not previously written up
anywhere): `weight_wp`/`weight_sos` in NPI's config dict are DEAD CONFIG,
exactly like the ot_win_weight/ot_loss_weight dead config P0.3 already
found -- `src/rankings/npi.py`'s fit loop hardcodes 0.25/0.75 and never
reads self.conf['weight_wp'] at all (confirmed: `grep -n "weight_wp"
src/rankings/npi.py` shows it ONLY in the constructor's default dict,
nowhere in fit()). Passing a different weight_wp through NPI(config=...)
and refitting silently does nothing. The men's-hockey critique
(reports/npi_critique.md's "2a. SOS Weight Sweep") got real variation
because it never actually refits NPI with a new weight_wp -- it uses
`reweight_npi()` (src/analysis/npi_vs_krach.py), which POST-HOC
recombines an already-converged fit's adj_wp/sos/qwb components with new
weights. That function is reused here directly (production code, read
only, per this workspace's isolation rules) rather than reimplemented.

QWB base IS genuinely wired up (confirmed in P0.3 and by this
experiment's own non-degenerate results below), so that dimension is
swept the direct way (a real refit per configuration).

Smaller-scope counterpart to the men's 98-configuration sweep
(research/npi_critique/experiments/e23_dial_interaction.py) -- this grid
covers the two dials with an independent, documented NCAA cross-sport
baseline (win%/SOS split, QWB base), not a full re-derivation of E23's
larger sweep.

Run from the project root as a module:
    python -m research.womens_comparison.experiments.w6_dial_sensitivity
"""
import pandas as pd
from scipy.stats import kendalltau

from src.analysis.npi_vs_krach import reweight_npi
from research.womens_comparison.harness.women_npi import (
    load_games, get_di_teams, filter_season, fit_npi, get_ranks,
    npi_women_config, BACKTEST_SEASONS,
)
from research.womens_comparison.harness.paths import results_path, report_path

WEIGHT_WP_GRID = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
QWB_BASE_GRID = [49.0, 50.0, 51.0, 51.5, 52.0, 53.0]
RANK_CHANGE_THRESHOLD = 3


def _rank_diff_stats(baseline_ranks, variant_ranks):
    teams = sorted(set(baseline_ranks) & set(variant_ranks))
    b = [baseline_ranks[t] for t in teams]
    v = [variant_ranks[t] for t in teams]
    changes = [abs(x - y) for x, y in zip(b, v)]
    tau, _ = kendalltau(b, v)
    return {
        "n_teams": len(teams),
        "max_rank_change": max(changes) if changes else 0,
        "n_teams_changed_gt3": sum(1 for c in changes if c > RANK_CHANGE_THRESHOLD),
        "tau_vs_official": round(float(tau), 4) if tau is not None else None,
    }


def main():
    print("Loading women's D-I games...")
    games_df = load_games()
    di_teams = get_di_teams()
    baseline_cfg = npi_women_config()

    weight_rows, qwb_rows = [], []

    for season in BACKTEST_SEASONS:
        sdf = filter_season(games_df, season, di_teams)
        if len(sdf) < 200:
            continue
        print(f"\nSeason {season}: {len(sdf)} games")

        baseline = fit_npi(sdf, config=baseline_cfg)
        baseline_ranks = get_ranks(baseline.ratings)

        # --- weight_wp sweep: post-hoc reweighting (the only correct way
        # -- see this module's docstring for why a direct refit is a no-op) ---
        for weight_wp in WEIGHT_WP_GRID:
            weight_sos = round(1 - weight_wp, 2)
            variant = reweight_npi(baseline, weight_wp=weight_wp, weight_sos=weight_sos)
            variant_ranks = get_ranks(variant.ratings)
            stats = _rank_diff_stats(baseline_ranks, variant_ranks)
            weight_rows.append({"season": season, "weight_wp": weight_wp, "weight_sos": weight_sos, **stats})

        # --- QWB base sweep: genuine refit (this dial IS wired up) ---
        for qwb_base in QWB_BASE_GRID:
            cfg = dict(baseline_cfg)
            cfg['quality_win_base'] = qwb_base
            variant = fit_npi(sdf, config=cfg)
            variant_ranks = get_ranks(variant.ratings)
            stats = _rank_diff_stats(baseline_ranks, variant_ranks)
            qwb_rows.append({"season": season, "qwb_base": qwb_base, **stats})

    weight_df = pd.DataFrame(weight_rows)
    qwb_df = pd.DataFrame(qwb_rows)
    weight_path = results_path("w6_dial_sensitivity", "weight_wp_sweep.csv")
    qwb_path = results_path("w6_dial_sensitivity", "qwb_base_sweep.csv")
    weight_df.to_csv(weight_path, index=False)
    qwb_df.to_csv(qwb_path, index=False)
    print(f"\nSaved {weight_path} and {qwb_path}")

    print("\n=== weight_wp sweep (mean across seasons) ===")
    print(weight_df.groupby('weight_wp')[['tau_vs_official', 'n_teams_changed_gt3', 'max_rank_change']].mean())
    print("\n=== QWB base sweep (mean across seasons) ===")
    print(qwb_df.groupby('qwb_base')[['tau_vs_official', 'n_teams_changed_gt3', 'max_rank_change']].mean())

    return weight_df, qwb_df


if __name__ == "__main__":
    main()
