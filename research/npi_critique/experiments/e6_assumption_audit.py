"""
Full audit of every simulation assumption against the last three
complete real seasons (2023-24, 2024-25, 2025-26), not just the single
season (2025-26) every prior calibration check in this workspace used.
Written in response to a direct request to restate and re-verify:
number of teams, spread (best to worst), distribution shape, conference
stratification/distribution, and win probabilities.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e6_assumption_audit
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

from research.npi_critique.harness.simulate import (
    get_conference_map, games_played, assign_true_strengths,
    assign_conference_stratified_strengths, simulate_season,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEASONS = [20232024, 20242025, 20252026]
SEASON_LABELS = {20232024: '2023-24', 20242025: '2024-25', 20252026: '2025-26'}


def load_season(season):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def team_win_pct(games_df):
    home = games_df[['HomeTeam', 'Result']].rename(columns={'HomeTeam': 'Team'})
    home['W'] = home['Result']
    away = games_df[['AwayTeam', 'Result']].rename(columns={'AwayTeam': 'Team'})
    away['W'] = 1 - away['Result']
    return pd.concat([home[['Team', 'W']], away[['Team', 'W']]]).groupby('Team')['W'].mean()


def main():
    print("=" * 80)
    print("1. NUMBER OF TEAMS")
    print("=" * 80)
    season_teams = {}
    for season in SEASONS:
        g = load_season(season)
        teams = sorted(set(g['HomeTeam']).union(g['AwayTeam']))
        season_teams[season] = teams
        print(f"  {SEASON_LABELS[season]}: {len(teams)} teams, {len(g)} games")
    all_teams_ever = set()
    for t in season_teams.values():
        all_teams_ever |= set(t)
    turnover = {s: sorted(set(season_teams[SEASONS[-1]]) ^ set(season_teams[s])) for s in SEASONS[:-1]}
    print(f"\n  Teams differing between 2025-26 and each earlier season (roster turnover):")
    for s, diff in turnover.items():
        print(f"    vs {SEASON_LABELS[s]}: {diff}")
    print(f"\n  SIMULATION ASSUMES: {len(season_teams[20252026])} teams (fixed at 2025-26's roster, "
          f"same schedule structure reused for every replication in every experiment in this workspace)")

    print("\n" + "=" * 80)
    print("2. SPREAD (BEST TO WORST) -- real win% dispersion")
    print("=" * 80)
    real_wp = {}
    for season in SEASONS:
        g = load_season(season)
        wp = team_win_pct(g)
        real_wp[season] = wp
        print(f"  {SEASON_LABELS[season]}: mean={wp.mean():.4f} std={wp.std():.4f} "
              f"min={wp.min():.4f} max={wp.max():.4f} ratio={wp.max()/max(wp.min(),1e-6):.2f}")
    print(f"\n  SIMULATION ASSUMES (iid, sigma=0.4): produces win% std ~0.175 (checked in "
          f"reports/e4_bad_wins_filter_games_mismatch.md against 2025-26's 0.158 alone)")

    print("\n" + "=" * 80)
    print("3. DISTRIBUTION SHAPE -- is real win% actually log-normal-like?")
    print("=" * 80)
    for season in SEASONS:
        wp = real_wp[season]
        skew, kurt = stats.skew(wp), stats.kurtosis(wp)
        shapiro_p = stats.shapiro(wp).pvalue
        print(f"  {SEASON_LABELS[season]}: skew={skew:+.3f} excess_kurtosis={kurt:+.3f} "
              f"Shapiro-Wilk normality p={shapiro_p:.4f}")
    print(f"\n  SIMULATION ASSUMES: true strength ~ Lognormal(0, sigma) -- right-skewed by "
          f"construction. Real win% is bounded [0,1] and directly observed, not the same object "
          f"as 'true strength', so this is a proxy comparison, not a like-for-like fit.")

    print("\n" + "=" * 80)
    print("4. CONFERENCE STRATIFICATION AND DISTRIBUTION")
    print("=" * 80)
    for season in SEASONS:
        g = load_season(season)
        conf_map = get_conference_map(g)
        sizes = pd.Series(conf_map).value_counts()
        n_independent = len(set(g['HomeTeam']).union(g['AwayTeam'])) - len(conf_map)
        print(f"  {SEASON_LABELS[season]}: conferences={dict(sizes)}, independents={n_independent}")

    print(f"\n  Between-conference vs. overall win% variance, per season (non-conference games only):")
    for season in SEASONS:
        g = load_season(season)
        conf_map = get_conference_map(g)
        conf_codes = ['ah', 'he', 'ec', 'nt', 'cc2', 'b10']
        nc = g[~g['Type'].str.lower().isin(conf_codes)]
        wp_nc = team_win_pct(nc).reset_index()
        wp_nc['conf'] = wp_nc['Team'].map(conf_map).fillna('independent')
        conf_means = wp_nc.groupby('conf')['W'].mean()
        overall_std = wp_nc['W'].std()
        between_std = conf_means.std()
        share = (between_std ** 2) / (overall_std ** 2) * 100 if overall_std > 0 else float('nan')
        print(f"    {SEASON_LABELS[season]}: between-conf std={between_std:.4f}, overall std={overall_std:.4f}, "
              f"conference share of variance={share:.1f}%")
        print(f"      conference means: {dict(conf_means.round(3))}")

    print(f"\n  SIMULATION ASSUMES (calibrated in this session, e5b): conf_log_sigma=1.1, "
          f"team_log_sigma=0.30 -- matched ONLY against 2025-26 (between-conf std 0.080 vs "
          f"target 0.102, overall 0.156 vs target 0.158). Not yet checked against 2023-24/2024-25.")

    print("\n" + "=" * 80)
    print("5. WIN PROBABILITIES -- home advantage, OT rate, scoring")
    print("=" * 80)
    for season in SEASONS:
        g = load_season(season)
        non_neutral = g[~g['NeutralSite'].astype(bool)]
        home_win_rate = non_neutral['Result'].mean()
        ot_rate = g['IsOT'].mean() if 'IsOT' in g.columns else float('nan')
        mean_goals = (g['HomeGoals'] + g['AwayGoals']).mean()
        tie_rate = (g['Result'] == 0.5).mean()
        print(f"  {SEASON_LABELS[season]}: home_win%={home_win_rate:.4f} OT_rate={ot_rate:.4f} "
              f"mean_goals={mean_goals:.3f} tie_rate={tie_rate:.4f}")

    print(f"\n  SIMULATION ASSUMES (e0_calibration_check.py, matched to 2025-26 only): "
          f"home_win%=0.5605 (target was 0.5665), OT_rate=0.1435 (target 0.15-0.20), "
          f"mean_goals=5.867 (target 5.5-6.0)")

    print("\n" + "=" * 80)
    print("6. DIRECT SIMULATOR OUTPUT vs. ALL THREE REAL SEASONS")
    print("=" * 80)
    schedule = load_season(20252026)
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    rng = np.random.default_rng(999)
    sim_wp_stds, sim_home_wins, sim_ot_rates, sim_goals = [], [], [], []
    for rep in range(40):
        strengths = assign_true_strengths(teams, rng)
        sim = simulate_season(schedule, strengths, rng)
        wp = team_win_pct(sim)
        sim_wp_stds.append(wp.std())
        sim_home_wins.append(sim[~sim['NeutralSite'].astype(bool)]['Result'].mean())
        sim_ot_rates.append(sim['IsOT'].mean())
        sim_goals.append((sim['HomeGoals'] + sim['AwayGoals']).mean())
    print(f"  Simulator (iid, sigma=0.4, 40 reps): win%_std={np.mean(sim_wp_stds):.4f}, "
          f"home_win%={np.mean(sim_home_wins):.4f}, OT_rate={np.mean(sim_ot_rates):.4f}, "
          f"mean_goals={np.mean(sim_goals):.3f}")
    for season in SEASONS:
        wp = real_wp[season]
        g = load_season(season)
        print(f"  Real {SEASON_LABELS[season]}: win%_std={wp.std():.4f}, "
              f"home_win%={g[~g['NeutralSite'].astype(bool)]['Result'].mean():.4f}, "
              f"OT_rate={g['IsOT'].mean():.4f}, "
              f"mean_goals={(g['HomeGoals']+g['AwayGoals']).mean():.3f}")


if __name__ == "__main__":
    main()
