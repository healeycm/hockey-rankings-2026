"""
E1: Truth recovery. Real data can never tell us which team was actually
better -- only what happened. This experiment simulates seasons with a
KNOWN ground-truth team strength (research.npi_critique.harness.simulate,
calibrated against this project's own real-data findings -- see
e0_calibration_check.py) and measures how closely each model's induced
ranking matches that ground truth, via Spearman rank correlation.

Three questions, each impossible to answer from real data alone:
  (a) Across the validated model roster, which ranking method actually
      recovers ground truth best -- not "predicts held-out games best,"
      a different (though related) question already answered in
      paper/draft.md?
  (b) Is NPI's official strength-of-schedule weight (0.75) actually the
      value that best recovers ground truth, or would a different weight
      do better -- something no amount of real-data dial-sensitivity
      analysis (reports/npi_critique.md) can settle, since real data
      never reveals which team was actually better?
  (c) At what rate does the "a win can lower your NPI" paradox
      (reports/npi_critique.md Section 5b, found 20 times in one real
      season) occur under controlled conditions, and does it concentrate
      on any particular pattern of true team strength?

Run from the project root as a module:
    python -m research.npi_critique.experiments.e1_truth_recovery
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

from src.rankings.npi import NPI
from src.rankings.krach import KRACH
from src.rankings.massey import Massey
from src.rankings.rpi import RPI
from src.analysis.npi_vs_krach import reweight_npi
from research.npi_critique.harness.simulate import assign_true_strengths, simulate_season, true_ranking
from research.npi_critique.harness.paths import results_path, report_path

# IMPORTANT, discovered while building this experiment: NPI.fit()
# (src/rankings/npi.py) hard-codes the 0.25/0.75 weight_wp/weight_sos
# split directly in its vectorized iterative solve -- passing a different
# weight_wp/weight_sos via `config` to NPI() is silently a no-op (verified
# directly: a first version of this script did exactly that and produced
# bit-identical Spearman correlations across every "different" dial
# value). This is a real, previously undocumented gap between what
# config.yaml's comments and reports/npi_critique.md's Section 2 imply is
# tunable and what the shipped class actually reads. It is NOT a new
# discovery, though -- src/analysis/npi_vs_krach.py already hit this and
# built reweight_npi() as the documented workaround: it recomputes ratings
# post-hoc from the *converged* adj_wp/sos/qwb components (themselves
# still produced by a fit at the hard-coded 0.75) using the requested
# weights, rather than truly re-running the iterative convergence at a
# different weight. That is what npi_critique.md's own dial-sensitivity
# analysis actually measured, and it's what we reuse here for
# methodological consistency -- but it means "sweeping weight_sos" here,
# as there, measures sensitivity to the *final linear combination* step
# only, not to a fully re-converged iteration (which would also change
# opponents' own NPI values, and therefore SOS itself, at each candidate
# weight). We report this caveat plainly rather than silently inheriting
# it.

PROJECT_ROOT = Path(__file__).resolve().parents[3]
N_REPLICATIONS = 200
SOS_WEIGHTS_TO_SWEEP = [0.10, 0.25, 0.50, 0.66, 0.75, 0.90]  # 0.75 is the official 2025-26 dial


def load_real_schedule(season=20252026):
    df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "games_archive.csv", parse_dates=['Date'])
    team_info = pd.read_csv(PROJECT_ROOT / "data" / "teams" / "team_info.csv")
    di_teams = set(team_info['USCHO_Name'].unique())
    df = df[df['Season'] == season].copy()
    df = df[~df['Is_Exhibition'].isin([True, 'True', 1, '1'])]
    df = df[df['HomeTeam'].isin(di_teams) & df['AwayTeam'].isin(di_teams)]
    return df.reset_index(drop=True)


def spearman_vs_truth(model_ratings, truth_order):
    """model_ratings: dict[team] -> rating (higher = better).
    truth_order: list of teams, strongest first.
    Returns Spearman rho between the model's induced rank and truth."""
    teams = list(truth_order)
    truth_rank = {t: i for i, t in enumerate(truth_order)}
    model_sorted = sorted(teams, key=lambda t: model_ratings.get(t, -np.inf), reverse=True)
    model_rank = {t: i for i, t in enumerate(model_sorted)}
    a = [truth_rank[t] for t in teams]
    b = [model_rank[t] for t in teams]
    rho, _ = spearmanr(a, b)
    return rho


