import numpy as np
import pandas as pd


# NOTE: sklearn imports removed to avoid type-check errors with soft labels

def apply_ot_weighting(df, ot_win_weight=0.6, ot_loss_weight=0.4):
    """
    Transforms the 'Result' column.
    Standard: Win=1.0, Loss=0.0
    Weighted: OT Win=0.6, OT Loss=0.4, Reg Win=1.0, Reg Loss=0.0

    Returns a pandas Series of the weighted results.
    """

    def get_val(row):
        # If it's a Tie (0.5), it stays 0.5 regardless of OT
        if row['Result'] == 0.5:
            return 0.5

        if row.get('IsOT', False):
            # OT Win (Home)
            if row['Result'] == 1.0:
                return ot_win_weight
            # OT Loss (Home) -> Meaning Away won in OT
            elif row['Result'] == 0.0:
                return ot_loss_weight

        # Regular Result
        return row['Result']

    return df.apply(get_val, axis=1)


def calculate_accuracy(df, target_col='Result'):
    """
    Binary Accuracy: Did the model predict the winner correctly?
    Tie games (Result=0.5) are excluded.
    For weighted targets (e.g. 0.6), we round to nearest integer (0 or 1).
    """
    # Filter out ties for binary accuracy
    valid_games = df[df[target_col] != 0.5].copy()
    if valid_games.empty:
        return 0.0

    # Round target to 0 or 1 (e.g. 0.6 -> 1.0, 0.4 -> 0.0)
    actual_winner = valid_games[target_col].round()
    predicted_winner = valid_games['HomeWinProb'].round()

    correct = (actual_winner == predicted_winner)
    return correct.mean()


def calculate_brier(df, target_col='Result'):
    """
    Brier Score: Mean Squared Error of probabilities.
    Lower is better. 0.0 is perfect.
    Handles soft labels (0.6) natively.
    """
    if df.empty:
        return 0.0

    # Manual MSE calculation
    return np.mean((df['HomeWinProb'] - df[target_col]) ** 2)


def calculate_log_loss(df, target_col='Result'):
    """
    Log Loss: Penalizes confident wrong answers heavily.
    Lower is better.

    Implemented manually to support soft labels (e.g. 0.6 for OT Win).
    Sklearn's log_loss requires binary targets or specific shapes for multiclass,
    which breaks when we introduce intermediate float values like 0.6.

    Formula: -mean( y * log(p) + (1-y) * log(1-p) )
    """
    # Filter pure ties (0.5) to keep log loss conceptually consistent
    # (though mathematically it works, 0.5 is usually excluded from binary metrics)
    valid_games = df[df[target_col] != 0.5].copy()
    if valid_games.empty:
        return 0.0

    y = valid_games[target_col]
    p = valid_games['HomeWinProb']

    # Clip probabilities to avoid log(0) error (standard practice)
    epsilon = 1e-15
    p = p.clip(epsilon, 1 - epsilon)

    # Manual Calculation
    loss = -1 * (y * np.log(p) + (1 - y) * np.log(1 - p))
    return np.mean(loss)


def calculate_calibration(df):
    """
    Returns the slope of Actual vs Predicted probabilities.
    1.0 is perfectly calibrated.
    """
    if len(df) < 10: return 0.0
    try:
        slope, _ = np.polyfit(df['HomeWinProb'], df['Result'], 1)
        return slope
    except:
        return 0.0


def _binned_calibration(p, y, n_bins=10):
    """
    Shared binning helper for ECE / Brier decomposition / the calibration
    table below. Bins by predicted probability into n_bins equal-width bins
    on [0, 1]; returns per-bin (lo, hi, count, mean_predicted, mean_actual).
    Empty bins are skipped rather than reported as 0/0.
    """
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)

    rows = []
    for b in range(n_bins):
        mask = idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append((bins[b], bins[b + 1], n, float(p[mask].mean()), float(y[mask].mean())))
    return rows


def get_calibration_table(df, target_col='Result', n_bins=10):
    """
    Bins predictions by predicted probability and reports, per bin: game
    count, mean predicted probability, mean actual outcome rate, and the
    gap between them. This is the diagnostic that made KRACH's
    overconfidence concrete rather than abstract: it predicted 94.2% in its
    top bin but was only right 82.2% of the time there (see
    reports/calibration_metrics.md).

    Returns a DataFrame with columns: BinLow, BinHigh, N, Predicted,
    Actual, Gap (Predicted - Actual; positive = overconfident in that bin,
    negative = underconfident).
    """
    rows = _binned_calibration(df['HomeWinProb'], df[target_col], n_bins=n_bins)
    out = pd.DataFrame(rows, columns=['BinLow', 'BinHigh', 'N', 'Predicted', 'Actual'])
    out['Gap'] = out['Predicted'] - out['Actual']
    return out


