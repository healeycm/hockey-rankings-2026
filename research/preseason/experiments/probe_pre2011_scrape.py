# research/preseason/experiments/probe_pre2011_scrape.py
"""
One-off probe: how far back does USCHO's composite-schedule page (the same
URL pattern production's src/data/scraper.py already uses) actually scrape
cleanly, before 2011-12 (games_archive.csv's current earliest season)?

Read-only and research-workspace-only by construction:
  - Reuses src/data/scraper.py's get_data_for_season() (a pure fetch+parse
    function, no writes) and validate_scraped_season() (a pure function) --
    imported, not modified.
  - Never calls scrape_seasons() (which writes to data/raw/) and never
    imports/touches anything under data/raw or data/processed.
  - All output goes through research/preseason/harness/paths.py's
    research_path(), which raises if a path would land outside this
    workspace.
  - Per the plan's "skip and log, don't crash" discipline (PLAN.md §1a): a
    season that fails to fetch/parse is recorded and skipped, never allowed
    to kill the whole probe run.

Usage (from project root):
    python -m research.preseason.experiments.probe_pre2011_scrape
"""
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.scraper import setup_driver, get_data_for_season, validate_scraped_season  # noqa: E402
from research.preseason.harness.paths import research_path  # noqa: E402

# Working backward from 2011-12 (the earliest season currently in
# games_archive.csv) in ~2-year steps, plus a deliberately-early sanity
# check (1998-99) to see if the site even resolves something that old vs.
# 404s/redirects cleanly. Not exhaustive -- just enough to locate roughly
# where (if anywhere) the archive stops being usable.
PROBE_SEASONS = [
    "20102011", "20092010", "20082009", "20072008", "20062007",
    "20052006", "20042005", "20032004", "20022003", "20012002", "20002001",
    "19992000", "19981999",
]

OUT_DIR = "pre2011_probe"


def main():
    driver = setup_driver()
    if not driver:
        print("Could not start the Selenium driver -- aborting probe (nothing written).")
        return

    log_rows = []
    try:
        for season in PROBE_SEASONS:
            print("-" * 60)
            print(f"Probing season {season}...")
            try:
                games = get_data_for_season(driver, season, division="men")
            except Exception as e:
                print(f"  ! Fetch/parse raised an exception, skipping: {e}")
                log_rows.append({"Season": season, "Status": "error", "Detail": str(e), "Games": 0})
                time.sleep(2)
                continue

            if not games:
                print("  -> 0 rows found (page likely 404s, redirects, or has no composite-schedule for this season).")
                log_rows.append({"Season": season, "Status": "empty", "Detail": "0 rows returned", "Games": 0})
                time.sleep(2)
                continue

            df = pd.DataFrame(games)
            df = df[df["Visitor_Team"] != ""]
            warnings = validate_scraped_season(df, season, is_current_season=False, division="men")

            status = "ok" if not warnings else "warnings"
            detail = "; ".join(warnings) if warnings else "looks like a clean full season"
            print(f"  -> {len(df)} rows. {detail}")
            log_rows.append({"Season": season, "Status": status, "Detail": detail, "Games": len(df)})

            # Save whatever we got either way -- even a partial/garbled
            # scrape is useful evidence of exactly where things break down.
            out_path = research_path("data", OUT_DIR, f"games_{season}.csv")
            df.to_csv(out_path, index=False)

            time.sleep(2)
    finally:
        driver.quit()

    log_df = pd.DataFrame(log_rows)
    log_path = research_path("data", OUT_DIR, "probe_log.csv")
    log_df.to_csv(log_path, index=False)

    print("\n" + "=" * 60)
    print("PROBE SUMMARY")
    print("=" * 60)
    print(log_df.to_string(index=False))
    print(f"\nFull log: {log_path}")
    print(f"Any scraped rows saved under: {log_path.parent}")


if __name__ == "__main__":
    main()
