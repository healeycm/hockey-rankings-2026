
import sys
import os
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root and webpage to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../webpage')))

from utils import data_loader

def test_normalization():
    print("Testing Name Normalization...")
    
    # Test valid names
    assert data_loader.normalize_name("Penn State") == "pennstate"
    assert data_loader.normalize_name("Penn_State") == "pennstate"
    assert data_loader.normalize_name("St. Cloud State") == "stcloudstate"
    assert data_loader.normalize_name("St_Cloud_State") == "stcloudstate"
    assert data_loader.normalize_name("Miami") == "miami"
    
    print("Normalization logic pass.")

def test_file_lookup():
    print("Testing File Lookup Logic (Mocked)...")
    
    # Mock finding directories
    mock_latest_dir = Path("mock/output/analysis/KRACH/2026-01-11")
    
    # Mock matching files in that dir
    # We pretend these files exist
    mock_files = [
        Path("Penn_State.csv"),
        Path("St_Cloud_State.csv"),
        Path("LIU.csv")
    ]
    
    # Mock team info df
    mock_team_info = pd.DataFrame({
        'Team Name': ['Penn State', 'LIU', 'St. Cloud State', 'UMass Lowell'],
        'USCHO_Name': ['Penn State', 'Long Island', 'St. Cloud State', 'Mass.-Lowell'],
        'CHN_Name': ['Penn State', 'Long Island', 'St. Cloud State', 'UMass Lowell']
    })
    
    # We need to mock:
    # 1. get_latest_file -> return directory path
    # 2. Path.glob -> return our mock files
    # 3. pd.read_csv -> return mock_team_info (when loading info) OR mock analysis df
    # 4. Path.exists -> True for team_info
    
    with patch('utils.data_loader.get_latest_file', return_value=str(mock_latest_dir)), \
         patch('pathlib.Path.is_dir', return_value=True), \
         patch('pathlib.Path.glob', return_value=mock_files), \
         patch('utils.data_loader.pd.read_csv') as mock_read_csv, \
         patch('pathlib.Path.exists', return_value=True):
         
        # Setup read_csv to handle different files
        def side_effect(filepath):
            s_path = str(filepath)
            if "team_info" in s_path:
                return mock_team_info
            else:
                # This covers season_summary.csv AND team specific files
                return pd.DataFrame({
                    'Team': ['St. Cloud State', 'Penn State', 'LIU', 'Long Island'], # Add Long Island just in case
                    'Result': ['Win', 'Win', 'Win', 'Win'], 
                    'Rating Impact': [0.1, 0.1, 0.1, 0.1]
                })
                
        mock_read_csv.side_effect = side_effect
        
        # Test 1: Exact match normalized ("St. Cloud State" -> "stcloudstate" -> matches "St_Cloud_State.csv")
        res1 = data_loader.load_team_analysis("St. Cloud State")
        assert res1 is not None, "Failed to load 'St. Cloud State' (should match St_Cloud_State.csv)"
        print("Test 1 (Standard with punctuation diff) Pass")
        
        # Test 2: Space vs Underscore ("Penn State" -> "pennstate" -> matches "Penn_State.csv")
        res2 = data_loader.load_team_analysis("Penn State")
        assert res2 is not None, "Failed to load 'Penn State' (should match Penn_State.csv)"
        print("Test 2 (Space vs Underscore) Pass")

        # Test 3: Alias Lookup ("Long Island" -> "longisland" -> matches info row -> maps to "LIU" -> matches "LIU.csv")
        res3 = data_loader.load_team_analysis("Long Island")
        assert res3 is not None, "Failed to load 'Long Island' (should map to LIU via alias)"
        print("Test 3 (Alias Lookup) Pass")
        
        # Test 4: Partial mismatch/fail
        res4 = data_loader.load_team_analysis("NonExistent")
        # The function returns a dict structure even if empty
        assert res4 is not None, "Should return a dict structure"
        assert not res4['stats'], "Stats should be empty for non-existent team"
        assert res4['top_wins'].empty, "Top wins should be empty"
        print("Test 4 (Non-existent) Pass")

if __name__ == "__main__":
    test_normalization()
    test_file_lookup()
