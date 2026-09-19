"""
S2 follow-up: does the direction of e3's finding (KRACH overrates the
weak-in-elite team more than NPI does; NPI actually underrates it) depend
on HOW weak the planted team truly is? e3 planted a true rank-52-of-63
team (a 7-30-type record) -- more extreme than the real Ohio State case
that motivated this study (14-13-8, a near-.500 record). If NPI's 25%
own-win% term dominates for a truly bad team but SOS credit matters more
for a team that's merely mediocre, the bias direction could flip as
planted strength rises toward the field median.

Same design as e3_weak_team_strong_conference.py, swept over
PLANTED_WEAK_STRENGTH, 120 replications per strength value (reduced from
300 to keep the sweep's total runtime reasonable -- this is a directional
check, not the headline number).

Run from the project root as a module:
    python -m research.npi_critique.experiments.e3b_strength_sweep
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from research.npi_critique.harness.simulate import (
    simulate_season, true_ranking, get_conference_map,
    assign_conference_stratified_strengths,
)
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 120
ELITE_CONF = 'b10'
ELITE_EFFECT = 0.65
STRENGTHS_TO_SWEEP = [0.55, 0.70, 0.85, 0.95, 1.05]  # last one is near/at the field median (~1.0)


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


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)
    elite_teams = [t for t, c in conf_map.items() if c == ELITE_CONF]
    planted = elite_teams[0]
    print(f"Planting varying true strength onto {planted} ({ELITE_CONF})")

    rng = np.random.default_rng(9999)
    rows = []

    for strength in STRENGTHS_TO_SWEEP:
        for rep in range(N_REPLICATIONS):
            strengths = assign_conference_stratified_strengths(
                teams, conf_map, rng, conf_effect_override={ELITE_CONF: ELITE_EFFECT},
            )
            strengths[planted] = strength
            true_rank = true_ranking(strengths).index(planted) + 1
            sim = simulate_season(schedule, strengths, rng)

            npi, krach = NPI(sim), KRACH(sim)
            massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
            for m in (npi, krach, massey):
                m.fit()

            for name, model in [('NPI', npi), ('KRACH', krach), ('Massey', massey)]:
                rk = rank_of(model.ratings, planted, teams)
                rows.append({
                    'planted_strength': strength, 'rep': rep, 'model': name,
                    'true_rank': true_rank, 'induced_rank': rk, 'rank_error': true_rank - rk,
                })
        print(f"  strength={strength} done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e3b_strength_sweep", "rank_error_by_strength.csv"), index=False)

    print(f"\n=== Mean rank error (true rank - induced rank; positive = overrated) by planted strength ===")
    pivot = results.groupby(['planted_strength', 'model'])['rank_error'].mean().unstack()
    print(pivot)

    print(f"\n=== Mean TRUE rank at each planted strength (for context) ===")
    print(results.groupby('planted_strength')['true_rank'].mean())

    return results


if __name__ == "__main__":
    main()
