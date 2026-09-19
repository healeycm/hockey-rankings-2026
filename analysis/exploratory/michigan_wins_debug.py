"""
Debug Michigan's bad wins removal using CHN opponent ratings.
Determine if CHN excludes the same wins we do, or uses different cutoff.
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.rankings.npi import NPI
from analysis.exploratory.compare_game_npi import CHN_GAMES
from analysis.exploratory.qwb_chn_ratings import CHN_RATINGS, CHN_SUMMARY, NAME_MAP, QWB_BASE, QWB_MULT

team_name = "Michigan"
chn_npi = CHN_SUMMARY[team_name]['npi']   # 59.10
chn_qwb = CHN_SUMMARY[team_name]['qwb']   # 0.40

def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)
    npi.fit()

    # Build Michigan games using CHN opponent ratings
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
        our_games.append({'date': mm_dd, 'opp': opp, 'pts': pts, 'wgt': wgt,
                          'is_win': is_win})

    # Match CHN games
    chn_games = CHN_GAMES[team_name]
    used = set()
    matched = []
    unmatched_chn = []
    for chn_date, chn_opp, chn_wtw, chn_wtl, chn_gnpi in chn_games:
        mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
        found = False
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
                                 'chn_wtw': chn_wtw, 'chn_wtl': chn_wtl,
                                 'chn_gnpi': chn_gnpi, 'chn_opp': chn_opp})
                found = True
                break
        if not found:
            unmatched_chn.append((chn_date, chn_opp, chn_gnpi))

    print(f"Matched {len(matched)}/{len(chn_games)} CHN games")
    if unmatched_chn:
        print(f"Unmatched CHN games: {unmatched_chn}")

    # Bad wins removal
    wins = [g for g in matched if g['is_win']]
    non_wins = [g for g in matched if not g['is_win']]
    wins.sort(key=lambda x: x['game_npi'], reverse=True)

    def _wavg(gms):
        t = sum(x['game_npi'] * x['wgt'] for x in gms)
        w = sum(x['wgt'] for x in gms)
        return t / w if w > 0 else 0

    valid = non_wins + wins[:12]
    threshold_after_12 = _wavg(valid)

    optional_wins = wins[12:]
    added = []
    for gw in optional_wins:
        if gw['game_npi'] >= _wavg(valid):
            valid.append(gw)
            added.append(gw)
    excluded = [g for g in wins[12:] if g not in added]

    print(f"\nAll wins sorted by Game NPI (using CHN ratings):")
    print(f"  {'#':>3} {'Date':<6} {'Opponent':<22} {'gWP':>5} {'OppNPI':>7} {'GameNPI':>8} {'CHN_NPI':>8} {'In/Out':>7}")
    print(f"  {'-'*70}")
    for i, g in enumerate(wins):
        status = "KEEP" if g in valid else "EXCL"
        marker = " <<< threshold" if i == 11 else ""
        print(f"  {i+1:>3} {g['date']:<6} {g['chn_opp']:<22} {g['game_wp']:>5.0f} {g['opp_npi']:>7.2f} "
              f"{g['game_npi']:>8.2f} {g['chn_gnpi']:>8.2f} {status:>7}{marker}")

    print(f"\nThreshold after top-12: {threshold_after_12:.4f}")
    print(f"Non-wins: {len(non_wins)}, Wins kept: {len(valid)-len(non_wins)}, Wins excl: {len(excluded)}")

    # Now compute NPI with and without bad wins removal
    def compute_npi(game_set, all_set):
        all_wgt = sum(g['wgt'] for g in all_set)
        all_pts = sum(g['pts'] for g in all_set)
        wp = all_pts / all_wgt if all_wgt > 0 else 0
        valid_wgt = sum(g['wgt'] for g in game_set)
        sos = sum(g['opp_npi'] * g['wgt'] for g in game_set) / valid_wgt if valid_wgt > 0 else 0
        qwb_sum = sum((g['opp_npi'] - QWB_BASE) * QWB_MULT * g['pts']
                      for g in game_set if g['pts'] > 0 and g['opp_npi'] > QWB_BASE)
        qwb = qwb_sum / all_wgt if all_wgt > 0 else 0
        npi_val = wp * 100 * 0.25 + sos * 0.75 + qwb
        return wp * 100, sos, qwb, npi_val

    wp1, sos1, qwb1, npi1 = compute_npi(valid, matched)
    wp2, sos2, qwb2, npi2 = compute_npi(matched, matched)  # no removal

    print(f"\n{'Scenario':<30} {'WP':>7} {'SOS':>7} {'QWB':>7} {'NPI':>7} {'CHN':>7} {'Diff':>7}")
    print(f"  {'With bad-wins removal':<30} {wp1:>7.2f} {sos1:>7.2f} {qwb1:>7.4f} {npi1:>7.2f} {chn_npi:>7.2f} {npi1-chn_npi:>+7.2f}")
    print(f"  {'No bad-wins removal':<30} {wp2:>7.2f} {sos2:>7.2f} {qwb2:>7.4f} {npi2:>7.2f} {chn_npi:>7.2f} {npi2-chn_npi:>+7.2f}")
    print(f"  {'CHN target':<30} {'':>7} {'':>7} {chn_qwb:>7.4f} {chn_npi:>7.2f}")

    # Try different win caps
    print(f"\nEffect of different win caps (all non-wins + top N wins, no optional adds):")
    print(f"  {'Cap':>4} {'SOS':>7} {'QWB':>7} {'NPI':>7} {'Diff':>7}")
    for cap in range(10, len(wins)+1):
        valid_c = non_wins + wins[:cap]
        _, sos_c, qwb_c, npi_c = compute_npi(valid_c, matched)
        print(f"  {cap:>4} {sos_c:>7.2f} {qwb_c:>7.4f} {npi_c:>7.2f} {npi_c-chn_npi:>+7.2f}")


if __name__ == "__main__":
    main()
