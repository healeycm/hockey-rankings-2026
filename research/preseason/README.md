# Preseason research workspace

This is an isolated workspace for preseason-rating experiments. **Nothing in here affects production**: the daily pipeline, `config.yaml`, `output/`, and the public site. See [PLAN.md](PLAN.md) for the research plan.

## Isolation rules

| Rule | Enforced by |
|---|---|
| `src/`, `scripts/`, and `webpage/` never import `research` | `tests/unit/test_research_isolation.py`, which fails the test suite if any production file references `research` |
| Research code may **read** from `src/` (models, loaders, metrics) but never edits it. Model variants are subclasses or wrappers in `research/preseason/models/`. | Code review, plus the isolation test's scan for writes |
| Experiments write **only** under `research/preseason/` (`results/`, `reports/`, `data/`) | `harness/paths.py`: `research_path()` raises if a path resolves outside this workspace |
| Research reads `config.yaml` read-only for base model settings. Experiment settings live in each experiment's own module or config. | `harness/paths.py` has no writer for anything outside the workspace |
| Collected data (polls, rosters, player stats) goes in `research/preseason/data/`, **not** `data/preseason/`, which production's `priors.py` reads | Convention, plus the isolation test |
| `reports/` at the project root is for production-validated work. Research reports stay in `research/preseason/reports/`. | Convention |

## Layout

```
research/preseason/
  PLAN.md              research plan (phases, gates, evaluation protocol)
  README.md            this file
  harness/             shared experiment runner, metrics wrappers, safe paths
  models/              research-only model variants (continuous Elo, O/D Massey, KRACH+prior, ...)
  experiments/         one module per phase, e.g. p1_history_prior.py
  data/                collected inputs (polls, rosters): research-only
  results/NN_<name>/   raw CSV outputs per experiment
  reports/NN_<name>.md one self-contained report per experiment, plus INDEX.md
```

Run experiments from the project root as modules, e.g. `python -m research.preseason.experiments.p1_history_prior`.

## Promotion to production

A result that clears its gate is **not** adopted automatically. Promotion is a separate, explicit step that needs your approval:
1. Port the winning variant into `src/` with its own unit tests.
2. Change `config.yaml`, citing the research report.
3. Re-run the full test suite and a full `daily_update --no-publish` run.
4. Only then consider showing it on the site.
