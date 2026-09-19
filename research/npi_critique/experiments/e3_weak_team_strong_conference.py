"""
S2: the weak team in a strong conference (research/npi_critique/PLAN.md).

The concern: a sub-.500 team in an elite conference gets ranked well
above its merit -- especially after one or two lucky wins over top teams
-- because NPI's SOS term (75% of the formula) is an average of
opponents' NPI, awarded for showing up, not for winning. This is the
Ohio State pattern in reports/npi_critique.md (14-13-8; NPI #19, KRACH
#24, win% #43), but real data can't prove NPI got it wrong, because we
don't know Ohio State's true strength. Simulation can.

Design: use the REAL 2025-26 conference structure (get_conference_map on
the real schedule). Fix one real conference's mean strength effect to be
genuinely elite and another to be genuinely weak (deterministic across
all replications, isolating the "given a strong conference truly exists"
question from any particular random draw of which conference is
strong). Plant one team of FIXED, deliberately mediocre true strength
inside the elite conference, and (mandatory symmetric control) one team
of fixed, deliberately strong true strength inside the weak conference.
Track each planted team's rank error (induced rank - true rank) across
replications, and specifically condition on replications where the
weak-in-elite team recorded >=1 genuine upset (beat a truly stronger
opponent) -- exactly the "1-2 lucky wins" scenario raised.

Run from the project root as a module:
    python -m research.npi_critique.experiments.e3_weak_team_strong_conference
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
N_REPLICATIONS = 300
ELITE_CONF = 'b10'   # Big Ten: 7 teams, real 2025-26 data
WEAK_CONF = 'ah'     # Atlantic Hockey: 10 teams, real 2025-26 data
ELITE_EFFECT = 0.65  # log-scale conference mean-strength boost
WEAK_EFFECT = -0.65
PLANTED_WEAK_STRENGTH = 0.55   # fixed, deliberately mediocre (well below the field median of ~1.0)
PLANTED_STRONG_STRENGTH = 1.85  # fixed, deliberately strong


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


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    conf_map = get_conference_map(schedule)

    elite_teams = [t for t, c in conf_map.items() if c == ELITE_CONF]
    weak_teams = [t for t, c in conf_map.items() if c == WEAK_CONF]
    print(f"Elite conference '{ELITE_CONF}': {len(elite_teams)} teams: {elite_teams}")
    print(f"Weak conference '{WEAK_CONF}': {len(weak_teams)} teams: {weak_teams}")

    planted_weak = elite_teams[0]     # a real team's SCHEDULE, fictional strength
    planted_strong = weak_teams[0]
    print(f"\nPlanting mediocre true strength ({PLANTED_WEAK_STRENGTH}) onto {planted_weak} "
          f"(schedule stays real -- only its assumed true strength is overridden).")
    print(f"Planting strong true strength ({PLANTED_STRONG_STRENGTH}) onto {planted_strong}.")

    rng = np.random.default_rng(31415)
    rows = []

    for rep in range(N_REPLICATIONS):
        strengths = assign_conference_stratified_strengths(
            teams, conf_map, rng,
            conf_effect_override={ELITE_CONF: ELITE_EFFECT, WEAK_CONF: WEAK_EFFECT},
        )
        strengths[planted_weak] = PLANTED_WEAK_STRENGTH
        strengths[planted_strong] = PLANTED_STRONG_STRENGTH
        truth = true_ranking(strengths)
        true_rank_weak = truth.index(planted_weak) + 1
        true_rank_strong = truth.index(planted_strong) + 1

        sim = simulate_season(schedule, strengths, rng)

        # Did the planted weak team score a genuine upset -- beat an
        # opponent whose TRUE strength exceeds its own -- this replication?
        weak_games = sim[(sim.HomeTeam == planted_weak) | (sim.AwayTeam == planted_weak)]
        n_upsets = 0
        for _, g in weak_games.iterrows():
            opp = g['AwayTeam'] if g['HomeTeam'] == planted_weak else g['HomeTeam']
            weak_won = (g['Result'] == 1.0) == (g['HomeTeam'] == planted_weak)
            if weak_won and strengths.get(opp, 0) > strengths[planted_weak]:
                n_upsets += 1

        npi, krach = NPI(sim), KRACH(sim)
        massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False})
        for m in (npi, krach, massey):
            m.fit()

        for model_name, model in [('NPI', npi), ('KRACH', krach), ('Massey', massey)]:
            rk_weak = rank_of(model.ratings, planted_weak, teams)
            rk_strong = rank_of(model.ratings, planted_strong, teams)
            rows.append({
                'rep': rep, 'model': model_name, 'role': 'weak_in_elite',
                'true_rank': true_rank_weak, 'induced_rank': rk_weak,
                'rank_error': true_rank_weak - rk_weak,  # positive = OVERrated (ranked better than truth)
                'n_upsets': n_upsets,
            })
            rows.append({
                'rep': rep, 'model': model_name, 'role': 'strong_in_weak',
                'true_rank': true_rank_strong, 'induced_rank': rk_strong,
                'rank_error': true_rank_strong - rk_strong,  # negative = UNDERrated
                'n_upsets': np.nan,
            })

        if rep == 17:
            print(f"\n=== Concrete example: replication {rep} ===")
            print(f"{planted_weak} (true strength {PLANTED_WEAK_STRENGTH}, true rank {true_rank_weak}/{len(teams)}, "
                  f"real schedule) recorded {n_upsets} genuine upset(s) this replication.")
            wl = weak_games.copy()
            wl['won'] = (wl['Result'] == 1.0) == (wl['HomeTeam'] == planted_weak)
            print(f"  Record: {wl['won'].sum()}-{(~wl['won']).sum()} "
                  f"({int((wl['IsOT'] & wl['won']).sum())} OT wins, {int((wl['IsOT'] & ~wl['won']).sum())} OT losses)")
            for _, g in wl.iterrows():
                opp = g['AwayTeam'] if g['HomeTeam'] == planted_weak else g['HomeTeam']
                tag = " <-- UPSET" if g['won'] and strengths.get(opp, 0) > strengths[planted_weak] else ""
                print(f"    {g['Date'].date()}  {g['HomeTeam']:>12s} {int(g['HomeGoals'])}-{int(g['AwayGoals'])} "
                      f"{g['AwayTeam']:<12s} {'(OT)' if g['IsOT'] else ''}{tag}")
            for model_name, model in [('NPI', npi), ('KRACH', krach), ('Massey', massey)]:
                rk = rank_of(model.ratings, planted_weak, teams)
                print(f"  {model_name}: induced rank {rk} (true rank {true_rank_weak}, "
                      f"error {true_rank_weak - rk:+d})")

        if (rep + 1) % 60 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} replications done")

    results = pd.DataFrame(rows)
    results.to_csv(results_path("e3_weak_team_strong_conference", "rank_error.csv"), index=False)

    print(f"\n=== Weak team planted in elite conference ({ELITE_CONF}), true rank ~"
          f"{results[(results.role == 'weak_in_elite')]['true_rank'].iloc[0]} of {len(teams)} ===")
    weak = results[results.role == 'weak_in_elite']
    print(weak.groupby('model')['rank_error'].agg(
        mean='mean', std='std',
        pct_overrated=lambda s: (s > 0).mean() * 100,
        p95='max', worst_overrate=lambda s: s.max(),
    ))

    print(f"\n=== Conditional on >=1 genuine upset by the planted weak team ===")
    upset_reps = weak[weak.n_upsets >= 1]
    print(f"({upset_reps['rep'].nunique()} of {N_REPLICATIONS} replications had >=1 upset)")
    if len(upset_reps):
        print(upset_reps.groupby('model')['rank_error'].agg(
            mean='mean', std='std', p90=lambda s: s.quantile(0.90),
            worst_overrate=lambda s: s.max(), n='count',
        ))

    print(f"\n=== Symmetric control: strong team planted in weak conference ({WEAK_CONF}) ===")
    strong = results[results.role == 'strong_in_weak']
    print(strong.groupby('model')['rank_error'].agg(
        mean='mean', std='std',
        pct_underrated=lambda s: (s < 0).mean() * 100,
        worst_underrate=lambda s: s.min(),
    ))

    return results


if __name__ == "__main__":
    main()
