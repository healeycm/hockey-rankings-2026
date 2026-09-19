"""
DGP robustness check, flagged as an open blocker since
reports/e1_truth_recovery.md and repeated in every subsequent report:
every experiment in this workspace used simulate_season()'s independent-
Poisson-goals process, which structurally favors margin-based models
(Massey) since it generates a continuous goal margin correlated with
strength. This re-checks the two headline model-comparison findings --
E1's "Massey recovers ground truth best" and S9's "KRACH beats NPI on
selection-field accuracy" -- under simulate_season_bradley_terry(), a
genuinely different DGP where WHO WINS is drawn directly from the
Bradley-Terry probability (the functional form KRACH's own likelihood
is built on, making KRACH the correctly-specified estimator here) and
margin is generated independently of strength entirely.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e15_dgp_robustness
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr
from scipy import stats

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import (
    assign_true_strengths, assign_conference_stratified_strengths,
    simulate_season_bradley_terry, true_ranking, get_conference_map,
)
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 200
FIELD_SIZE = 16


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def spearman_vs_truth(ratings, truth_order):
    teams = list(truth_order)
    truth_rank = {t: i for i, t in enumerate(truth_order)}
    model_sorted = sorted(teams, key=lambda t: ratings.get(t, -np.inf), reverse=True)
    model_rank = {t: i for i, t in enumerate(model_sorted)}
    rho, _ = spearmanr([truth_rank[t] for t in teams], [model_rank[t] for t in teams])
    return rho


def top_n(ratings, teams, n):
    return set(sorted(teams, key=lambda t: ratings.get(t, -np.inf), reverse=True)[:n])


def fit_all(sim):
    npi, krach, rpi = NPI(sim), KRACH(sim), RPI(sim)
    massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
    for m in (npi, krach, rpi, massey):
        m.fit()
    return {'NPI': npi, 'KRACH': krach, 'RPI': rpi, 'Massey': massey}


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)
    rng_truth = np.random.default_rng(7001)
    rng_field = np.random.default_rng(7002)

    print("=== Part 1: Truth recovery under Bradley-Terry DGP (iid strengths) ===")
    truth_rows = []
    for rep in range(N_REPLICATIONS):
        strengths = assign_true_strengths(teams, rng_truth)
        truth = true_ranking(strengths)
        sim = simulate_season_bradley_terry(schedule, strengths, rng_truth)
        models = fit_all(sim)
        for name, model in models.items():
            truth_rows.append({'rep': rep, 'model': name, 'rho': spearman_vs_truth(model.ratings, truth)})
        if (rep + 1) % 50 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    truth_df = pd.DataFrame(truth_rows)
    truth_df.to_csv(results_path("e15_dgp_robustness", "truth_recovery.csv"), index=False)
    print("\nMean Spearman rho vs. ground truth, by model:")
    print(truth_df.groupby('model')['rho'].agg(mean='mean', std='std').sort_values('mean', ascending=False))
    piv = truth_df.pivot(index='rep', columns='model', values='rho')
    print("\nPaired significance vs. Massey:")
    for other in ['KRACH', 'NPI', 'RPI']:
        t, p = stats.ttest_rel(piv['Massey'], piv[other])
        print(f"  Massey vs {other}: p={p:.2e}")

    print("\n=== Part 2: Selection-field accuracy under Bradley-Terry DGP (conference-stratified) ===")
    field_rows = []
    for rep in range(N_REPLICATIONS):
        strengths = assign_conference_stratified_strengths(teams, conf_map, rng_field, conf_log_sigma=0.4, team_log_sigma=0.24)
        truth = true_ranking(strengths)
        true_field = set(truth[:FIELD_SIZE])
        sim = simulate_season_bradley_terry(schedule, strengths, rng_field)
        models = fit_all(sim)
        for name, model in models.items():
            overlap = len(true_field & top_n(model.ratings, teams, FIELD_SIZE))
            field_rows.append({'rep': rep, 'model': name, 'overlap': overlap})
        if (rep + 1) % 50 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    field_df = pd.DataFrame(field_rows)
    field_df.to_csv(results_path("e15_dgp_robustness", "field_accuracy.csv"), index=False)
    print("\nMean field overlap (of 16), by model:")
    print(field_df.groupby('model')['overlap'].agg(mean='mean', std='std').sort_values('mean', ascending=False))
    piv2 = field_df.pivot(index='rep', columns='model', values='overlap')
    t, p = stats.ttest_rel(piv2['KRACH'], piv2['NPI'])
    print(f"\nKRACH vs NPI paired t-test: p={p:.4f}")


if __name__ == "__main__":
    main()
