"""
QWB diagnostic using CHN's actual NPI values as opponent ratings.
This isolates whether the formula is correct but iterative propagation
inflates our ratings, or the formula itself is wrong.
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.rankings.npi import NPI
from analysis.exploratory.compare_game_npi import CHN_GAMES

NAME_MAP = {
    "Mass.-Lowell": "UMass Lowell",
    "Long Island": "LIU",
    "Minnesota-Duluth": "Minnesota Duluth",
}

# CHN's actual NPI values for all 63 teams
CHN_RATINGS = {
    "Michigan": 59.10,
    "North Dakota": 58.21,
    "Michigan State": 58.01,
    "Western Michigan": 57.39,
    "Denver": 57.15,
    "Dartmouth": 56.41,
    "Providence": 56.06,
    "Minnesota Duluth": 55.90,
    "Penn State": 55.36,
    "Quinnipiac": 55.34,
    "Cornell": 55.14,
    "Wisconsin": 55.01,
    "Minnesota State": 54.27,
    "Connecticut": 54.18,
    "Augustana": 54.00,
    "St. Thomas": 53.90,
    "Massachusetts": 53.87,
    "Boston College": 53.36,
    "Merrimack": 53.35,
    "Michigan Tech": 53.02,
    "Ohio State": 52.86,
    "Princeton": 52.78,
    "Bentley": 52.68,
    "Bowling Green": 52.67,
    "Maine": 52.62,
    "Union": 52.30,
    "Northeastern": 52.05,
    "Boston University": 52.02,
    "Sacred Heart": 51.81,
    "St. Cloud State": 51.76,
    "Colorado College": 51.54,
    "Harvard": 51.47,
    "Miami": 51.47,
    "Clarkson": 50.90,
    "Alaska": 50.59,
    "Air Force": 50.56,
    "Lindenwood": 50.43,
    "Holy Cross": 50.41,
    "Minnesota": 50.16,
    "New Hampshire": 49.82,
    "Arizona State": 49.65,
    "LIU": 49.48,
    "Omaha": 49.41,
    "RIT": 49.10,
    "Army": 48.77,
    "UMass Lowell": 48.69,
    "Robert Morris": 48.61,
    "Canisius": 48.39,
    "Colgate": 48.36,
    "Bemidji State": 48.30,
    "Notre Dame": 48.02,
    "Vermont": 47.92,
    "Lake Superior": 47.52,
    "RPI": 46.79,
    "Niagara": 45.95,
    "Ferris State": 45.90,
    "Stonehill": 45.48,
    "Yale": 44.96,
    "Brown": 44.01,
    "Northern Michigan": 43.25,
    "St. Lawrence": 43.19,
    "Alaska Anchorage": 42.81,
    "Mercyhurst": 42.69,
}

CHN_SUMMARY = {
    "Merrimack": {"npi": 53.35, "qwb": 0.28},
    "Michigan": {"npi": 59.10, "qwb": 0.40},
    "Mercyhurst": {"npi": 42.69, "qwb": 0.01},
    "Miami": {"npi": 51.47, "qwb": 0.23},
    "Colgate": {"npi": 48.36, "qwb": 0.21},
}

QWB_BASE = 51.0
QWB_MULT = 0.5


def compute_for_team(team_name, npi_obj, use_chn_ratings=True):
    """Compute NPI components using either our ratings or CHN's ratings as opp_npi."""
    ratings = CHN_RATINGS if use_chn_ratings else npi_obj.ratings
    chn_games = CHN_GAMES.get(team_name, [])

    # Build our game list from archive
    our_games = []
    for idx, row in npi_obj.games.iterrows():
        if row['HomeTeam'] == team_name:
            pts, wgt = npi_obj._calculate_game_points(row, 'Home')
            opp = row['AwayTeam']
            role = 'Home'
        elif row['AwayTeam'] == team_name:
            pts, wgt = npi_obj._calculate_game_points(row, 'Away')
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
        our_games.append({'date': mm_dd, 'opp': opp, 'pts': pts, 'wgt': wgt, 'is_win': is_win})

    # Match with CHN games
    used = set()
    matched = []
    for chn_date, chn_opp, chn_wtw, chn_wtl, chn_gnpi in chn_games:
        mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
        for i, g in enumerate(our_games):
            if i in used:
                continue
            if g['date'] == chn_date and g['opp'] == mapped_opp:
                used.add(i)
                opp_npi = ratings.get(mapped_opp, 50.0)
                game_wp = (g['pts'] / g['wgt'] * 100) if g['wgt'] > 0 else 0.0
                bonus = max(0, (opp_npi - QWB_BASE) * QWB_MULT) * game_wp / 100.0
                game_npi = 0.25 * game_wp + 0.75 * opp_npi + bonus
                matched.append({**g, 'opp_npi': opp_npi, 'game_wp': game_wp,
                                 'bonus': bonus, 'game_npi': game_npi})
                break

    # Bad wins removal
    wins = [g for g in matched if g['is_win']]
    non_wins = [g for g in matched if not g['is_win']]
    wins.sort(key=lambda x: x['game_npi'], reverse=True)
    valid = non_wins + wins[:12]

    def _wavg(gms):
        t = sum(x['game_npi'] * x['wgt'] for x in gms)
        w = sum(x['wgt'] for x in gms)
        return t / w if w > 0 else 0

    if valid and wins[12:]:
        avg = _wavg(valid)
        for gw in wins[12:]:
            if gw['game_npi'] >= avg:
                valid.append(gw)
                avg = _wavg(valid)
            else:
                break

    excluded = [g for g in matched if g not in valid]

    all_pts = sum(g['pts'] for g in matched)
    all_wgt = sum(g['wgt'] for g in matched)
    valid_wgt = sum(g['wgt'] for g in valid)

    wp_all = (all_pts / all_wgt) if all_wgt > 0 else 0.0
    sos = sum(g['opp_npi'] * g['wgt'] for g in valid) / valid_wgt if valid_wgt > 0 else 0.0
    qwb_sum = sum((g['opp_npi'] - QWB_BASE) * QWB_MULT * g['pts']
                  for g in valid if g['pts'] > 0 and g['opp_npi'] > QWB_BASE)
    qwb = qwb_sum / all_wgt if all_wgt > 0 else 0.0

    npi = wp_all * 100 * 0.25 + sos * 0.75 + qwb
    npi_direct = _wavg(valid)

    return {
        'wp': wp_all * 100,
        'sos': sos,
        'qwb': qwb,
        'npi': npi,
        'npi_direct': npi_direct,
        'all_wgt': all_wgt,
        'valid_wgt': valid_wgt,
        'n_excl': len(excluded),
        'n_matched': len(matched),
    }


