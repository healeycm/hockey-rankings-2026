"""
E8: calibrate and verify the CLOSE_GAME_PROB fix for the OT-rate
undershoot flagged in reports/e6_assumption_audit.md (simulator gave
14.3% vs. real 18.1-22.3% across the last three seasons) and confirmed
not to be a false alarm the way the distribution-shape item was
(see reports/e7_distribution_shape_resolution.md) -- this one is a real,
consistent gap on the actual simulator output, not just an input
assumption.

Verifies the fix (research/npi_critique/harness/simulate.py's
CLOSE_GAME_PROB mechanism) against all three real seasons individually,
for both strength-assignment methods used in this workspace, and checks
that the other already-calibrated statistics (home win%, mean goals,
win% spread) were not disturbed.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e8_ot_rate_calibration
"""
import numpy as np
import pandas as pd
from pathlib import Path

from research.npi_critique.harness.simulate import (
    assign_true_strengths, assign_conference_stratified_strengths,
    get_conference_map, simulate_season,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 100

REAL = {
    '2023-24': {'ot_rate': 0.2159, 'home_win': 0.5782, 'goals': 5.969},
    '2024-25': {'ot_rate': 0.2232, 'home_win': 0.5320, 'goals': 5.688},
    '2025-26': {'ot_rate': 0.1811, 'home_win': 0.5505, 'goals': 5.892},
}


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def run_check(schedule, teams, strength_fn, label, rng):
    ot_rates, home_wins, goals, wp_stds = [], [], [], []
    for _ in range(N_REPLICATIONS):
        strengths = strength_fn(rng)
        sim = simulate_season(schedule, strengths, rng)
        ot_rates.append(sim['IsOT'].mean())
        home_wins.append(sim[~sim['NeutralSite'].astype(bool)]['Result'].mean())
        goals.append((sim['HomeGoals'] + sim['AwayGoals']).mean())
        home = sim[['HomeTeam', 'Result']].rename(columns={'HomeTeam': 'Team'})
        home['W'] = home['Result']
        away = sim[['AwayTeam', 'Result']].rename(columns={'AwayTeam': 'Team'})
        away['W'] = 1 - away['Result']
        wp = pd.concat([home[['Team', 'W']], away[['Team', 'W']]]).groupby('Team')['W'].mean()
        wp_stds.append(wp.std())

    print(f"\n=== {label} ({N_REPLICATIONS} replications) ===")
    print(f"  OT rate:   {np.mean(ot_rates):.4f}")
    print(f"  Home win%: {np.mean(home_wins):.4f}")
    print(f"  Mean goals: {np.mean(goals):.3f}")
    print(f"  Win% std:  {np.mean(wp_stds):.4f}")
    print(f"\n  Real reference (all 3 seasons):")
    for season, vals in REAL.items():
        print(f"    {season}: OT={vals['ot_rate']:.4f}, home_win={vals['home_win']:.4f}, goals={vals['goals']:.3f}")


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)
    rng = np.random.default_rng(2026)

    run_check(schedule, teams, lambda r: assign_true_strengths(teams, r),
              "IID strengths, post-fix", rng)
    run_check(schedule, teams,
              lambda r: assign_conference_stratified_strengths(teams, conf_map, r, conf_log_sigma=0.4, team_log_sigma=0.24),
              "Conference-stratified strengths, post-fix", rng)


if __name__ == "__main__":
    main()
