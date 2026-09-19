"""
S6 DGP-verification: does the connectivity/degenerate-case finding
(reports/e11_connectivity_degenerate_cases.md -- KRACH's field-spread
ratio hits ~875,000x for an undefeated/winless team, vs. NPI/RPI's
~1.7x) survive under simulate_season_bradley_terry() instead of
simulate_season()'s independent-Poisson-goals process?

reports/e15_dgp_robustness.md argued, but did not directly verify, that
this finding should be DGP-independent: it's a property of KRACH's
iterative MLE fitting procedure applied to a given win/loss record, not
of how that record was generated. This experiment checks that argument
directly rather than leave it as an assumption -- exactly the standard
this workspace held E1/S9 to.

Identical design to e11_connectivity_degenerate_cases.py: force one
real team undefeated and a different one winless, fit all four models
on baseline and forced seasons, measure the extreme team's own rating
and collateral distortion to the rest of the field -- only the
outcome-generating process is swapped.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e16_connectivity_bt_dgp
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import assign_true_strengths, simulate_season_bradley_terry, games_played
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 100


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


def force_result(df, team, win):
    """Force every game involving `team` to a win (or loss) for that
    team, adjusting goals minimally so the margin is decisive (>=1) and
    IsOT is cleared -- a clean, unambiguous decisive result in every
    game, not just a Result-column override that would leave Massey's
    goal-margin fit looking at a contradictory (still-tied) scoreline."""
    df = df.copy()
    mask = (df.HomeTeam == team) | (df.AwayTeam == team)
    is_home = df['HomeTeam'] == team
    for idx in df[mask].index:
        h, a = df.loc[idx, 'HomeGoals'], df.loc[idx, 'AwayGoals']
        team_is_home = is_home[idx]
        team_should_win = win
        if team_is_home:
            if team_should_win and h <= a:
                h = a + 1
            elif not team_should_win and a <= h:
                a = h + 1
        else:
            if team_should_win and a <= h:
                a = h + 1
            elif not team_should_win and h <= a:
                h = a + 1
        df.loc[idx, 'HomeGoals'] = h
        df.loc[idx, 'AwayGoals'] = a
        df.loc[idx, 'IsOT'] = False
        df.loc[idx, 'GoalMargin'] = h - a
        df.loc[idx, 'Result'] = 1.0 if h > a else 0.0
    return df


def fit_all(sim):
    npi, krach, rpi = NPI(sim), KRACH(sim), RPI(sim)
    massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
    for m in (npi, krach, rpi, massey):
        m.fit()
    return {'NPI': npi, 'KRACH': krach, 'RPI': rpi, 'Massey': massey}


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    gp = games_played(schedule)
    median_games_teams = gp[(gp >= 35) & (gp <= 37)].index.tolist()
    undefeated_team = median_games_teams[0]
    winless_team = median_games_teams[1]
    print(f"Forcing {undefeated_team} undefeated ({int(gp[undefeated_team])} games) "
          f"and {winless_team} winless ({int(gp[winless_team])} games)")

    rng = np.random.default_rng(31337)
    extreme_rows = []
    collateral_rows = []
    printed_example = False

    for rep in range(N_REPLICATIONS):
        strengths = assign_true_strengths(teams, rng)
        sim_baseline = simulate_season_bradley_terry(schedule, strengths, rng)
        sim_forced = force_result(sim_baseline, undefeated_team, win=True)
        sim_forced = force_result(sim_forced, winless_team, win=False)

        base_models = fit_all(sim_baseline)
        forced_models = fit_all(sim_forced)

        for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
            r_undef = forced_models[name].ratings.get(undefeated_team, float('nan'))
            r_winless = forced_models[name].ratings.get(winless_team, float('nan'))
            rk_undef = rank_of(forced_models[name].ratings, undefeated_team, teams)
            rk_winless = rank_of(forced_models[name].ratings, winless_team, teams)
            all_ratings = np.array(list(forced_models[name].ratings.values()))
            spread = np.nanmax(all_ratings) / max(np.nanmin(all_ratings[all_ratings > 0]), 1e-9) \
                if np.any(all_ratings > 0) else float('nan')

            extreme_rows.append({
                'rep': rep, 'model': name,
                'undefeated_rating': r_undef, 'undefeated_rank': rk_undef,
                'winless_rating': r_winless, 'winless_rank': rk_winless,
                'is_finite': np.isfinite(r_undef) and np.isfinite(r_winless),
                'field_spread_ratio': spread,
            })

            # Collateral distortion: for every OTHER team, how much did
            # its rank shift between baseline and forced?
            for team in teams:
                if team in (undefeated_team, winless_team):
                    continue
                rk_before = rank_of(base_models[name].ratings, team, teams)
                rk_after = rank_of(forced_models[name].ratings, team, teams)
                collateral_rows.append({
                    'rep': rep, 'model': name, 'team': team,
                    'rank_before': rk_before, 'rank_after': rk_after,
                    'abs_shift': abs(rk_after - rk_before),
                })

        if not printed_example and rep == 7:
            printed_example = True
            print(f"\n=== Concrete example: replication {rep} ===")
            for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
                r_undef = forced_models[name].ratings.get(undefeated_team)
                r_winless = forced_models[name].ratings.get(winless_team)
                rk_undef = rank_of(forced_models[name].ratings, undefeated_team, teams)
                rk_winless = rank_of(forced_models[name].ratings, winless_team, teams)
                print(f"  {name}: {undefeated_team} (undefeated) rating={r_undef:.4g} rank={rk_undef}  |  "
                      f"{winless_team} (winless) rating={r_winless:.4g} rank={rk_winless}")

        if (rep + 1) % 20 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    extreme_df = pd.DataFrame(extreme_rows)
    collateral_df = pd.DataFrame(collateral_rows)
    extreme_df.to_csv(results_path("e16_connectivity_bt_dgp", "extreme_team_ratings.csv"), index=False)
    collateral_df.to_csv(results_path("e16_connectivity_bt_dgp", "collateral_distortion.csv"), index=False)

    print(f"\n=== Extreme-team rating summary, {N_REPLICATIONS} replications ===")
    print(extreme_df.groupby('model').agg(
        pct_finite=('is_finite', lambda s: s.mean() * 100),
        mean_undefeated_rating=('undefeated_rating', 'mean'),
        max_undefeated_rating=('undefeated_rating', 'max'),
        mean_winless_rating=('winless_rating', 'mean'),
        min_winless_rating=('winless_rating', 'min'),
        mean_field_spread_ratio=('field_spread_ratio', 'mean'),
        max_field_spread_ratio=('field_spread_ratio', 'max'),
    ))

    print(f"\n=== Collateral distortion to the OTHER {len(teams)-2} teams (rank shift, baseline vs. forced) ===")
    print(collateral_df.groupby('model')['abs_shift'].agg(mean='mean', std='std', max='max',
                                                            pct_shifted_5plus=lambda s: (s >= 5).mean() * 100))


if __name__ == "__main__":
    main()
