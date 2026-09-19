import pandas as pd
import numpy as np
from src.analysis.simulator import MonteCarloSimulator
from src.rankings.elo import ELO
from src.rankings.massey import Massey
from src.rankings.markov import Markov

# 1. Create dummy data
teams = [chr(65+i) for i in range(10)]
current_games_list = []
for i in range(20):
    t1, t2 = np.random.choice(teams, 2, replace=False)
    current_games_list.append({
        'HomeTeam': t1, 'AwayTeam': t2, 'Result': 0.5, 'HomeGoals': 2, 'AwayGoals': 2, 
        'NeutralSite': False, 'Date': pd.Timestamp('2026-01-01') + pd.Timedelta(days=i), 
        'Season': 2026
    })
current_games = pd.DataFrame(current_games_list)

upcoming_list = []
for i in range(5):
    t1, t2 = np.random.choice(teams, 2, replace=False)
    upcoming_list.append({'HomeTeam': t1, 'AwayTeam': t2, 'Season': 2026, 'NeutralSite': False})
upcoming = pd.DataFrame(upcoming_list)

def test_model(model_cls):
    print(f"\n--- Testing {model_cls.__name__} ---")
    sim = MonteCarloSimulator(
        model_class=model_cls,
        model_config={},
        current_games_df=current_games,
        upcoming_schedule_df=upcoming
    )
    try:
        sim.run(num_iterations=10)
        print(f"Success for {model_cls.__name__}")
        var_found = False
        for team, ranks in sim.rank_history.items():
            if len(set(ranks)) > 1:
                var_found = True
                print(f"  {team}: {set(ranks)}")
        if not var_found:
            print("  WARNING: No variation in ranks found across 10 iterations!")
    except Exception as e:
        print(f"FAILED for {model_cls.__name__}: {e}")

test_model(ELO)
test_model(Massey)
test_model(Markov)
