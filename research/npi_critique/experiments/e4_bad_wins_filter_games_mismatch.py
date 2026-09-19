"""
S4 (raised in priority after S1): does the bad-wins filter specifically
-- not just games-played mismatch in general, which e2 already found no
unique NPI bias from -- give a longer-schedule team an unearned
advantage? `NPIGames` (src/rankings/npi_games.py) implements the REAL
official mechanism: only a team's 12 best regulation wins are mandatory
(`regulation_wins[:12]`); anything beyond the 12th-best is "optional" and
gets dropped unless it improves the team's rating
(`optional_set = regulation_wins[12:]`). This directly ties games played
to filter benefit: a team needs strictly MORE than 12 wins before the
filter can drop anything at all. A short-schedule team hovering around
10-12 wins gets zero filtering benefit; a long-schedule team with 18-20
wins has up to 6-8 droppable wins to selectively exclude.

This experiment measures that mechanism two ways:
  (a) Directly, mechanically: for a fixed win RATE (not fixed strength --
      see below), does the number of wins NPIGames actually drops grow
      with games played? This is a fact about the filter's own behavior,
      assertable causally regardless of any model comparison.
  (b) Comparatively: same games-played-thinning causal design as
      e2_games_played_mismatch.py, but with NPIGames added alongside
      NPI/KRACH/Massey, to see whether NPIGames' rank/rating responds
      differently to games-played thinning than the other three do.

True strength is chosen to target a ~50% win rate (a "bubble" team) --
low enough that going from ~40 games to ~25 keeps the team's win count
straddling the 12-win mandatory floor, which is exactly the regime where
(a) predicts the filter's effect should appear or disappear.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e4_bad_wins_filter_games_mismatch
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
N_REPLICATIONS = 30
TARGET_TEAM_STRENGTH = 1.0   # ~field median -> roughly a .500 team
LONG_GAMES = 40              # near the real max (Denver: 41)
SHORT_GAMES = 25             # deliberately below 12*2=24-ish decisive-game floor headroom,
                              # to guarantee the short version can plausibly sit AT/BELOW 12 wins
TARGET_TEAM_OVERRIDE = 'Sacred Heart'  # real 40-game Atlantic Hockey (weak-conference) schedule;
                                        # None reverts to the original Denver/NCHC design


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
    # First pass used Denver (gp.idxmax(), NCHC -- a strong, homogeneous
    # conference) and found the filter almost never triggers. Per
    # reports/e4_bad_wins_filter_games_mismatch.md's own recommendation,
    # re-run with a team that has the same thinning headroom (>=40 real
    # games) but plays a weaker, more heterogeneous conference (Atlantic
    # Hockey) instead -- more likely to have genuine mismatch games on
    # its real schedule for the filter to have anything to act on.
    target_team = TARGET_TEAM_OVERRIDE or gp.idxmax()
    print(f"Target team (uses {target_team}'s real schedule, thinned to {SHORT_GAMES} and "
          f"{LONG_GAMES} games): baseline {int(gp[target_team])} real games")

    other_strengths_rng = np.random.default_rng(0)
    rng = np.random.default_rng(42)
    rows = []

    for rep in range(N_REPLICATIONS):
        strengths = {t: float(v) for t, v in zip(
            teams, other_strengths_rng.lognormal(0.0, 0.4, size=len(teams)))}
        strengths[target_team] = TARGET_TEAM_STRENGTH
        truth = true_ranking(strengths)
        true_rank = truth.index(target_team) + 1

        sim_full = simulate_season(schedule, strengths, rng)
        sim_long = thin_team_schedule(sim_full, target_team, LONG_GAMES, rng, prefer_type='nc')
        sim_short = thin_team_schedule(sim_full, target_team, SHORT_GAMES, rng, prefer_type='nc')

        wins_long, gp_long = count_wins(sim_long, target_team)
        wins_short, gp_short = count_wins(sim_short, target_team)

        for label, sim in [('long', sim_long), ('short', sim_short)]:
            npi, npig, krach = NPI(sim), NPIGames(sim), KRACH(sim)
            massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
            for m in (npi, npig, krach, massey):
                m.fit()

            dropped = npig.details.get(target_team, {}).get('dropped_wins', 0)
            wins, played = (wins_long, gp_long) if label == 'long' else (wins_short, gp_short)

            for name, model in [('NPI', npi), ('NPIGames', npig), ('KRACH', krach), ('Massey', massey)]:
                rows.append({
                    'rep': rep, 'schedule': label, 'model': name,
                    'games_played': played, 'wins': wins, 'true_rank': true_rank,
                    'induced_rank': rank_of(model.ratings, target_team, teams),
                    'dropped_wins': dropped if name == 'NPIGames' else np.nan,
                })

        if (rep + 1) % 40 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e4_bad_wins_filter_games_mismatch", "results.csv"), index=False)

    print(f"\n=== (a) NPIGames' own dropped-wins count, by schedule length ===")
    dw = results[results.model == 'NPIGames'].groupby('schedule').agg(
        mean_games=('games_played', 'mean'), mean_wins=('wins', 'mean'),
        mean_dropped=('dropped_wins', 'mean'), pct_any_dropped=('dropped_wins', lambda s: (s > 0).mean() * 100),
    )
    print(dw)

    print(f"\n=== (b) Rank gained by going from 'short' to 'long' schedule, per model ===")
    piv = results.pivot_table(index=['rep', 'model'], columns='schedule', values='induced_rank').reset_index()
    piv['gain'] = piv['short'] - piv['long']  # positive = long schedule ranks better
    print(piv.groupby('model')['gain'].agg(mean='mean', std='std', pct_gained=lambda s: (s > 0).mean() * 100))

    return results


if __name__ == "__main__":
    main()
