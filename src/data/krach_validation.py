import requests
import pandas as pd
import time
import random
import sys
from pathlib import Path
import logging

# --- Configuration ---
# Calculate project root: src/data/krach_validation.py -> ... -> hockey_rankings
CURRENT_FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE_PATH.parents[2]
VALIDATION_DIR = PROJECT_ROOT / "data" / "validation"

sys.path.insert(0, str(PROJECT_ROOT))
from src.utils.season import get_current_season_code, season_end_year

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def flatten_cols(df):
    """
    Flattens MultiIndex columns (tuples) into strings if they exist.
    Example: ('Conference', 'W') -> 'Conference_W'
    """
    if isinstance(df.columns, pd.MultiIndex):
        # Join levels with underscore, filtering out empty strings
        df.columns = [
            '_'.join([str(c) for c in col if str(c) and "Unnamed" not in str(c)]).strip()
            for col in df.columns.values
        ]
    return df


def get_chn_ratings(year):
    """
    Fetches ratings from College Hockey News for a specific year ending.
    URL: https://www.collegehockeynews.com/ratings/chn-power-ratings/{year}
    """
    url = f"https://www.collegehockeynews.com/ratings/chn-power-ratings/{year}"
    logging.info(f"Fetching: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Parse tables
        dfs = pd.read_html(response.text)

        target_df = None
        for df in dfs:
            # 1. Flatten columns to handle MultiIndex headers (Fixes 'tuple' error)
            df = flatten_cols(df)

            # 2. Check for characteristic columns
            # Convert to lower string safely
            cols = [str(c).lower() for c in df.columns]

            # CHN ratings usually have 'Team' and 'Rating' or 'PWR'
            if 'team_team' in cols and ('krach_rating' in cols or 'pwr' in cols or 'krach' in cols):
                target_df = df
                break

        if target_df is None:
            logging.warning(f"Could not find a valid ratings table for {year}.")
            return None

        # Clean up
        # Find the actual 'Team' column name (case insensitive match)
        team_col = next((c for c in target_df.columns if str(c).lower() == 'Team_Team'), None)

        if team_col:
            target_df[team_col] = target_df[team_col].astype(str).str.strip()
            # Standardize column name
            target_df.rename(columns={team_col: 'Team'}, inplace=True)

        target_df['Season_End_Year'] = year

        return target_df

    except Exception as e:
        logging.error(f"Error fetching data for {year}: {e}")
        return None


def main():
    # Ensure output directory exists
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    # Define range: last 10 seasons, ending with the current one.
    current_end_year = season_end_year(get_current_season_code())
    start_year = current_end_year - 9

    years = range(start_year, current_end_year + 1)

    logging.info(f"Starting CHN Validation Scrape for years: {list(years)}")
    logging.info(f"Output Directory: {VALIDATION_DIR}")

    for year in years:
        df = get_chn_ratings(year)

        if df is not None:
            filename = f"chn_krach_{year}.csv"
            output_path = VALIDATION_DIR / filename

            df.to_csv(output_path, index=False)
            logging.info(f"Saved {len(df)} rows to {filename}")

        # Be polite to the server
        sleep_time = random.uniform(2, 5)
        time.sleep(sleep_time)

    logging.info("Scraping complete.")


if __name__ == "__main__":
    main()