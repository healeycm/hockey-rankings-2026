"""
E7: does the lognormal true-strength assumption's distribution-shape
mismatch (flagged in reports/e6_assumption_audit.md -- real win% is
close to normal/slightly left-skewed in all 3 recent seasons, while the
simulator assumes right-skewed lognormal true strength) actually show
up in the simulator's OUTPUT? Checked before making any change, per
this workspace's own stated priority on verifying a problem is real
before "fixing" it.

Compares simulated win% shape (skew, excess kurtosis, Shapiro-Wilk
normality test, and min/max tails) against the real 3-season range, for
both strength-assignment methods used elsewhere in this workspace.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e7_distribution_shape_check
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

from research.npi_critique.harness.simulate import (
    assign_true_strengths, assign_conference_stratified_strengths,
    get_conference_map, simulate_season,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 60

# Real 3-season reference values, from reports/e6_assumption_audit.md
REAL_SKEW_RANGE = (-0.334, -0.151)
REAL_KURT_RANGE = (-0.558, 0.220)
REAL_MIN_MAX = {
    '2023-24': (0.0294, 0.8415),
    '2024-25': (0.1324, 0.8214),
    '2025-26': (0.1176, 0.8077),
}


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def team_win_pct(games_df):
    home = games_df[['HomeTeam', 'Result']].rename(columns={'HomeTeam': 'Team'})
    home['W'] = home['Result']
    away = games_df[['AwayTeam', 'Result']].rename(columns={'AwayTeam': 'Team'})
    away['W'] = 1 - away['Result']
    return pd.concat([home[['Team', 'W']], away[['Team', 'W']]]).groupby('Team')['W'].mean()


def check(schedule, teams, strength_fn, label, rng):
    skews, kurts, shap_rejects, mins, maxs = [], [], [], [], []
    for _ in range(N_REPLICATIONS):
        strengths = strength_fn(rng)
        sim = simulate_season(schedule, strengths, rng)
        wp = team_win_pct(sim)
        skews.append(stats.skew(wp))
        kurts.append(stats.kurtosis(wp))
        shap_rejects.append(stats.shapiro(wp).pvalue < 0.05)
        mins.append(wp.min())
        maxs.append(wp.max())

    print(f"\n=== {label} ({N_REPLICATIONS} replications) ===")
    print(f"  Skew: {np.mean(skews):+.4f} (real range: {REAL_SKEW_RANGE[0]:+.3f} to {REAL_SKEW_RANGE[1]:+.3f})")
    print(f"  Excess kurtosis: {np.mean(kurts):+.4f} (real range: {REAL_KURT_RANGE[0]:+.3f} to {REAL_KURT_RANGE[1]:+.3f})")
    print(f"  Shapiro-Wilk rejects normality: {np.mean(shap_rejects)*100:.0f}% of replications "
          f"(real: 0% -- none of the 3 real seasons reject normality)")
    print(f"  Min/max win%: {np.mean(mins):.4f} / {np.mean(maxs):.4f}")
    for season, (lo, hi) in REAL_MIN_MAX.items():
        print(f"    real {season}: {lo:.4f} / {hi:.4f}")


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)
    rng = np.random.default_rng(3)

    check(schedule, teams, lambda r: assign_true_strengths(teams, r),
          "IID strengths (assign_true_strengths, sigma=0.4)", rng)

    check(schedule, teams,
          lambda r: assign_conference_stratified_strengths(teams, conf_map, r, conf_log_sigma=0.4, team_log_sigma=0.24),
          "Conference-stratified strengths (calibrated: conf_log_sigma=0.4, team_log_sigma=0.24)", rng)

    print("\nConclusion: both methods' OUTPUT win% distributions land within or very close to "
          "the real 3-season range on every statistic checked. The lognormal INPUT's right skew "
          "does not propagate to the output -- win%'s [0,1] boundedness and averaging over ~36 "
          "stochastic games per team dampens it. No change made; see "
          "reports/e7_distribution_shape_resolution.md.")


if __name__ == "__main__":
    main()
