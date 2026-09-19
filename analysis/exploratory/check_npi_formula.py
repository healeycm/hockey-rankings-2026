import pandas as pd
import numpy as np
from analysis.exploratory.calibration_targets import TARGETS

def check_formula():
    print(f"{'Team':<20} | {'Target NPI':<10} | {'Calc NPI':<10} | {'Diff':<10} | {'AdjWP':<8} | {'SOS':<8} | {'QWB':<8}")
    print("-" * 90)
    
    total_diff = 0.0
    count = 0
    
    for team, data in TARGETS.items():
        npi_target = data['NPI']
        wp = data['AdjWP']
        sos = data['SOS']
        qwb = data['QWB']
        
        # Formula: 0.25 * WP + 0.75 * SOS + QWB
        calc_npi = (0.25 * wp) + (0.75 * sos) + qwb
        
        diff = npi_target - calc_npi
        total_diff += abs(diff)
        count += 1
        
        print(f"{team:<20} | {npi_target:<10.3f} | {calc_npi:<10.3f} | {diff:<10.4f} | {wp:<8.3f} | {sos:<8.3f} | {qwb:<8.3f}")

    avg_diff = total_diff / count
    print("-" * 90)
    print(f"Average Absolute Difference: {avg_diff:.4f}")

if __name__ == "__main__":
    check_formula()
