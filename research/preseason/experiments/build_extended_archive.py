# research/preseason/experiments/build_extended_archive.py
"""
Builds a research-only extended game archive: production's 2011-12+ raw
seasons, plus the pre-2011 seasons recovered by probe_pre2011_scrape.py
(2001-02 through 2008-09, and 2010-11 -- 2009-10 excluded, see
research/preseason/reports/probe_pre2011_scrape.md: USCHO silently aliases
that URL to the 2010-11 schedule).

Isolation: copies raw CSVs into research/preseason/data/extended_raw/ (never
reads/writes data/raw/ in place) and reuses src/data/loader.py's DataLoader
UNMODIFIED (read-only reuse) to parse/dedupe/compute results -- the same
validated logic production uses, including the exact-duplicate-row fix
(src/data/loader.py's `_load_all_raw`). Output goes only to
research/preseason/data/extended_archive.csv via research_path().

Usage (from project root):
    python -m research.preseason.experiments.build_extended_archive
"""
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loader import DataLoader  # noqa: E402
from research.preseason.harness.paths import research_path  # noqa: E402

PRODUCTION_RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROBE_DIR = research_path("data", "pre2011_probe", "probe_log.csv", mkdir_parent=False).parent
EXCLUDED_SEASONS = {"20092010"}  # confirmed URL-aliasing bug, see probe report


def main():
    extended_raw_dir = research_path("data", "extended_raw", "_placeholder", mkdir_parent=True).parent

    # 1. Copy production's raw men's season files (2011-12 onward) as-is.
    n_copied = 0
    for f in sorted(PRODUCTION_RAW_DIR.glob("games_*.csv")):
        shutil.copy2(f, extended_raw_dir / f.name)
        n_copied += 1
    print(f"Copied {n_copied} production raw season files (2011-12+).")

    # 2. Copy the recovered pre-2011 seasons, excluding the aliased one.
    n_recovered = 0
    for f in sorted(PROBE_DIR.glob("games_*.csv")):
        season = f.stem.replace("games_", "")
        if season in EXCLUDED_SEASONS:
            print(f"Skipping {f.name} (confirmed URL-aliasing bug, not real 2009-10 data).")
            continue
        shutil.copy2(f, extended_raw_dir / f.name)
        n_recovered += 1
    print(f"Copied {n_recovered} recovered pre-2011 season files.")

    # 3. Parse via the SAME production DataLoader (unmodified) -- includes
    # the exact-duplicate-row fix, exhibition filter, and Result computation.
    loader = DataLoader(data_dir=extended_raw_dir)
    history_df = loader.get_history()
    history_df = history_df[~history_df['HomeTeam'].str.contains("Exhibition", case=False, na=False)]

    out_path = research_path("data", "extended_archive.csv")
    history_df.to_csv(out_path, index=False)

    seasons = sorted(history_df['Season'].unique())
    print(f"\nSaved {len(history_df)} games across {len(seasons)} seasons to {out_path}")
    print(f"Seasons: {seasons}")


if __name__ == "__main__":
    main()
