import pandas as pd
import numpy as np

def compare_npi():
    print("Loading Data...")
    calc_df = pd.read_csv('data/processed/npi_games_rankings.csv')
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    
    # Rename for merge
    ref_df = ref_df[['Team', 'NPI', 'SOS']].rename(columns={'NPI': 'Ref_NPI', 'SOS': 'Ref_SOS'})
    calc_df = calc_df[['Team', 'NPI', 'SOS']].rename(columns={'NPI': 'Calc_NPI', 'SOS': 'Calc_SOS'})
    
    # Merge
    merged = pd.merge(calc_df, ref_df, on='Team', how='inner')
    
    # Calculate Differences
    merged['NPI_Diff'] = merged['Calc_NPI'] - merged['Ref_NPI']
    merged['SOS_Diff'] = merged['Calc_SOS'] - merged['Ref_SOS']
    merged['Abs_NPI_Diff'] = merged['NPI_Diff'].abs()
    
    # Sort by NPI Diff
    merged.sort_values('Abs_NPI_Diff', ascending=False, inplace=True)
    
    print("\n--- Top 20 NPI Discrepancies ---")
    print(merged[['Team', 'Calc_NPI', 'Ref_NPI', 'NPI_Diff', 'Calc_SOS', 'Ref_SOS', 'SOS_Diff']].head(20).to_string(index=False))
    
    # Calculate Stats
    mae = merged['Abs_NPI_Diff'].mean()
    rmse = np.sqrt((merged['NPI_Diff'] ** 2).mean())
    print(f"\nMAE: {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    
    # Save comparison
    merged.to_csv('data/processed/npi_comparison_2026_01_27.csv', index=False)
    print("\nFull comparison saved to 'data/processed/npi_comparison_2026_01_27.csv'")

if __name__ == "__main__":
    compare_npi()
