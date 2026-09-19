"""
S1: games-played mismatch (research/npi_critique/PLAN.md).

Real 2025-26 DI schedule spans 30-41 games/team (verified in PLAN.md);
Ivy teams (Yale/Brown 31, Princeton 33, Harvard/Cornell/Dartmouth 34) sit
at the short end, but so do non-Ivy independents (Alaska 33, LIU 32,
Lindenwood 30). Does playing fewer games systematically distort a team's
rating, holding true strength fixed?

Design (causal, ceteris paribus): simulate a full season once (every
scheduled game gets a realized outcome from known true strength). Fit
every model on that full realization -- this is the "full schedule"
rating. Then, for a set of teams chosen at random (independent of true
strength, removing the confound that real short-schedule teams might
also differ in true strength), drop a subset of their ALREADY-REALIZED
games down to a target count and refit -- the "thinned schedule" rating.
Because the underlying random outcomes are identical between the two
conditions (only which already-realized games are visible to the fit
differs), any change in rank is attributable to games-played alone, not
to redrawn randomness.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e2_games_played_mismatch
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from research.npi_critique.harness.simulate import (
    assign_true_strengths, simulate_season, true_ranking,
    thin_multiple_teams, games_played,
)
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 200
N_TEAMS_TO_THIN = 8          # matches the real Ivy-ish short-schedule count
TARGET_GAMES = 31            # matches Yale/Brown's real 2025-26 count


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
    return order.index(team) + 1  # 1-indexed, 1 = best


def true_rank_of(true_strength, team, teams):
    order = true_ranking(true_strength)
    return order.index(team) + 1


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    rng = np.random.default_rng(777)

    gp_full = games_played(schedule)
    eligible_for_thinning = [t for t in teams if gp_full.get(t, 0) > TARGET_GAMES]
    print(f"{len(eligible_for_thinning)}/{len(teams)} teams have > {TARGET_GAMES} games "
          f"and are eligible to be thinned down to it.")

    rows = []

    for rep in range(N_REPLICATIONS):
        strengths = assign_true_strengths(teams, rng)
        sim_full = simulate_season(schedule, strengths, rng)

        # Random selection of teams to thin, independent of true strength.
        thin_targets = rng.choice(eligible_for_thinning, size=N_TEAMS_TO_THIN, replace=False)
        sim_thinned = thin_multiple_teams(
            sim_full, {t: TARGET_GAMES for t in thin_targets}, rng, prefer_type='nc'
        )
        thinned_gp = games_played(sim_thinned)
        off_target = {t: int(thinned_gp.get(t, 0)) for t in thin_targets
                      if int(thinned_gp.get(t, 0)) != TARGET_GAMES}
        if off_target:
            print(f"  [rep {rep}] WARNING: thinning missed target for {off_target} "
                  f"(protection fallback likely triggered -- see thin_team_schedule docstring)")

        models_full = {
            'NPI': NPI(sim_full), 'KRACH': KRACH(sim_full),
            'Massey': Massey(sim_full, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False}),
        }
        models_thinned = {
            'NPI': NPI(sim_thinned), 'KRACH': KRACH(sim_thinned),
            'Massey': Massey(sim_thinned, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False}),
        }
        for m in models_full.values():
            m.fit()
        for m in models_thinned.values():
            m.fit()

        for team in thin_targets:
            true_rk = true_rank_of(strengths, team, teams)
            actual_games_after_thin = int(thinned_gp.get(team, 0))
            for model_name in models_full:
                rk_full = rank_of(models_full[model_name].ratings, team, teams)
                rk_thin = rank_of(models_thinned[model_name].ratings, team, teams)
                rows.append({
                    'rep': rep, 'team': team, 'model': model_name,
                    'true_rank': true_rk,
                    'games_before': int(gp_full.get(team, 0)),
                    'games_after': actual_games_after_thin,
                    'rank_full': rk_full, 'rank_thinned': rk_thin,
                    'delta_rank': rk_thin - rk_full,  # positive = got WORSE after fewer games
                })

        if (rep + 1) % 40 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} replications done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e2_games_played_mismatch", "delta_rank_by_model.csv"), index=False)

    print(f"\n=== S1: effect of thinning {N_TEAMS_TO_THIN} teams to {TARGET_GAMES} games "
          f"({N_REPLICATIONS} replications, {len(results)} team-model observations) ===\n")
    summary = results.groupby('model')['delta_rank'].agg(
        mean='mean', std='std',
        pct_worse=lambda s: (s > 0).mean() * 100,
        pct_better=lambda s: (s < 0).mean() * 100,
        p95_abs=lambda s: s.abs().quantile(0.95),
        worst=lambda s: s.max(),
    )
    print(summary)

    print("\n=== Worst single case per model (largest rank swing from thinning alone) ===")
    for model_name in results['model'].unique():
        sub = results[results['model'] == model_name]
        worst = sub.loc[sub['delta_rank'].idxmax()]
        print(f"  {model_name}: rep {int(worst['rep'])}, team true-rank {int(worst['true_rank'])}, "
              f"games {int(worst['games_before'])}->{int(worst['games_after'])}, "
              f"rank {int(worst['rank_full'])}->{int(worst['rank_thinned'])} "
              f"(Delta={int(worst['delta_rank'])})")

    return results, summary


if __name__ == "__main__":
    main()
