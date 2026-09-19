# src/data/backfill_manpower.py
"""
Backfills even-manpower-goal (away_ev_goals/home_ev_goals) columns into
existing data/raw_advanced/chn_games_*.csv files, which were scraped before
extract_even_manpower_goals() existed in advanced_metrics_scraper.py —
mirrors backfill_eng.py's pattern exactly (reuse each row's already-stored
box-score `url`, no re-scraping of the schedule page itself).

Used to build the manpower-adjusted-margin experiment for Massey — see
reports/massey_experiments_2026.md.

Usage:
    python -m src.data.backfill_manpower [--files chn_games_2024_2025.csv ...] [--limit N] [--sleep 0.5]
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.data.advanced_metrics_scraper import extract_even_manpower_goals, HEADERS, DATA_RAW_DIR


def backfill_file(path: Path, limit=None, sleep=0.5):
    df = pd.read_csv(path)
    if 'away_ev_goals' in df.columns and 'home_ev_goals' in df.columns and df['away_ev_goals'].notna().all():
        print(f"{path.name}: already has complete even-manpower-goal data, skipping.")
        return

    if 'away_ev_goals' not in df.columns:
        df['away_ev_goals'] = pd.NA
    if 'home_ev_goals' not in df.columns:
        df['home_ev_goals'] = pd.NA

    todo = df[df['away_ev_goals'].isna() & df['url'].notna()].index.tolist()
    if limit:
        todo = todo[:limit]

    print(f"{path.name}: {len(todo)} games to backfill (of {len(df)} total)...")

    n_ok, n_fail = 0, 0
    for i, idx in enumerate(todo):
        url = df.at[idx, 'url']
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            away_ev, home_ev = extract_even_manpower_goals(soup)
            df.at[idx, 'away_ev_goals'] = away_ev
            df.at[idx, 'home_ev_goals'] = home_ev
            n_ok += 1
        except Exception as e:
            print(f"  ! Failed {url}: {e}")
            n_fail += 1

        if (i + 1) % 50 == 0:
            print(f"  ... {i + 1}/{len(todo)} ({n_ok} ok, {n_fail} failed)")
            # Checkpoint periodically in case of a crash/interrupt mid-run.
            df.to_csv(path, index=False)

        time.sleep(sleep)

    df.to_csv(path, index=False)
    print(f"{path.name}: done. {n_ok} ok, {n_fail} failed. Saved.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--files', nargs='*', default=None,
                         help="Specific chn_games_*.csv filenames (default: all found in data/raw_advanced/)")
    parser.add_argument('--limit', type=int, default=None, help="Only backfill the first N missing rows per file (for testing).")
    parser.add_argument('--sleep', type=float, default=0.5, help="Delay between requests (seconds).")
    args = parser.parse_args()

    if args.files:
        paths = [DATA_RAW_DIR / f for f in args.files]
    else:
        paths = sorted(DATA_RAW_DIR.glob("chn_games_*.csv"))

    for p in paths:
        if not p.exists():
            print(f"Skipping missing file: {p}")
            continue
        backfill_file(p, limit=args.limit, sleep=args.sleep)


if __name__ == "__main__":
    main()
