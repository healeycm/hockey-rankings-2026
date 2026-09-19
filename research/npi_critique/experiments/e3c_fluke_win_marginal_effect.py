"""
S2, precise version of the concern: NOT "does a mediocre team in a strong
conference end up overrated overall" (e3's question, and the answer there
was subtler than expected) but the specific causal question you actually
asked -- **holding a below-.500 team's season otherwise fixed, what is
the marginal effect on its rating/rank of flipping one or two of its
losses against very highly-ranked opponents into wins?** That isolates
the fluke-win/QWB mechanism directly, rather than mixing it with the
team's overall record and conference-strength context the way e3's
aggregate rank-error measure does.

Design: simulate a season for a below-.500 planted team in a real elite
conference (same setup as e3). Identify its two losses against the
highest true-strength opponents it played. Construct two counterfactual
seasons -- one where its single toughest loss becomes a narrow (OT) win,
one where its two toughest losses both become narrow wins -- with every
other game held fixed. Refit NPI, KRACH, and Massey on the original and
both counterfactuals; report the marginal rank/rating change attributable
to the flip(s) alone, per model, averaged over many replications (fresh
season each time, same flip procedure).

Run from the project root as a module:
    python -m research.npi_critique.experiments.e3c_fluke_win_marginal_effect
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
N_REPLICATIONS = 150
ELITE_CONF = 'b10'
ELITE_EFFECT = 0.65
PLANTED_STRENGTH = 0.85   # a genuinely below-.500-caliber team, not the extreme 0.55 tail case


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


def flip_loss_to_win(sim_df, team, game_idx):
    """Flip one specific game where `team` lost into a narrow OT win for
    `team`, holding every other game fixed. Uses a plausible close score
    (whatever the loss margin was, inverted to a 1-goal OT edge) rather
    than an unrealistic blowout, since the concern is specifically about
    a *fluke* (narrow) win, not a dominant one."""
    df = sim_df.copy()
    row = df.loc[game_idx]
    is_home = row['HomeTeam'] == team
    if is_home:
        # team was home and lost; give them a 1-goal OT win instead
        loser_goals = row['HomeGoals']
        df.loc[game_idx, 'HomeGoals'] = loser_goals + 1
        df.loc[game_idx, 'AwayGoals'] = loser_goals
    else:
        loser_goals = row['AwayGoals']
        df.loc[game_idx, 'AwayGoals'] = loser_goals + 1
        df.loc[game_idx, 'HomeGoals'] = loser_goals
    df.loc[game_idx, 'IsOT'] = True
    df.loc[game_idx, 'Result'] = 1.0 if is_home else 0.0
    df.loc[game_idx, 'GoalMargin'] = (df.loc[game_idx, 'HomeGoals'] - df.loc[game_idx, 'AwayGoals'])
    return df


def fit_all(sim_df):
    npi, krach = NPI(sim_df), KRACH(sim_df)
    massey = Massey(sim_df, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
    for m in (npi, krach, massey):
        m.fit()
    return {'NPI': npi, 'KRACH': krach, 'Massey': massey}


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)
    elite_teams = [t for t, c in conf_map.items() if c == ELITE_CONF]
    planted = elite_teams[0]
    print(f"Planting strength {PLANTED_STRENGTH} onto {planted} ({ELITE_CONF})")

    rng = np.random.default_rng(2718)
    rows = []
    printed_example = False

    for rep in range(N_REPLICATIONS):
        strengths = assign_conference_stratified_strengths(
            teams, conf_map, rng, conf_effect_override={ELITE_CONF: ELITE_EFFECT},
        )
        strengths[planted] = PLANTED_STRENGTH
        sim = simulate_season(schedule, strengths, rng)

        team_games = sim[(sim.HomeTeam == planted) | (sim.AwayTeam == planted)].copy()
        team_games['won'] = (team_games['Result'] == 1.0) == (team_games['HomeTeam'] == planted)
        team_games['opp'] = np.where(team_games['HomeTeam'] == planted, team_games['AwayTeam'], team_games['HomeTeam'])
        team_games['opp_strength'] = team_games['opp'].map(strengths)

        losses = team_games[~team_games['won']].sort_values('opp_strength', ascending=False)
        if len(losses) < 2:
            continue  # skip replications with too few losses to test on (rare)

        toughest_two = losses.index[:2].tolist()

        baseline_models = fit_all(sim)
        sim_flip1 = flip_loss_to_win(sim, planted, toughest_two[0])
        flip1_models = fit_all(sim_flip1)
        sim_flip2 = flip_loss_to_win(sim_flip1, planted, toughest_two[1])
        flip2_models = fit_all(sim_flip2)

        for name in ['NPI', 'KRACH', 'Massey']:
            rk0 = rank_of(baseline_models[name].ratings, planted, teams)
            rk1 = rank_of(flip1_models[name].ratings, planted, teams)
            rk2 = rank_of(flip2_models[name].ratings, planted, teams)
            rows.append({
                'rep': rep, 'model': name,
                'rank_baseline': rk0, 'rank_after_1_flip': rk1, 'rank_after_2_flips': rk2,
                'gain_from_1_flip': rk0 - rk1,   # positive = rank improved (moved up)
                'gain_from_2_flips': rk0 - rk2,
                'opp1_strength': strengths[team_games.loc[toughest_two[0], 'opp']],
                'opp2_strength': strengths[team_games.loc[toughest_two[1], 'opp']],
            })

        if not printed_example and rep == 5:
            printed_example = True
            print(f"\n=== Concrete example: replication {rep} ===")
            print(f"{planted}'s two toughest losses (about to be flipped to narrow OT wins):")
            for idx in toughest_two:
                g = team_games.loc[idx]
                print(f"  vs {g['opp']} (true strength {g['opp_strength']:.2f}): "
                      f"{'lost as home' if g['HomeTeam'] == planted else 'lost as away'}, "
                      f"{int(sim.loc[idx, 'HomeGoals'])}-{int(sim.loc[idx, 'AwayGoals'])}")
            for name in ['NPI', 'KRACH', 'Massey']:
                rk0 = rank_of(baseline_models[name].ratings, planted, teams)
                rk1 = rank_of(flip1_models[name].ratings, planted, teams)
                rk2 = rank_of(flip2_models[name].ratings, planted, teams)
                print(f"  {name}: rank {rk0} -> {rk1} (after 1 flip) -> {rk2} (after 2 flips)")

        if (rep + 1) % 40 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e3c_fluke_win_marginal_effect", "marginal_gain.csv"), index=False)

    print(f"\n=== Marginal rank gain from flipping the single toughest loss into a narrow win "
          f"({len(results)} valid replications) ===")
    print(results.groupby('model')['gain_from_1_flip'].agg(
        mean='mean', std='std', pct_gained=lambda s: (s > 0).mean() * 100,
        max_gain='max', pct_no_effect=lambda s: (s == 0).mean() * 100,
    ))

    print(f"\n=== Marginal rank gain from flipping BOTH toughest losses into narrow wins ===")
    print(results.groupby('model')['gain_from_2_flips'].agg(
        mean='mean', std='std', pct_gained=lambda s: (s > 0).mean() * 100, max_gain='max',
    ))


if __name__ == "__main__":
    main()
