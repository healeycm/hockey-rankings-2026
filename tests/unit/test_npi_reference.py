"""
Regression test: our NPI calculation must stay within tolerance of the
published USCHO/CHN reference NPI snapshot at data/raw/npi_2026_01_27.csv.

This guards against two classes of regression discovered during the
2026-01-27 investigation (see reports/npi_investigation_2026.md):
  1. Comparing against the wrong game set (e.g. omitting the date cutoff
     and leaking future games into a frozen reference comparison) —
     previously produced a uniform ~-0.19 NPI / -0.19 SOS bias across
     every team.
  2. Computing SOS (and Wgt W%) over only the games that survive the
     "bad wins" filter, instead of over the full schedule — inflated the
     SOS error by roughly 2x.

If this test starts failing after an unrelated change, don't just raise
the tolerance — first check whether the change reintroduced one of the
above two bugs.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.npi_games import NPIGames

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_PATH = PROJECT_ROOT / "data" / "processed" / "games_archive.csv"
REFERENCE_PATH = PROJECT_ROOT / "data" / "raw" / "npi_2026_01_27.csv"
REFERENCE_CUTOFF = "2026-01-27"
REFERENCE_SEASON = 20252026

# Empirically achieved MAE after the date-cutoff and SOS/WP fixes is ~0.07
# (NPI) / ~0.10 (SOS) on a 0-100 scale. Generous tolerances below leave
# headroom for season-to-season noise while still catching a regression
# back toward the ~0.19 pre-fix bias.
NPI_MAE_TOLERANCE = 0.15
SOS_MAE_TOLERANCE = 0.20


@pytest.mark.skipif(not ARCHIVE_PATH.exists() or not REFERENCE_PATH.exists(),
                     reason="Reference/archive data not present in this environment.")
def test_npi_matches_published_reference():
    games_df = pd.read_csv(ARCHIVE_PATH)
    games_df["Date"] = pd.to_datetime(games_df["Date"])
    season_df = games_df[games_df["Season"] == REFERENCE_SEASON].copy()
    season_df = season_df[season_df["Date"] <= pd.Timestamp(REFERENCE_CUTOFF)].copy()
    assert len(season_df) > 0, "No games found through the reference cutoff date."

    model = NPIGames(season_df)
    model.fit(tolerance=1e-6, max_iterations=200)

    ref = pd.read_csv(REFERENCE_PATH)[["Team", "NPI", "SOS"]]

    calc_rows = [
        {"Team": t, "Calc_NPI": d["npi"], "Calc_SOS": d["sos"]}
        for t, d in model.details.items()
    ]
    calc = pd.DataFrame(calc_rows)

    merged = calc.merge(ref, on="Team", how="inner")
    assert len(merged) >= 0.9 * len(ref), "Too few teams matched between calc and reference."

    npi_mae = (merged["Calc_NPI"] - merged["NPI"]).abs().mean()
    sos_mae = (merged["Calc_SOS"] - merged["SOS"]).abs().mean()

    assert npi_mae < NPI_MAE_TOLERANCE, f"NPI MAE {npi_mae:.4f} exceeds tolerance {NPI_MAE_TOLERANCE}"
    assert sos_mae < SOS_MAE_TOLERANCE, f"SOS MAE {sos_mae:.4f} exceeds tolerance {SOS_MAE_TOLERANCE}"
