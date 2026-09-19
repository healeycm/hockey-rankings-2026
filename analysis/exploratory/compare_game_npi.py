"""
Game-by-game NPI component comparison: Our code vs CHN detail pages.
Verifies Game NPI formula, bad wins removal, and final NPI computation.
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.rankings.npi import NPI

NAME_MAP = {
    "Mass.-Lowell": "UMass Lowell",
    "Long Island": "LIU",
    "Minnesota-Duluth": "Minnesota Duluth",
}

# CHN data: (date, opponent_chn_name, wtw, wtl, game_npi)
CHN_GAMES = {
    "Merrimack": [
        ("03/14", "Providence", 1.00, 0.00, 69.57),
        ("11/15", "Providence", 0.80, 0.00, 69.57),
        ("10/24", "Quinnipiac", 0.80, 0.00, 68.68),
        ("03/21", "Connecticut", 1.00, 0.00, 67.23),
        ("03/20", "Massachusetts", 1.00, 0.00, 66.83),
        ("02/13", "Boston College", 0.80, 0.00, 66.20),
        ("01/23", "Northeastern", 0.80, 0.00, 64.56),
        ("01/22", "Northeastern", 0.80, 0.00, 64.56),
        ("01/10", "Holy Cross", 1.20, 0.00, 62.81),
        ("01/30", "New Hampshire", 0.80, 0.00, 62.37),
        ("10/18", "New Hampshire", 0.80, 0.00, 62.37),
        ("12/13", "Long Island", 0.80, 0.00, 62.11),
        ("11/21", "Long Island", 1.20, 0.00, 62.11),
        ("03/11", "Mass.-Lowell", 1.00, 0.00, 61.51),
        ("03/05", "Mass.-Lowell", 0.80, 0.00, 61.51),
        ("10/10", "Mass.-Lowell", 0.80, 0.00, 61.51),
        ("02/27", "Vermont", 0.80, 0.00, 60.94),
        ("12/29", "Vermont", 1.20, 0.00, 60.94),
        ("02/03", "Stonehill", 1.20, 0.00, 59.11),
        ("12/12", "Yale", 0.80, 0.00, 58.72),
        ("01/03", "Brown", 1.20, 0.00, 58.01),
        ("01/31", "New Hampshire", 0.60, 0.40, 52.37),
        ("11/07", "Boston University", 0.48, 0.52, 51.26),
        ("02/28", "Vermont", 0.40, 0.60, 45.94),
        ("11/29", "Dartmouth", 0.00, 0.80, 42.31),
        ("11/14", "Providence", 0.00, 0.80, 42.04),
        ("12/06", "Connecticut", 0.00, 0.80, 40.64),
        ("12/05", "Connecticut", 0.00, 1.20, 40.64),
        ("11/01", "Connecticut", 0.00, 0.80, 40.64),
        ("01/17", "Massachusetts", 0.00, 0.80, 40.40),
        ("01/16", "Massachusetts", 0.00, 1.20, 40.40),
        ("02/14", "Boston College", 0.00, 0.80, 40.02),
        ("02/21", "Maine", 0.00, 0.80, 39.47),
        ("02/20", "Maine", 0.00, 0.80, 39.47),
        ("11/08", "Boston University", 0.00, 1.20, 39.02),
        ("10/25", "Long Island", 0.00, 1.20, 37.11),
        ("10/03", "Mass.-Lowell", 0.00, 0.80, 36.51),
        ("11/26", "Notre Dame", 0.00, 1.20, 36.02),
    ],
    "Michigan": [
        ("12/05", "Michigan State", 1.20, 0.00, 72.01),
        ("10/23", "Western Michigan", 0.80, 0.00, 71.24),
        ("10/11", "Providence", 1.20, 0.00, 69.57),
        ("10/10", "Providence", 1.20, 0.00, 69.57),
        ("03/14", "Penn State", 1.00, 0.00, 68.70),
        ("02/14", "Penn State", 0.80, 0.00, 68.70),
        ("11/14", "Penn State", 1.20, 0.00, 68.70),
        ("02/21", "Wisconsin", 1.20, 0.00, 68.26),
        ("11/07", "Wisconsin", 0.80, 0.00, 68.26),
        ("03/21", "Ohio State", 1.00, 0.00, 65.57),
        ("01/30", "Ohio State", 1.20, 0.00, 65.57),
        ("11/22", "Ohio State", 0.80, 0.00, 65.57),
        ("11/21", "Ohio State", 0.80, 0.00, 65.57),
        ("11/28", "Harvard", 1.20, 0.00, 63.84),
        ("02/27", "Minnesota", 0.80, 0.00, 62.62),
        ("01/16", "Minnesota", 1.20, 0.00, 62.62),
        ("10/17", "Robert Morris", 0.80, 0.00, 61.46),
        ("10/16", "Robert Morris", 0.80, 0.00, 61.46),
        ("03/11", "Notre Dame", 1.00, 0.00, 61.02),
        ("01/10", "Notre Dame", 0.80, 0.00, 61.02),
        ("01/09", "Notre Dame", 0.80, 0.00, 61.02),
        ("10/31", "Notre Dame", 1.20, 0.00, 61.02),
        ("02/06", "Michigan State", 0.52, 0.48, 58.33),
        ("01/31", "Ohio State", 0.68, 0.32, 57.28),
        ("10/04", "Mercyhurst", 0.80, 0.00, 57.02),
        ("10/03", "Mercyhurst", 0.80, 0.00, 57.02),
        ("11/29", "Harvard", 0.68, 0.32, 55.77),
        ("01/17", "Minnesota", 0.68, 0.32, 54.62),
        ("11/01", "Notre Dame", 0.68, 0.32, 53.02),
        ("02/13", "Penn State", 0.40, 0.60, 52.39),
        ("02/07", "Michigan State", 0.00, 1.00, 43.50),
        ("12/06", "Michigan State", 0.00, 1.20, 43.50),
        ("10/24", "Western Michigan", 0.00, 0.80, 43.04),
        ("11/15", "Penn State", 0.00, 0.80, 41.52),
        ("02/20", "Wisconsin", 0.00, 0.80, 41.26),
        ("11/08", "Wisconsin", 0.00, 1.20, 41.26),
        ("02/26", "Minnesota", 0.00, 1.20, 37.62),
    ],
    "Mercyhurst": [
        ("02/07", "Sacred Heart", 1.20, 0.00, 64.26),
        ("01/09", "Army", 0.80, 0.00, 61.58),
        ("03/03", "Canisius", 1.00, 0.00, 61.29),
        ("02/20", "Niagara", 0.80, 0.00, 59.47),
        ("01/17", "Niagara", 1.20, 0.00, 59.47),
        ("01/16", "Niagara", 0.80, 0.00, 59.47),
        ("02/13", "Air Force", 0.60, 0.40, 52.92),
        ("11/29", "Robert Morris", 0.60, 0.40, 51.46),
        ("01/30", "RIT", 0.40, 0.60, 46.83),
        ("10/04", "Michigan", 0.00, 0.80, 44.32),
        ("10/03", "Michigan", 0.00, 0.80, 44.32),
        ("01/03", "North Dakota", 0.00, 0.80, 43.66),
        ("01/02", "North Dakota", 0.00, 0.80, 43.66),
        ("03/07", "Bentley", 0.00, 1.00, 39.51),
        ("03/06", "Bentley", 0.00, 1.00, 39.51),
        ("11/01", "Bentley", 0.00, 1.20, 39.51),
        ("10/31", "Bentley", 0.00, 1.20, 39.51),
        ("10/11", "Union", 0.00, 1.20, 39.22),
        ("10/10", "Union", 0.00, 1.20, 39.22),
        ("02/06", "Sacred Heart", 0.00, 0.80, 38.86),
        ("02/14", "Air Force", 0.00, 0.80, 37.92),
        ("12/06", "Holy Cross", 0.00, 0.80, 37.81),
        ("10/18", "Holy Cross", 0.00, 1.20, 37.81),
        ("01/31", "RIT", 0.00, 1.20, 36.83),
        ("11/08", "RIT", 0.00, 0.80, 36.83),
        ("11/07", "RIT", 0.00, 0.80, 36.83),
        ("01/10", "Army", 0.00, 1.20, 36.58),
        ("10/25", "Mass.-Lowell", 0.00, 1.20, 36.51),
        ("10/24", "Mass.-Lowell", 0.00, 1.20, 36.51),
        ("02/28", "Robert Morris", 0.00, 0.80, 36.46),
        ("02/27", "Robert Morris", 0.00, 1.20, 36.46),
        ("11/28", "Robert Morris", 0.00, 1.20, 36.46),
        ("01/24", "Canisius", 0.00, 1.20, 36.29),
        ("01/23", "Canisius", 0.00, 1.20, 36.29),
        ("11/22", "Canisius", 0.00, 0.80, 36.29),
        ("11/21", "Canisius", 0.00, 0.80, 36.29),
        ("02/21", "Niagara", 0.00, 0.80, 34.47),
    ],
    "Miami": [
        ("11/29", "Union", 1.00, 0.00, 64.87),
        ("01/31", "St. Cloud State", 1.20, 0.00, 64.20),
        ("01/30", "St. Cloud State", 1.20, 0.00, 64.20),
        ("11/01", "Arizona State", 0.80, 0.00, 62.24),
        ("02/28", "Omaha", 1.20, 0.00, 62.06),
        ("01/17", "Omaha", 0.80, 0.00, 62.06),
        ("01/16", "Omaha", 0.80, 0.00, 62.06),
        ("11/28", "RIT", 1.00, 0.00, 61.83),
        ("10/11", "RPI", 1.20, 0.00, 60.09),
        ("10/10", "RPI", 1.20, 0.00, 60.09),
        ("12/29", "Ferris State", 1.00, 0.00, 59.43),
        ("10/04", "Ferris State", 0.80, 0.00, 59.43),
        ("10/03", "Ferris State", 0.80, 0.00, 59.43),
        ("02/06", "Western Michigan", 0.52, 0.48, 57.70),
        ("02/14", "North Dakota", 0.48, 0.52, 57.39),
        ("10/25", "Lindenwood", 0.68, 0.32, 54.82),
        ("10/24", "Lindenwood", 0.68, 0.32, 54.82),
        ("01/09", "Arizona State", 0.68, 0.32, 54.24),
        ("11/21", "St. Cloud State", 0.52, 0.48, 52.01),
        ("12/13", "Colorado College", 0.40, 0.60, 48.77),
        ("12/12", "Colorado College", 0.40, 0.60, 48.77),
        ("02/13", "North Dakota", 0.00, 0.80, 43.66),
        ("02/07", "Western Michigan", 0.00, 1.20, 43.04),
        ("11/15", "Western Michigan", 0.00, 0.80, 43.04),
        ("11/14", "Western Michigan", 0.00, 0.80, 43.04),
        ("03/07", "Denver", 0.00, 1.00, 42.86),
        ("03/06", "Denver", 0.00, 1.00, 42.86),
        ("12/06", "Denver", 0.00, 0.80, 42.86),
        ("12/05", "Denver", 0.00, 0.80, 42.86),
        ("02/21", "Minnesota-Duluth", 0.00, 1.20, 41.93),
        ("02/20", "Minnesota-Duluth", 0.00, 1.20, 41.93),
        ("12/28", "Michigan Tech", 0.00, 1.00, 39.77),
        ("11/22", "St. Cloud State", 0.00, 1.20, 38.82),
        ("01/10", "Arizona State", 0.00, 0.80, 37.24),
        ("10/31", "Arizona State", 0.00, 1.20, 37.24),
        ("02/27", "Omaha", 0.00, 0.80, 37.06),
    ],
    "Colgate": [
        ("01/24", "Dartmouth", 0.80, 0.00, 70.01),
        ("01/17", "Princeton", 0.80, 0.00, 65.47),
        ("10/24", "Maine", 1.20, 0.00, 65.28),
        ("01/03", "New Hampshire", 1.20, 0.00, 62.37),
        ("10/18", "Canisius", 0.80, 0.00, 61.29),
        ("11/21", "RPI", 0.80, 0.00, 60.09),
        ("02/07", "Cornell", 0.68, 0.32, 59.77),
        ("03/07", "Yale", 1.00, 0.00, 58.72),
        ("01/31", "Yale", 1.20, 0.00, 58.72),
        ("11/15", "Brown", 0.80, 0.00, 58.01),
        ("02/28", "St. Lawrence", 0.80, 0.00, 57.39),
        ("12/05", "St. Lawrence", 1.20, 0.00, 57.39),
        ("02/20", "Princeton", 0.60, 0.40, 55.12),
        ("10/11", "Boston University", 0.60, 0.40, 54.33),
        ("10/25", "Maine", 0.48, 0.52, 51.86),
        ("11/22", "Union", 0.40, 0.60, 49.48),
        ("01/30", "Brown", 0.60, 0.40, 48.01),
        ("11/14", "Yale", 0.52, 0.48, 46.72),
        ("11/28", "Michigan State", 0.00, 0.80, 43.50),
        ("11/26", "Michigan State", 0.00, 0.80, 43.50),
        ("03/14", "Dartmouth", 0.00, 1.00, 42.31),
        ("03/13", "Dartmouth", 0.00, 1.00, 42.31),
        ("11/07", "Dartmouth", 0.00, 0.80, 42.31),
        ("02/21", "Quinnipiac", 0.00, 0.80, 41.51),
        ("01/16", "Quinnipiac", 0.00, 1.20, 41.51),
        ("02/06", "Cornell", 0.00, 1.20, 41.36),
        ("02/13", "Union", 0.00, 0.80, 39.22),
        ("10/10", "Boston University", 0.00, 0.80, 39.02),
        ("01/23", "Harvard", 0.00, 1.20, 38.61),
        ("11/08", "Harvard", 0.00, 0.80, 38.61),
        ("02/27", "Clarkson", 0.00, 1.20, 38.18),
        ("12/06", "Clarkson", 0.00, 0.80, 38.18),
        ("01/04", "New Hampshire", 0.00, 0.80, 37.37),
        ("11/01", "RIT", 0.00, 1.20, 36.83),
        ("10/31", "RIT", 0.00, 1.20, 36.83),
        ("10/17", "Canisius", 0.00, 1.20, 36.29),
        ("02/14", "RPI", 0.00, 0.80, 35.09),
    ],
}

CHN_SUMMARY = {
    "Merrimack": {"npi": 53.35, "qwb": 0.28},
    "Michigan": {"npi": 59.10, "qwb": 0.40},
    "Mercyhurst": {"npi": 42.69, "qwb": 0.01},
    "Miami": {"npi": 51.47, "qwb": 0.23},
    "Colgate": {"npi": 48.36, "qwb": 0.21},
}


def analyze_team(team_name, chn_games, npi):
    print(f"\n{'='*80}")
    print(f"  {team_name}  (CHN NPI={CHN_SUMMARY[team_name]['npi']}, CHN QWB={CHN_SUMMARY[team_name]['qwb']})")
    print(f"{'='*80}")

    # Build our game data
    our_games = []
    for idx, row in npi.games.iterrows():
        if row['HomeTeam'] == team_name:
            pts, wgt = npi._calculate_game_points(row, 'Home')
            opp = row['AwayTeam']
            role = 'Home'
        elif row['AwayTeam'] == team_name:
            pts, wgt = npi._calculate_game_points(row, 'Away')
            opp = row['HomeTeam']
            role = 'Away'
        else:
            continue

        try:
            mm_dd = pd.Timestamp(row['Date']).strftime('%m/%d')
        except:
            mm_dd = str(row['Date'])

        is_win = (role == 'Home' and row['Result'] == 1.0) or \
                 (role == 'Away' and row['Result'] == 0.0)

        our_games.append({
            'date': mm_dd,
            'opp': opp,
            'pts': pts,
            'wgt': wgt,
            'is_win': is_win,
            'result': row['Result'],
        })

    # Match games and compute Game NPI using the proportional QWB formula
    used = set()
    matched_games = []

    for chn_date, chn_opp, chn_wtw, chn_wtl, chn_gnpi in chn_games:
        mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
        for i, g in enumerate(our_games):
            if i in used:
                continue
            if g['date'] == chn_date and g['opp'] == mapped_opp:
                used.add(i)
                opp_npi = npi.ratings.get(mapped_opp, 50.0)
                game_wp = (g['pts'] / g['wgt'] * 100) if g['wgt'] > 0 else 0.0

                # Proportional QWB formula (hypothesis)
                prop_qwb = max(0, (opp_npi - 51.0) * 0.5) * game_wp / 100.0
                our_gnpi = 0.25 * game_wp + 0.75 * opp_npi + prop_qwb

                # Current code QWB (flat, wins only)
                old_qwb = 0.0
                if g['is_win'] and opp_npi > 51.0:
                    old_qwb = (opp_npi - 51.0) * 0.5
                old_gnpi = 0.25 * game_wp + 0.75 * opp_npi + old_qwb

                matched_games.append({
                    'date': chn_date,
                    'opp': chn_opp,
                    'chn_gnpi': chn_gnpi,
                    'our_gnpi_new': round(our_gnpi, 2),
                    'our_gnpi_old': round(old_gnpi, 2),
                    'opp_npi': round(opp_npi, 2),
                    'game_wp': round(game_wp, 2),
                    'pts': g['pts'],
                    'wgt': g['wgt'],
                    'is_win': g['is_win'],
                    'prop_qwb': round(prop_qwb, 4),
                })
                break

    # Compare Game NPI values
    print(f"\n  Game NPI Comparison ({len(matched_games)} matched):")
    print(f"  {'Date':<6} {'Opponent':<20} {'gWP':>5} {'OppNPI':>7} {'CHN':>7} {'New':>7} {'Old':>7} {'Diff':>6}")
    print(f"  {'-'*72}")

    mismatches_new = 0
    mismatches_old = 0
    for g in matched_games:
        diff_new = g['our_gnpi_new'] - g['chn_gnpi']
        diff_old = g['our_gnpi_old'] - g['chn_gnpi']
        flag = ""
        if abs(diff_new) > 0.15:
            flag = " ***"
            mismatches_new += 1
        if abs(diff_old) > 0.15:
            mismatches_old += 1

        print(f"  {g['date']:<6} {g['opp']:<20} {g['game_wp']:>5.0f} {g['opp_npi']:>7.2f} "
              f"{g['chn_gnpi']:>7.2f} {g['our_gnpi_new']:>7.2f} {g['our_gnpi_old']:>7.2f} "
              f"{diff_new:>+6.2f}{flag}")

    print(f"\n  Game NPI mismatches (>0.15): New formula={mismatches_new}, Old formula={mismatches_old}")

    # --- Bad wins analysis ---
    # Sort wins by Game NPI descending
    wins = [g for g in matched_games if g['is_win']]
    non_wins = [g for g in matched_games if not g['is_win']]
    wins.sort(key=lambda x: x['our_gnpi_new'], reverse=True)

    top_wins = wins[:12]
    optional_wins = wins[12:]

    valid = non_wins + top_wins

    if valid and optional_wins:
        def _wavg(gms):
            t = sum(x['our_gnpi_new'] * x['wgt'] for x in gms)
            w = sum(x['wgt'] for x in gms)
            return t / w if w > 0 else 0

        current_avg = _wavg(valid)
        for gw in optional_wins:
            if gw['our_gnpi_new'] >= current_avg:
                valid.append(gw)
                current_avg = _wavg(valid)
            else:
                break

    excluded = [g for g in matched_games if g not in valid]
    if excluded:
        print(f"\n  Bad Wins Removed ({len(excluded)}):")
        for g in excluded:
            print(f"    {g['date']} vs {g['opp']:<20} Game NPI={g['our_gnpi_new']:.2f}")

    # --- Final NPI computation ---
    # WP from ALL games
    all_pts = sum(g['pts'] for g in our_games)
    all_wgt = sum(g['wgt'] for g in our_games)
    wp_all = (all_pts / all_wgt) if all_wgt > 0 else 0.0

    # SOS from valid games
    valid_sos_num = sum(g['opp_npi'] * g['wgt'] for g in valid)
    valid_sos_den = sum(g['wgt'] for g in valid)
    sos_valid = valid_sos_num / valid_sos_den if valid_sos_den > 0 else 0.0

    # QWB from valid games - try different denominators
    qwb_num = sum(g['prop_qwb'] * g['wgt'] for g in valid)

    qwb_denom_all = all_wgt
    qwb_denom_valid = valid_sos_den

    qwb_over_all = qwb_num / qwb_denom_all if qwb_denom_all > 0 else 0.0
    qwb_over_valid = qwb_num / qwb_denom_valid if qwb_denom_valid > 0 else 0.0

    npi_with_all_denom = wp_all * 100 * 0.25 + sos_valid * 0.75 + qwb_over_all
    npi_with_valid_denom = wp_all * 100 * 0.25 + sos_valid * 0.75 + qwb_over_valid

    chn_npi = CHN_SUMMARY[team_name]['npi']
    chn_qwb = CHN_SUMMARY[team_name]['qwb']

    print(f"\n  NPI Components:")
    print(f"    WP (all games): {wp_all*100:.4f}%  => 0.25*WP*100 = {wp_all*100*0.25:.4f}")
    print(f"    SOS (valid):    {sos_valid:.4f}  => 0.75*SOS = {sos_valid*0.75:.4f}")
    print(f"    QWB num:        {qwb_num:.4f}")
    print(f"    QWB /all_wgt:   {qwb_over_all:.4f}  (denom={qwb_denom_all:.2f})")
    print(f"    QWB /valid_wgt: {qwb_over_valid:.4f}  (denom={qwb_denom_valid:.2f})")
    print(f"")
    print(f"    NPI (QWB/all):   {npi_with_all_denom:.2f}  vs CHN {chn_npi}  (diff={npi_with_all_denom-chn_npi:+.2f})")
    print(f"    NPI (QWB/valid): {npi_with_valid_denom:.2f}  vs CHN {chn_npi}  (diff={npi_with_valid_denom-chn_npi:+.2f})")
    print(f"    CHN QWB:         {chn_qwb}")
    print(f"    Our QWB/all:     {qwb_over_all:.4f}")
    print(f"    Our QWB/valid:   {qwb_over_valid:.4f}")


def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)
    npi.fit()

    for team_name in CHN_GAMES:
        analyze_team(team_name, CHN_GAMES[team_name], npi)


if __name__ == "__main__":
    main()
