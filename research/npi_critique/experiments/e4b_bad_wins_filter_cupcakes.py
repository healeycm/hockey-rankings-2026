"""
S4, corrected design. e4's first two attempts both failed to trigger the
bad-wins filter meaningfully, for two different reasons now understood:
(1) Denver's real NCHC schedule is strong and homogeneous; (2) switching
to Sacred Heart's real Atlantic Hockey schedule did nothing either,
because that run used IID true strengths for every team -- the
"Atlantic Hockey" conference label carried no actual weakness in the
simulation, so it was cosmetic, not a real fix. Confirmed error, not
guessed: `assign_true_strengths` draws every team's strength
independently regardless of conference, so relabeling the target team's
conference changes nothing about its opponents' actual strength
distribution.

This version fixes the actual problem directly: it PLANTS a small,
fixed number of genuinely weak "cupcake" opponents onto the target
team's real schedule (true strength well below the field median), and
explicitly protects those specific games from being dropped during
schedule-thinning (reusing `thin_team_schedule`'s `protect_teams`
mechanism already built for S1). This guarantees the target has some
genuinely droppable wins available in BOTH the long and short schedule
conditions -- isolating the actual question (does having MORE total wins,
letting the win count cross the 12-mandatory floor, let the filter drop
MORE of those already-available weak wins) from whether weak opponents
exist on the schedule at all.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e4b_bad_wins_filter_cupcakes
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.npi_games import NPIGames
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from research.npi_critique.harness.simulate import (
    simulate_season, true_ranking, thin_team_schedule, games_played,
)
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 150
TARGET_TEAM = 'Sacred Heart'   # real 40-game schedule
TARGET_STRENGTH = 1.0          # ~field median, a bubble-caliber team
CUPCAKE_STRENGTH = 0.30        # deliberately, unambiguously weak
N_CUPCAKES = 5                 # number of the target's real opponents planted this weak
LONG_GAMES = 40
SHORT_GAMES = 25


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


def count_wins(sim_df, team):
    g = sim_df[(sim_df.HomeTeam == team) | (sim_df.AwayTeam == team)]
    won = (g['Result'] == 1.0) == (g['HomeTeam'] == team)
    return int(won.sum()), len(g)


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    gp = games_played(schedule)
    print(f"Target: {TARGET_TEAM} ({int(gp[TARGET_TEAM])} real games)")

    target_games = schedule[(schedule.HomeTeam == TARGET_TEAM) | (schedule.AwayTeam == TARGET_TEAM)]
    opponents = pd.unique(np.where(target_games.HomeTeam == TARGET_TEAM,
                                    target_games.AwayTeam, target_games.HomeTeam))
    rng_setup = np.random.default_rng(55)
    cupcakes = list(rng_setup.choice(opponents, size=min(N_CUPCAKES, len(opponents)), replace=False))
    print(f"Planted cupcakes (true strength {CUPCAKE_STRENGTH}): {cupcakes}")

    other_rng = np.random.default_rng(0)
    rng = np.random.default_rng(42)
    rows = []

    for rep in range(N_REPLICATIONS):
        strengths = {t: float(v) for t, v in zip(teams, other_rng.lognormal(0.0, 0.4, size=len(teams)))}
        strengths[TARGET_TEAM] = TARGET_STRENGTH
        for c in cupcakes:
            strengths[c] = CUPCAKE_STRENGTH
        true_rank = true_ranking(strengths).index(TARGET_TEAM) + 1

        sim_full = simulate_season(schedule, strengths, rng)
        # Protect only a FRACTION-matched subset of cupcakes per
        # condition, not the full fixed count in both -- protecting all
        # N_CUPCAKES regardless of target length was a real confound
        # (caught by inspecting mean_wins/win-rate directly): it made
        # the short schedule disproportionately cupcake-concentrated
        # (5/25=20% vs 5/40=12.5%), inflating its win rate and biasing
        # EVERY model's rank comparison in the same direction, not just
        # NPIGames'. Holding the cupcake FRACTION constant instead keeps
        # win-rate comparable across conditions, isolating the actual
        # question (does crossing the 12-win floor unlock more dropping)
        # from this artifact.
        cupcake_frac = len(cupcakes) / LONG_GAMES
        n_cupcakes_short = max(1, round(cupcake_frac * SHORT_GAMES))
        cupcakes_short = cupcakes[:n_cupcakes_short]

        sim_long = thin_team_schedule(sim_full, TARGET_TEAM, LONG_GAMES, rng,
                                       prefer_type='nc', protect_teams=cupcakes)
        sim_short = thin_team_schedule(sim_full, TARGET_TEAM, SHORT_GAMES, rng,
                                        prefer_type='nc', protect_teams=cupcakes_short)

        for label, sim in [('long', sim_long), ('short', sim_short)]:
            wins, played = count_wins(sim, TARGET_TEAM)
            cupcake_wins = sum(
                1 for c in cupcakes
                if len(sim[((sim.HomeTeam == TARGET_TEAM) & (sim.AwayTeam == c) & (sim.Result == 1.0)) |
                           ((sim.AwayTeam == TARGET_TEAM) & (sim.HomeTeam == c) & (sim.Result == 0.0))]) > 0
            )

            npi, npig, krach = NPI(sim), NPIGames(sim), KRACH(sim)
            massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
            for m in (npi, npig, krach, massey):
                m.fit()

            dropped = npig.details.get(TARGET_TEAM, {}).get('dropped_wins', 0)
            for name, model in [('NPI', npi), ('NPIGames', npig), ('KRACH', krach), ('Massey', massey)]:
                rows.append({
                    'rep': rep, 'schedule': label, 'model': name,
                    'games_played': played, 'wins': wins, 'cupcake_wins_available': cupcake_wins,
                    'true_rank': true_rank, 'induced_rank': rank_of(model.ratings, TARGET_TEAM, teams),
                    'dropped_wins': dropped if name == 'NPIGames' else np.nan,
                })

        if (rep + 1) % 40 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e4b_bad_wins_filter_cupcakes", "results.csv"), index=False)

    print(f"\n=== (a) NPIGames' dropped-wins count, by schedule length ===")
    dw = results[results.model == 'NPIGames'].groupby('schedule').agg(
        mean_games=('games_played', 'mean'), mean_wins=('wins', 'mean'),
        mean_cupcake_wins=('cupcake_wins_available', 'mean'),
        mean_dropped=('dropped_wins', 'mean'),
        pct_any_dropped=('dropped_wins', lambda s: (s > 0).mean() * 100),
    )
    print(dw)

    print(f"\n=== (b) Rank gained by going from 'short' to 'long' schedule, per model ===")
    piv = results.pivot_table(index=['rep', 'model'], columns='schedule', values='induced_rank').reset_index()
    piv['gain'] = piv['short'] - piv['long']
    print(piv.groupby('model')['gain'].agg(mean='mean', std='std', pct_gained=lambda s: (s > 0).mean() * 100))

    return results


if __name__ == "__main__":
    main()
