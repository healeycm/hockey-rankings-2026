"""
Correctness gate for HockeyBT: with fit_home_ice=False, fit_ties=False,
prior_strength=0.0 (K0), it must be exactly standard Bradley-Terry — the
same model KRACH's iterative solver computes. Verifies the L-BFGS-B-based
solver is correct, independent of whether the Davidson-Beaver extensions
(theta, nu, kappa) are worth having.

Run from the project root as a module:
    python -m analysis.exploratory.hockey_bt_k0_check
"""
import pandas as pd
import numpy as np
from src.data.loader import DataLoader
from src.rankings.krach import KRACH
from src.rankings.hockey_bt import HockeyBT


def main():
    loader = DataLoader()
    history_df = loader.get_history()
    season = history_df[history_df['Season'] == 20242025].copy()

    k = KRACH(season)
    k.fit()
    b = HockeyBT(season, config={'fit_home_ice': False, 'fit_ties': False, 'prior_strength': 0.0})
    b.fit()

    kr = pd.Series(k.ratings).sort_index()
    br = pd.Series(b.ratings).sort_index()
    assert (kr.index == br.index).all()

    diff = kr - br
    print("Optimizer converged:", b.fit_result_.success, b.fit_result_.message)
    print("N teams:", len(kr))
    print("Correlation:", np.corrcoef(kr, br)[0, 1])
    print("Max abs diff:", diff.abs().max())
    print("Mean abs diff:", diff.abs().mean())
    print("theta (should be 1.0):", b.theta, "nu (should be 0.0):", b.nu)

    worst = diff.abs().sort_values(ascending=False).head(5)
    print("\nWorst 5 discrepancies:")
    for t in worst.index:
        print(f"  {t}: KRACH={kr[t]:.3f} HockeyBT_K0={br[t]:.3f} diff={diff[t]:+.3f}")


if __name__ == "__main__":
    main()
