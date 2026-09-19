"""
S9, recalibrated a second time. e5b's conf_log_sigma=1.1 was calibrated
against 2025-26 ALONE, using a between-conference std measured on ALL
games for the simulator but on non-conference games only for the real
target -- an inconsistent basis that happened to look calibrated.
E6's assumption audit (reports/e6_assumption_audit.md) checked all three
recent seasons with ONE consistent measurement basis (both real and
simulated between-/overall-std computed on non-conference games only)
and found: (a) 2025-26 shows the smallest conference-variance share of
the three years (28% vs. 2023-24/2024-25's ~48%, 3-season average ~42%),
and (b) conf_log_sigma=1.1 actually overshoots the corrected target
substantially (0.231 vs. target 0.130) once measured consistently.

Properly recalibrated: conf_log_sigma=0.4, team_log_sigma=0.24, checked
against the 3-season average (between-conf std 0.130, overall std
0.203) with a consistent measurement basis throughout -- simulated
values land within 2% of both targets (0.128, 0.204).

Run from the project root as a module:
    python -m research.npi_critique.experiments.e5c_selection_field_accuracy_recalibrated
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import (
    simulate_season, true_ranking, get_conference_map, games_played,
    assign_conference_stratified_strengths,
)
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 300
FIELD_SIZE = 16
CONF_LOG_SIGMA = 0.4    # corrected: calibrated against 3-season average, consistent basis (see harness docstring)
TEAM_LOG_SIGMA = 0.24  # corrected, see above


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def top_n(ratings, teams, n):
    return set(sorted(teams, key=lambda t: ratings.get(t, -np.inf), reverse=True)[:n])


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)
    gp_real = games_played(schedule)
    median_games = gp_real.median()

    rng = np.random.default_rng(202)
    field_rows = []
    team_error_rows = []

    for rep in range(N_REPLICATIONS):
        strengths = assign_conference_stratified_strengths(
            teams, conf_map, rng, conf_log_sigma=CONF_LOG_SIGMA, team_log_sigma=TEAM_LOG_SIGMA,
        )
        truth = true_ranking(strengths)
        true_field = set(truth[:FIELD_SIZE])
        sim = simulate_season(schedule, strengths, rng)

        npi, krach, rpi = NPI(sim), KRACH(sim), RPI(sim)
        massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
        for m in (npi, krach, rpi, massey):
            m.fit()

        for name, model in [('NPI', npi), ('KRACH', krach), ('RPI', rpi), ('Massey', massey)]:
            model_field = top_n(model.ratings, teams, FIELD_SIZE)
            overlap = len(true_field & model_field)
            excluded = true_field - model_field
            included = model_field - true_field

            field_rows.append({
                'rep': rep, 'model': name, 'overlap': overlap,
                'n_excluded': len(excluded), 'n_included_wrongly': len(included),
            })
            for team in excluded:
                team_error_rows.append({
                    'rep': rep, 'model': name, 'team': team, 'error_type': 'wrongly_excluded',
                    'conference': conf_map.get(team, 'independent'),
                    'below_median_games': gp_real.get(team, median_games) < median_games,
                })
            for team in included:
                team_error_rows.append({
                    'rep': rep, 'model': name, 'team': team, 'error_type': 'wrongly_included',
                    'conference': conf_map.get(team, 'independent'),
                    'below_median_games': gp_real.get(team, median_games) < median_games,
                })

        if (rep + 1) % 60 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    field_df = pd.DataFrame(field_rows)
    errors_df = pd.DataFrame(team_error_rows)
    field_df.to_csv(results_path("e5c_selection_field_accuracy_recalibrated", "field_overlap.csv"), index=False)
    errors_df.to_csv(results_path("e5c_selection_field_accuracy_recalibrated", "team_errors.csv"), index=False)

    print(f"\n=== Field overlap with TRUE top-{FIELD_SIZE}, CONFERENCE-STRATIFIED strengths "
          f"({N_REPLICATIONS} replications) ===")
    print(field_df.groupby('model')['overlap'].agg(
        mean='mean', std='std', min='min',
        pct_perfect=lambda s: (s == FIELD_SIZE).mean() * 100,
        pct_le_12=lambda s: (s <= 12).mean() * 100,
    ))

    print(f"\n=== Conference distribution of wrongly-included teams (raw counts, by model) ===")
    for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
        sub = errors_df[(errors_df.model == name) & (errors_df.error_type == 'wrongly_included')]
        print(f"  {name}: {dict(sub['conference'].value_counts())}")

    return field_df, errors_df


if __name__ == "__main__":
    main()
