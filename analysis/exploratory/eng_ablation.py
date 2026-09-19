"""
Empty-net-goal ablation for HockeyLRMC: real ENG data vs. the blind proxy
heuristic vs. no correction at all.

Run from the project root as a module:
    python -m analysis.exploratory.eng_ablation

Result (see reports/lrmc_empty_net.md): the real-data correction is WORST of
the three arms — `use_real_eng` ships defaulted to False. Restricted to the
two seasons with CHN empty-net coverage (2024-25, 2025-26); including
earlier seasons would dilute the comparison with splits where all three arms
are byte-identical.
"""
import pandas as pd
from pathlib import Path
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.rankings.hockey_lrmc import HockeyLRMC

loader = DataLoader()
history_df = loader.get_history()

MODELS = {
    "ENG_real": HockeyLRMC,        # real empty-net-goal correction (new)
    "ENG_none": HockeyLRMC,        # no empty-net correction at all
    "ENG_proxy": HockeyLRMC,       # old blind 2-goal-margin heuristic
}
base = {'auto_fit': True, 'fit_source': 'history'}
configs = {
    "ENG_real":  {**base, 'use_real_eng': True,  'empty_net_shrink': False},
    "ENG_none":  {**base, 'use_real_eng': False, 'empty_net_shrink': False},
    "ENG_proxy": {**base, 'use_real_eng': False, 'empty_net_shrink': True},
}

# Only the seasons with real ENG coverage -- including 2021-24 would dilute
# the comparison with 3 seasons where all three arms are identical.
seasons = [20242025, 20252026]
cutoffs = ['Jan1','Jan15','Feb1','Feb15']

out_dir = Path('data/validation/backtest_results')
engine = BacktestEngine(history_df, out_dir, ot_win_weight=0.6, ot_loss_weight=0.4)
engine.run(seasons=seasons, cutoffs=cutoffs, model_factory=MODELS, model_configs=configs)

summary = pd.DataFrame(engine.results_summary)
summary.to_csv(out_dir / 'eng_ablation.csv', index=False)
print("\n=== Empty-Net Ablation (ENG-covered seasons only: 2024-25, 2025-26; 8 splits) ===")
print(summary.groupby('Model')[['Accuracy','Brier','LogLoss']].mean().reindex(['ENG_none','ENG_proxy','ENG_real']))
print("\n=== Per-split detail (accuracy) ===")
piv = summary.pivot_table(index=['Season','Cutoff'], columns='Model', values='Accuracy')
print(piv[['ENG_none','ENG_proxy','ENG_real']].round(4))
print("\nSplits where ENG_real beat ENG_none (accuracy):",
      (piv['ENG_real'] > piv['ENG_none']).sum(), "of", len(piv))
