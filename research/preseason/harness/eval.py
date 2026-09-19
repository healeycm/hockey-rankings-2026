# research/preseason/harness/eval.py
"""
Shared evaluation helpers for preseason-prior experiments -- reuses
src/validation/metrics.py's OT-weighting convention (0.6/0.4, matching
every other backtest report in this project) and the same paired-test
pattern used throughout tests/*_backtest.py (paired t-test for Brier/
LogLoss, McNemar for accuracy).
"""
import numpy as np
import pandas as pd
from scipy import stats

from src.validation.metrics import apply_ot_weighting, calculate_accuracy, calculate_brier, calculate_log_loss


def weighted_result(pred_df):
    return apply_ot_weighting(pred_df, ot_win_weight=0.6, ot_loss_weight=0.4)


def game_level_metrics(p, y):
    """p, y: aligned numpy arrays of predicted home-win prob and weighted
    result. Returns accuracy/brier/logloss (unpaired, single-arm)."""
    df = pd.DataFrame({'HomeWinProb': p, 'WeightedResult': y})
    return {
        'Accuracy': calculate_accuracy(df, target_col='WeightedResult'),
        'Brier': calculate_brier(df, target_col='WeightedResult'),
        'LogLoss': calculate_log_loss(df, target_col='WeightedResult'),
    }


def paired_comparison(p_off, p_on, y):
    """Paired comparison of two arms' predictions against the same games
    (off = baseline, on = candidate). Returns a dict with both arms'
    metrics, diffs, and significance tests."""
    b_off, b_on = (p_off - y) ** 2, (p_on - y) ** 2
    _, p_brier = stats.ttest_rel(b_on, b_off) if len(y) > 1 else (None, np.nan)

    mask = y != 0.5
    yy = y[mask]
    pc_off, pc_on = np.clip(p_off[mask], 1e-15, 1 - 1e-15), np.clip(p_on[mask], 1e-15, 1 - 1e-15)
    ll_off = -(yy * np.log(pc_off) + (1 - yy) * np.log(1 - pc_off))
    ll_on = -(yy * np.log(pc_on) + (1 - yy) * np.log(1 - pc_on))
    _, p_logloss = stats.ttest_rel(ll_on, ll_off) if mask.sum() > 1 else (None, np.nan)

    correct_off = np.round(pc_off) == np.round(yy)
    correct_on = np.round(pc_on) == np.round(yy)
    b01, b10 = np.sum(correct_on & ~correct_off), np.sum(~correct_on & correct_off)
    mcnemar = (abs(b01 - b10) - 1) ** 2 / (b01 + b10) if (b01 + b10) > 0 else 0
    p_mcnemar = 1 - stats.chi2.cdf(mcnemar, df=1) if (b01 + b10) > 0 else np.nan

    return {
        'n': len(y),
        'acc_off': correct_off.mean(), 'acc_on': correct_on.mean(), 'p_mcnemar': p_mcnemar,
        'brier_off': b_off.mean(), 'brier_on': b_on.mean(), 'p_brier': p_brier,
        'logloss_off': ll_off.mean(), 'logloss_on': ll_on.mean(), 'p_logloss': p_logloss,
    }


def holm_correct(pvals):
    """Holm-Bonferroni step-down correction. Returns adjusted p-values in
    the same order as input (None/nan entries pass through unchanged)."""
    pvals = list(pvals)
    valid = [(i, p) for i, p in enumerate(pvals) if p is not None and not np.isnan(p)]
    valid.sort(key=lambda x: x[1])
    m = len(valid)
    adjusted = list(pvals)
    running_max = 0.0
    for rank, (i, p) in enumerate(valid):
        adj = min(1.0, (m - rank) * p)
        running_max = max(running_max, adj)
        adjusted[i] = running_max
    return adjusted
