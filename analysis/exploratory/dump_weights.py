import pandas as pd
from src.rankings.npi import NPI

def dump_weights():
    # Mock data is not needed, we can just call the helper with a mock row
    # But NPI init requires a dataframe.
    df = pd.DataFrame({
        'HomeTeam': ['A'], 'AwayTeam': ['B'], 'Season': [20252026],
        'Result': [1.0], 'Notes': [''], 'Type': ['nc'], 'Date': ['2025-01-01'],
        'NeutralSite': [False], 'IsOT': [False]
    })
    npi = NPI(df)
    
    scenarios = [
        ("Home Win", True, 1.0, False),
        ("Home Loss", True, 0.0, False),
        ("Home Tie", True, 0.5, False),
        ("Away Win", False, 0.0, False), # Away Team perspective: Result 0.0 is Away Win
        ("Away Loss", False, 1.0, False),
        ("Away Tie", False, 0.5, False),
        ("Home OT Win", True, 1.0, True),
        ("Home OT Loss", True, 0.0, True),
        ("Away OT Win", False, 0.0, True),
        ("Away OT Loss", False, 1.0, True),
        ("Neutral Win", True, 1.0, False, True), # Neutral Site
        ("Neutral Loss", True, 0.0, False, True)
    ]
    
    print(f"{'Scenario':<15} | {'Pts':<6} | {'Wgt':<6} | {'Pct':<6}")
    print("-" * 45)
    
    for name, is_home, result, is_ot, *neutral in scenarios:
        is_neutral = neutral[0] if neutral else False
        
        row = {
            'HomeTeam': 'A', 'AwayTeam': 'B', 
            'Result': result, 
            'NeutralSite': is_neutral,
            'Type': 'nc', # Non-conference to ensure multipliers apply (if logical check was active)
            # Actually our code applies global multipliers now.
            'IsOT': is_ot
        }
        
        # calculate_game_points expects row and role
        role = 'Home' if is_home else 'Away'
        if not is_home:
             # If we are calculating for Away Team, we need to pass the row as is.
             # In NPI code: 
             # pts, wgt = npi._calculate_game_points(row, 'Away')
             pass

        pts, wgt = npi._calculate_game_points(row, role)
        pct = (pts/wgt)*100 if wgt > 0 else 0
        print(f"{name:<15} | {pts:<6.4f} | {wgt:<6.4f} | {pct:<6.2f}%")

if __name__ == "__main__":
    dump_weights()
