"""
Test convergence variants: Jacobi vs Gauss-Seidel, and rounding during iteration.
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.rankings.npi import NPI

CHN = {
    'Michigan': 59.10, 'North Dakota': 58.21, 'Michigan State': 58.01,
    'Western Michigan': 57.39, 'Denver': 57.15, 'Dartmouth': 56.41,
    'Providence': 56.06, 'Minnesota Duluth': 55.90, 'Penn State': 55.36,
    'Quinnipiac': 55.34, 'Cornell': 55.14, 'Wisconsin': 55.01,
    'Minnesota State': 54.27, 'Connecticut': 54.18, 'Augustana': 54.00,
    'St. Thomas': 53.90, 'Massachusetts': 53.87, 'Boston College': 53.36,
    'Merrimack': 53.35, 'Michigan Tech': 53.02, 'Ohio State': 52.86,
    'Princeton': 52.78, 'Bentley': 52.68, 'Bowling Green': 52.67,
    'Maine': 52.62, 'Union': 52.30, 'Northeastern': 52.05,
    'Boston University': 52.02, 'Sacred Heart': 51.81, 'St. Cloud State': 51.76,
    'Colorado College': 51.54, 'Harvard': 51.47, 'Miami': 51.47,
    'Clarkson': 50.90, 'Alaska': 50.59, 'Air Force': 50.56,
    'Lindenwood': 50.43, 'Holy Cross': 50.41, 'Minnesota': 50.16,
    'New Hampshire': 49.82, 'Arizona State': 49.65, 'LIU': 49.48,
    'Omaha': 49.41, 'RIT': 49.10, 'Army': 48.77, 'UMass Lowell': 48.69,
    'Robert Morris': 48.61, 'Canisius': 48.39, 'Colgate': 48.36,
    'Bemidji State': 48.30, 'Notre Dame': 48.02, 'Vermont': 47.92,
    'Lake Superior': 47.52, 'RPI': 46.79, 'Niagara': 45.95,
    'Ferris State': 45.90, 'Stonehill': 45.48, 'Yale': 44.96,
    'Brown': 44.01, 'Northern Michigan': 43.25, 'St. Lawrence': 43.19,
    'Alaska Anchorage': 42.81, 'Mercyhurst': 42.69,
}


def run_variant(npi_obj, team_games, raw_wps, mode='jacobi', round_dp=None, max_iter=200, tol=1e-5):
    """Run iterative NPI with different update strategies."""
    QWB_BASE = npi_obj.conf['quality_win_base']
    QWB_MULT = npi_obj.conf['quality_win_mult']
    teams = npi_obj.teams

    # Start from WP
    current = {}
    for t in teams:
        games = team_games[t]
        pts = sum(g['pts'] for g in games)
        wgt = sum(g['wgt'] for g in games)
        current[t] = (pts / wgt * 100) if wgt > 0 else 50.0

    for iteration in range(1, max_iter + 1):
        max_diff = 0.0
        new_ratings = {} if mode == 'jacobi' else None

        for team in teams:
            games = team_games[team]
            total_wgt = sum(g['wgt'] for g in games)
            total_pts = sum(g['pts'] for g in games)
            if total_wgt == 0:
                if mode == 'jacobi':
                    new_ratings[team] = current[team]
                continue

            wp = total_pts / total_wgt

            # Use current ratings (for Gauss-Seidel, this includes already-updated teams)
            sos_num = 0.0
            qwb_sum = 0.0
            for g in games:
                opp_npi = current[g['opponent']]
                sos_num += opp_npi * g['wgt']
                if g['pts'] > 0 and opp_npi > QWB_BASE:
                    qwb_sum += (opp_npi - QWB_BASE) * QWB_MULT * g['pts']

            sos = sos_num / total_wgt
            qwb = qwb_sum / total_wgt
            new_npi = wp * 100 * 0.25 + sos * 0.75 + qwb

            if round_dp is not None:
                new_npi = round(new_npi, round_dp)

            max_diff = max(max_diff, abs(new_npi - current[team]))

            if mode == 'jacobi':
                new_ratings[team] = new_npi
            else:
                current[team] = new_npi  # Gauss-Seidel: update in-place

        if mode == 'jacobi':
            current = new_ratings

        if max_diff < tol:
            break

    return current, iteration


def compare(ratings, label):
    diffs = [(t, ratings[t] - CHN[t]) for t in CHN if t in ratings]
    avg = sum(d for _, d in diffs) / len(diffs)
    mae = sum(abs(d) for _, d in diffs) / len(diffs)
    max_err = max(abs(d) for _, d in diffs)
    print(f"  {label:<40}  avg={avg:+.6f}  MAE={mae:.6f}  max={max_err:.4f}")
    return avg, mae, max_err


def main():
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    npi = NPI(season_df)

    # Build team_games dict the same way fit() does
    team_games = {t: [] for t in npi.teams}
    for _, row in npi.games.iterrows():
        h, a = row['HomeTeam'], row['AwayTeam']
        h_pts, h_wgt = npi._calculate_game_points(row, 'Home')
        a_pts, a_wgt = npi._calculate_game_points(row, 'Away')
        h_is_win = row['Result'] == 1.0
        a_is_win = row['Result'] == 0.0
        team_games[h].append({'opponent': a, 'pts': h_pts, 'wgt': h_wgt, 'is_win': h_is_win})
        team_games[a].append({'opponent': h, 'pts': a_pts, 'wgt': a_wgt, 'is_win': a_is_win})

    raw_wps = {}
    for t, g in team_games.items():
        pts = sum(x['pts'] for x in g)
        wgt = sum(x['wgt'] for x in g)
        raw_wps[t] = (pts / wgt * 100) if wgt > 0 else 50.0

    print("Convergence variants vs CHN:")

    # Jacobi (current method)
    r, n = run_variant(npi, team_games, raw_wps, mode='jacobi', round_dp=None)
    compare(r, f"Jacobi, no rounding (iter={n})")

    # Gauss-Seidel
    r, n = run_variant(npi, team_games, raw_wps, mode='gauss-seidel', round_dp=None)
    compare(r, f"Gauss-Seidel, no rounding (iter={n})")

    # Jacobi with 2dp rounding
    r, n = run_variant(npi, team_games, raw_wps, mode='jacobi', round_dp=2)
    compare(r, f"Jacobi, round 2dp (iter={n})")

    # Gauss-Seidel with 2dp rounding
    r, n = run_variant(npi, team_games, raw_wps, mode='gauss-seidel', round_dp=2)
    compare(r, f"Gauss-Seidel, round 2dp (iter={n})")

    # Jacobi with 4dp rounding
    r, n = run_variant(npi, team_games, raw_wps, mode='jacobi', round_dp=4)
    compare(r, f"Jacobi, round 4dp (iter={n})")

    # Gauss-Seidel with 4dp rounding
    r, n = run_variant(npi, team_games, raw_wps, mode='gauss-seidel', round_dp=4)
    compare(r, f"Gauss-Seidel, round 4dp (iter={n})")

    # Print top-10 for the best variant
    print("\nTop-10 for Gauss-Seidel 2dp:")
    r_best, _ = run_variant(npi, team_games, raw_wps, mode='gauss-seidel', round_dp=2)
    for rank, (t, v) in enumerate(sorted(r_best.items(), key=lambda x: -x[1])[:10], 1):
        chn_v = CHN.get(t, 0)
        print(f"  {rank:2d}. {t:<22} {v:7.2f} vs {chn_v:7.2f} ({v-chn_v:+.2f})")


if __name__ == "__main__":
    main()
