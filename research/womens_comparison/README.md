# Men's vs. women's hockey comparison workspace

Isolated workspace for a systematic comparison of the models paper
(`paper/draft.md`) and the NPI critique (`paper/npi_critique_draft.md`)
findings against NCAA women's D-I hockey -- a structurally different field
(45 vs. 63 teams, ~26% more dispersed win percentages, a denser but
slightly less algebraically connected schedule graph) that the NCAA governs
with the **identical** NPI formula and dials. See [PLAN.md](PLAN.md) for the
full experiment design, pre-registered predictions, and the publication
decision rule (fold into the existing papers vs. a standalone paper vs.
report the divergences themselves -- decided by the results, not before
them).

**Nothing in here affects production**: the daily pipeline, `config.yaml`,
`output/`, or the public site.

## Isolation rules

Same rules as every other workspace under `research/`:

| Rule | Enforced by |
|---|---|
| `src/`, `scripts/`, and `webpage/` never import `research` | `tests/unit/test_research_isolation.py` |
| Research code may **read** from `src/` (models, loaders, metrics) but never edits it | Code review, plus the isolation test's scan for writes |
| Experiments write **only** under `research/womens_comparison/` (`results/`, `reports/`) | `harness/paths.py`: `research_path()` raises if a path resolves outside this workspace |
| This workspace never writes into another workspace's `data/`/`results/`/`reports/`, or vice versa | `test_research_workspaces_do_not_overlap` in the isolation test |
| `reports/` at the project root is for production-validated work; research reports stay here | Convention |

**One deliberate exception, documented rather than hidden:** the simulation
harness this workspace needs (`assign_true_strengths`,
`make_multiconference_schedule`, the three DGPs) already exists, fully
parameterized, at `research/npi_critique/harness/simulate.py` -- see PLAN.md's
Phase 4. Rather than fork or duplicate ~450 lines of simulation code,
experiments here **import it read-only** (`from
research.npi_critique.harness.simulate import ...`). This workspace never
writes into `research/npi_critique/`'s `results/`, `reports/`, or `data/` --
only reads its `harness/`, the same way any workspace here may read
(never edit) `src/`. If `research/npi_critique/` is ever archived or
removed, `simulate.py` should be promoted to a shared location rather than
this workspace silently breaking.

## Layout

```
research/womens_comparison/
  README.md            this file
  PLAN.md              experiment plan, pre-registered predictions, decision rule
  harness/             paths.py (safe-write helper); simulation code is
                        borrowed read-only from research/npi_critique/harness/
  experiments/         one module per experiment (w1_structural_comparison.py, ...)
  results/<name>/      raw CSV outputs per experiment
  reports/             one self-contained report per experiment
```

Run experiments from the project root as modules, e.g.
`python -m research.womens_comparison.experiments.w1_structural_comparison`.

Every model instantiation on women's data must happen inside a
`using_di_team_path(...)` block (`src/rankings/base_ranker.py`) -- see that
module's docstring for why the usual overlap-based safety check can't catch
a men's/women's mixup (most school names are shared between divisions, so
"wrong naming convention" doesn't fire). `analysis/exploratory/
womens_hockey_backtest.py` is the reference example already in production
code for this pattern.

## Promotion

This workspace supports research, not a production feature -- there is no
promotion path into `src/`. Findings that bear on the *production*
methodology page (`src/site/build_site.py`'s `MODEL_DOCS`) or a paper should
be written up as their own report and promoted as a separate, explicit step,
per PLAN.md's publication decision rule.
