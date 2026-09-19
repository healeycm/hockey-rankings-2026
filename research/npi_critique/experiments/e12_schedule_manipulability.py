"""
S8: schedule manipulability -- can a team raise its rank WITHOUT getting
any better, purely by whom it plays? This is impossible to test with
real data (teams can't be re-run on a counterfactual schedule) and is
arguably the sharpest available result in this whole critique battery:
if a metric's induced rank for a team of FIXED true strength depends
systematically on the strength of its opponent pool, that metric
rewards athletic-department scheduling decisions, not on-ice
performance.

Design: fix one target team's true strength at the field median
throughout. Build five alternative schedules for it, holding its total
games played constant (its real 2025-26 game count) -- for each of its
real scheduled games (same dates, same home/away assignment), replace
the opponent with a team drawn from a specific TRUE-STRENGTH PERCENTILE
BAND (0-20, 20-40, 40-60 [~its real schedule's actual mix], 60-80,
80-100), leaving every other team's schedule untouched except for the
substitute-opponent bookkeeping noted below. The target's resulting
win-loss record necessarily changes with opponent strength (a fixed-
ability team beats weak opponents more often) -- that's expected and
correct; the question is whether its INDUCED RANK moves by more than
its unchanged true strength justifies, which we can check directly
because ground truth is known.

"Schedule alpha": the fitted slope of induced rank vs. mean opponent
strength, holding the target's own true strength fixed. A perfectly
opponent-strength-adjusted method (in principle, KRACH) should show
alpha near zero; a method whose formula credits schedule strength more
than it should (candidate: NPI) should show a clearly nonzero slope.

Caveat, stated directly: substitute opponents gain one extra game
against the target beyond their own real schedule for each date they're
drawn (their original opponent for that date loses that specific game
instead) -- a minor, documented bookkeeping side effect of holding the
target's schedule structure exactly fixed while only relabeling who it
plays, not a source of bias in the target's own measured rank.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e12_schedule_manipulability
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import assign_true_strengths, simulate_season, true_ranking, games_played
from research.npi_critique.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 150
TARGET_STRENGTH = 1.0  # field median, fixed throughout
PERCENTILE_BANDS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]


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


def build_schedule_with_opponent_pool(schedule, target, opponent_pool, rng):
    """Same dates/home-away assignment as the target's real schedule;
    opponent on each date redrawn (with replacement) from opponent_pool."""
    df = schedule.copy()
    mask = (df.HomeTeam == target) | (df.AwayTeam == target)
    target_rows = df[mask].index
    new_opponents = rng.choice(opponent_pool, size=len(target_rows), replace=True)
    for i, idx in enumerate(target_rows):
        if df.loc[idx, 'HomeTeam'] == target:
            df.loc[idx, 'AwayTeam'] = new_opponents[i]
        else:
            df.loc[idx, 'HomeTeam'] = new_opponents[i]
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
    target = gp[(gp >= 35) & (gp <= 37)].index[0]
    print(f"Target: {target} ({int(gp[target])} real games, schedule structure/dates held fixed throughout)")

    rng = np.random.default_rng(24601)
    rows = []

    for rep in range(N_REPLICATIONS):
        other_teams = [t for t in teams if t != target]
        strengths = {t: float(v) for t, v in zip(other_teams, rng.lognormal(0.0, 0.4, size=len(other_teams)))}
        strengths[target] = TARGET_STRENGTH
        true_rank = true_ranking(strengths).index(target) + 1

        sorted_others = sorted(other_teams, key=lambda t: strengths[t])
        n = len(sorted_others)

        for lo, hi in PERCENTILE_BANDS:
            lo_i, hi_i = int(n * lo / 100), max(int(n * hi / 100), int(n * lo / 100) + 1)
            pool = sorted_others[lo_i:hi_i]
            sched_variant = build_schedule_with_opponent_pool(schedule, target, pool, rng)
            mean_opp_strength = np.mean([strengths[t] for t in pool])

            sim = simulate_season(sched_variant, strengths, rng)
            models = fit_all(sim)
            for name, model in models.items():
                rk = rank_of(model.ratings, target, teams)
                rows.append({
                    'rep': rep, 'band': f"{lo}-{hi}", 'mean_opp_strength': mean_opp_strength,
                    'model': name, 'true_rank': true_rank, 'induced_rank': rk,
                })

        if (rep + 1) % 30 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e12_schedule_manipulability", "results.csv"), index=False)

    print(f"\n=== Mean induced rank by opponent-strength band, per model ({N_REPLICATIONS} reps) ===")
    print(f"(true rank held constant at ~{results['true_rank'].mean():.1f} throughout -- true strength never changes)")
    pivot = results.groupby(['band', 'model'])['induced_rank'].mean().unstack()
    print(pivot.reindex(['0-20', '20-40', '40-60', '60-80', '80-100']))

    print(f"\n=== Schedule alpha: slope of induced rank vs. mean opponent strength (OLS, per model) ===")
    for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
        sub = results[results.model == name]
        slope, intercept = np.polyfit(sub['mean_opp_strength'], sub['induced_rank'], 1)
        print(f"  {name}: alpha = {slope:+.3f} rank positions per unit of mean opponent strength")

    return results


if __name__ == "__main__":
    main()
