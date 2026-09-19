"""
Likelihood-ratio tests for Dixon-Coles' eta (home-ice) and rho (low-score
correction), one season at a time. Unlike HockeyBT's fit_ties boundary,
eta and rho nest smoothly here (verified: evaluating the rho-model's
objective at [eta-model's solution, rho=0] exactly recovers the eta-model's
likelihood), so a straightforward LR test is valid across both boundaries.

Run from the project root as a module:
    python -m analysis.exploratory.dixon_coles_lr_check

Note: fit() warm-starts each stage from the previous (simpler) one
specifically because a cold start can converge to a WORSE likelihood than a
strictly-nested simpler model — caught on the 2025-26 season, where it
produced an impossible negative LR statistic before the warm-start fix (see
dixon_coles.py's fit() docstring).
"""
import pandas as pd
from scipy import stats
from src.data.loader import DataLoader
from src.rankings.dixon_coles import DixonColes


def main():
    loader = DataLoader()
    history_df = loader.get_history()

    for season in [20222023, 20232024, 20242025, 20252026]:
        sdf = history_df[history_df['Season'] == season].copy()
        d0 = DixonColes(sdf, config={'fit_home_ice': False, 'fit_rho': False}); d0.fit()
        d1 = DixonColes(sdf, config={'fit_home_ice': True, 'fit_rho': False}); d1.fit()
        d2 = DixonColes(sdf, config={'fit_home_ice': True, 'fit_rho': True}); d2.fit()

        lr01 = 2 * (d0.fit_result_.fun - d1.fit_result_.fun)
        lr12 = 2 * (d1.fit_result_.fun - d2.fit_result_.fun)
        p01 = 1 - stats.chi2.cdf(lr01, df=1)
        p12 = 1 - stats.chi2.cdf(lr12, df=1)
        print(f"{season}: eta={d1.eta:.4f} (LR={lr01:.2f} p={p01:.2e})   "
              f"rho={d2.rho:.4f} (LR={lr12:.2f} p={p12:.2e})")


if __name__ == "__main__":
    main()
