import argparse
import pandas as pd
from src.rankings.npi_games import NPIGames

def run_npi_games(season=20252026, cutoff=None):
    """
    cutoff: optional 'YYYY-MM-DD' string. If given, only games on/before this
    date are included. IMPORTANT: when comparing against a published reference
    NPI snapshot (e.g. USCHO/CHN NPI as of a given date), this MUST be set to
    that same date. Omitting it silently includes games played after the
    reference was generated and produces a uniform negative bias across every
    team (see reports/npi_investigation_2026.md).
    """
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    games_df['Date'] = pd.to_datetime(games_df['Date'])
    season_df = games_df[games_df['Season'] == season].copy()
    if cutoff:
        cutoff_ts = pd.Timestamp(cutoff)
        season_df = season_df[season_df['Date'] <= cutoff_ts].copy()
        print(f"Filtered to games on/before {cutoff_ts.date()}: {len(season_df)} games")

    print("Running NPI Games Logic...")
    npi_system = NPIGames(season_df)
    npi_system.fit()
    
    # Extract ratings
    ratings = []
    for team, details in npi_system.details.items():
        ratings.append({
            'Team': team,
            'NPI': details['npi'],
            'SOS': details['sos'],
            'QWB': details['qwb'],
            'WP': details['wp'],
            'Dropped Wins': details.get('dropped_wins', 0),
            'Dropped Losses': details.get('dropped_losses', 0)
        })
        
    ratings_df = pd.DataFrame(ratings)
    ratings_df.sort_values('NPI', ascending=False, inplace=True)
    ratings_df.reset_index(drop=True, inplace=True)
    ratings_df['Rank'] = ratings_df.index + 1
    
    # Display Top 20
    print("\nTop 20 Teams (NPI Games Logic + Good Loss Filter):")
    print(ratings_df[['Rank', 'Team', 'NPI', 'SOS', 'Dropped Wins', 'Dropped Losses']].head(20).to_string(index=False))
    
    # Identify teams with Dropped Wins/Losses
    dropped_wins = ratings_df[ratings_df['Dropped Wins'] > 0]
    dropped_losses = ratings_df[ratings_df['Dropped Losses'] > 0]
    
    if not dropped_wins.empty:
        print(f"\nTeams with Bad Wins Removed ({len(dropped_wins)}):")
        print(dropped_wins[['Rank', 'Team', 'Dropped Wins']].to_string(index=False))
        
    if not dropped_losses.empty:
        print(f"\nTeams with Good Losses Removed ({len(dropped_losses)}):")
        print(dropped_losses[['Rank', 'Team', 'Dropped Losses']].to_string(index=False))
    else:
        print("\nNo teams had good losses removed.")
    
    # Save full results
    out_path = 'data/processed/npi_games_rankings.csv'
    ratings_df.to_csv(out_path, index=False)
    print(f"\nFull rankings saved to: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', type=int, default=20252026)
    parser.add_argument('--cutoff', type=str, default=None,
                         help="YYYY-MM-DD. Match this to the reference NPI snapshot's date "
                              "when validating against published USCHO/CHN NPI values.")
    args = parser.parse_args()
    run_npi_games(season=args.season, cutoff=args.cutoff)
