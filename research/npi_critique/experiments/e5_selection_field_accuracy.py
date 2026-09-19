"""
S9: selection-field accuracy -- the actual policy outcome everything else
in this workspace is instrumental to. NPI's job is to help pick a
16-team tournament field. Does it pick the RIGHT 16, relative to known
ground truth? This closes a gap flagged in reports/calibration_metrics.md
("no rank-stability or bubble-team-accuracy metric was formalized") and
converts every mechanism tested so far (S1 games-played, S2 conference
effects) into its real consequence: not "is this team's rank off by N
positions" but "did the wrong team make the tournament."

Design: standard iid true-strength assignment (log-normal, sigma=0.4 --
now validated in reports/e4_bad_wins_filter_games_mismatch.md against
real win-percentage dispersion, std 0.175 vs. real 0.158) on the REAL
2025-26 schedule. This is deliberately NOT a constructed scenario like
S1/S2 -- the real schedule already has genuine games-played variation
(30-41 games) and genuine conference structure (Big Ten vs. Atlantic
Hockey, etc.), so every selection error each model makes can be checked
directly against each real team's actual games-played count and actual
conference, without any extra synthetic manipulation. This tests whether
S1/S2's mechanisms show up in the realistic, undistorted setting, not
just the deliberately-constructed stress tests.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e5_selection_field_accuracy
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import (
    assign_true_strengths, simulate_season, true_ranking, get_conference_map, games_played,
)
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 300
FIELD_SIZE = 16


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

    rng = np.random.default_rng(101)
    field_rows = []       # one row per (rep, model): overlap-count-level summary
    team_error_rows = []  # one row per (rep, model, team) that was ever wrongly in/out

    for rep in range(N_REPLICATIONS):
        strengths = assign_true_strengths(teams, rng)
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
            excluded = true_field - model_field   # true top-16 team left out
            included = model_field - true_field   # non-top-16 team let in

            field_rows.append({
                'rep': rep, 'model': name, 'overlap': overlap,
                'n_excluded': len(excluded), 'n_included_wrongly': len(included),
            })

            for team in excluded:
                team_error_rows.append({
                    'rep': rep, 'model': name, 'team': team, 'error_type': 'wrongly_excluded',
                    'games_played': int(gp_real.get(team, np.nan)),
                    'below_median_games': gp_real.get(team, median_games) < median_games,
                    'conference': conf_map.get(team, 'independent'),
                })
            for team in included:
                team_error_rows.append({
                    'rep': rep, 'model': name, 'team': team, 'error_type': 'wrongly_included',
                    'games_played': int(gp_real.get(team, np.nan)),
                    'below_median_games': gp_real.get(team, median_games) < median_games,
                    'conference': conf_map.get(team, 'independent'),
                })

        if (rep + 1) % 60 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    field_df = pd.DataFrame(field_rows)
    errors_df = pd.DataFrame(team_error_rows)
    field_df.to_csv(results_path("e5_selection_field_accuracy", "field_overlap.csv"), index=False)
    errors_df.to_csv(results_path("e5_selection_field_accuracy", "team_errors.csv"), index=False)

    print(f"\n=== Field overlap with TRUE top-{FIELD_SIZE} ({N_REPLICATIONS} replications) ===")
    print(field_df.groupby('model')['overlap'].agg(
        mean='mean', std='std', min='min',
        pct_perfect=lambda s: (s == FIELD_SIZE).mean() * 100,
        pct_le_12=lambda s: (s <= 12).mean() * 100,
    ))

    print(f"\n=== Do selection errors concentrate on below-median-games-played real teams? ===")
    print("(overall real-schedule rate: %.1f%% of teams are below median games)" %
          (100 * (gp_real < median_games).mean()))
    print(errors_df.groupby(['model', 'error_type'])['below_median_games'].mean().unstack() * 100)

    print(f"\n=== Which real teams are wrongly EXCLUDED most often, by model (top 5 each) ===")
    for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
        sub = errors_df[(errors_df.model == name) & (errors_df.error_type == 'wrongly_excluded')]
        top = sub['team'].value_counts().head(5)
        print(f"  {name}: {dict(top)}")

    print(f"\n=== Which real teams are wrongly INCLUDED most often, by model (top 5 each) ===")
    for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
        sub = errors_df[(errors_df.model == name) & (errors_df.error_type == 'wrongly_included')]
        top = sub['team'].value_counts().head(5)
        print(f"  {name}: {dict(top)}")

    print(f"\n=== Conference distribution of wrongly-included teams, by model ===")
    for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
        sub = errors_df[(errors_df.model == name) & (errors_df.error_type == 'wrongly_included')]
        print(f"  {name}: {dict(sub['conference'].value_counts().head(5))}")

    return field_df, errors_df


if __name__ == "__main__":
    main()
