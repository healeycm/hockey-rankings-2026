"""
QWB Diagnostic: Test different QWB aggregation hypotheses against CHN values.
Goal: Find the formula that makes our QWB match CHN's QWB for all 5 teams.
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

CHN_SUMMARY = {
    "Merrimack": {"npi": 53.35, "qwb": 0.28},
    "Michigan": {"npi": 59.10, "qwb": 0.40},
    "Mercyhurst": {"npi": 42.69, "qwb": 0.01},
    "Miami": {"npi": 51.47, "qwb": 0.23},
    "Colgate": {"npi": 48.36, "qwb": 0.21},
}

# CHN game data from compare_game_npi.py (reuse)
from analysis.exploratory.compare_game_npi import CHN_GAMES


def analyze_qwb(npi_obj):
    """For each team, compute QWB under multiple hypotheses and compare to CHN."""

    print(f"\n{'='*100}")
    print(f"  QWB AGGREGATION HYPOTHESES")
    print(f"{'='*100}")

    results = {}

    for team_name in CHN_SUMMARY:
        chn_games = CHN_GAMES.get(team_name, [])
        if not chn_games:
            continue

        # Build our game list
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

            our_games.append({
                'date': mm_dd, 'opp': opp, 'pts': pts, 'wgt': wgt,
                'is_win': is_win, 'result': row['Result'],
            })

        # Match games with CHN
        used = set()
        matched = []
        for chn_date, chn_opp, chn_wtw, chn_wtl, chn_gnpi in chn_games:
            mapped_opp = NAME_MAP.get(chn_opp, chn_opp)
            for i, g in enumerate(our_games):
                if i in used:
                    continue
                if g['date'] == chn_date and g['opp'] == mapped_opp:
                    used.add(i)
                    opp_npi = npi_obj.ratings.get(mapped_opp, 50.0)
                    game_wp = (g['pts'] / g['wgt'] * 100) if g['wgt'] > 0 else 0.0

                    # Per-game bonus (confirmed formula)
                    bonus = max(0, (opp_npi - 51.0) * 0.5) * game_wp / 100.0
                    game_npi = 0.25 * game_wp + 0.75 * opp_npi + bonus

                    matched.append({
                        **g,
                        'opp_npi': opp_npi,
                        'game_wp': game_wp,
                        'bonus': bonus,
                        'game_npi': game_npi,
                        'chn_gnpi': chn_gnpi,
                    })
                    break

        # === Do bad wins removal ===
        wins = [g for g in matched if g['is_win']]
        non_wins = [g for g in matched if not g['is_win']]
        wins.sort(key=lambda x: x['game_npi'], reverse=True)

        top_wins = wins[:12]
        optional_wins = wins[12:]
        valid = non_wins + top_wins

        if valid and optional_wins:
            def _wavg(gms):
                t = sum(x['game_npi'] * x['wgt'] for x in gms)
                w = sum(x['wgt'] for x in gms)
                return t / w if w > 0 else 0

            current_avg = _wavg(valid)
            for gw in optional_wins:
                if gw['game_npi'] >= current_avg:
                    valid.append(gw)
                    current_avg = _wavg(valid)
                else:
                    break

        excluded = [g for g in matched if g not in valid]

        # === Compute various aggregates ===
        all_pts = sum(g['pts'] for g in matched)
        all_wgt = sum(g['wgt'] for g in matched)
        all_count = len(matched)

        valid_pts = sum(g['pts'] for g in valid)
        valid_wgt = sum(g['wgt'] for g in valid)
        valid_count = len(valid)

        wp_all = (all_pts / all_wgt) if all_wgt > 0 else 0.0
        wp_valid = (valid_pts / valid_wgt) if valid_wgt > 0 else 0.0

        sos_valid_num = sum(g['opp_npi'] * g['wgt'] for g in valid)
        sos_valid = sos_valid_num / valid_wgt if valid_wgt > 0 else 0.0

        # QWB numerator variants
        # A: sum(bonus * wgt) over valid games
        qwb_num_A = sum(g['bonus'] * g['wgt'] for g in valid)
        # B: sum(bonus) over valid games (unweighted)
        qwb_num_B = sum(g['bonus'] for g in valid)
        # C: sum(bonus * wgt) over ALL games
        qwb_num_C = sum(g['bonus'] * g['wgt'] for g in matched)
        # D: sum(bonus) over ALL games
        qwb_num_D = sum(g['bonus'] for g in matched)

        # QWB denominator variants
        denoms = {
            'all_wgt': all_wgt,
            'valid_wgt': valid_wgt,
            'all_count': all_count,
            'valid_count': valid_count,
            '2*all_wgt': 2 * all_wgt,
        }

        # Try all combinations
        hypotheses = {}
        for num_label, num_val in [('A_bonus*wgt_valid', qwb_num_A),
                                     ('B_bonus_valid', qwb_num_B),
                                     ('C_bonus*wgt_all', qwb_num_C),
                                     ('D_bonus_all', qwb_num_D)]:
            for den_label, den_val in denoms.items():
                key = f"{num_label}/{den_label}"
                hypotheses[key] = num_val / den_val if den_val > 0 else 0.0

        # Also try: NPI as direct weighted average of Game NPI over valid games
        # NPI_direct = sum(game_npi * wgt) / sum(wgt) over valid
        npi_direct = sum(g['game_npi'] * g['wgt'] for g in valid) / valid_wgt if valid_wgt > 0 else 0.0
        qwb_from_direct = npi_direct - (wp_valid * 100 * 0.25) - (sos_valid * 0.75)
        hypotheses['direct_avg_residual(wp_valid)'] = qwb_from_direct

        # What about: NPI_direct = sum(game_npi * wgt) / sum(wgt) over valid,
        # but displayed QWB = NPI_direct - 0.25*WP_all - 0.75*SOS_valid
        qwb_display = npi_direct - (wp_all * 100 * 0.25) - (sos_valid * 0.75)
        hypotheses['direct_avg_residual(wp_all)'] = qwb_display

        chn_qwb = CHN_SUMMARY[team_name]['qwb']
        chn_npi = CHN_SUMMARY[team_name]['npi']

        results[team_name] = {
            'hypotheses': hypotheses,
            'chn_qwb': chn_qwb,
            'chn_npi': chn_npi,
            'npi_direct': npi_direct,
            'wp_all': wp_all,
            'wp_valid': wp_valid,
            'sos_valid': sos_valid,
            'all_wgt': all_wgt,
            'valid_wgt': valid_wgt,
            'all_count': all_count,
            'valid_count': valid_count,
            'excluded': excluded,
            'qwb_num_A': qwb_num_A,
        }

    # --- Print summary ---
    # Find which hypothesis best matches across all teams
    all_keys = list(next(iter(results.values()))['hypotheses'].keys())

    print(f"\n  Per-team QWB comparison:")
    print(f"  {'Hypothesis':<40} ", end="")
    for team in results:
        print(f"| {team[:8]:>8} ", end="")
    print(f"| {'MaxErr':>7}")
    print(f"  {'-'*40}-", end="")
    for _ in results:
        print(f"+{'-'*10}", end="")
    print(f"+{'-'*8}")

    # Print CHN reference
    print(f"  {'CHN QWB':<40} ", end="")
    for team in results:
        print(f"| {results[team]['chn_qwb']:>8.4f} ", end="")
    print(f"|")
    print()

    best_key = None
    best_max_err = 999

    for key in all_keys:
        max_err = 0
        vals = []
        for team in results:
            val = results[team]['hypotheses'][key]
            err = abs(val - results[team]['chn_qwb'])
            max_err = max(max_err, err)
            vals.append(val)

        # Only print promising hypotheses (max error < 1.0)
        if max_err < 1.0:
            print(f"  {key:<40} ", end="")
            for v in vals:
                print(f"| {v:>8.4f} ", end="")
            print(f"| {max_err:>7.4f}")

        if max_err < best_max_err:
            best_max_err = max_err
            best_key = key

    print(f"\n  Best hypothesis: {best_key} (max error={best_max_err:.4f})")

    # Print NPI comparison
    print(f"\n\n  NPI Comparison:")
    print(f"  {'Team':<20} {'CHN NPI':>8} {'Direct':>8} {'Diff':>7} | {'WP_all':>8} {'WP_val':>8} {'SOS':>8} | {'ExclN':>5} {'AllWgt':>7} {'ValWgt':>7}")
    for team in results:
        r = results[team]
        print(f"  {team:<20} {r['chn_npi']:>8.2f} {r['npi_direct']:>8.2f} {r['npi_direct']-r['chn_npi']:>+7.2f} "
              f"| {r['wp_all']*100:>8.2f} {r['wp_valid']*100:>8.2f} {r['sos_valid']:>8.2f} "
              f"| {len(r['excluded']):>5} {r['all_wgt']:>7.2f} {r['valid_wgt']:>7.2f}")

    # Try reverse-engineering: what multiplier would match CHN's QWB?
    print(f"\n\n  Reverse-engineering QWB multiplier:")
    print(f"  Using numerator A (sum bonus*wgt over valid) / all_wgt:")
    for team in results:
        r = results[team]
        if r['chn_qwb'] > 0 and r['qwb_num_A'] > 0:
            # current: qwb = (qwb_num_A / all_wgt) with mult=0.5
            # we want: qwb * factor = chn_qwb
            # so factor = chn_qwb / (qwb_num_A / all_wgt)
            our_qwb = r['qwb_num_A'] / r['all_wgt']
            factor = r['chn_qwb'] / our_qwb
            print(f"    {team:<20}: our={our_qwb:.4f}, chn={r['chn_qwb']:.4f}, needed_factor={factor:.4f}")


def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)
    npi.fit()

    analyze_qwb(npi)


if __name__ == "__main__":
    main()
