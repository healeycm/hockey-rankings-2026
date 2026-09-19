import sys
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation.metrics import (
    calculate_brier,
    calculate_ece,
    calculate_brier_decomposition,
    calculate_rps,
    get_calibration_table,
)


def test_ece_is_zero_for_perfect_calibration():
    """A model whose predicted probability always exactly equals the bin's
    actual outcome rate should have ECE = 0."""
    df = pd.DataFrame({
        'HomeWinProb': [0.5] * 100,
        'Result': [1.0] * 50 + [0.0] * 50,  # actual rate in this bin is exactly 0.5
    })
    assert calculate_ece(df) == pytest.approx(0.0, abs=1e-9)


def test_ece_detects_overconfidence():
    """A model predicting 0.95 that's only right half the time should have
    a large ECE, not a small one."""
    df = pd.DataFrame({
        'HomeWinProb': [0.95] * 100,
        'Result': [1.0] * 50 + [0.0] * 50,
    })
    ece = calculate_ece(df)
    assert ece == pytest.approx(0.45, abs=1e-9)  # |0.95 - 0.5|


def test_ece_empty_dataframe():
    assert calculate_ece(pd.DataFrame({'HomeWinProb': [], 'Result': []})) == 0.0


def test_brier_decomposition_reconstructs_brier():
    """reliability - resolution + uncertainty must equal (or very closely
    approximate) the plain Brier score computed directly -- this is the
    whole point of Murphy's decomposition being a decomposition."""
    rng = np.random.default_rng(0)
    n = 500
    p = rng.uniform(0.1, 0.9, n)
    y = (rng.random(n) < p).astype(float)
    df = pd.DataFrame({'HomeWinProb': p, 'Result': y})

    brier = calculate_brier(df)
    decomp = calculate_brier_decomposition(df, n_bins=20)

    assert decomp['brier_check'] == pytest.approx(brier, abs=0.01)


def test_brier_decomposition_zero_resolution_for_constant_prediction():
    """A model that always predicts the same probability (e.g. the base
    rate) has zero resolution by definition -- it doesn't discriminate at
    all between games."""
    df = pd.DataFrame({
        'HomeWinProb': [0.6] * 200,
        'Result': [1.0] * 120 + [0.0] * 80,  # base rate is exactly 0.6
    })
    decomp = calculate_brier_decomposition(df, n_bins=10)
    assert decomp['resolution'] == pytest.approx(0.0, abs=1e-9)


def test_brier_decomposition_empty_dataframe():
    decomp = calculate_brier_decomposition(pd.DataFrame({'HomeWinProb': [], 'Result': []}))
    assert decomp == {'reliability': 0.0, 'resolution': 0.0, 'uncertainty': 0.0, 'brier_check': 0.0}


def test_calibration_table_bins_and_gap():
    df = pd.DataFrame({
        'HomeWinProb': [0.1, 0.15, 0.85, 0.9],
        'Result': [0.0, 1.0, 1.0, 1.0],
    })
    table = get_calibration_table(df, n_bins=10)
    assert set(table.columns) == {'BinLow', 'BinHigh', 'N', 'Predicted', 'Actual', 'Gap'}
    assert table['N'].sum() == 4
    # Gap = Predicted - Actual, so an underconfident bin has negative Gap
    low_bin = table[table['BinLow'] == pytest.approx(0.1)]
    assert (low_bin['Gap'] < 0).all()  # predicted 0.1-0.15, actual outcome rate is 0.5 in that bin


def test_rps_zero_for_perfect_prediction():
    df = pd.DataFrame({
        'P_Home': [1.0, 0.0, 0.0],
        'P_Tie': [0.0, 1.0, 0.0],
        'P_Away': [0.0, 0.0, 1.0],
        'Result': [1.0, 0.5, 0.0],
    })
    assert calculate_rps(df) == pytest.approx(0.0, abs=1e-9)


def test_rps_penalizes_ordinal_distance():
    """Predicting a tie when a home win occurs should be a SMALLER RPS
    error than predicting an away win would have been for that same
    home-win outcome -- the whole point of using an ordinal score."""
    df_tie_guess = pd.DataFrame({'P_Home': [0.0], 'P_Tie': [1.0], 'P_Away': [0.0], 'Result': [1.0]})
    df_away_guess = pd.DataFrame({'P_Home': [0.0], 'P_Tie': [0.0], 'P_Away': [1.0], 'Result': [1.0]})
    rps_tie = calculate_rps(df_tie_guess)
    rps_away = calculate_rps(df_away_guess)
    assert rps_tie < rps_away


def test_rps_empty_dataframe():
    assert calculate_rps(pd.DataFrame({'P_Home': [], 'P_Tie': [], 'P_Away': [], 'Result': []})) == 0.0
