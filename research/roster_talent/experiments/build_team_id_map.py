# research/roster_talent/experiments/build_team_id_map.py
"""
R0: scrapes /reports/standings.php for every team's CHN slug + numeric ID
(the roster/stats URLs need both, e.g. /reports/roster/Michigan/31), and
cross-checks the result against data/teams/team_info.csv's CHN_Name column
(read-only) so naming mismatches are visible before R1/R2 scrape ~2,800
pages against a possibly-wrong team list.

Run from the project root:
    python -m research.roster_talent.experiments.build_team_id_map
"""
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from research.roster_talent.harness.paths import research_path  # noqa: E402
from research.roster_talent.harness.scrape import fetch  # noqa: E402

STANDINGS_PATH = "/reports/standings.php"
ROSTER_LINK_RE = re.compile(r"^/reports/roster/([^/]+)/(\d+)$")


def parse_team_links(html):
    """The roster link's own text is just the label "Roster" -- the real
    team name is in its `title` attribute, e.g. title="Michigan Roster"
    (confirmed by inspecting the raw HTML: standings.php lists each team as
    a <p> block with team-page/schedule/roster/stats links side by side,
    all sharing the same numeric ID)."""
    soup = BeautifulSoup(html, "html.parser")
    teams = {}
    for a in soup.find_all("a", href=True):
        m = ROSTER_LINK_RE.match(a["href"])
        if m:
            slug, team_id = m.group(1), int(m.group(2))
            title = a.get("title", "")
            name = title[:-len(" Roster")].strip() if title.endswith(" Roster") else slug.replace("-", " ")
            teams[team_id] = {"TeamID": team_id, "Slug": slug, "Name": name}
    return list(teams.values())


def main():
    print(f"Fetching {STANDINGS_PATH}...")
    html, err = fetch(STANDINGS_PATH)
    if html is None:
        print(f"FAILED: {err}")
        sys.exit(1)

    teams = parse_team_links(html)
    if not teams:
        print("No team roster links found on the standings page -- page structure may have changed.")
        sys.exit(1)

    df = pd.DataFrame(teams).sort_values("Name").reset_index(drop=True)
    print(f"Found {len(df)} teams.")

    # Cross-check against production's team_info.csv (read-only reference,
    # not edited) to catch naming mismatches before the big R1/R2 scrapes.
    team_info_path = PROJECT_ROOT / "data" / "teams" / "team_info.csv"
    if team_info_path.exists():
        prod_names = set(pd.read_csv(team_info_path)['CHN_Name'].dropna())
        df['InProductionTeamInfo'] = df['Name'].isin(prod_names)
        unmatched = df[~df['InProductionTeamInfo']]['Name'].tolist()
        if unmatched:
            print(f"{len(unmatched)} CHN team names not found in data/teams/team_info.csv's CHN_Name "
                  f"column (may just be a naming variant, e.g. 'St. Cloud State' vs 'St Cloud State' "
                  f"-- worth a manual look before relying on this for joins): {unmatched}")

    out_path = research_path("data", "team_id_map.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
