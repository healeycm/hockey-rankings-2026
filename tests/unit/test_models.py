import sys
import os
import pandas as pd
import pytest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.rankings.krach import KRACH

@pytest.fixture
def sample_data():
    data = {
        'Season': [20252026, 20252026],
        'HomeTeam': ['Team A', 'Team B'],
        'AwayTeam': ['Team B', 'Team A'],
        'Result': [1.0, 0.0],  # Team A won twice against Team B
        'IsOT': [False, False]
    }
    return pd.DataFrame(data)

def test_krach_fit(sample_data):
    model = KRACH(sample_data)
    model.fit()
    rankings = model.get_rankings()
    
    assert 'Team A' in rankings['Team'].values
    assert 'Team B' in rankings['Team'].values
    # Team A should be ranked higher
    rank_a = rankings[rankings['Team'] == 'Team A']['Rating'].iloc[0]
    rank_b = rankings[rankings['Team'] == 'Team B']['Rating'].iloc[0]
    assert rank_a > rank_b

def test_krach_predict(sample_data):
    model = KRACH(sample_data)
    model.fit()
    prob = model.predict('Team A', 'Team B')
    assert prob > 0.5
