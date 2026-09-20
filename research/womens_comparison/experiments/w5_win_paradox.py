# research/womens_comparison/experiments/w5_win_paradox.py
"""
W5 (PLAN.md) -- does NPI's win paradox (a team's own win LOWERS its
computed NPI) replicate on real women's D-I games, and at what rate?

Same leave-one-out refit protocol as src/analysis/npi_vs_krach.py's
phase5b_paradox_detection (men's): for every decisive (non-tie) game in a
season, refit NPI with that one game removed and check whether the
winner's NPI is HIGHER without their own win than with it. KRACH is
checked the same way as a sample control -- by the MLE property, KRACH
should have ~zero such cases (a rating that improves when you remove a
game where you did nothing you weren't credited for).

Two deliberate differences from the men's version, both toward *more*
rigor given a smaller field where "the paper's whole case rests on 20
examples" is a fair criticism to pre-empt:
  1. No 20-game cap -- scans every decisive game in the season, reporting
     both the count AND the rate (paradoxes / decisive games), since raw
     counts aren't comparable across a 45-team vs. 63-team field (PLAN.md's
     C1/C2 confounds apply here too).
  2. KRACH control also scans every decisive game, not just the first 50 --
     women's is a small enough field (817 games/season) that the full scan
     is cheap.

Run from the project root as a module:
    python -m research.womens_comparison.experiments.w5_win_paradox
"""
import pandas as pd

from research.womens_comparison.harness.women_npi import (
    load_games, get_di_teams, filter_season, fit_npi, fit_krach, BACKTEST_SEASONS,
)
from research.womens_comparison.harness.paths import results_path, report_path

NPI_THRESHOLD = -0.05  # same threshold as the men's script: "measurable hurt"
KRACH_THRESHOLD = -0.5  # KRACH is scale-~100; same normalizing factor as men's


def scan_season(games_df, season, di_teams):
    sdf = filter_season(games_df, season, di_teams)
    if len(sdf) < 100:
        return None

    npi_full = fit_npi(sdf)
    krach_full = fit_krach(sdf)
    npi_ratings = npi_full.ratings.copy()
    krach_ratings = krach_full.ratings.copy()

    decisive = sdf[sdf["Result"] != 0.5]
    npi_paradoxes, krach_paradoxes = [], []

    for idx in decisive.index:
        row = sdf.loc[idx]
        winner = row["HomeTeam"] if row["Result"] == 1.0 else row["AwayTeam"]
        loser = row["AwayTeam"] if row["Result"] == 1.0 else row["HomeTeam"]
        sdf_minus = sdf.drop(idx)

        try:
            npi_minus = fit_npi(sdf_minus)
            npi_before = npi_ratings.get(winner, 50)
            npi_without = npi_minus.ratings.get(winner, 50)
            npi_impact = npi_before - npi_without
            if npi_impact < NPI_THRESHOLD:
                npi_paradoxes.append({
                    "season": season, "winner": winner, "loser": loser,
                    "loser_npi": round(npi_ratings.get(loser, 50), 2),
                    "npi_with_win": round(npi_before, 3), "npi_without_win": round(npi_without, 3),
                    "npi_impact": round(npi_impact, 3), "is_ot": bool(row.get("IsOT", False)),
                    "date": str(row.get("Date", ""))[:10],
                })
        except Exception:
            pass

        try:
            krach_minus = fit_krach(sdf_minus)
            k_before = krach_ratings.get(winner, 100)
            k_without = krach_minus.ratings.get(winner, 100)
            if k_before < k_without + KRACH_THRESHOLD:
                krach_paradoxes.append({
                    "season": season, "winner": winner,
                    "krach_with_win": round(k_before, 3), "krach_without_win": round(k_without, 3),
                })
        except Exception:
            pass

    return {
        "season": season,
        "decisive_games": len(decisive),
        "npi_paradox_count": len(npi_paradoxes),
        "npi_paradox_rate": len(npi_paradoxes) / len(decisive) if len(decisive) else 0.0,
        "krach_paradox_count": len(krach_paradoxes),
        "npi_paradoxes": npi_paradoxes,
        "krach_paradoxes": krach_paradoxes,
    }


def main():
    print("Loading women's D-I games...")
    games_df = load_games()
    di_teams = get_di_teams()

    all_results = []
    all_paradox_rows = []
    for season in BACKTEST_SEASONS:
        print(f"\n=== Season {season} ===")
        result = scan_season(games_df, season, di_teams)
        if result is None:
            print("  Too few games, skipped.")
            continue
        print(f"  Decisive games: {result['decisive_games']}")
        print(f"  NPI paradoxes: {result['npi_paradox_count']} "
              f"({result['npi_paradox_rate']:.2%} of decisive games)")
        print(f"  KRACH paradoxes (control): {result['krach_paradox_count']}")
        all_results.append({k: v for k, v in result.items()
                             if k not in ("npi_paradoxes", "krach_paradoxes")})
        all_paradox_rows.extend(result["npi_paradoxes"])

    summary_df = pd.DataFrame(all_results)
    summary_path = results_path("w5_win_paradox", "season_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSaved season summary to {summary_path}")

    if all_paradox_rows:
        paradox_df = pd.DataFrame(all_paradox_rows)
        paradox_path = results_path("w5_win_paradox", "paradox_games.csv")
        paradox_df.to_csv(paradox_path, index=False)
        print(f"Saved {len(paradox_df)} paradox games to {paradox_path}")

    total_decisive = summary_df["decisive_games"].sum()
    total_npi_paradoxes = summary_df["npi_paradox_count"].sum()
    total_krach_paradoxes = summary_df["krach_paradox_count"].sum()
    print(f"\n=== TOTAL across {len(summary_df)} seasons ===")
    print(f"Decisive games: {total_decisive}")
    print(f"NPI paradoxes: {total_npi_paradoxes} ({total_npi_paradoxes/total_decisive:.2%})")
    print(f"KRACH paradoxes: {total_krach_paradoxes} ({total_krach_paradoxes/total_decisive:.2%})")
    return summary_df, all_paradox_rows


if __name__ == "__main__":
    main()
