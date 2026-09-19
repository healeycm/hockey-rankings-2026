# src/generate_womens_rankings.py
"""
DEPRECATED — retired in favor of `python -m src.run_system --division women`.

This script originally generated rankings-only output for women's hockey as
a standalone path outside the main pipeline (see
reports/womens_hockey_import.md). As of the in-season revamp
(reports/in_season_revamp_plan.md), run_system.py is division-aware end to
end (rankings, projections, sensitivity analysis, AND simulations — this
script only ever did rankings), driven by config.yaml's
`models.active_models_women` list. Kept as a thin wrapper, not deleted
outright, in case anything still invokes it directly.
"""
import sys

if __name__ == "__main__":
    print("src/generate_womens_rankings.py is deprecated. Running "
          "'python -m src.run_system --division women' instead...\n")
    sys.argv = [sys.argv[0], "--division", "women"]
    from src.run_system import main
    main()
