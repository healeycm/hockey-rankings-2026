"""
Test NPI formula with NO bad wins removal for all 5 teams, using CHN ratings.
Compare: with removal vs without removal vs CHN target.
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.rankings.npi import NPI
from analysis.exploratory.compare_game_npi import CHN_GAMES
from analysis.exploratory.qwb_chn_ratings import CHN_RATINGS, CHN_SUMMARY, NAME_MAP, QWB_BASE, QWB_MULT


def compute_both(team_name, npi_obj):
    chn_games = CHN_GAMES.get(team_name, [])

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

    # Match CHN games, using CHN ratings
    used = set()
    matched = []
    for chn_date, chn_opp, chn_wtw, chn_wtl, chn_gnpi in chn_games:
        mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
        for i, g in enumerate(our_games):
            if i in used:
                continue
            if g['date'] == chn_date and g['opp'] == mapped_opp:
                used.add(i)
                opp_npi = CHN_RATINGS.get(mapped_opp, 50.0)
                game_wp = (g['pts'] / g['wgt'] * 100) if g['wgt'] > 0 else 0.0
                bonus = max(0, (opp_npi - QWB_BASE) * QWB_MULT) * game_wp / 100.0
                game_npi = 0.25 * game_wp + 0.75 * opp_npi + bonus
                matched.append({**g, 'opp_npi': opp_npi, 'game_wp': game_wp,
                                 'bonus': bonus, 'game_npi': game_npi,
                                 'chn_wtw': chn_wtw, 'chn_wtl': chn_wtl, 'chn_gnpi': chn_gnpi})
                break

    def calc_npi(game_set, all_set):
        all_wgt = sum(g['wgt'] for g in all_set)
        all_pts = sum(g['pts'] for g in all_set)
        wp = (all_pts / all_wgt * 100) if all_wgt > 0 else 0
        vwgt = sum(g['wgt'] for g in game_set)
        sos = sum(g['opp_npi'] * g['wgt'] for g in game_set) / vwgt if vwgt > 0 else 0
        qwb_s = sum((g['opp_npi'] - QWB_BASE) * QWB_MULT * g['pts']
                    for g in game_set if g['pts'] > 0 and g['opp_npi'] > QWB_BASE)
        qwb = qwb_s / all_wgt if all_wgt > 0 else 0
        npi_val = wp * 0.25 + sos * 0.75 + qwb
        return wp, sos, qwb, npi_val, all_wgt, vwgt

    # With bad wins removal
    wins = [g for g in matched if g['is_win']]
    non_wins = [g for g in matched if not g['is_win']]
    wins.sort(key=lambda x: x['game_npi'], reverse=True)
    valid_r = non_wins + wins[:12]

    def _wavg(gms):
        t = sum(x['game_npi'] * x['wgt'] for x in gms)
        w = sum(x['wgt'] for x in gms)
        return t / w if w > 0 else 0

    if valid_r and wins[12:]:
        avg = _wavg(valid_r)
        for gw in wins[12:]:
            if gw['game_npi'] >= avg:
                valid_r.append(gw)
                avg = _wavg(valid_r)
            else:
                break

    excluded_r = [g for g in matched if g not in valid_r]

    wp_r, sos_r, qwb_r, npi_r, aw, vw_r = calc_npi(valid_r, matched)
    wp_n, sos_n, qwb_n, npi_n, _, vw_n = calc_npi(matched, matched)  # no removal

    # Also: compute as direct weighted average (no formula split)
    npi_direct_r = _wavg(valid_r)
    npi_direct_n = _wavg(matched)

    chn = CHN_SUMMARY[team_name]
    return {
        'team': team_name,
        'n_wins': len(wins),
        'n_nonwins': len(non_wins),
        'n_excl': len(excluded_r),
        # With removal
        'wp_r': wp_r, 'sos_r': sos_r, 'qwb_r': qwb_r, 'npi_r': npi_r,
        # Without removal
        'wp_n': wp_n, 'sos_n': sos_n, 'qwb_n': qwb_n, 'npi_n': npi_n,
        # CHN reference
        'chn_npi': chn['npi'], 'chn_qwb': chn['qwb'],
        # Direct avg
        'npi_direct_r': npi_direct_r, 'npi_direct_n': npi_direct_n,
    }


def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)
    npi.fit()

    print("\n=== Using CHN opponent ratings: With vs Without bad-wins removal ===")
    print(f"\n{'Team':<20} {'W':>3} {'L':>3} {'Ex':>3} | {'NPI_removal':>11} {'NPI_noremov':>11} {'CHN_NPI':>8} | {'QWB_r':>6} {'QWB_n':>6} {'CHN_QWB':>8}")
    print("-" * 90)

    for team in CHN_SUMMARY:
        r = compute_both(team, npi)
        print(f"  {r['team']:<20} {r['n_wins']:>3} {r['n_nonwins']:>3} {r['n_excl']:>3} | "
              f"{r['npi_r']:>+11.4f} {r['npi_n']:>+11.4f} {r['chn_npi']:>8.2f} | "
              f"{r['qwb_r']:>6.4f} {r['qwb_n']:>6.4f} {r['chn_qwb']:>8.4f}")

    print("\n=== NPI differences from CHN ===")
    print(f"\n{'Team':<20} {'diff_removal':>13} {'diff_noremov':>13}")
    print("-" * 50)
    for team in CHN_SUMMARY:
        r = compute_both(team, npi)
        d_r = r['npi_r'] - r['chn_npi']
        d_n = r['npi_n'] - r['chn_npi']
        print(f"  {r['team']:<20} {d_r:>+13.4f} {d_n:>+13.4f}")

    # Now verify: do the CHN Wt.W/Wt.L values in our data match exactly?
    print("\n\n=== Verifying CHN wtw/wtl match our pts/wgt ===")
    print("(For games in CHN table, checking if chn_wtw matches our pts and chn_wtl matches wgt-pts)")
    print()

    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi_fresh = NPI(season_df)
    npi_fresh.fit()

    for team_name in list(CHN_SUMMARY.keys())[:2]:  # Check first 2 teams in detail
        print(f"\n  {team_name}:")
        print(f"  {'Date':<6} {'Opponent':<22} {'Our_pts':>8} {'CHN_wtw':>8} {'Δwt':>6} | {'Our_wgt-pts':>11} {'CHN_wtl':>8} {'Δwl':>6}")
        print(f"  {'-'*80}")
        chn_games = CHN_GAMES[team_name]

        our_g2 = []
        for idx, row in npi_fresh.games.iterrows():
            if row['HomeTeam'] == team_name:
                pts, wgt = npi_fresh._calculate_game_points(row, 'Home')
                opp = row['AwayTeam']
            elif row['AwayTeam'] == team_name:
                pts, wgt = npi_fresh._calculate_game_points(row, 'Away')
                opp = row['HomeTeam']
            else:
                continue
            try:
                mm_dd = pd.Timestamp(row['Date']).strftime('%m/%d')
            except:
                mm_dd = str(row['Date'])
            our_g2.append({'date': mm_dd, 'opp': opp, 'pts': pts, 'wgt': wgt})

        used2 = set()
        mismatches = 0
        for chn_date, chn_opp, chn_wtw, chn_wtl, chn_gnpi in chn_games:
            mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
            for i, g in enumerate(our_g2):
                if i in used2:
                    continue
                if g['date'] == chn_date and g['opp'] == mapped_opp:
                    used2.add(i)
                    delta_w = g['pts'] - chn_wtw
                    delta_l = (g['wgt'] - g['pts']) - chn_wtl
                    flag = " ***" if abs(delta_w) > 0.01 or abs(delta_l) > 0.01 else ""
                    if flag:
                        mismatches += 1
                    print(f"  {chn_date:<6} {chn_opp:<22} {g['pts']:>8.2f} {chn_wtw:>8.2f} {delta_w:>+6.2f} | {g['wgt']-g['pts']:>11.2f} {chn_wtl:>8.2f} {delta_l:>+6.2f}{flag}")
                    break
        print(f"  Mismatches: {mismatches}")


if __name__ == "__main__":
    main()
