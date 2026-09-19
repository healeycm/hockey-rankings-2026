# src/data/backfill_eng.py
"""
Backfills empty-net-goal (away_eng/home_eng) columns into existing
data/raw_advanced/chn_games_*.csv files, which were scraped before
extract_empty_net_goals() existed in advanced_metrics_scraper.py.

Reuses each row's already-stored box-score `url` — no need to re-scrape the
schedule page or re-parse goals/shots/xG, just fetch the same page again and
pull the one additional div. Writes the result back in place (with a .bak
backup of the original).

Usage:
    python -m src.data.backfill_eng [--files chn_games_2024_2025.csv ...] [--limit N] [--sleep 0.5]
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.data.advanced_metrics_scraper import extract_empty_net_goals, HEADERS, DATA_RAW_DIR


def backfill_file(path: Path, limit=None, sleep=0.5):
    df = pd.read_csv(path)
    if 'away_eng' in df.columns and 'home_eng' in df.columns and df['away_eng'].notna().all():
        print(f"{path.name}: already has complete ENG data, skipping.")
        return

    if 'away_eng' not in df.columns:
        df['away_eng'] = pd.NA
    if 'home_eng' not in df.columns:
        df['home_eng'] = pd.NA

    todo = df[df['away_eng'].isna() & df['url'].notna()].index.tolist()
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
            away_eng, home_eng = extract_empty_net_goals(soup)
            df.at[idx, 'away_eng'] = away_eng
            df.at[idx, 'home_eng'] = home_eng
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
