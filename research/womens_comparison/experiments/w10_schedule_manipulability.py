# research/womens_comparison/experiments/w10_schedule_manipulability.py
"""
W10 (PLAN.md) -- can a team raise its rank WITHOUT getting any better,
purely by whom it plays? Direct women's-data counterpart to the men's
S8/E12 (research/npi_critique/experiments/e12_schedule_manipulability.py),
which found RPI is the field's worst offender, not NPI, by a wide margin.

Same hybrid design as E12, reused via the shared, already-parameterized
simulation harness (research/npi_critique/harness/simulate.py -- imported
read-only, per this workspace's README): a real season's SCHEDULE
STRUCTURE (dates, home/away assignment) is held fixed for one target team,
but its opponent on each date is redrawn from a specific true-strength
percentile band, and outcomes are SIMULATED from known ground truth (real
data can't test this -- a team can't be re-run on a counterfactual
schedule). "Schedule alpha": the fitted slope of a model's induced rank
for the target vs. mean opponent strength, holding the target's own true
strength fixed throughout. Alpha near zero = opponent-strength-adjusted as
it should be; a clearly nonzero alpha = the model credits schedule
strength beyond what the target's own unchanged ability justifies.

Women's-specific choices:
- Target team: games_archive shows women's teams average ~36 games/season,
  same range as men's -- so the same target-selection rule (a team with
  35-37 real games) applies unchanged, no re-derivation needed.
- NPI uses the corrected women's dials from P0.3 (config.yaml's
  npi_women), not men's defaults.
- N_REPLICATIONS = 150, matching men's E12 exactly (women's field is
  smaller, so each replication is proportionally cheaper -- 150 reps here
  run in well under a minute) for a direct, same-sample-size comparison of
  alpha magnitudes between divisions.

Run from the project root as a module:
    python -m research.womens_comparison.experiments.w10_schedule_manipulability
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.krach import KRACH
from src.rankings.rpi import RPI
from research.npi_critique.harness.simulate import (
    simulate_season, true_ranking, games_played,
)
from research.womens_comparison.harness.women_npi import (
    fit_npi as fit_npi_women, fit_massey as fit_massey_women, npi_women_config,
)
from src.rankings.npi import NPI
from src.rankings.massey import Massey
from src.rankings.base_ranker import using_di_team_path
from research.womens_comparison.harness.paths import results_path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WOMENS_TEAM_INFO = PROJECT_ROOT / "data" / "teams" / "team_info_women.csv"
N_REPLICATIONS = 150
TARGET_STRENGTH = 1.0
PERCENTILE_BANDS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "women" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(WOMENS_TEAM_INFO)
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def rank_of(ratings, team, teams):
    order = sorted(teams, key=lambda t: ratings.get(t, -np.inf), reverse=True)
    return order.index(team) + 1


def build_schedule_with_opponent_pool(schedule, target, opponent_pool, rng):
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
    """Fits all 4 models on a SIMULATED women's season. NPI/KRACH/Massey
    need the DI-team-path context for women's; RPI too (all BaseRanker
    subclasses). This deliberately does NOT reuse women_npi.py's fit_npi/
    fit_massey wrappers for KRACH/RPI (they don't have women's equivalents
    there -- only NPI's dials differ by division) but DOES reuse them for
    NPI/Massey so the exact same corrected config is used everywhere in
    this workspace."""
    with using_di_team_path(WOMENS_TEAM_INFO):
        krach = KRACH(sim)
        rpi = RPI(sim)
        krach.fit()
        rpi.fit()
    npi = fit_npi_women(sim)  # already wrapped in using_di_team_path + npi_women config
    massey = fit_massey_women(sim)
    return {'NPI': npi, 'KRACH': krach, 'RPI': rpi, 'Massey': massey}


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    gp = games_played(schedule)
    candidates = gp[(gp >= 35) & (gp <= 37)]
    if candidates.empty:
        candidates = gp[(gp >= 33) & (gp <= 39)]
    target = candidates.index[0]
    print(f"Target: {target} ({int(gp[target])} real games, schedule structure/dates held fixed throughout)")
    print(f"Field: {len(teams)} teams")

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

        if (rep + 1) % 20 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    results = pd.DataFrame(rows)
    out_path = results_path("w10_schedule_manipulability", "results.csv")
    results.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    print(f"\n=== Mean induced rank by opponent-strength band, per model ({N_REPLICATIONS} reps) ===")
    print(f"(true rank held constant at ~{results['true_rank'].mean():.1f} throughout -- true strength never changes)")
    pivot = results.groupby(['band', 'model'])['induced_rank'].mean().unstack()
    print(pivot.reindex(['0-20', '20-40', '40-60', '60-80', '80-100']))

    print(f"\n=== Schedule alpha: slope of induced rank vs. mean opponent strength (OLS, per model) ===")
    alphas = {}
    for name in ['NPI', 'KRACH', 'RPI', 'Massey']:
        sub = results[results.model == name]
        slope, intercept = np.polyfit(sub['mean_opp_strength'], sub['induced_rank'], 1)
        # Standard error of the slope, for honesty about precision at a
        # reduced replication count relative to the men's version.
        resid = sub['induced_rank'] - (slope * sub['mean_opp_strength'] + intercept)
        x = sub['mean_opp_strength']
        se = np.sqrt((resid ** 2).sum() / (len(x) - 2)) / np.sqrt(((x - x.mean()) ** 2).sum())
        alphas[name] = (slope, se)
        print(f"  {name}: alpha = {slope:+.3f} +/- {se:.3f} rank positions per unit of mean opponent strength")

    return results, alphas


if __name__ == "__main__":
    main()
