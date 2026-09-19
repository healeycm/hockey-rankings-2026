import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.season import get_current_season_code

# --- Configuration ---
# Scrape the two most recent seasons (prior + current) by default. Pass an
# explicit list of season code strings (e.g. ["20242025", "20252026"]) if you
# need a different range.
_current = get_current_season_code()
_previous = _current - 10001  # e.g. 20262027 -> 20252026 (shift both year halves by 1)
SEASONS = [str(_previous), str(_current)]
BASE_URL = "https://www.collegehockeynews.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Debug Limit: Set to integer (e.g., 10) to test quickly, or None to run full season
DEBUG_LIMIT = None

CURRENT_FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE_PATH.parents[2]  # Go up: data -> src -> hockey_rankings
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw_advanced"


def clean_text(text):
    """Removes rankings (e.g., '(10)') and whitespace."""
    if not text: return None
    # Remove parens with numbers inside, e.g. (1) or (10)
    cleaned = re.sub(r'\s*\(\d+\)', '', text)
    return cleaned.strip()


def get_col_index(header_row, target_name):
    """Finds the index of a column header (case-insensitive)."""
    cols = header_row.find_all(['th', 'td'])
    for i, col in enumerate(cols):
        if target_name.lower() == col.get_text(strip=True).lower():
            return i
    return -1


def extract_stat_from_div(soup, div_id, col_name):
    """
    Generic extractor for your specific DOM logic:
    1. Find <div id="div_id">
    2. Find the table inside it.
    3. Find the column index for "col_name".
    4. Return tuple (TopRowVal, BottomRowVal) -> (Away, Home).
    """
    container = soup.find("div", id=div_id)
    if not container:
        return None, None

    table = container.find("table")
    if not table:
        return None, None

    rows = table.find_all("tr")
    if len(rows) < 3:  # Header + Away + Home
        return None, None

    # 1. Find Header Index
    header_idx = get_col_index(rows[0], col_name)
    if header_idx == -1:
        return None, None

    # 2. Get Values (Row 1 = Away, Row 2 = Home)
    try:
        away_cells = rows[1].find_all('td')
        home_cells = rows[2].find_all('td')

        val_away = away_cells[header_idx].get_text(strip=True)
        val_home = home_cells[header_idx].get_text(strip=True)
        return val_away, val_home
    except IndexError:
        return None, None


def extract_empty_net_goals(soup):
    """
    Parses the <div id="scoring"> goal-by-goal table and counts empty-net
    goals for each side.

    CHN tags each goal's row with a CSS class of 'vscore' (visiting/away
    team scored) or 'hscore' (home team scored) — this is used instead of
    the team-name text in the first <td>, which is inconsistently an
    abbreviation ("MSU") or a full name ("Michigan") depending on the game.
    The second <td> holds the situation tag: blank (even strength), 'PP',
    'SH', '3x3' (OT), or 'EN' (empty net) — exact text match, whitespace
    stripped.

    Returns (away_eng, home_eng) as ints. Returns (None, None) if no
    scoring table is found (e.g. page layout differs or fetch failed).
    """
    container = soup.find("div", id="scoring")
    if not container:
        return None, None

    away_eng = 0
    home_eng = 0
    for row in container.find_all("tr", class_=["vscore", "hscore"]):
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        situation = tds[1].get_text(strip=True)
        if situation == "EN":
            if "vscore" in row.get("class", []):
                away_eng += 1
            else:
                home_eng += 1

    return away_eng, home_eng


def extract_even_manpower_goals(soup):
    """
    Sibling to extract_empty_net_goals() — same <div id="scoring"> table,
    same 'vscore'/'hscore' row tagging, same situation-tag column — but
    counts EVEN-MANPOWER goals instead of empty-net goals. Used to build a
    "manpower-adjusted" margin (reports/massey_experiments_2026.md) that
    excludes power-play/short-handed goals, isolating how a team performed
    when neither side had a man advantage.

    "Even manpower" here means situation in ('', '3x3') — a blank tag (5-on-5)
    or '3x3' (3-on-3 sudden-death overtime, still no man advantage even
    though it's not literally 5-on-5). 'PP'/'SH' (a man advantage/
    disadvantage) and 'EN' (empty net — a distinct "game already decided"
    phenomenon, not a manpower situation reflecting team ability, and
    already excluded here the same way extract_empty_net_goals() treats it
    separately) are excluded from the count.

    Returns (away_ev_goals, home_ev_goals) as ints. Returns (None, None) if
    no scoring table is found (e.g. page layout differs or fetch failed).
    """
    container = soup.find("div", id="scoring")
    if not container:
        return None, None

    away_ev = 0
    home_ev = 0
    EVEN_MANPOWER_TAGS = ("", "3x3")
    for row in container.find_all("tr", class_=["vscore", "hscore"]):
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        situation = tds[1].get_text(strip=True)
        if situation in EVEN_MANPOWER_TAGS:
            if "vscore" in row.get("class", []):
                away_ev += 1
            else:
                home_ev += 1

    return away_ev, home_ev


