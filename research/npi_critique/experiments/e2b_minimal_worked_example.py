"""
S1, minimal worked example: the same games-played-mismatch question as
e2_games_played_mismatch.py, but on a small (12-team) fully synthetic
round-robin league instead of the real 63-team schedule -- small enough
that one specific replication's entire schedule and results can be
printed and hand-verified, per PLAN.md's "named minimal example"
reporting standard. Complements, does not replace, the large-N result in
e2_games_played_mismatch.py.

12 teams, every pair plays home-and-home (22 games/team baseline). Two
middling-strength teams get cut to 14 games (a deliberately more
aggressive ~36% cut than the real ~14% Yale/Brown cut, chosen to make the
mechanism visible in a system this small -- not meant to be a realistic
proportion match).

Run from the project root as a module:
    python -m research.npi_critique.experiments.e2b_minimal_worked_example
"""
import numpy as np
import pandas as pd

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from research.npi_critique.harness.simulate import (
    make_round_robin_schedule, simulate_season, true_ranking, thin_multiple_teams, games_played,
)
from research.npi_critique.harness.paths import results_path

N_TEAMS = 12
TEAMS = [f"Team{i:02d}" for i in range(1, N_TEAMS + 1)]
THINNED_TEAMS = ["Team06", "Team07"]   # deliberately mid-strength, not the best/worst
TARGET_GAMES = 14                       # from 22 -> 14, a 36% cut
N_REPLICATIONS = 2000


def rank_of(ratings, team, teams):
    order = sorted(teams, key=lambda t: ratings.get(t, -np.inf), reverse=True)
    return order.index(team) + 1


def true_rank_of(true_strength, team, teams):
    return true_ranking(true_strength).index(team) + 1


def fixed_true_strengths():
    """Deterministic, evenly log-spaced strengths -- fixed across all
    replications, so every replication is a fresh random *outcome* draw
    from the SAME known truth, not a fresh truth each time. This isolates
    outcome-luck as the only source of variation, which is exactly what
    the "1-2 lucky results" concern is about."""
    log_vals = np.linspace(-0.8, 0.8, N_TEAMS)
    return {t: float(np.exp(v)) for t, v in zip(TEAMS, log_vals)}


def main():
    schedule = make_round_robin_schedule(TEAMS, games_per_pair=2)
    print(f"Synthetic league: {N_TEAMS} teams, {len(schedule)} games "
          f"({len(schedule) // N_TEAMS if False else 2 * (N_TEAMS - 1)} games/team baseline)")

    strengths = fixed_true_strengths()
    truth = true_ranking(strengths)
    print(f"True ranking (strongest first): {truth}")
    for t in THINNED_TEAMS:
        print(f"  {t}: true strength {strengths[t]:.3f}, true rank {true_rank_of(strengths, t, TEAMS)}")

    rng = np.random.default_rng(555)
    rows = []
    printed_example = False

    for rep in range(N_REPLICATIONS):
        sim_full = simulate_season(schedule, strengths, rng)
        sim_thin = thin_multiple_teams(sim_full, {t: TARGET_GAMES for t in THINNED_TEAMS}, rng, prefer_type='nc')

        models_full = {'NPI': NPI(sim_full), 'KRACH': KRACH(sim_full),
                       'Massey': Massey(sim_full, config={'fit_home_ice': True, 'fit_beta': False})}
        models_thin = {'NPI': NPI(sim_thin), 'KRACH': KRACH(sim_thin),
                       'Massey': Massey(sim_thin, config={'fit_home_ice': True, 'fit_beta': False})}
        for m in list(models_full.values()) + list(models_thin.values()):
            m.fit()

        for team in THINNED_TEAMS:
            for name in models_full:
                rf = rank_of(models_full[name].ratings, team, TEAMS)
                rt = rank_of(models_thin[name].ratings, team, TEAMS)
                rows.append({'rep': rep, 'team': team, 'model': name,
                             'rank_full': rf, 'rank_thinned': rt, 'delta': rt - rf})

        # Print ONE fully concrete, hand-checkable replication in full.
        if not printed_example and rep == 42:
            printed_example = True
            print(f"\n=== Concrete example: replication {rep} ===")
            # Match games by identity (HomeTeam, AwayTeam, Date), not raw
            # index -- thin_team_schedule resets the index on every drop,
            # so comparing indices between sim_full and sim_thin directly
            # compares two incompatible label sets and silently produces a
            # meaningless "dropped" list (caught while writing this fix).
            key_cols = ['HomeTeam', 'AwayTeam', 'Date']
            gp_full_check = games_played(sim_full)
            gp_thin_check = games_played(sim_thin)
            for team in THINNED_TEAMS:
                team_games = sim_full[(sim_full.HomeTeam == team) | (sim_full.AwayTeam == team)]
                print(f"\n{team}'s full {int(gp_full_check[team])}-game results "
                      f"(Result=1.0 means {team} won as listed):")
                for _, g in team_games.iterrows():
                    print(f"  {g['Date'].date()}  {g['HomeTeam']:>8s} {int(g['HomeGoals'])}-{int(g['AwayGoals'])} "
                          f"{g['AwayTeam']:<8s} {'(OT)' if g['IsOT'] else ''}")
                thinned_keys = set(map(tuple, sim_thin[key_cols].values.tolist()))
                dropped_rows = team_games[~team_games[key_cols].apply(tuple, axis=1).isin(thinned_keys)]
                dropped_desc = [f"{r['HomeTeam']} vs {r['AwayTeam']}" for _, r in dropped_rows.iterrows()]
                n_after = int(gp_thin_check.get(team, 0))
                print(f"  --> {len(dropped_desc)} games dropped, {n_after} remain (target {TARGET_GAMES}): {dropped_desc}")
                for name in ['NPI', 'KRACH', 'Massey']:
                    rf = rank_of({**{k: v.ratings for k, v in models_full.items()}[name]}, team, TEAMS)
                    rt = rank_of({**{k: v.ratings for k, v in models_thin.items()}[name]}, team, TEAMS)
                    print(f"  {name}: rank {rf} ({int(gp_full_check[team])} games) -> "
                          f"rank {rt} ({n_after} games), true rank {true_rank_of(strengths, team, TEAMS)}")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e2b_minimal_worked_example", "delta_rank.csv"), index=False)

    print(f"\n=== Summary across {N_REPLICATIONS} replications, {N_TEAMS}-team synthetic league ===")
    print(results.groupby('model')['delta'].agg(
        mean='mean', std='std',
        pct_worse=lambda s: (s > 0).mean() * 100,
        p95_abs=lambda s: s.abs().quantile(0.95),
        worst=lambda s: s.max(), best=lambda s: s.min(),
    ))


if __name__ == "__main__":
    main()
