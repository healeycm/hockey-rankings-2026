# College Hockey Rankings

A from-scratch college hockey ranking system (NCAA Division I men's and
women's), built to answer a specific question: **do the metrics the NCAA
actually uses for tournament selection (NPI, KRACH-style PairWise
components) hold up against properly-validated statistical alternatives?**

This is a research project first and a website second. Every model in the
active roster earned its place through a backtest documented in
[`reports/`](reports/); every rejected idea is documented there too. See
[`reports/`](reports/) for the full evidence behind every claim below.

## Headline result

A least-squares (Massey) model, with two structural fixes over the
textbook version — fitted (not hardcoded) constants, and a rest/fatigue
adjustment fit from the schedule — beats the NCAA's own selection-committee
metrics (NPI, KRACH) on accuracy, Brier score, and log loss simultaneously,
across a 5-season / 20-split walk-forward backtest (8,371 pooled test
games), with every comparison statistically significant.
See [`reports/massey_calibration_results.md`](reports/massey_calibration_results.md)
and [`reports/massey_and_dixon_coles.md`](reports/massey_and_dixon_coles.md).

Several other ideas that looked promising were tested and **rejected** —
ensembling, empty-net-goal correction, time decay, Dixon-Coles, LRMC
self-consistent iterative fitting — with the negative evidence kept and
reported rather than discarded. See "Negative results" below.

## Model roster

Every model is implemented from its published specification and
independently validated against real data (not just internal
consistency). Currently active on the public site (`config.yaml`,
`active_models`):

| Model | What it is | Status |
|---|---|---|
| **Massey** | Least-squares ratings on goal differential, fitted home-ice + rest/fatigue terms, ridge-regularized | Best model overall — accuracy/Brier/LogLoss, 9/9 significant comparisons |
| **KRACH** | Bradley-Terry MLE (the model behind the NCAA committee's own PairWise tool) | Kept as the incumbent/committee-relevant baseline |
| **NPI** | From-scratch reimplementation of the NCAA's official Nutting Power Index | Kept as the incumbent/committee-relevant baseline |
| **ELO** | Sequential margin-of-victory-weighted rating, with a preseason carryover prior | Validated, best-calibrated model in the roster (ECE) |

Implemented, validated, and kept in the codebase but not currently
surfaced on the site (see each model's report for why):
HockeyBT (Davidson-Beaver Bradley-Terry), RPI, Colley, Keener, Glicko-2,
Dixon-Coles, Ensemble, Markov, and several LRMC variants (base LRMC and a
hockey-specific adaptation, HockeyLRMC). Every removed model is fully
functional — see `config.yaml`'s `active_models` comment for the specific
report backing each inclusion/exclusion decision.

## Negative results

Publishing what *didn't* work is as much a part of this project as what
did — it's the strongest evidence that the validated results aren't
cherry-picked:

- Ensembling multiple models does not improve on the best single model ([`reports/ensembling.md`](reports/ensembling.md))
- Real empty-net-goal data does not improve LRMC ([`reports/empty_net_result.md`](reports/empty_net_result.md))
- Time decay and manpower-margin adjustments to Massey are clean negatives ([`reports/massey_experiments_2026.md`](reports/massey_experiments_2026.md))
- Dixon-Coles ties (doesn't beat) the best model rather than improving on it ([`reports/massey_and_dixon_coles.md`](reports/massey_and_dixon_coles.md))
- Self-consistent iterative fitting for LRMC is a severe, decisive negative ([`reports/lrmc_experiments_2026.md`](reports/lrmc_experiments_2026.md))
- Keener's method and Glicko-2 both lose decisively to Massey ([`reports/keener_and_glicko2_results.md`](reports/keener_and_glicko2_results.md))

## Evaluation methodology

- **Walk-forward backtesting**: fit on games before a cutoff date, test on
  games after it. Standard protocol is 5 seasons (2021-22 through 2025-26)
  × 4 cutoffs (Jan 1 / Jan 15 / Feb 1 / Feb 15) = 20 independent splits,
  ~8,000+ pooled test games.
- **Metrics**: Accuracy, Brier score, log loss, Expected Calibration Error,
  Brier decomposition, and RPS — see [`reports/calibration_metrics.md`](reports/calibration_metrics.md).
- **Significance testing**: paired t-tests (Brier/LogLoss) and McNemar's
  test (accuracy) against each comparison's baseline, on every reported
  result.
- **Research isolation**: experimental work happens in `research/<topic>/`
  with its own report; nothing gets promoted into production (`src/`,
  `scripts/`, `webpage/`) without an explicit, separately-reviewed step.
  Enforced by [`tests/unit/test_research_isolation.py`](tests/unit/test_research_isolation.py).

## Repository layout

```
src/rankings/     ranking model implementations (one file per model)
src/data/         scraping (USCHO, CHN) and data processing
src/backtesting/  walk-forward backtest engine
src/validation/   metrics, significance testing, batch validation runs
src/site/         builds the static public site from model output
src/run_system.py single entry point: rankings + projections + sensitivity + simulation
webpage/          Dash app (team detail pages, live during the season)
config.yaml       season, active model roster, and every model's hyperparameters
                  (each active_models entry is commented with the report that justifies it)
reports/          every validated finding, positive and negative, with methodology
research/         active/ongoing experimental work, isolated from production
data/             scraped season data (raw + processed)
tests/unit/       the real automated test suite (145 tests)
analysis/exploratory/  one-off audit/debug/backtest scripts kept for provenance
                       (not part of the automated test suite)
scripts/          daily automation (scraping, rebuilding, publishing the site)
```

## Running it

```bash
pip install -r requirements.txt

# Full pipeline: rankings, projections, sensitivity analysis, simulation
python -m src.run_system --division men     # or --division women

# Rebuild the static public site from the latest output
python -m src.site.build_site

# Run the real test suite
pytest tests/unit -q

# Reproduce a specific backtest/finding from reports/
python -m analysis.exploratory.five_year_backtest
python -m analysis.exploratory.massey_backtest
# (each report names the exact command that reproduces its numbers)
```

`config.yaml` documents the current season, active model roster, and every
model's tunable parameters inline; `scripts/daily_update.py` is the
unattended entry point used during the season (scrape → reprocess →
rank/project/simulate → rebuild site → optionally publish).

## Author

Chris Healey, Merrimack College. Not affiliated with USCHO, the NCAA,
or any conference.