def scrape_schedule(season):
    """
    Scrapes the schedule page to get a list of games with Metadata + Box Score Link.
    This ensures we get Team Names from the main list.
    """
    url = f"{BASE_URL}/schedules/?season={season}"
    print(f"Scraping schedule: {url}")

    games = []

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # CHN Schedule is usually a large table
        # We iterate through rows looking for the "Box" link

        # Iterate all rows in the main content area
        for tr in soup.find_all("tr"):
            # Look for the Box Score link
            box_link = tr.find("a", href=True, string=re.compile("Box"))

            if box_link and "/box/final/" in box_link['href']:
                full_link = f"{BASE_URL}{box_link['href']}" if box_link['href'].startswith("/") else box_link['href']

                # Extract Teams from this row
                # Structure is typically: Date | Visitor | Home | ...
                tds = tr.find_all("td")

                # Usually Visitor is index 1, Home is index 2 (Index 0 is Date)
                # But sometimes structure varies. Let's assume standard layout.
                if len(tds) >= 4:
                    visitor_text = clean_text(tds[0].get_text(strip=True))
                    home_text = clean_text(tds[3].get_text(strip=True))

                    games.append({
                        "season": season,
                        "away_team": visitor_text,
                        "home_team": home_text,
                        "url": full_link
                    })

        # Remove duplicates based on URL
        unique_games = {v['url']: v for v in games}.values()
        return list(unique_games)

    except Exception as e:
        print(f"Error scraping schedule for {season}: {e}")
        return []


def parse_box_score(game_meta):
    """
    Visits the box score URL and fills in Goals, Shots, and xG
    using the specific IDs provided.
    """
    url = game_meta['url']

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # 1. Goals: <div id="goals"> column "T"
        g_away, g_home = extract_stat_from_div(soup, "goals", "T")
        game_meta['away_goals'] = g_away
        game_meta['home_goals'] = g_home

        # 2. Shots: <div id="shots"> column "T"
        s_away, s_home = extract_stat_from_div(soup, "shots", "T")
        game_meta['away_shots'] = s_away
        game_meta['home_shots'] = s_home

        # 3. Expected Goals: <div id="pp"> column "xG"
        # Note: 'pp' usually contains the Advanced Stats table in new CHN layout
        x_away, x_home = extract_stat_from_div(soup, "pp", "xG")
        game_meta['away_xg'] = x_away
        game_meta['home_xg'] = x_home

        # 4. Empty-net goals: <div id="scoring"> goal-by-goal table
        eng_away, eng_home = extract_empty_net_goals(soup)
        game_meta['away_eng'] = eng_away
        game_meta['home_eng'] = eng_home

        # 5. Even-manpower goals: same table, see extract_even_manpower_goals()
        ev_away, ev_home = extract_even_manpower_goals(soup)
        game_meta['away_ev_goals'] = ev_away
        game_meta['home_ev_goals'] = ev_home

        return game_meta

    except Exception as e:
        print(f"Error parsing box score {url}: {e}")
        return game_meta  # Return partial data


def main():
    final_data = []

    for season in SEASONS:
        # Step 1: Get list of games and names from Schedule Page
        games = scrape_schedule(season)
        print(f"Found {len(games)} games for {season}")

        if DEBUG_LIMIT:
            print(f"DEBUG: Processing first {DEBUG_LIMIT} only.")
            games = games[:DEBUG_LIMIT]
        final_data = []
        # Step 2: Visit each box score to get stats
        for i, game in enumerate(games):
            print(f"[{i + 1}/{len(games)}] {game['away_team']} @ {game['home_team']} ... ", end="")

            updated_game = parse_box_score(game)

            # Print status check
            if updated_game.get('away_xg'):
                print(f"xG: {updated_game['away_xg']}-{updated_game['home_xg']}")
            elif updated_game.get('away_goals'):
                print(f"Goals: {updated_game['away_goals']}-{updated_game['home_goals']} (No xG)")
            else:
                print("Failed to parse stats.")

            final_data.append(updated_game)
            # Be polite
            time.sleep(1)

        y1 = season[:4]
        y2 = season[4:]
        filename = f"chn_games_{y1}_{y2}.csv"
        filepath = DATA_RAW_DIR / filename

        df = pd.DataFrame(final_data)

        # Reorder columns for cleanliness
        cols = ['season', 'date', 'away_team', 'home_team', 'away_goals', 'home_goals',
                'away_shots', 'home_shots', 'away_xg', 'home_xg',
                'away_eng', 'home_eng', 'url']

        cols = [c for c in cols if c in df.columns]
        df = df[cols]

        df.to_csv(filepath, index=False)
        print(f"\nCompleted. Data saved to {filepath}")



    # Save

if __name__ == "__main__":
    main()