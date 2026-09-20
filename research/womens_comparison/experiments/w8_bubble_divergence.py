# research/womens_comparison/experiments/w8_bubble_divergence.py
"""
W8 (PLAN.md) -- does NPI's own field disagree with KRACH's or Massey's, on
real, already-completed women's seasons? Direct women's-data counterpart
to the men's paper's most concrete artifact (E24:
research/npi_critique/experiments/e24_real_bubble_divergence.py, which
found NPI ranked Miami 32nd in 2025-26 while KRACH ranked the same team's
results 15th -- a specific, named team on opposite sides of the line).

Same documented simplification as E24, carried over unchanged: the real
NCAA women's tournament field is NOT simply "the top 11 by rating" --
5 teams earn automatic bids by winning their conference tournament
regardless of rating, and only the remaining 6 slots are at-large. This
does not reconstruct real conference-tournament brackets (same
data-engineering scope decision E24 made) and instead reports each
metric's own unconditional top-FIELD_SIZE -- answering "does the metric's
own ranking disagree with another metric's own ranking at the cutoff that
matters" rather than "would the literal real bracket have differed."

FIELD_SIZE = 11, matching the real 2025-26 women's field size (5 auto +
6 at-large; see PLAN.md's W7 note and the 2026 NCAA field announcement).

Run from the project root as a module:
    python -m research.womens_comparison.experiments.w8_bubble_divergence
"""
import pandas as pd

from research.womens_comparison.harness.women_npi import (
    load_games, get_di_teams, filter_season, fit_npi, fit_krach, fit_massey,
    get_ranks, BACKTEST_SEASONS,
)
from research.womens_comparison.harness.paths import results_path, report_path

FIELD_SIZE = 11


def main():
    print("Loading women's D-I games...")
    games_df = load_games()
    di_teams = get_di_teams()

    rows = []
    for season in BACKTEST_SEASONS:
        sdf = filter_season(games_df, season, di_teams)
        if len(sdf) < 200:
            continue
        print(f"\nSeason {season}: {len(sdf)} games")

        npi = fit_npi(sdf)
        krach = fit_krach(sdf)
        massey = fit_massey(sdf)

        npi_ranks = get_ranks(npi.ratings)
        krach_ranks = get_ranks(krach.ratings)
        massey_ranks = get_ranks(massey.ratings)

        teams = set(npi_ranks) & set(krach_ranks) & set(massey_ranks)
        for team in teams:
            rows.append({
                "season": season, "team": team,
                "npi_rank": npi_ranks[team], "krach_rank": krach_ranks[team],
                "massey_rank": massey_ranks[team],
                "npi_in": npi_ranks[team] <= FIELD_SIZE,
                "krach_in": krach_ranks[team] <= FIELD_SIZE,
                "massey_in": massey_ranks[team] <= FIELD_SIZE,
            })

    df = pd.DataFrame(rows)
    df["npi_vs_krach_disagree"] = df["npi_in"] != df["krach_in"]
    df["npi_vs_massey_disagree"] = df["npi_in"] != df["massey_in"]
    df["max_rank_gap_npi_krach"] = (df["npi_rank"] - df["krach_rank"]).abs()

    out_path = results_path("w8_bubble_divergence", "team_season_ranks.csv")
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)} team-seasons to {out_path}")

    n = len(df)
    npi_krach_rate = df["npi_vs_krach_disagree"].mean()
    npi_massey_rate = df["npi_vs_massey_disagree"].mean()
    print(f"\n=== Field-membership disagreement (top-{FIELD_SIZE}), {n} team-seasons ===")
    print(f"NPI vs. KRACH: {df['npi_vs_krach_disagree'].sum()} ({npi_krach_rate:.2%})")
    print(f"NPI vs. Massey: {df['npi_vs_massey_disagree'].sum()} ({npi_massey_rate:.2%})")

    # The single most divergent team-season per pairing (largest rank gap
    # AMONG disagreement cases) -- the "named team" artifact.
    disagree_nk = df[df["npi_vs_krach_disagree"]].sort_values("max_rank_gap_npi_krach", ascending=False)
    print("\nTop 5 NPI-vs-KRACH bubble disagreements (largest rank gap):")
    print(disagree_nk[["season", "team", "npi_rank", "krach_rank", "npi_in", "krach_in"]].head(5).to_string(index=False))

    return df


if __name__ == "__main__":
    main()
