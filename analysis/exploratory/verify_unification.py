import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))
sys.path.append(str(root / "webpage"))

from webpage.utils.data_loader import get_canonical_name, get_logo_url

def test_naming():
    test_cases = [
        ("UMass Lowell", "UMass Lowell"),
        ("Mass.-Lowell", "UMass Lowell"),
        ("Minnesota-Duluth", "Minnesota Duluth"),
        ("Minnesota Duluth", "Minnesota Duluth"),
        ("St. Cloud State", "St. Cloud State"),
        ("St-Cloud-State", "St. Cloud State"),
        ("Penn State", "Penn State"),
        ("Penn_State", "Penn State"),
        ("Alaska-Anchorage", "Alaska Anchorage"),
        ("Alaska Anchorage", "Alaska Anchorage")
    ]
    
    print("--- Testing Canonical Mapping ---")
    for input_name, expected in test_cases:
        canonical = get_canonical_name(input_name)
        status = "PASS" if canonical == expected else f"FAIL (Got: {canonical})"
        print(f"Input: {input_name:20} -> Canonical: {canonical:20} | {status}")

    print("\n--- Testing Logo URL Lookup ---")
    logo_tests = ["UMass Lowell", "Mass.-Lowell", "Minnesota Duluth", "Minnesota-Duluth"]
    for team in logo_tests:
        url = get_logo_url(team)
        print(f"Team: {team:20} -> Logo: {url}")

if __name__ == "__main__":
    test_naming()
