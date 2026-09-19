import pandas as pd
from src.rankings.npi import NPI

def check_math():
    print("Loading Data...")
    games_df = pd.read_csv('data/processed/games_archive.csv')
    season_df = games_df[games_df['Season'] == 20252026].copy()
    if 'Is_Exhibition' in season_df.columns:
         season_df = season_df[~season_df['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
         
    npi = NPI(season_df)
    npi.fit()
    
    target = "Michigan"
    d = npi.details[target]
    
    print(f"\n--- {target} Details ---")
    print(f"NPI: {d['npi']}")
    print(f"AdjWP: {d['adj_wp']}")
    print(f"SOS: {d['sos']}")
    print(f"QWB: {d['qwb']}")
    
    calc_sum = (d['adj_wp'] * 0.25) + (d['sos'] * 0.75) + d['qwb']
    print(f"\nRe-Summing Components:")
    print(f"WP Part: {d['adj_wp'] * 0.25}")
    print(f"SOS Part: {d['sos'] * 0.75}")
    print(f"QWB Part: {d['qwb']}")
    print(f"Total: {calc_sum}")
    
    print(f"Diff: {d['npi'] - calc_sum}")

if __name__ == "__main__":
    check_math()