def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)
    npi.fit()

    print("\nUsing CHN opponent ratings vs our converged ratings:")
    print(f"\n{'Team':<20} {'Source':>8} | {'WP':>7} {'SOS':>7} {'QWB':>6} {'NPI':>7} {'CHN_NPI':>8} {'Diff':>6} | {'QWB_CHN':>7} {'QWB_diff':>8} | {'nExcl':>5}")
    print("-" * 100)

    for team in CHN_SUMMARY:
        chn = CHN_SUMMARY[team]
        for label, use_chn in [("CHN_opp", True), ("Our_opp", False)]:
            r = compute_for_team(team, npi, use_chn_ratings=use_chn)
            qwb_diff = r['qwb'] - chn['qwb']
            npi_diff = r['npi'] - chn['npi']
            print(f"  {team:<20} {label:>8} | {r['wp']:>7.2f} {r['sos']:>7.2f} {r['qwb']:>6.4f} {r['npi']:>7.2f} {chn['npi']:>8.2f} {npi_diff:>+6.2f} | {chn['qwb']:>7.4f} {qwb_diff:>+8.4f} | {r['n_excl']:>5}")
        print()

    # Also print CHN-ratings NPI difference breakdown
    print("\n--- Detail: using CHN opponent ratings ---")
    print(f"{'Team':<20} {'0.25*WP':>8} {'0.75*SOS':>9} {'QWB':>7} {'NPI':>7} {'CHN':>7} | NPI without QWB vs CHN without QWB")
    for team in CHN_SUMMARY:
        chn = CHN_SUMMARY[team]
        r = compute_for_team(team, npi, use_chn_ratings=True)
        base = r['wp'] * 0.25 + r['sos'] * 0.75
        chn_base = chn['npi'] - chn['qwb']
        print(f"  {team:<20} {r['wp']*0.25:>8.4f} {r['sos']*0.75:>9.4f} {r['qwb']:>7.4f} {r['npi']:>7.4f} {chn['npi']:>7.2f} | base={base:.4f} vs CHN_base={chn_base:.4f} (diff={base-chn_base:+.4f})")


if __name__ == "__main__":
    main()
