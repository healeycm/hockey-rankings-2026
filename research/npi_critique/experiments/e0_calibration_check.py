"""
Sanity gate, run before trusting any result from the simulation harness:
does simulate_season() actually produce a season that looks like a real
one on the handful of statistics this project has already validated
against real data? If not, every downstream truth-recovery number is
built on a simulator that doesn't resemble the sport being critiqued.

Checks against this project's own established real-data findings:
  - Home win rate in decisive (non-neutral) games: HockeyBT found 56.65%
    in real data (reports/hockey_bt_results.md).
  - OT/shootout rate: this project's real-data reports consistently cite
    roughly 15-20% (reports/lrmc_hockey_adaptation.md,
    reports/hockey_bt_results.md's 20.2% figure).
  - Mean total goals/game: Division I hockey typically runs ~5.5-6.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e0_calibration_check
"""
import numpy as np
import pandas as pd
from pathlib import Path

from research.npi_critique.harness.simulate import assign_true_strengths, simulate_season

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    print(f"Real 2025-26 DI schedule: {len(schedule)} games, {len(teams)} teams")

    rng = np.random.default_rng(42)
    n_reps = 50
    home_win_rates, ot_rates, mean_goals = [], [], []

    for _ in range(n_reps):
        strengths = assign_true_strengths(teams, rng)
        sim = simulate_season(schedule, strengths, rng)
        decisive_non_neutral = sim[~sim['NeutralSite'].astype(bool)]
        home_win_rates.append(decisive_non_neutral['Result'].mean())
        ot_rates.append(sim['IsOT'].mean())
        mean_goals.append((sim['HomeGoals'] + sim['AwayGoals']).mean())

    print(f"\nOver {n_reps} simulated seasons (same real schedule, fresh true strengths each time):")
    print(f"  Home win rate (non-neutral):  {np.mean(home_win_rates):.4f}  (real data: 0.5665)")
    print(f"  OT/shootout rate:             {np.mean(ot_rates):.4f}  (real data: ~0.15-0.20)")
    print(f"  Mean total goals/game:        {np.mean(mean_goals):.3f}  (real Division I: ~5.5-6.0)")


if __name__ == "__main__":
    main()
