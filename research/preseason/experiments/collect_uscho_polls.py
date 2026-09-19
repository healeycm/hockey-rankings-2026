# research/preseason/experiments/collect_uscho_polls.py
"""
PLAN.md P4 (best-effort): collects the USCHO.com preseason poll for every
season in the extended archive, from Wikipedia's per-season
"NCAA Division I men's ice hockey rankings" pages -- NOT from USCHO.com
directly. Wikipedia turned out to be a much better source than USCHO's own
site for this: static HTML (no Selenium needed), a consistent
`<table class="wikitable">` per poll headed by an "USCHO" heading, with a
"Preseason ..." column giving rank 1-20 and team name (+ first-place votes
in parens where applicable) -- confirmed by hand on 2000-01 and 2022-23
before writing this script.

Skip-and-log discipline (per PLAN.md's data-source caution): a season whose
page doesn't exist, doesn't have a USCHO table, or doesn't parse is logged
and skipped, never allowed to crash the whole collection run.

Isolation: reads only from Wikipedia (a public, external, read-only source
unrelated to production's USCHO/CHN scrapers); writes only under
research/preseason/data/polls/ via research_path().

Usage (from project root):
    python -m research.preseason.experiments.collect_uscho_polls
"""
import re
import sys
import time
import urllib.request
import urllib.error
from io import StringIO
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "webpage"))

from research.preseason.harness.paths import research_path  # noqa: E402
from utils.data_loader import get_canonical_name  # noqa: E402 (read-only reuse of production's name matching)

HEADERS = {"User-Agent": "Mozilla/5.0 (research script; college hockey preseason-prior study; no contact)"}
VOTES_RE = re.compile(r"\s*\(\d+\)\s*$")


def safe_print(text):
    """Windows' console codepage (cp1252) can't encode some characters
    Wikipedia uses in team names (en-dashes, etc.) -- replace rather than
    crash the whole collection run over a print statement."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))


def season_code_to_wiki_title(season_code):
    """20222023 -> '2022–23_NCAA_Division_I_men's_ice_hockey_rankings' (URL-encoded)."""
    y1 = str(season_code)[:4]
    y2_short = str(season_code)[6:]
    return f"{y1}%E2%80%93{y2_short}_NCAA_Division_I_men%27s_ice_hockey_rankings"


def fetch_page(season_code):
    url = f"https://en.wikipedia.org/wiki/{season_code_to_wiki_title(season_code)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore"), url


def extract_uscho_preseason_table(html):
    """Returns a DataFrame [Rank, Team, FirstPlaceVotes] for the USCHO
    poll's preseason column, or None if not found."""
    soup = BeautifulSoup(html, "html.parser")
    uscho_table = None
    for table in soup.find_all("table", class_="wikitable"):
        heading = table.find_previous(["h2", "h3"])
        if heading and "uscho" in heading.get_text(strip=True).lower():
            uscho_table = table
            break
    if uscho_table is None:
        return None

    dfs = pd.read_html(StringIO(str(uscho_table)))
    if not dfs:
        return None
    df = dfs[0]

    preseason_col = next((c for c in df.columns if str(c).strip().lower().startswith("preseason")), None)
    rank_col = df.columns[0]

    if preseason_col is None:
        # Older pages (confirmed on 2001-02) render the header row as plain
        # <td> cells, which pandas.read_html doesn't recognize as column
        # headers -- it ends up as row 0 of the data instead, with integer
        # column names. Detect that case: row 0's first cell is NaN (no
        # rank yet) and one of its other cells starts with "Preseason".
        if pd.isna(df.iloc[0, 0]):
            candidate_header = df.iloc[0]
            preseason_col = next((c for c in df.columns if str(candidate_header[c]).strip().lower().startswith("preseason")), None)
            if preseason_col is not None:
                df = df.iloc[1:].reset_index(drop=True)

    if preseason_col is None:
        return None

    rows = []
    for _, row in df.iterrows():
        rank = row[rank_col]
        team_cell = row[preseason_col]
        try:
            rank = int(float(rank))
        except (ValueError, TypeError):
            continue
        if not (1 <= rank <= 40) or pd.isna(team_cell):
            continue
        team_cell = str(team_cell).strip()
        votes_match = VOTES_RE.search(team_cell)
        votes = int(re.search(r"\d+", votes_match.group()).group()) if votes_match else 0
        team = VOTES_RE.sub("", team_cell).strip()
        if not team or team.lower().startswith("preseason"):
            continue
        rows.append({"Rank": rank, "Team": team, "FirstPlaceVotes": votes})

    if not rows:
        return None
    return pd.DataFrame(rows).drop_duplicates(subset="Rank").sort_values("Rank").reset_index(drop=True)


def main():
    archive = pd.read_csv(PROJECT_ROOT / "research" / "preseason" / "data" / "extended_archive.csv")
    seasons = sorted(archive['Season'].unique())

    log_rows = []
    out_dir = research_path("data", "polls", "_log.csv", mkdir_parent=True).parent

    for season in seasons:
        print(f"Fetching poll for {season}...")
        try:
            html, url = fetch_page(season)
        except urllib.error.HTTPError as e:
            print(f"  ! HTTP {e.code} -- skipping")
            log_rows.append({"Season": season, "Status": "http_error", "Detail": str(e), "Teams": 0})
            time.sleep(1)
            continue
        except Exception as e:
            print(f"  ! Fetch failed: {e} -- skipping")
            log_rows.append({"Season": season, "Status": "fetch_error", "Detail": str(e), "Teams": 0})
            time.sleep(1)
            continue

        try:
            poll_df = extract_uscho_preseason_table(html)
        except Exception as e:
            print(f"  ! Parse failed: {e} -- skipping")
            log_rows.append({"Season": season, "Status": "parse_error", "Detail": str(e), "Teams": 0})
            time.sleep(1)
            continue

        if poll_df is None or poll_df.empty:
            print("  ! No USCHO preseason table found -- skipping")
            log_rows.append({"Season": season, "Status": "no_table", "Detail": "", "Teams": 0})
            time.sleep(1)
            continue

        # Canonicalize team names to match production's USCHO naming
        # (get_canonical_name falls back to the input unchanged if no
        # mapping is found -- logged here so unmatched names are visible,
        # not silently wrong).
        poll_df['CanonicalTeam'] = poll_df['Team'].apply(get_canonical_name)
        unmatched = poll_df[poll_df['CanonicalTeam'] == poll_df['Team']]['Team'].tolist()

        out_path = out_dir / f"poll_{season}.csv"
        poll_df.to_csv(out_path, index=False)
        detail = f"{len(poll_df)} teams" + (f"; unresolved names (kept as-is): {unmatched}" if unmatched else "")
        safe_print(f"  -> {detail}")
        log_rows.append({"Season": season, "Status": "ok", "Detail": detail, "Teams": len(poll_df)})
        time.sleep(1)  # polite delay between Wikipedia requests

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(out_dir / "_log.csv", index=False)
    safe_print("\n" + "=" * 60)
    safe_print(log_df.to_string(index=False))
    print(f"\nLog written to {out_dir / '_log.csv'}")


if __name__ == "__main__":
    main()
