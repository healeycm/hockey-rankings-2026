"""
Game-by-game WP comparison: Our NPI vs CHN detail pages (fetched 2026-03-22).
Teams: Merrimack, Mercyhurst, Miami, Michigan, Colgate.
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.rankings.npi import NPI

# CHN name -> our USCHO name
NAME_MAP = {
    "Mass.-Lowell": "UMass Lowell",
    "Long Island": "LIU",
    "Minnesota-Duluth": "Minnesota Duluth",
}

# CHN reference data: (date, opponent_chn_name, wtw, wtl)
CHN_DATA = {
    "Merrimack": [
        ("10/03", "Mass.-Lowell", 0.00, 0.80),
        ("10/10", "Mass.-Lowell", 0.80, 0.00),
        ("10/18", "New Hampshire", 0.80, 0.00),
        ("10/24", "Quinnipiac", 0.80, 0.00),
        ("10/25", "Long Island", 0.00, 1.20),
        ("11/01", "Connecticut", 0.00, 0.80),
        ("11/07", "Boston University", 0.48, 0.52),  # OT Loss Away
        ("11/08", "Boston University", 0.00, 1.20),
        ("11/14", "Providence", 0.00, 0.80),
        ("11/15", "Providence", 0.80, 0.00),
        ("11/21", "Long Island", 1.20, 0.00),
        ("11/26", "Notre Dame", 0.00, 1.20),
        ("11/29", "Dartmouth", 0.00, 0.80),
        ("12/05", "Connecticut", 0.00, 1.20),
        ("12/06", "Connecticut", 0.00, 0.80),
        ("12/12", "Yale", 0.80, 0.00),
        ("12/13", "Long Island", 0.80, 0.00),
        ("12/29", "Vermont", 1.20, 0.00),
        ("01/03", "Brown", 1.20, 0.00),
        ("01/10", "Holy Cross", 1.20, 0.00),
        ("01/16", "Massachusetts", 0.00, 1.20),
        ("01/17", "Massachusetts", 0.00, 0.80),
        ("01/22", "Northeastern", 0.80, 0.00),
        ("01/23", "Northeastern", 0.80, 0.00),
        ("01/30", "New Hampshire", 0.80, 0.00),
        ("01/31", "New Hampshire", 0.60, 0.40),  # Tie Away
        ("02/03", "Stonehill", 1.20, 0.00),
        ("02/13", "Boston College", 0.80, 0.00),
        ("02/14", "Boston College", 0.00, 0.80),
        ("02/20", "Maine", 0.00, 0.80),
        ("02/21", "Maine", 0.00, 0.80),
        ("02/27", "Vermont", 0.80, 0.00),
        ("02/28", "Vermont", 0.40, 0.60),  # Tie Home
        ("03/05", "Mass.-Lowell", 0.80, 0.00),
        ("03/11", "Mass.-Lowell", 1.00, 0.00),  # CT
        ("03/14", "Providence", 1.00, 0.00),  # CT OT Win
        ("03/20", "Massachusetts", 1.00, 0.00),  # Neutral
        ("03/21", "Connecticut", 1.00, 0.00),  # Neutral - we may not have
    ],
    "Michigan": [
        ("10/03", "Mercyhurst", 0.80, 0.00),
        ("10/04", "Mercyhurst", 0.80, 0.00),
        ("10/10", "Providence", 1.20, 0.00),
        ("10/11", "Providence", 1.20, 0.00),
        ("10/16", "Robert Morris", 0.80, 0.00),
        ("10/17", "Robert Morris", 0.80, 0.00),
        ("10/23", "Western Michigan", 0.80, 0.00),
        ("10/24", "Western Michigan", 0.00, 0.80),
        ("10/31", "Notre Dame", 1.20, 0.00),
        ("11/01", "Notre Dame", 0.68, 0.32),  # OT Win Away
        ("11/07", "Wisconsin", 0.80, 0.00),
        ("11/08", "Wisconsin", 0.00, 1.20),
        ("11/14", "Penn State", 1.20, 0.00),
        ("11/15", "Penn State", 0.00, 0.80),
        ("11/21", "Ohio State", 0.80, 0.00),
        ("11/22", "Ohio State", 0.80, 0.00),
        ("11/28", "Harvard", 1.20, 0.00),
        ("11/29", "Harvard", 0.68, 0.32),  # OT Win Away
        ("12/05", "Michigan State", 1.20, 0.00),
        ("12/06", "Michigan State", 0.00, 1.20),
        ("01/09", "Notre Dame", 0.80, 0.00),
        ("01/10", "Notre Dame", 0.80, 0.00),
        ("01/16", "Minnesota", 1.20, 0.00),
        ("01/17", "Minnesota", 0.68, 0.32),  # OT Win Away
        ("01/30", "Ohio State", 1.20, 0.00),
        ("01/31", "Ohio State", 0.68, 0.32),  # OT Win Away
        ("02/06", "Michigan State", 0.52, 0.48),  # OT Win Home
        ("02/07", "Michigan State", 0.00, 1.00),  # Neutral Loss
        ("02/13", "Penn State", 0.40, 0.60),  # Tie Home
        ("02/14", "Penn State", 0.80, 0.00),
        ("02/20", "Wisconsin", 0.00, 0.80),
        ("02/21", "Wisconsin", 1.20, 0.00),
        ("02/26", "Minnesota", 0.00, 1.20),
        ("02/27", "Minnesota", 0.80, 0.00),
        ("03/11", "Notre Dame", 1.00, 0.00),  # CT
        ("03/14", "Penn State", 1.00, 0.00),  # CT
        ("03/21", "Ohio State", 1.00, 0.00),  # Neutral - we may not have
    ],
    "Mercyhurst": [
        ("10/03", "Michigan", 0.00, 0.80),
        ("10/04", "Michigan", 0.00, 0.80),
        ("10/10", "Union", 0.00, 1.20),
        ("10/11", "Union", 0.00, 1.20),
        ("10/18", "Holy Cross", 0.00, 1.20),
        ("10/24", "Mass.-Lowell", 0.00, 1.20),
        ("10/25", "Mass.-Lowell", 0.00, 1.20),
        ("10/31", "Bentley", 0.00, 1.20),
        ("11/01", "Bentley", 0.00, 1.20),
        ("11/07", "RIT", 0.00, 0.80),
        ("11/08", "RIT", 0.00, 0.80),
        ("11/21", "Canisius", 0.00, 0.80),
        ("11/22", "Canisius", 0.00, 0.80),
        ("11/28", "Robert Morris", 0.00, 1.20),
        ("11/29", "Robert Morris", 0.60, 0.40),  # Tie Away
        ("12/06", "Holy Cross", 0.00, 0.80),
        ("01/02", "North Dakota", 0.00, 0.80),
        ("01/03", "North Dakota", 0.00, 0.80),
        ("01/09", "Army", 0.80, 0.00),
        ("01/10", "Army", 0.00, 1.20),
        ("01/16", "Niagara", 0.80, 0.00),
        ("01/17", "Niagara", 1.20, 0.00),
        ("01/23", "Canisius", 0.00, 1.20),
        ("01/24", "Canisius", 0.00, 1.20),
        ("01/30", "RIT", 0.40, 0.60),  # Tie Home
        ("01/31", "RIT", 0.00, 1.20),
        ("02/06", "Sacred Heart", 0.00, 0.80),
        ("02/07", "Sacred Heart", 1.20, 0.00),
        ("02/13", "Air Force", 0.60, 0.40),  # Tie Away
        ("02/14", "Air Force", 0.00, 0.80),
        ("02/20", "Niagara", 0.80, 0.00),
        ("02/21", "Niagara", 0.00, 0.80),
        ("02/27", "Robert Morris", 0.00, 1.20),
        ("02/28", "Robert Morris", 0.00, 0.80),
        ("03/03", "Canisius", 1.00, 0.00),  # CT
        ("03/06", "Bentley", 0.00, 1.00),  # CT OT Loss
        ("03/07", "Bentley", 0.00, 1.00),  # CT
    ],
    "Miami": [
        ("10/03", "Ferris State", 0.80, 0.00),
        ("10/04", "Ferris State", 0.80, 0.00),
        ("10/10", "RPI", 1.20, 0.00),
        ("10/11", "RPI", 1.20, 0.00),
        ("10/24", "Lindenwood", 0.68, 0.32),  # OT Win Away
        ("10/25", "Lindenwood", 0.68, 0.32),  # OT Win Away
        ("10/31", "Arizona State", 0.00, 1.20),
        ("11/01", "Arizona State", 0.80, 0.00),
        ("11/14", "Western Michigan", 0.00, 0.80),
        ("11/15", "Western Michigan", 0.00, 0.80),
        ("11/21", "St. Cloud State", 0.52, 0.48),  # OT Win Home
        ("11/22", "St. Cloud State", 0.00, 1.20),
        ("11/28", "RIT", 1.00, 0.00),  # Neutral
        ("11/29", "Union", 1.00, 0.00),  # Neutral
        ("12/05", "Denver", 0.00, 0.80),
        ("12/06", "Denver", 0.00, 0.80),
        ("12/12", "Colorado College", 0.40, 0.60),  # Tie Home
        ("12/13", "Colorado College", 0.40, 0.60),  # Tie Home
        ("12/28", "Michigan Tech", 0.00, 1.00),  # Neutral Loss
        ("12/29", "Ferris State", 1.00, 0.00),  # Neutral
        ("01/09", "Arizona State", 0.68, 0.32),  # OT Win Away
        ("01/10", "Arizona State", 0.00, 0.80),
        ("01/16", "Omaha", 0.80, 0.00),
        ("01/17", "Omaha", 0.80, 0.00),
        ("01/30", "St. Cloud State", 1.20, 0.00),
        ("01/31", "St. Cloud State", 1.20, 0.00),
        ("02/06", "Western Michigan", 0.52, 0.48),  # OT Win Home
        ("02/07", "Western Michigan", 0.00, 1.20),
        ("02/13", "North Dakota", 0.00, 0.80),
        ("02/14", "North Dakota", 0.48, 0.52),  # OT Loss Away
        ("02/20", "Minnesota-Duluth", 0.00, 1.20),
        ("02/21", "Minnesota-Duluth", 0.00, 1.20),
        ("02/27", "Omaha", 0.00, 0.80),
        ("02/28", "Omaha", 1.20, 0.00),
        ("03/06", "Denver", 0.00, 1.00),  # CT
        ("03/07", "Denver", 0.00, 1.00),  # CT
    ],
    "Colgate": [
        ("10/10", "Boston University", 0.00, 0.80),
        ("10/11", "Boston University", 0.60, 0.40),  # Tie Away
        ("10/17", "Canisius", 0.00, 1.20),
        ("10/18", "Canisius", 0.80, 0.00),
        ("10/24", "Maine", 1.20, 0.00),
        ("10/25", "Maine", 0.48, 0.52),  # OT Loss Away
        ("10/31", "RIT", 0.00, 1.20),
        ("11/01", "RIT", 0.00, 1.20),
        ("11/07", "Dartmouth", 0.00, 0.80),
        ("11/08", "Harvard", 0.00, 0.80),
        ("11/14", "Yale", 0.52, 0.48),  # OT Win Home
        ("11/15", "Brown", 0.80, 0.00),
        ("11/21", "RPI", 0.80, 0.00),
        ("11/22", "Union", 0.40, 0.60),  # Tie Home
        ("11/26", "Michigan State", 0.00, 0.80),
        ("11/28", "Michigan State", 0.00, 0.80),
        ("12/05", "St. Lawrence", 1.20, 0.00),
        ("12/06", "Clarkson", 0.00, 0.80),
        ("01/03", "New Hampshire", 1.20, 0.00),
        ("01/04", "New Hampshire", 0.00, 0.80),
        ("01/16", "Quinnipiac", 0.00, 1.20),
        ("01/17", "Princeton", 0.80, 0.00),
        ("01/23", "Harvard", 0.00, 1.20),
        ("01/24", "Dartmouth", 0.80, 0.00),
        ("01/30", "Brown", 0.60, 0.40),  # Tie Away
        ("01/31", "Yale", 1.20, 0.00),
        ("02/06", "Cornell", 0.00, 1.20),
        ("02/07", "Cornell", 0.68, 0.32),  # OT Win Away
        ("02/13", "Union", 0.00, 0.80),
        ("02/14", "RPI", 0.00, 0.80),
        ("02/20", "Princeton", 0.60, 0.40),  # Tie Away
        ("02/21", "Quinnipiac", 0.00, 0.80),
        ("02/27", "Clarkson", 0.00, 1.20),
        ("02/28", "St. Lawrence", 0.80, 0.00),
        ("03/07", "Yale", 1.00, 0.00),  # CT
        ("03/13", "Dartmouth", 0.00, 1.00),  # CT
        ("03/14", "Dartmouth", 0.00, 1.00),  # CT
    ],
}


def compare_team(team_name, chn_games, npi):
    """Compare game-by-game Wt.W/Wt.L for a team."""
    print(f"\n{'='*70}")
    print(f"  {team_name}")
    print(f"{'='*70}")

    our_games = []
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == team_name:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            opp = row['AwayTeam']
        elif row['AwayTeam'] == team_name:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            opp = row['HomeTeam']
        else:
            continue

        try:
            dt = pd.Timestamp(row['Date'])
            mm_dd = dt.strftime('%m/%d')
        except:
            mm_dd = str(row['Date'])

        # Wt.W = pts, Wt.L = wgt - pts (always sums to weight)
        wtw = pts
        wtl = wgt - pts

        our_games.append({
            'date': mm_dd,
            'opp': opp,
            'wtw': round(wtw, 4),
            'wtl': round(wtl, 4),
            'is_ot': row.get('IsOT', False),
            'type': row.get('Type', ''),
            'result': row['Result'],
            'neutral': row.get('NeutralSite', False),
        })

    # Match and compare
    mismatches = []
    matched = 0
    unmatched_chn = []
    used_our = set()

    for chn_date, chn_opp, chn_wtw, chn_wtl in chn_games:
        mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
        found = False

        for i, g in enumerate(our_games):
            if i in used_our:
                continue
            if g['date'] == chn_date and g['opp'] == mapped_opp:
                used_our.add(i)
                matched += 1
                wtw_diff = abs(g['wtw'] - chn_wtw)
                wtl_diff = abs(g['wtl'] - chn_wtl)
                if wtw_diff > 0.005 or wtl_diff > 0.005:
                    mismatches.append({
                        'date': chn_date,
                        'opp': chn_opp,
                        'chn_wtw': chn_wtw, 'chn_wtl': chn_wtl,
                        'our_wtw': g['wtw'], 'our_wtl': g['wtl'],
                        'is_ot': g['is_ot'], 'type': g['type'],
                        'result': g['result'], 'neutral': g['neutral'],
                    })
                found = True
                break

        if not found:
            unmatched_chn.append((chn_date, chn_opp, chn_wtw, chn_wtl))

    # Compute WP (using only matched games for fair comparison)
    our_total_wtw = sum(g['wtw'] for g in our_games)
    our_total_wtl = sum(g['wtl'] for g in our_games)
    our_wp = (our_total_wtw / (our_total_wtw + our_total_wtl) * 100) if (our_total_wtw + our_total_wtl) > 0 else 0

    chn_total_wtw = sum(x[2] for x in chn_games)
    chn_total_wtl = sum(x[3] for x in chn_games)
    chn_wp = (chn_total_wtw / (chn_total_wtw + chn_total_wtl) * 100) if (chn_total_wtw + chn_total_wtl) > 0 else 0

    print(f"  Games: CHN={len(chn_games)}, Ours={len(our_games)}, Matched={matched}")
    print(f"  CHN  sum(Wt.W)={chn_total_wtw:.4f}  sum(Wt.L)={chn_total_wtl:.4f}  WP={chn_wp:.2f}%")
    print(f"  Ours sum(Wt.W)={our_total_wtw:.4f}  sum(Wt.L)={our_total_wtl:.4f}  WP={our_wp:.2f}%")
    print(f"  WP diff: {abs(our_wp - chn_wp):.4f}pp")

    if mismatches:
        print(f"\n  MISMATCHES ({len(mismatches)}):")
        for m in mismatches:
            print(f"    {m['date']} vs {m['opp']:<20} [OT={m['is_ot']}, Type={m['type']}, Res={m['result']}, Neut={m['neutral']}]")
            print(f"      CHN:  Wt.W={m['chn_wtw']:.2f}  Wt.L={m['chn_wtl']:.2f}")
            print(f"      Ours: Wt.W={m['our_wtw']:.4f}  Wt.L={m['our_wtl']:.4f}")
    else:
        print(f"\n  No Wt.W/Wt.L mismatches in matched games!")

    if unmatched_chn:
        print(f"\n  UNMATCHED CHN games ({len(unmatched_chn)}):")
        for d, o, w, l in unmatched_chn:
            print(f"    {d} vs {o} (Wt.W={w:.2f}, Wt.L={l:.2f})")

    unmatched_our = [g for i, g in enumerate(our_games) if i not in used_our]
    if unmatched_our:
        print(f"\n  UNMATCHED OUR games ({len(unmatched_our)}):")
        for g in unmatched_our:
            print(f"    {g['date']} vs {g['opp']} (Wt.W={g['wtw']:.2f}, Wt.L={g['wtl']:.2f})")

    return our_wp, chn_wp


def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)

    results = []
    for team_name, chn_games in CHN_DATA.items():
        our_wp, chn_wp = compare_team(team_name, chn_games, npi)
        results.append((team_name, our_wp, chn_wp, abs(our_wp - chn_wp)))

    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Team':<20} {'Our WP':>8} {'CHN WP':>8} {'Diff':>8}")
    print(f"  {'-'*48}")
    for team, owp, cwp, diff in results:
        flag = " ***" if diff > 0.5 else ""
        print(f"  {team:<20} {owp:>7.2f}% {cwp:>7.2f}% {diff:>7.4f}{flag}")


if __name__ == "__main__":
    main()
