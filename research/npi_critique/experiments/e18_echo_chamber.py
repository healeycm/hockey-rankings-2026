"""
S5: conference echo chamber under controlled connectivity. Real data
showed (reports/npi_critique.md Section 6) a strong correlation
(rho=0.886) between a conference's non-conference win% and its members'
average SOS -- suggestive of an "echo chamber" where playing in a
conference whose OTHER members happen to do well inflates your own
schedule credit. But real data can't isolate whether that's a genuine
signal (the conference IS actually strong) or a structural artifact of
sparse cross-conference connectivity, since real conferences always
have some true strength difference confounded with their connectivity.

Design: build a fully synthetic schedule (make_multiconference_schedule)
with EVERY conference given EQUAL true strength (conf_log_sigma=0 --
the null hypothesis) and vary the cross-conference game fraction from
sparse (10%) to well-mixed (60%). If ratings still cluster by
conference at low cross-conference fractions despite zero true
difference, that clustering is provably an artifact of network
sparsity, not signal -- something no analysis of real, confounded data
can establish.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e18_echo_chamber
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import make_multiconference_schedule, simulate_season
from research.npi_critique.harness.paths import results_path

N_REPLICATIONS = 60
N_CONFERENCES = 6
TEAMS_PER_CONF = 10
# NOTE: make_multiconference_schedule's generation mechanism (each team
# independently draws its own opponents, which ALSO appear as away
# assignments in return) roughly doubles realized games/team relative to
# the input -- verified directly (input 18 -> realized mean 36.0, std
# 4.19, comparable to the real schedule's own 30-41 game range). Pass
# half of the intended games/team here.
GAMES_PER_TEAM = 18  # -> realized mean ~36 games/team
CROSS_FRACS = [0.10, 0.25, 0.40, 0.60]
TEAM_LOG_SIGMA = 0.24  # within-conference team-level noise, matching the calibrated value elsewhere


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
    rng = np.random.default_rng(90210)
    rows = []

    for cross_frac in CROSS_FRACS:
        for rep in range(N_REPLICATIONS):
            schedule, teams, conf_map = make_multiconference_schedule(
                N_CONFERENCES, TEAMS_PER_CONF, cross_frac, rng, games_per_team=GAMES_PER_TEAM)

            # NULL HYPOTHESIS: every conference has EQUAL true strength
            # (conf_log_sigma=0); only within-conference team-level noise.
            strengths = {t: float(np.exp(rng.normal(0, TEAM_LOG_SIGMA))) for t in teams}

            sim = simulate_season(schedule, strengths, rng)
            models = fit_all(sim)

            for name, model in models.items():
                team_ratings = pd.Series({t: model.ratings.get(t, np.nan) for t in teams})
                conf_series = pd.Series({t: conf_map[t] for t in teams})
                conf_means = team_ratings.groupby(conf_series).mean()
                # normalize by the field's own rating std so this is
                # comparable in scale across NPI/KRACH/RPI/Massey
                overall_std = team_ratings.std()
                between_conf_std = conf_means.std()
                normalized_clustering = between_conf_std / overall_std if overall_std > 0 else np.nan

                rows.append({
                    'cross_frac': cross_frac, 'rep': rep, 'model': name,
                    'between_conf_std': between_conf_std, 'overall_std': overall_std,
                    'normalized_clustering': normalized_clustering,
                })

        print(f"  cross_frac={cross_frac} done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e18_echo_chamber", "results.csv"), index=False)

    print(f"\n=== Normalized conference clustering (between-conf std / overall std) ===")
    print("(true world: EVERY conference has EQUAL strength -- any nonzero clustering is a network artifact)")
    pivot = results.groupby(['cross_frac', 'model'])['normalized_clustering'].mean().unstack()
    print(pivot)

    return results


if __name__ == "__main__":
    main()
