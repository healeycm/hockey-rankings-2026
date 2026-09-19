"""
College Hockey Ranking System - Project Structure
=================================================

Recommended folder structure:

hockey_rankings/
│
├── data/                          # Flat file storage
│   ├── raw/
│   │   ├── games_2024_2025.csv    # Scraped game data
│   │   ├── games_2023_2024.csv    # Historical seasons
│   │   └── games_2022_2023.csv
│   ├── processed/
│   │   ├── rankings.csv           # Latest rankings (all systems)
│   │   ├── projections.csv        # Game projections
│   │   └── team_records.csv       # Win/loss records
│   ├── validation/
│   │   ├── pairwise_2023_2024.csv # Known rankings from websites
│   │   ├── krach_2023_2024.csv
│   │   └── elo_2023_2024.csv
│   └── teams/
│       └── team_info.csv          # Team metadata (conference, etc)
│
├── src/
│   ├── __init__.py
│   │
│   ├── data/                      # Data handling
│   │   ├── __init__.py
│   │   ├── scraper.py             # Your existing scraper
│   │   └── data_manager.py        # Load/save CSV operations with pandas
│   │
│   ├── models/                    # Team and season models
│   │   ├── __init__.py
│   │   ├── team.py                # Team class
│   │   └── season.py              # Season class
│   │
│   ├── rankings/                  # Ranking systems
│   │   ├── __init__.py
│   │   ├── base_ranker.py         # Abstract base class
│   │   ├── elo.py                 # ELO implementation
│   │   ├── krach.py               # KRACH implementation
│   │   ├── colley.py              # Colley implementation
│   │   ├── npi.py                 # NPI implementation
│   │   └── lrmc.py                # LRMC implementation
│   │
│   ├── projections/               # Win probability & projections
│   │   ├── __init__.py
│   │   ├── probability.py         # Win probability calculator
│   │   └── projector.py           # Season projector
│   │
│   ├── validation/                # Model validation
│   │   ├── __init__.py
│   │   ├── ranking_validator.py   # Compare to known rankings
│   │   └── metrics.py             # Correlation, RMSE, etc.
│   │
│   ├── backtesting/               # Historical performance testing
│   │   ├── __init__.py
│   │   ├── backtest_engine.py     # Run backtests on historical data
│   │   ├── prediction_scorer.py   # Score prediction accuracy
│   │   └── model_comparison.py    # Compare model performance
│   │
│   ├── reports/                   # Report generation
│   │   ├── __init__.py
│   │   ├── team_report.py         # Individual team reports
│   │   └── rankings_report.py     # Overall rankings
│   │
│   └── utils/
│       ├── __init__.py
│       └── config.py              # Configuration settings
│
├── docs/                          # Documentation
│   ├── models/                    # Model documentation
│   │   ├── README.md              # Overview of all models
│   │   ├── elo.md                 # ELO methodology & parameters
│   │   ├── krach.md               # KRACH methodology
│   │   ├── colley.md              # Colley methodology
│   │   ├── npi.md                 # NPI methodology
│   │   └── lrmc.md                # LRMC methodology & references
│   │
│   ├── research/                  # Research reports
│   │   ├── 01_validation_study.md # Model validation results
│   │   ├── 02_mov_investigation.md # Margin of victory analysis
│   │   ├── 03_home_ice_advantage.md # Home ice effects
│   │   ├── 04_model_comparison.md  # Comparative performance
│   │   └── figures/               # Charts and visualizations
│   │       ├── model_accuracy.png
│   │       ├── calibration_plots.png
│   │       └── correlation_heatmap.png
│   │
│   ├── api/                       # Code documentation
│   │   ├── data_structures.md    # Data models and schemas
│   │   ├── rankers.md            # Ranker API reference
│   │   └── backtesting.md        # Backtesting framework
│   │
│   └── user_guide/               # Usage documentation
│       ├── quickstart.md
│       ├── updating_rankings.md
│       └── adding_models.md
│
├── notebooks/                     # Jupyter notebooks for analysis
│   ├── exploratory/
│   │   ├── data_exploration.ipynb
│   │   └── initial_model_tests.ipynb
│   └── research/
│       ├── mov_analysis.ipynb    # MOV investigation notebook
│       ├── model_comparison.ipynb # Model comparison analysis
│       └── parameter_tuning.ipynb # Hyperparameter exploration
│
├── papers/                        # Academic outputs
│   ├── drafts/
│   │   └── hockey_ranking_comparison.tex
│   ├── figures/
│   │   └── paper_figures/
│   ├── references.bib
│   └── README.md                 # Paper status and notes
│
├── scripts/                       # Execution scripts
│   ├── update_rankings.py         # Main update script
│   ├── generate_reports.py        # Generate all reports
│   ├── validate_rankings.py       # Compare rankings to known sources
│   ├── backtest_models.py         # Historical performance testing
│   └── backfill_season.py         # Historical data processing
│
├── tests/                         # Unit tests
│   ├── __init__.py
│   ├── test_rankings.py
│   ├── test_projections.py
│   ├── test_validation.py
│   └── test_backtesting.py
│
├── output/                        # Generated reports
│   ├── rankings/                 # Public-facing rankings
│   ├── teams/                    # Team pages
│   ├── projections/              # Season projections
│   ├── validation/               # Validation reports
│   └── backtest/                 # Backtest results
│
├── requirements.txt
├── README.md
└── .gitignore


DEPENDENCIES (requirements.txt):
================================

pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0  # For linear algebra in ranking systems
matplotlib>=3.7.0  # For validation/backtest visualizations
seaborn>=0.12.0  # For prettier plots
jupyter>=1.0.0  # For research notebooks
nbconvert>=7.0.0  # For converting notebooks to reports


Key Classes and Their Responsibilities:
=======================================

1. DATA LAYER
-------------

CSV Schema for games_2025_2026.csv:
    Day,Date,Time,Visitor_Team,Visitor_Score,Location_Indicator,
Home_Team,Home_Score,OT_Info,Notes,Type,
s_Final,Is_Neutral,Is_Exhibition,Is_OT,Season

class DataManager:
    '''Handles all CSV I/O operations using pandas'''
    Methods:
    - load_games(filepath) -> pd.DataFrame
    - save_games(df: pd.DataFrame, filepath)
    - load_rankings(filepath) -> pd.DataFrame
    - save_rankings(df: pd.DataFrame, filepath)
    - load_projections(filepath) -> pd.DataFrame
    - save_projections(df: pd.DataFrame, filepath)
    - load_team_info(filepath) -> pd.DataFrame


2. MODEL LAYER
--------------

class Team:
    '''Represents a team with stats and metadata'''
    - name: str
    - conference: str
    - games_df: pd.DataFrame  # subset of games involving this team
    - rankings: dict  # {system_name: rating}
    
    Methods:
    - record() -> Tuple[int, int, int]  # W, L, T
    - win_percentage() -> float
    - get_ranking(system: str) -> float
    - completed_games() -> pd.DataFrame
    - remaining_games() -> pd.DataFrame

class Season:
    '''Manages the entire season's data using DataFrames'''
    - year: str
    - teams: Dict[str, Team]
    - games_df: pd.DataFrame  # all games
    - team_info_df: pd.DataFrame  # team metadata
    
    Methods:
    - load_from_csv(games_path: str, team_info_path: str)
    - get_team(name: str) -> Team
    - get_completed_games() -> pd.DataFrame
    - get_remaining_games() -> pd.DataFrame
    - get_standings() -> pd.DataFrame


3. RANKING LAYER
----------------

class BaseRanker(ABC):
    '''Abstract base class for all ranking systems'''
    - season: Season
    - ratings_df: pd.DataFrame  # columns: team, rating
    - include_margin: bool = False  # For MOV-based models
    
    @abstractmethod
    - calculate_ratings() -> pd.DataFrame
    
    Methods:
    - rank_teams() -> pd.DataFrame  # sorted by rating
    - get_rating(team: str) -> float
    - get_rankings_df() -> pd.DataFrame
    - reset() -> None  # Reset ratings to initial state

class ELORanker(BaseRanker):
    - k_factor: float
    - home_advantage: float
    - margin_multiplier: float = 0.0  # Optional MOV component
    
    Methods:
    - calculate_ratings() -> pd.DataFrame
    - expected_score(rating_a, rating_b) -> float
    - process_games() -> pd.DataFrame  # returns df with ELO evolution
    - get_rating_history() -> pd.DataFrame  # ELO over time for all teams

class KRACHRanker(BaseRanker):
    Methods:
    - calculate_ratings() -> pd.DataFrame
    - build_win_matrix() -> pd.DataFrame
    - solve_system() -> pd.DataFrame

class MarginAwareRanker(BaseRanker):
    '''Base class for rankings that use margin of victory'''
    - margin_cap: float = None  # Optional cap on MOV influence
    
    Methods:
    - normalize_margin(margin: int) -> float
    - weight_by_margin(margin: int) -> float

# Similar structure for Colley, NPI, LRMC


4. PROJECTION LAYER
-------------------

class WinProbabilityCalculator:
    '''Calculates win probabilities based on rankings'''
    - ratings_df: pd.DataFrame
    
    Methods:
    - calculate_probability(team_a: str, team_b: str, 
                           home_advantage: float = 0) -> float
    - calculate_all_remaining(games_df: pd.DataFrame) -> pd.DataFrame
        # Returns df with added columns: home_win_prob, away_win_prob

class SeasonProjector:
    '''Projects remaining games and final records'''
    - season: Season
    - probability_calculator: WinProbabilityCalculator
    
    Methods:
    - project_remaining_games() -> pd.DataFrame
        # Returns df with: team, current_record, projected_wins, 
        # projected_losses, expected_final_record
    - project_team_games(team: str) -> pd.DataFrame
        # Game-by-game breakdown for one team
    - simulate_season(n_simulations: int = 1000) -> pd.DataFrame
        # Monte Carlo simulation results


5. REPORT LAYER
---------------

class TeamReport:
    '''Generates individual team reports'''
    - team: Team
    - projections_df: pd.DataFrame
    
    Methods:
    - generate_html() -> str
    - to_dataframe() -> pd.DataFrame
    - get_game_by_game_breakdown() -> pd.DataFrame

class RankingsReport:
    '''Generates overall rankings page'''
    - season: Season
    - all_rankings_df: pd.DataFrame  # merged rankings from all systems
    
    Methods:
    - generate_html() -> str
    - create_comparison_table() -> pd.DataFrame
    - export_to_csv(filepath: str)


6. VALIDATION LAYER
-------------------

class RankingValidator:
    '''Compare calculated rankings to known/published rankings'''
    - calculated_rankings_df: pd.DataFrame
    - known_rankings_df: pd.DataFrame
    
    Methods:
    - load_known_rankings(filepath: str) -> pd.DataFrame
    - compare_rankings() -> dict
        # Returns: correlation, RMSE, rank_difference_stats
    - generate_comparison_report() -> pd.DataFrame
        # Side-by-side comparison with differences
    - plot_correlation() -> None  # Scatter plot

class ValidationMetrics:
    '''Statistical metrics for comparing rankings'''
    Methods:
    - spearman_correlation(rank1: pd.Series, rank2: pd.Series) -> float
    - kendall_tau(rank1: pd.Series, rank2: pd.Series) -> float
    - rmse(values1: pd.Series, values2: pd.Series) -> float
    - mean_rank_difference(rank1: pd.Series, rank2: pd.Series) -> float
    - top_n_agreement(rank1: pd.Series, rank2: pd.Series, n: int) -> float


7. BACKTESTING LAYER
--------------------

class BacktestEngine:
    '''Run historical backtests on ranking models'''
    - seasons: List[str]  # e.g., ['2022-2023', '2023-2024']
    - rankers: Dict[str, BaseRanker]
    
    Methods:
    - run_backtest(season: str, train_pct: float = 0.7) -> pd.DataFrame
        # Split season, train on first X%, test on remainder
    - run_all_seasons() -> pd.DataFrame
        # Returns aggregated results across all seasons
    - compare_models() -> pd.DataFrame
        # Compare all rankers on same data

class PredictionScorer:
    '''Score the accuracy of predictions'''
    Methods:
    - score_predictions(predictions_df: pd.DataFrame, 
                       actual_results_df: pd.DataFrame) -> dict
        # Returns: accuracy, log_loss, brier_score, calibration
    - calculate_accuracy(predictions: pd.Series, 
                        actuals: pd.Series) -> float
    - calculate_log_loss(probabilities: pd.Series, 
                         actuals: pd.Series) -> float
    - calculate_brier_score(probabilities: pd.Series, 
                            actuals: pd.Series) -> float
    - get_calibration_curve(probabilities: pd.Series, 
                           actuals: pd.Series) -> pd.DataFrame

class ModelComparison:
    '''Compare performance of different ranking models'''
    - backtest_results_df: pd.DataFrame
    
    Methods:
    - summarize_performance() -> pd.DataFrame
        # Aggregate stats for each model
    - compare_by_metric(metric: str) -> pd.DataFrame
        # Sort models by specific metric
    - plot_performance_comparison() -> None
    - generate_comparison_report() -> str  # HTML report


USAGE WORKFLOW:
==============

# scripts/validate_rankings.py
"""
Validate that your ranking implementation matches known published rankings
"""
import pandas as pd
from src.data.data_manager import DataManager
from src.models.season import Season
from src.rankings.krach import KRACHRanker
from src.validation.ranking_validator import RankingValidator
from src.validation.metrics import ValidationMetrics

def main():
    # 1. Load historical season
    dm = DataManager()
    games_df = dm.load_games('data/raw/games_2023_2024.csv')
    
    # 2. Calculate rankings
    season = Season(year='2023-2024')
    season.load_from_csv(games_df, None)
    
    ranker = KRACHRanker(season)
    calculated_rankings = ranker.calculate_ratings()
    
    # 3. Load known rankings from website
    known_rankings = pd.read_csv('data/validation/krach_2023_2024.csv')
    
    # 4. Compare
    validator = RankingValidator(calculated_rankings, known_rankings)
    comparison = validator.compare_rankings()
    
    print("Validation Results:")
    print(f"Spearman Correlation: {comparison['spearman']:.4f}")
    print(f"RMSE: {comparison['rmse']:.4f}")
    print(f"Mean Rank Difference: {comparison['mean_rank_diff']:.2f}")
    print(f"Top 10 Agreement: {comparison['top_10_agreement']:.1%}")
    
    # 5. Show detailed comparison
    comparison_df = validator.generate_comparison_report()
    print("\nTop 10 Comparison:")
    print(comparison_df.head(10))
    
    # Save for inspection
    comparison_df.to_csv('output/validation/krach_comparison.csv', index=False)

if __name__ == '__main__':
    main()


# scripts/backtest_models.py
"""
Run backtests to compare model performance on historical data
"""
import pandas as pd
from src.data.data_manager import DataManager
from src.models.season import Season
from src.rankings.elo import ELORanker
from src.rankings.krach import KRACHRanker
from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.prediction_scorer import PredictionScorer
from src.backtesting.model_comparison import ModelComparison

def main():
    # 1. Define models to test
    models_to_test = {
        'ELO_Standard': lambda s: ELORanker(s, k_factor=32, margin_multiplier=0.0),
        'ELO_MOV_Low': lambda s: ELORanker(s, k_factor=32, margin_multiplier=0.5),
        'ELO_MOV_High': lambda s: ELORanker(s, k_factor=32, margin_multiplier=1.0),
        'KRACH': lambda s: KRACHRanker(s),
        # Add more models...
    }
    
    # 2. Run backtest on multiple seasons
    engine = BacktestEngine(
        seasons=['2021-2022', '2022-2023', '2023-2024'],
        model_factories=models_to_test
    )
    
    # Run with 70/30 train/test split for each season
    results_df = engine.run_all_seasons(train_pct=0.7)
    
    # 3. Analyze results
    comparison = ModelComparison(results_df)
    summary = comparison.summarize_performance()
    
    print("Model Performance Summary:")
    print(summary.to_string(index=False))
    
    # 4. Save detailed results
    results_df.to_csv('data/backtest_results/detailed_results.csv', index=False)
    summary.to_csv('data/backtest_results/model_summary.csv', index=False)
    
    # 5. Generate HTML report
    comparison.generate_comparison_report('output/backtest/model_comparison.html')
    
    # 6. Find best model
    best_model = summary.loc[summary['log_loss'].idxmin()]
    print(f"\nBest Model by Log Loss: {best_model['model']}")
    print(f"  Accuracy: {best_model['accuracy']:.1%}")
    print(f"  Log Loss: {best_model['log_loss']:.4f}")
    print(f"  Brier Score: {best_model['brier_score']:.4f}")

if __name__ == '__main__':
    main()


# scripts/update_rankings.py
import pandas as pd
from src.data.data_manager import DataManager
from src.models.season import Season
from src.rankings.elo import ELORanker
from src.rankings.krach import KRACHRanker
from src.reports.rankings_report import RankingsReport

def main():
    # 1. Load data
    dm = DataManager()
    games_df = dm.load_games('data/raw/games_2024_2025.csv')
    team_info_df = dm.load_team_info('data/teams/team_info.csv')
    
    # 2. Build season model
    season = Season(year='2024-2025')
    season.load_from_csv(games_df, team_info_df)
    
    # 3. Calculate rankings (each returns a DataFrame)
    rankers = {
        'ELO': ELORanker(season, k_factor=32),
        'KRACH': KRACHRanker(season),
        'Colley': ColleyRanker(season),
        # ... add more
    }
    
    ranking_dfs = {}
    for name, ranker in rankers.items():
        ranking_dfs[name] = ranker.calculate_ratings()
    
    # 4. Merge all rankings into one DataFrame
    # Result: team | ELO | KRACH | Colley | NPI | LRMC
    all_rankings_df = pd.DataFrame({'team': season.teams.keys()})
    for name, df in ranking_dfs.items():
        all_rankings_df = all_rankings_df.merge(
            df[['team', 'rating']].rename(columns={'rating': name}),
            on='team',
            how='left'
        )
    
    # 5. Generate projections
    from src.projections.projector import SeasonProjector
    from src.projections.probability import WinProbabilityCalculator
    
    prob_calc = WinProbabilityCalculator(ranking_dfs['ELO'])
    projector = SeasonProjector(season, prob_calc)
    projections_df = projector.project_remaining_games()
    
    # 6. Save results to CSV
    dm.save_rankings(all_rankings_df, 'data/processed/rankings.csv')
    dm.save_projections(projections_df, 'data/processed/projections.csv')
    
    # 7. Generate reports
    report = RankingsReport(season, all_rankings_df)
    report.generate_html('output/rankings/index.html')
    
    print("Rankings updated successfully!")
    print(f"Teams ranked: {len(all_rankings_df)}")
    print(f"\nTop 5 by ELO:")
    print(all_rankings_df.nlargest(5, 'ELO')[['team', 'ELO']])

if __name__ == '__main__':
    main()


CSV FILE FORMATS:
=================

# data/raw/games_2024_2025.csv
date,home_team,away_team,home_score,away_score,is_conference,is_completed,venue
2024-10-05,Boston College,Michigan,3,2,False,True,Conte Forum
2024-10-12,Minnesota,Wisconsin,,,True,False,3M Arena
...

# data/processed/rankings.csv
team,ELO,KRACH,Colley,NPI,LRMC
Boston College,1650.5,0.875,0.823,0.892,1.245
Minnesota,1645.2,0.868,0.815,0.885,1.238
...

# data/processed/projections.csv
team,wins,losses,ties,projected_wins,projected_losses,projected_ties,win_prob_remaining
Boston College,8,2,0,5.3,2.1,0.6,0.715
Minnesota,7,3,0,4.8,2.8,0.4,0.632
...

# data/teams/team_info.csv
team,conference,division,arena,location
Boston College,Hockey East,,,Chestnut Hill MA
Minnesota,Big Ten,,,Minneapolis MN
...

# data/validation/krach_2023_2024.csv (from published source)
team,krach_rating,rank
Boston College,0.892,1
Denver,0.875,2
...

# backtesting output format
# data/backtest_results/model_performance_2023_2024.csv
model,season,accuracy,log_loss,brier_score,games_predicted
ELO,2023-2024,0.672,0.598,0.215,450
ELO_MOV,2023-2024,0.685,0.582,0.208,450
KRACH,2023-2024,0.664,0.612,0.223,450
...


BENEFITS OF THIS STRUCTURE:
===========================

1. Easy to add new ranking systems - just inherit from BaseRanker
2. Clear separation of concerns - data, models, rankings, projections, reports
3. Simple to update - run one script after scraping new games
4. Testable - each component can be unit tested
5. Extensible - easy to add new features without refactoring
6. Reusable - components can be used independently
7. **Validation-ready** - Compare your rankings to known sources
8. **Backtest-friendly** - Test models on historical data with train/test splits
9. **MOV-flexible** - Easy to add/remove margin of victory components
10. **Performance comparison** - Systematically compare models with metrics

NEXT STEPS:
===========

**Phase 1: Core Infrastructure**
1. Start with Game, Team, and Season classes
2. Implement DataManager for CSV operations
3. Build BaseRanker abstract class

**Phase 2: First Ranking System**
4. Implement one ranking system (e.g., KRACH) to test the pipeline
5. Use validate_rankings.py to compare against published rankings
6. Iterate until your implementation matches

**Phase 3: Additional Models**
7. Add more ranking systems (ELO, Colley, etc.)
8. Create variants with margin of victory
9. Validate each against known sources

**Phase 4: Backtesting**
10. Implement backtesting framework
11. Run historical tests on 2-3 past seasons
12. Compare models using accuracy, log loss, Brier score
13. Identify best models for predictions

**Phase 5: Projections & Reports**
14. Add projections layer using best model(s)
15. Create basic reports
16. Polish reports with HTML/CSS for FiveThirtyEight style

**Recommended Order for Rankings:**
1. KRACH - easiest to validate (widely published)
2. ELO - popular, many variants to test
3. Colley - good baseline
4. RPI/NPI - NCAA standard
5. LRMC - more complex

**Key Validation Sources:**
- USCHO.com (publishes Pairwise, RPI)
- College Hockey News (KRACH)
- CHN Power Rankings
- NCAA official rankings


DOCUMENTATION STRUCTURE:
========================

1. MODEL DOCUMENTATION (docs/models/)
------------------------------------

Each model gets its own markdown file with:

**Template Structure (docs/models/lrmc.md):**

```markdown
# LRMC (Logistic Regression Markov Chain)

## Overview
Brief description of the method and its purpose.

## Methodology
### Mathematical Foundation
- Equations and formulas
- Step-by-step algorithm
- Key assumptions

### Implementation Details
- Parameters and their meanings
- Default values and reasoning
- Computational complexity

## References
- Original paper: Kvam & Sokol (2006)
- Related work
- Online resources

## Usage
```python
from src.rankings.lrmc import LRMCRanker

ranker = LRMCRanker(season, home_advantage_mode='logistic')
rankings = ranker.calculate_ratings()
```

## Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| home_advantage_mode | str | 'logistic' | How to model home advantage |

## Validation Results
Link to validation study: [See validation report](../research/01_validation_study.md#lrmc)

## Known Issues & Limitations
- Requires sufficient games for convergence
- Sensitive to early-season data
```

**Keep these updated as you:**
- Tune parameters
- Fix bugs
- Discover edge cases
- Find better implementations


2. RESEARCH REPORTS (docs/research/)
------------------------------------

These are formal write-ups of your investigations:

**Template (docs/research/02_mov_investigation.md):**

```markdown
# Margin of Victory Analysis in College Hockey Rankings

**Author:** [Your Name]
**Date:** December 2024
**Status:** Draft

## Abstract
Brief summary of the investigation and key findings.

## Research Question
Does incorporating margin of victory improve prediction accuracy 
for college hockey game outcomes?

## Methodology
### Data
- Seasons analyzed: 2021-2022, 2022-2023, 2023-2024
- Total games: 1,234
- Teams: 60

### Models Compared
1. ELO (standard, win/loss only)
2. ELO-MOV (margin multiplier = 0.5)
3. ELO-MOV (margin multiplier = 1.0)
4. LRMC (inherently MOV-based)
5. KRACH (baseline, win/loss only)

### Evaluation Metrics
- Prediction accuracy
- Log loss
- Brier score
- Calibration curves

## Results

### Table 1: Model Performance Summary
| Model | Accuracy | Log Loss | Brier Score |
|-------|----------|----------|-------------|
| ELO Standard | 65.2% | 0.612 | 0.223 |
| ELO-MOV (0.5) | 68.5% | 0.582 | 0.208 |
| ELO-MOV (1.0) | 67.8% | 0.591 | 0.215 |
| LRMC | 69.1% | 0.575 | 0.205 |
| KRACH | 64.8% | 0.625 | 0.230 |

### Figure 1: Model Accuracy by Season
![Accuracy comparison](figures/model_accuracy.png)

### Key Findings
1. MOV-based methods outperform win/loss methods by ~3-4%
2. LRMC shows best overall performance
3. Optimal margin multiplier for ELO appears to be ~0.5
4. Early season predictions benefit most from MOV

## Discussion
### Why MOV Helps in Hockey
- Close games (1-goal) are often "coin flips"
- Blowouts indicate true strength difference
- Home ice advantage more visible in margins

### Limitations
- Sample size limited to 3 seasons
- Conference strength variations not fully accounted for
- Overtime/shootout games treated same as regulation

## Conclusions
Incorporating margin of victory significantly improves prediction 
accuracy for college hockey. Recommend using ELO-MOV (multiplier=0.5) 
or LRMC for production rankings.

## Future Work
- Test on tournament predictions specifically
- Investigate non-linear MOV scaling
- Compare to neural network approaches

## References
1. Kvam & Sokol (2006). "A logistic regression/Markov chain model..."
2. Your validation study
3. Related sports analytics papers

## Appendix
### A. Data Processing
Code snippets and data cleaning steps

### B. Statistical Tests
Detailed statistical comparisons

### C. Reproducibility
```bash
python scripts/backtest_models.py --seasons 2021-2022 2022-2023 2023-2024
jupyter notebook notebooks/research/mov_analysis.ipynb
```
```


3. JUPYTER NOTEBOOKS (notebooks/)
---------------------------------

**Two types:**

**Exploratory (notebooks/exploratory/):**
- Quick investigations
- Data quality checks
- Informal testing
- Don't need to be polished

**Research (notebooks/research/):**
- Clean, well-documented
- Reproducible analyses
- Publication-quality figures
- Can be converted to reports

**Example: notebooks/research/mov_analysis.ipynb**
```python
# Cell 1: Setup
import pandas as pd
import matplotlib.pyplot as plt
from src.backtesting.backtest_engine import BacktestEngine

# Cell 2: Load Results
results = pd.read_csv('data/backtest_results/model_performance.csv')

# Cell 3: Visualize
fig, ax = plt.subplots(figsize=(10, 6))
results.groupby('model')['accuracy'].mean().plot(kind='bar', ax=ax)
plt.title('Model Accuracy Comparison')
plt.savefig('../docs/research/figures/model_accuracy.png', dpi=300)

# Cell 4: Statistical Tests
from scipy.stats import ttest_ind
...
```

**Convert to report:**
```bash
jupyter nbconvert --to markdown notebooks/research/mov_analysis.ipynb \
  --output ../../docs/research/02_mov_investigation_appendix.md
```


4. ACADEMIC PAPERS (papers/)
----------------------------

If you want to publish, keep drafts here:

**Structure:**
```
papers/
├── drafts/
│   └── hockey_ranking_comparison.tex
├── figures/
│   └── paper_figures/          # High-res figures for publication
│       ├── fig1_model_comparison.pdf
│       └── fig2_calibration.pdf
├── references.bib
└── README.md
```

**papers/README.md tracks progress:**
```markdown
# Academic Papers

## Active Papers

### 1. "Comparative Analysis of Ranking Systems in College Hockey"
- **Status:** Draft
- **Target:** Journal of Quantitative Analysis in Sports
- **File:** drafts/hockey_ranking_comparison.tex
- **Key Results:** MOV-based methods outperform by 3-4%
- **Next Steps:** Add tournament prediction section

## Data/Code References
All figures can be regenerated with:
```bash
python scripts/generate_paper_figures.py --paper hockey_ranking
```
```


5. API DOCUMENTATION (docs/api/)
--------------------------------

Technical reference for other developers:

**docs/api/rankers.md:**
```markdown
# Ranker API Reference

## BaseRanker

Abstract base class for all ranking systems.

### Methods

#### `calculate_ratings() -> pd.DataFrame`
Calculates ratings for all teams.

**Returns:**
- DataFrame with columns: `['team', 'rating']`

**Example:**
```python
ranker = KRACHRanker(season)
rankings = ranker.calculate_ratings()
```

#### `rank_teams() -> pd.DataFrame`
Returns rankings sorted by rating (highest first).
...
```


WORKFLOW FOR ACADEMIC DOCUMENTATION:
===================================

1. **During Development:**
   - Quick notes in exploratory notebooks
   - Document parameters in code comments
   - Keep informal notes on findings

2. **After Getting Results:**
   - Clean up analysis notebook
   - Move to research notebooks
   - Generate figures and save to docs/research/figures/

3. **Write Research Report:**
   - Create markdown file in docs/research/
   - Include tables, figures, methodology
   - Link to reproducible code/notebooks

4. **If Publishing:**
   - Move to papers/ directory
   - Write formal LaTeX paper
   - Reference your research reports
   - Include reproducibility instructions

5. **Keep Model Docs Updated:**
   - When you tune parameters, update docs/models/
   - When validation results change, update references
   - Keep these as "living documents"
"""