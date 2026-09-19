"""
S10: single-game leverage / rank stability. A metric where one game's
result swings a bubble team many places is fragile for a selection
decision regardless of its average accuracy -- this measures that
fragility directly via leave-one-game-out, reusing the same idea as
E1's paradox-detection LOO machinery but applied to rank stability
generally rather than the NPI-specific paradox question.

Design: simulate one full season per replication. Fit baseline ratings
for all four models. For a random sample of games, remove that single
game and refit; measure (a) the rank shift for the two teams DIRECTLY
involved (the most interpretable "how much does one result matter"
measure) and (b) the mean absolute rank shift across the WHOLE field
(a broader stability measure, since one game could in principle ripple
through opponent-adjusted ratings well beyond the two teams that played
it).

Run from the project root as a module:
    python -m research.npi_critique.experiments.e19_single_game_leverage
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import assign_true_strengths, simulate_season
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 10
N_GAMES_PER_REP = 40


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def rank_of(ratings, team, teams):
    order = sorted(teams, key=lambda t: ratings.get(t, -np.inf), reverse=True)
    return order.index(team) + 1


def fit_all(sim):
    npi, krach, rpi = NPI(sim), KRACH(sim), RPI(sim)
    massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
    for m in (npi, krach, rpi, massey):
        m.fit()
    return {'NPI': npi, 'KRACH': krach, 'RPI': rpi, 'Massey': massey}


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))

    rng = np.random.default_rng(11235)
    rows = []

    for rep in range(N_REPLICATIONS):
        strengths = assign_true_strengths(teams, rng)
        sim = simulate_season(schedule, strengths, rng)
        baseline_models = fit_all(sim)
        baseline_ranks = {name: {t: rank_of(m.ratings, t, teams) for t in teams}
                           for name, m in baseline_models.items()}

        sample_idx = rng.choice(sim.index, size=min(N_GAMES_PER_REP, len(sim)), replace=False)

        for game_idx in sample_idx:
            home, away = sim.loc[game_idx, 'HomeTeam'], sim.loc[game_idx, 'AwayTeam']
            sim_without = sim.drop(game_idx)
            without_models = fit_all(sim_without)

            for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
                shift_home = abs(rank_of(without_models[name].ratings, home, teams) - baseline_ranks[name][home])
                shift_away = abs(rank_of(without_models[name].ratings, away, teams) - baseline_ranks[name][away])

                all_shifts = [abs(rank_of(without_models[name].ratings, t, teams) - baseline_ranks[name][t])
                              for t in teams]

                rows.append({
                    'rep': rep, 'game_idx': game_idx, 'model': name,
                    'direct_shift_home': shift_home, 'direct_shift_away': shift_away,
                    'direct_shift_max': max(shift_home, shift_away),
                    'field_mean_shift': np.mean(all_shifts), 'field_max_shift': np.max(all_shifts),
                })

        print(f"  rep {rep + 1}/{N_REPLICATIONS} done ({len(sample_idx)} games tested)")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e19_single_game_leverage", "results.csv"), index=False)

    print(f"\n=== Single-game leverage summary ({len(results) // 4} game-removals x 4 models) ===")
    print(results.groupby('model').agg(
        mean_direct_shift=('direct_shift_max', 'mean'),
        p90_direct_shift=('direct_shift_max', lambda s: s.quantile(0.90)),
        max_direct_shift=('direct_shift_max', 'max'),
        mean_field_shift=('field_mean_shift', 'mean'),
        max_field_shift=('field_max_shift', 'max'),
    ))

    return results


if __name__ == "__main__":
    main()
