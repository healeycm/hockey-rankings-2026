"""
S9, re-tested under realistic conference structure. e5's original design
used `assign_true_strengths` -- fully independent (iid) team strengths,
which implicitly assumes every conference is equal in expectation.
Caught by direct question: is that assumption realistic? Checked against
real 2025-26 data and it is not -- real conferences differ substantially
in non-conference win% (NCHC/Big Ten ~0.64, independents ~0.38, a 0.26
spread; between-conference std 0.102 vs. overall team-level std 0.158,
meaning conference membership accounts for roughly 40% of total win%
variance in real data). e5's iid assumption implicitly set that share to
zero.

This re-runs e5's exact design with `assign_conference_stratified_strengths`
instead, calibrated against the real between-conference and overall
win% dispersion above (conf_log_sigma=1.1, team_log_sigma=0.30 -->
simulated between-conference std 0.080 vs. real 0.102, overall std 0.156
vs. real 0.158 -- a substantial, though not perfect, improvement over
the iid default's 0.042 between-conference std).

Run from the project root as a module:
    python -m research.npi_critique.experiments.e5b_selection_field_accuracy_conf_stratified
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
CONF_LOG_SIGMA = 1.1   # calibrated against real between-conference win% dispersion
TEAM_LOG_SIGMA = 0.30  # calibrated against real overall win% dispersion, jointly with the above


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
    field_df.to_csv(results_path("e5b_selection_field_accuracy_conf_stratified", "field_overlap.csv"), index=False)
    errors_df.to_csv(results_path("e5b_selection_field_accuracy_conf_stratified", "team_errors.csv"), index=False)

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
