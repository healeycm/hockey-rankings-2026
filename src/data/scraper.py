import os
import time
import re
import argparse
import datetime
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- Configuration ---
# Calculate project root assuming this file is in src/data/
CURRENT_FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE_PATH.parents[2]  # Go up: data -> src -> hockey_rankings
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# A full DI season is ~1300-1500 games (63-64 teams x ~34 games, both sides
# counted once each in this row-per-game format). Used only to flag a
# suspiciously small/large scrape for a season that should be complete —
# NOT enforced for the current in-progress season, which legitimately has
# fewer games early on. Women's D-I is a smaller field (~40 programs) with
# a materially different expected range — see
# reports/womens_hockey_import.md for how this was derived (from an actual
# completed season's game count, not guessed).
EXPECTED_FULL_SEASON_GAMES = {
    'men': (1000, 1700),
    # Derived from 5 actually-completed women's seasons (2021-22 through
    # 2025-26): observed range 717-829 games. Bounds set generously wider
    # than that observed range (not tight to it) so a normal season isn't
    # flagged, while still catching a genuinely broken/partial scrape.
    'women': (600, 1000),
}


def setup_driver():
    """Initializes the Firefox Selenium driver with headless options."""
    options = Options()
    options.add_argument("--headless")
    options.page_load_strategy = 'eager'
    options.set_preference("general.useragent.override",
                           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    print("Initializing Firefox Driver...")
    try:
        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(30)
        return driver
    except WebDriverException:
        print("CRITICAL ERROR: Geckodriver not found or Firefox not installed.")
        print("Please ensure geckodriver is in your PATH.")
        return None


def clean_team_name(name):
    """
    Removes text between parentheses and surrounding whitespace.
    Example: "Denver (1) (10-0-0)" -> "Denver"
    """
    if not name:
        return ""
    cleaned = re.sub(r'\s*\(.*?\)', '', name)
    return cleaned.strip()


def get_current_season_code():
    """
    Calculates the current season code (e.g., '20242025') based on today's date.
    If month is roughly Aug-Dec, the season started this year.
    If Jan-July, the season started last year.
    """
    today = datetime.date.today()
    if today.month >= 8:
        start_year = today.year
    else:
        start_year = today.year - 1

    end_year = start_year + 1
    return f"{start_year}{end_year}"


def get_data_for_season(driver, season_code, division='men'):
    """
    Navigates to the specific season URL and extracts game data.

    `division`: 'men' or 'women'. USCHO publishes a structurally identical
    composite schedule at the parallel 'division-i-women' URL (verified
    directly: same #app div, same <tr> row structure, same parsing logic
    applies unchanged — see reports/womens_hockey_import.md).
    """
    url = f"https://www.uscho.com/scoreboard/division-i-{division}/{season_code}/composite-schedule/"
    print(f"Navigating to: {url}")

    try:
        driver.get(url)
    except TimeoutException:
        print("Page load timeout (likely due to ads). Proceeding...")
    except Exception as e:
        print(f"Navigation error for {season_code}: {e}")
        return []

    # --- Wait for Content ---
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "app")))
        time.sleep(3)  # Allow JS to settle
        html = driver.page_source
    except Exception as e:
        print(f"Error extracting content for {season_code}: {e}")
        return []

    # --- Parse HTML ---
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find('div', {'id': 'app'})

    if not content_div:
        print(f"Structure mismatch for {season_code}: 'app' div not found.")
        return []

    rows = content_div.find_all('tr')
    print(f"  - Found {len(rows)} rows for {season_code}.")

    games = []
    last_known_date = "Unknown"

    for row in rows:
        cols = row.find_all('td')

        if len(cols) >= 11:
            try:
                col_texts = [c.get_text(strip=True) for c in cols]

                # Map columns
                day, date, time_val = col_texts[0], col_texts[1], col_texts[2]
                raw_opponent, opponent_score = col_texts[3], col_texts[4]
                home_neutral = col_texts[5]
                raw_home, home_score = col_texts[6], col_texts[7]
                ot_info, notes, game_type = col_texts[8], col_texts[9], col_texts[10]

                visitor_team_final = clean_team_name(raw_opponent)
                home_team_final = clean_team_name(raw_home)

                # Date inheritance
                if date:
                    last_known_date = date
                else:
                    date = last_known_date

                # Logic Analysis
                is_neutral = "vs" in home_neutral.lower().replace('.', '')

                is_final = False
                if opponent_score.isdigit() and home_score.isdigit():
                    is_final = True

                is_exhibition = False
                if "Exhibition" in game_type or "ex" in game_type or "Exhibition" in notes:
                    is_exhibition = True

                is_ot = any(x in ot_info for x in ["OT", "SW", "SO", "ot", "3x3"])

                game_data = {
                    "Day": day, "Date": date, "Time": time_val,
                    "Visitor_Team": visitor_team_final, "Visitor_Score": opponent_score,
                    "Location_Indicator": home_neutral,
                    "Home_Team": home_team_final, "Home_Score": home_score,
                    "OT_Info": ot_info, "Notes": notes, "Type": game_type,
                    "Is_Final": is_final, "Is_Neutral": is_neutral,
                    "Is_Exhibition": is_exhibition, "Is_OT": is_ot,
                    "Season": season_code
                }
                games.append(game_data)
            except Exception:
                continue
    return games