def find_npi_paradoxes(sim_df, npi_ratings, n_candidates=15, rng=None):
    """Leave-one-out check, mirroring reports/npi_critique.md Section 5b:
    for a sample of games where the winner's opponent has a below-median
    NPI rating, does removing that win from the winner's schedule
    INCREASE the winner's NPI? If so, the win paradoxically lowered it.
    Capped at n_candidates games per replication to keep runtime bounded
    across N_REPLICATIONS replications."""
    median_rating = np.median(list(npi_ratings.values()))
    decisive = sim_df[sim_df['Result'] == 1.0].copy()
    decisive['LoserNPI'] = decisive['AwayTeam'].map(npi_ratings)
    candidates = decisive[decisive['LoserNPI'] < median_rating]
    if len(candidates) == 0:
        return 0, 0
    if rng is not None and len(candidates) > n_candidates:
        candidates = candidates.sample(n=n_candidates, random_state=rng.integers(0, 2**31 - 1))

    paradox_count = 0
    for idx in candidates.index:
        winner = sim_df.loc[idx, 'HomeTeam']
        without_game = sim_df.drop(idx)
        npi_without = NPI(without_game)
        npi_without.fit()
        rating_without = npi_without.ratings.get(winner, npi_ratings[winner])
        if rating_without > npi_ratings[winner]:
            paradox_count += 1
    return paradox_count, len(candidates)


def main():
    schedule = load_real_schedule()
    teams = sorted(set(schedule['HomeTeam']).union(schedule['AwayTeam']))
    rng = np.random.default_rng(2026)

    rows = []
    paradox_hits, paradox_total = 0, 0

    for rep in range(N_REPLICATIONS):
        strengths = assign_true_strengths(teams, rng)
        truth = true_ranking(strengths)
        sim = simulate_season(schedule, strengths, rng)

        krach = KRACH(sim); krach.fit()
        massey = Massey(sim, config={'fit_home_ice': True, 'ridge_lambda': 1.0, 'fit_beta': False}); massey.fit()
        rpi = RPI(sim); rpi.fit()
        npi_official = NPI(sim); npi_official.fit()

        rows.append({
            'rep': rep, 'model': 'KRACH', 'rho': spearman_vs_truth(krach.ratings, truth),
        })
        rows.append({
            'rep': rep, 'model': 'Massey', 'rho': spearman_vs_truth(massey.ratings, truth),
        })
        rows.append({
            'rep': rep, 'model': 'RPI', 'rho': spearman_vs_truth(rpi.ratings, truth),
        })
        rows.append({
            'rep': rep, 'model': 'NPI (official, sos=0.75)', 'rho': spearman_vs_truth(npi_official.ratings, truth),
        })

        for w in SOS_WEIGHTS_TO_SWEEP:
            if w == 0.75:
                continue  # already have it as npi_official above
            npi_w = reweight_npi(npi_official, weight_wp=1 - w, weight_sos=w)
            rows.append({
                'rep': rep, 'model': f'NPI (sos={w})', 'rho': spearman_vs_truth(npi_w.ratings, truth),
            })

        # Paradox check: only first 20 replications, capped candidates each,
        # to keep total leave-one-out refits bounded.
        if rep < 20:
            hits, total = find_npi_paradoxes(sim, npi_official.ratings, n_candidates=15, rng=rng)
            paradox_hits += hits
            paradox_total += total

        if (rep + 1) % 20 == 0:
            print(f"  ... {rep + 1}/{N_REPLICATIONS} replications done")

    results = pd.DataFrame(rows)
    out_path = results_path("e1_truth_recovery", "spearman_by_model.csv")
    results.to_csv(out_path, index=False)

    summary = results.groupby('model')['rho'].agg(['mean', 'std', 'count']).sort_values('mean', ascending=False)
    print(f"\n=== Truth-recovery Spearman correlation, {N_REPLICATIONS} replications ===")
    print(summary)

    print(f"\n=== NPI paradox rate (first 20 replications, capped 15 candidates each) ===")
    print(f"  {paradox_hits}/{paradox_total} sampled below-median-opponent wins LOWERED the winner's NPI "
          f"({100 * paradox_hits / paradox_total:.1f}%)" if paradox_total else "  no candidates found")

    return results, summary, paradox_hits, paradox_total


if __name__ == "__main__":
    main()