def calculate_ece(df, target_col='Result', n_bins=10):
    """
    Expected Calibration Error: the game-count-weighted average absolute
    gap between predicted probability and actual outcome rate, across
    n_bins equal-width probability bins. 0.0 is perfectly calibrated;
    unlike Brier/LogLoss, ECE isolates calibration specifically from
    sharpness/resolution (see calculate_brier_decomposition below for that
    split spelled out explicitly).
    """
    if df.empty:
        return 0.0
    rows = _binned_calibration(df['HomeWinProb'], df[target_col], n_bins=n_bins)
    n_total = len(df)
    return float(sum(n * abs(pred - act) for _, _, n, pred, act in rows) / n_total)


def calculate_brier_decomposition(df, target_col='Result', n_bins=10):
    """
    Murphy (1973) three-term decomposition: Brier = Reliability - Resolution
    + Uncertainty.
      Uncertainty  -- irreducible: the base rate's own variance, y_bar*(1-y_bar).
                      Identical for any two models evaluated on the same
                      games; differences in Brier come entirely from the
                      other two terms.
      Reliability  -- (lower is better) average, per probability bin, of
                      (predicted - actual)^2, weighted by bin size. This IS
                      calibration error, in the same units as Brier.
      Resolution   -- (HIGHER is better, note the sign in the formula above)
                      average, per bin, of (bin's actual rate - overall base
                      rate)^2. Measures how much the model's predictions
                      actually discriminate winners from losers, independent
                      of whether those predictions are well-calibrated.
    A model can win on Brier via better reliability (genuinely better
    calibrated), via better resolution (sharper/more discriminating), or
    both -- this project found a real case of the two models it applies to
    (ELO: best reliability; Massey: best resolution) winning for different
    reasons despite Massey having the better raw Brier score overall (see
    reports/calibration_metrics.md).

    Returns a dict: {'reliability', 'resolution', 'uncertainty', 'brier_check'}
    -- brier_check is reliability - resolution + uncertainty, included so
    callers can sanity-check it against calculate_brier()'s own result
    (they should match to within binning/rounding error).
    """
    if df.empty:
        return {'reliability': 0.0, 'resolution': 0.0, 'uncertainty': 0.0, 'brier_check': 0.0}

    p = df['HomeWinProb'].values.astype(float)
    y = df[target_col].values.astype(float)
    n = len(p)
    y_bar = y.mean()
    uncertainty = y_bar * (1 - y_bar)

    rows = _binned_calibration(p, y, n_bins=n_bins)
    reliability = sum(cnt * (pred - act) ** 2 for _, _, cnt, pred, act in rows) / n
    resolution = sum(cnt * (act - y_bar) ** 2 for _, _, cnt, pred, act in rows) / n

    return {
        'reliability': float(reliability),
        'resolution': float(resolution),
        'uncertainty': float(uncertainty),
        'brier_check': float(reliability - resolution + uncertainty),
    }


def calculate_rps(df):
    """
    Ranked Probability Score for a native 3-outcome (home win / tie / away
    win) prediction — the proper generalization of Brier score to an
    ORDERED categorical outcome (away-win < tie < home-win is a genuine
    ordinal scale, unlike e.g. predicting among unordered team identities).
    Unlike collapsing to a single HomeWinProb scalar (this project's
    standard convention elsewhere, for comparability with models that only
    predict two outcomes), RPS gives partial credit for "almost right" in a
    way that respects the ordering — predicting a tie when the actual
    result was a home win is a smaller error than predicting an away win
    would have been.

    Only meaningful for models that expose a `predict_outcomes()` method
    (HockeyBT, DixonColes) returning (P_home_win, P_tie, P_away_win) per
    game — see reports/calibration_metrics.md's first-ever evaluation of
    these models' native tie predictions, previously never checked because
    every backtest metric before this used the collapsed scalar.

    Expects df with columns 'P_Home', 'P_Tie', 'P_Away', and 'Result'
    (1.0/0.5/0.0). Returns the mean RPS (lower is better; 0 is perfect).
    """
    if df.empty:
        return 0.0

    p_home = df['P_Home'].values.astype(float)
    p_tie = df['P_Tie'].values.astype(float)
    p_away = df['P_Away'].values.astype(float)
    result = df['Result'].values.astype(float)

    actual_home = (result == 1.0).astype(float)
    actual_tie = (result == 0.5).astype(float)
    actual_away = (result == 0.0).astype(float)

    # Ordinal order: away-win, tie, home-win. Cumulative sums up to (but
    # excluding) the final category always equal 1 for both predicted and
    # actual, so only the first two cumulative terms carry information.
    cum_pred_1 = p_away
    cum_pred_2 = p_away + p_tie
    cum_actual_1 = actual_away
    cum_actual_2 = actual_away + actual_tie

    rps = ((cum_pred_1 - cum_actual_1) ** 2 + (cum_pred_2 - cum_actual_2) ** 2) / 2.0
    return float(np.mean(rps))