def validate_scraped_season(df, season, is_current_season=False, division='men'):
    """
    Sanity-checks a freshly scraped season before it overwrites the raw CSV.
    Returns a list of warning strings (empty = looks fine). Does not raise —
    a bad scrape should be visible, not silently written over good data
    without a chance to notice, but a partial in-progress season is expected
    to trip the game-count check and that alone shouldn't block a save.
    """
    warnings = []

    n = len(df)
    if not is_current_season:
        lo, hi = EXPECTED_FULL_SEASON_GAMES[division]
        if n < lo or n > hi:
            warnings.append(
                f"Game count {n} is outside the expected full-season range "
                f"[{lo}, {hi}] for season {season}. Scrape may be incomplete "
                f"or the site structure may have changed."
            )

    for col in ('Home_Team', 'Visitor_Team'):
        if col in df.columns:
            n_null = df[col].isna().sum() + (df[col] == '').sum()
            if n_null > 0:
                warnings.append(f"{n_null} rows have a missing/blank {col}.")

    dupe_cols = [c for c in ['Date', 'Home_Team', 'Visitor_Team'] if c in df.columns]
    if dupe_cols:
        n_dupe = df.duplicated(subset=dupe_cols).sum()
        if n_dupe > 0:
            warnings.append(f"{n_dupe} rows look like duplicate games (same {dupe_cols}).")

    if 'Date' in df.columns:
        parsed = pd.to_datetime(df['Date'], errors='coerce')
        n_bad_date = parsed.isna().sum()
        if n_bad_date > 0:
            warnings.append(f"{n_bad_date} rows have an unparseable Date.")
        if parsed.notna().any():
            start_year = int(str(season)[:4])
            expected_range = (pd.Timestamp(f"{start_year}-08-01"), pd.Timestamp(f"{start_year + 1}-06-01"))
            out_of_range = ((parsed < expected_range[0]) | (parsed > expected_range[1])).sum()
            if out_of_range > 0:
                warnings.append(
                    f"{out_of_range} rows have a Date outside the expected "
                    f"{expected_range[0].date()}–{expected_range[1].date()} window for season {season}."
                )

    return warnings


def scrape_seasons(season_list, division='men'):
    """
    Main logic loop to scrape a list of season codes.

    `division`: 'men' (default) writes to data/raw/ exactly as before --
    fully backward compatible, byte-identical paths to the pre-division
    behavior. 'women' writes to data/raw/women/ instead, a pure addition
    that never touches or overlaps the men's files. This physical
    separation is deliberate (see reports/womens_hockey_import.md) — this
    project has hit silent-data-mixing bugs from shared paths/filters
    multiple times (the missing DI-opponent filter, the BacktestEngine
    history_df leak), and a single combined file with a "Division" column
    would depend on every future model/script remembering to filter by it.
    """
    raw_dir = DATA_RAW_DIR if division == 'men' else (DATA_RAW_DIR / division)
    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving data to: {raw_dir}")

    driver = setup_driver()
    if not driver:
        return

    current_code = get_current_season_code()

    for season in season_list:
        print("-" * 40)
        print(f"Starting scrape for Season: {season} ({division})")

        games = get_data_for_season(driver, season, division=division)

        if games:
            df = pd.DataFrame(games)
            # Basic cleaning
            df = df[df['Visitor_Team'] != '']

            issues = validate_scraped_season(df, season, is_current_season=(season == current_code),
                                              division=division)
            if issues:
                print(f"VALIDATION WARNINGS for season {season}:")
                for w in issues:
                    print(f"  - {w}")
            else:
                print(f"Validation OK: {len(df)} games look consistent.")

            # Format filename: games_2024_2025.csv
            y1 = season[:4]
            y2 = season[4:]
            filename = f"games_{y1}_{y2}.csv"
            filepath = raw_dir / filename

            df.to_csv(filepath, index=False)
            print(f"SUCCESS: Saved {len(df)} games to {filename}")
        else:
            print(f"WARNING: No games found for season {season}")

        time.sleep(2)

    driver.quit()
    print("-" * 40)
    print("Scraping complete.")


def main():
    parser = argparse.ArgumentParser(description="Scrape College Hockey Game Data")

    # Flags for different modes
    parser.add_argument('--latest', action='store_true', help="Update only the current season.")
    parser.add_argument('--season', type=str, help="Scrape a specific season (format: YYYYYYYY, e.g., 20232024)")
    parser.add_argument('--history', type=int, default=0, help="Scrape the last N seasons (default: 0).")
    parser.add_argument('--division', type=str, default='men', choices=['men', 'women'],
                         help="'men' (default, writes to data/raw/ as before) or 'women' (writes to data/raw/women/).")

    args = parser.parse_args()

    # Determine which seasons to scrape
    target_seasons = []

    current = get_current_season_code()

    if args.season:
        # Specific season manually provided
        target_seasons.append(args.season)

    elif args.latest:
        # Only the current calculated season
        target_seasons.append(current)

    elif args.history > 0:
        # Generate last N seasons
        curr_start = int(current[:4])
        for i in range(args.history):
            y1 = curr_start - i
            y2 = y1 + 1
            target_seasons.append(f"{y1}{y2}")

    else:
        # Default behavior if no flags: Do Latest + 1 previous (or adjust as preferred)
        print("No specific arguments provided. Defaulting to current season.")
        target_seasons.append(current)

    print(f"Targeting Seasons: {target_seasons} (division={args.division})")
    scrape_seasons(target_seasons, division=args.division)


if __name__ == "__main__":
    main()