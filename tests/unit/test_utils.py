import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from webpage.utils.data_loader import normalize_name

def test_normalize_name():
    assert normalize_name("Penn State") == "pennstate"
    assert normalize_name("Penn_State") == "pennstate"
    assert normalize_name("St. Cloud State") == "stcloudstate"
    assert normalize_name("St_Cloud_State") == "stcloudstate"
    assert normalize_name("MIAMI") == "miami"
    assert normalize_name(None) == ""
    assert normalize_name(123) == ""
