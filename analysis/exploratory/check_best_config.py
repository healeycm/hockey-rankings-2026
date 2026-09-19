import pandas as pd
import numpy as np

def check_mae():
    print("Loading Results...")
    exp_df = pd.read_csv('data/processed/qwb_experiment_results.csv')
    ref_df = pd.read_csv('data/raw/npi_2026_01_27.csv')
    
    # Merge on Team
    merged = pd.merge(exp_df, ref_df[['Team', 'NPI']], on='Team')
    
    configs = [
        'Base', # Suffix
        'High Bar (53/0.8)', 
        'Low Bar (49/0.3)',
        'Additive (Simple Avg)'
    ]
    
    print("\n--- Calibration Results (MAE vs Reference) ---")
    for conf in configs:
        if conf == 'Base':
            col = 'Base_NPI'
        else:
            col = f"{conf}_NPI"
            
        merged['Diff'] = merged[col] - merged['NPI'] # Ref NPI
        mae = merged['Diff'].abs().mean()
        rmse = np.sqrt((merged['Diff'] ** 2).mean())
        bias = merged['Diff'].mean()
        
        print(f"{conf:25} | MAE: {mae:.4f} | RMSE: {rmse:.4f} | Bias: {bias:.4f}")

if __name__ == "__main__":
    check_mae()
