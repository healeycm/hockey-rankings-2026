import pandas as pd

def export_michigan_schedule():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    # Load Reference NPIs
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    ref_data = {}
    for _, row in ref_df.iterrows():
        ref_data[row['Team']] = {'NPI': float(row['NPI']), 'QWB': float(row['QWB'])}
    
    team = "Merrimack"
    team_games = season_df[(season_df['HomeTeam'] == team) | (season_df['AwayTeam'] == team)]
    
    rows = []
    for _, row in team_games.iterrows():
        if row['HomeTeam'] == team:
            opp = row['AwayTeam']
            loc = "Home"
        else:
            opp = row['HomeTeam']
            loc = "Away"
            
        if row['NeutralSite']:
            loc = "Neutral"
            
        opp_info = ref_data.get(opp, {'NPI': 0.0, 'QWB': 0.0})
        opp_npi = opp_info['NPI']
        opp_qwb_total = opp_info['QWB']
        
        # Calculated Bonus for Michigan (if win)
        bonus_val = max(0.0, (opp_npi - 51.0) * 0.5) if (loc != "Home" or row['HomeTeam'] == team) and ((row['HomeTeam'] == team and row['Result'] == 1.0) or (row['AwayTeam'] == team and row['Result'] == 0.0)) else 0.0
        
        rows.append({
            'Date': row['Date'],
            'Opponent': opp,
            'Location': loc,
            'Neutral Site': row['NeutralSite'],
            'Opponent NPI': opp_npi,
            'Opponent Table QWB': opp_qwb_total
        })
        
    out_df = pd.DataFrame(rows)
    # Sort by Date
    out_df['Date'] = pd.to_datetime(out_df['Date'])
    out_df.sort_values('Date', inplace=True)
    
    csv_path = 'merrimack_schedule_analysis.csv'
    out_df.to_csv(csv_path, index=False)
    print(f"Exported {len(out_df)} games to {csv_path}")

if __name__ == "__main__":
    export_michigan_schedule()
