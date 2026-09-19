# NPI-critique research workspace

Isolated workspace supporting the follow-up paper critiquing NPI
(`paper/npi_critique_paper_plan.md`). **Nothing in here affects
production**: the daily pipeline, `config.yaml`, `output/`, or the public
site. See [PLAN.md](PLAN.md) for the simulation study design.

## Isolation rules

Same rules as `research/preseason/` and `research/roster_talent/`:

| Rule | Enforced by |
|---|---|
| `src/`, `scripts/`, and `webpage/` never import `research` | `tests/unit/test_research_isolation.py` |
| Research code may **read** from `src/` (models, loaders, metrics) but never edits it | Code review, plus the isolation test's scan for writes |
| Experiments write **only** under `research/npi_critique/` (`results/`, `reports/`) | `harness/paths.py`: `research_path()` raises if a path resolves outside this workspace |
| `reports/` at the project root is for production-validated work; research reports stay here | Convention |

## Layout

```
research/npi_critique/
  PLAN.md              simulation study design
  README.md            this file
  harness/             simulation engine (paths.py, simulate.py)
  experiments/         one module per experiment
  reports/             one self-contained report per experiment
  results/<name>/      raw CSV outputs per experiment
```

Run experiments from the project root as modules, e.g.
`python -m research.npi_critique.experiments.e1_truth_recovery`.

## Promotion

This workspace supports a paper, not a production feature -- there is no
promotion path into `src/`. Findings that bear on the *production* NPI
critique (`reports/npi_critique.md`) or the production model roster
should be written up as their own root-level `reports/*.md` if and when
that's warranted, as a separate, explicit step.
