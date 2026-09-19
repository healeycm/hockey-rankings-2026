# src/data/processor.py

import pandas as pd
import numpy as np
from pathlib import Path
from src.data.loader import DataLoader

# Paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def process_data(division='men'):
    """
    Orchestrates the loading of raw data and saving of processed artifacts.

    `division`: 'men' (default) reads data/raw/ and writes
    data/processed/games_archive.csv + upcoming_schedule.csv exactly as
    before division support existed -- fully backward compatible, no path
    changes for existing callers. 'women' reads data/raw/women/ and writes
    to data/processed/women/ instead, a pure addition (see
    reports/womens_hockey_import.md for why physical separation, not a
    shared file with a Division column, was the chosen design).
    """
    print(f"--- Processing Raw Data ({division}) ---")
    processed_dir = PROCESSED_DIR if division == 'men' else (PROCESSED_DIR / division)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize Loader
    raw_dir = None if division == 'men' else (PROJECT_ROOT / "data" / "raw" / division)
    loader = DataLoader(data_dir=raw_dir)

    # 2. Get Historical Games (Training Data)
    print("Generating Historical Archive...")
    history_df = loader.get_history()

    # Add modeling helper columns
    # Standard KRACH uses Wins=1, Ties=0.5.
    # LRMC uses goal margin.

    # Validation: Ensure no exhibitions slipped through
    history_df = history_df[~history_df['HomeTeam'].str.contains("Exhibition", case=False, na=False)]

    # Save
    hist_path = processed_dir / "games_archive.csv"
    history_df.to_csv(hist_path, index=False)
    print(f"Saved {len(history_df)} historical games to {hist_path}")

    # 3. Get Upcoming Schedule (Prediction Data)
    print("Generating Upcoming Schedule...")
    schedule_df = loader.get_schedule()

    # Save
    sched_path = processed_dir / "upcoming_schedule.csv"
    schedule_df.to_csv(sched_path, index=False)
    print(f"Saved {len(schedule_df)} future games to {sched_path}")
    print("-" * 30)


if __name__ == "__main__":
    process_data()