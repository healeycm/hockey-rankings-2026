"""
Guards the boundary between production code and every isolated research
workspace under research/ (research/preseason/, research/roster_talent/,
and any future one -- see each workspace's own README.md): production must
never import or reference research code, and each workspace's own
research_path() must refuse to write outside itself.
"""
import re
from pathlib import Path

import pytest

from research.preseason.harness.paths import WORKSPACE as PRESEASON_WORKSPACE, research_path as preseason_research_path
from research.roster_talent.harness.paths import WORKSPACE as ROSTER_TALENT_WORKSPACE, research_path as roster_talent_research_path
from research.npi_critique.harness.paths import WORKSPACE as NPI_CRITIQUE_WORKSPACE, research_path as npi_critique_research_path
from research.womens_comparison.harness.paths import WORKSPACE as WOMENS_COMPARISON_WORKSPACE, research_path as womens_comparison_research_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_DIRS = ["src", "scripts", "webpage"]
RESEARCH_REF = re.compile(r"^\s*(from|import)\s+research\b|['\"]research[/\\.]", re.MULTILINE)

WORKSPACES = [
    (PRESEASON_WORKSPACE, preseason_research_path),
    (ROSTER_TALENT_WORKSPACE, roster_talent_research_path),
    (NPI_CRITIQUE_WORKSPACE, npi_critique_research_path),
    (WOMENS_COMPARISON_WORKSPACE, womens_comparison_research_path),
]


def _production_py_files():
    for d in PRODUCTION_DIRS:
        yield from (PROJECT_ROOT / d).rglob("*.py")


def test_production_code_never_references_research():
    offenders = [
        str(p.relative_to(PROJECT_ROOT))
        for p in _production_py_files()
        if RESEARCH_REF.search(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not offenders, f"Production files reference a research workspace: {offenders}"


@pytest.mark.parametrize("workspace,research_path", WORKSPACES)
def test_research_path_stays_inside_workspace(workspace, research_path):
    p = research_path("results", "demo", "x.csv", mkdir_parent=False)
    assert workspace in p.parents


@pytest.mark.parametrize("workspace,research_path", WORKSPACES)
@pytest.mark.parametrize("escape", [
    ("..", "..", "output", "x.csv"),
    ("..", "..", "config.yaml"),
    ("..", "..", "data", "preseason", "polls.csv"),
])
def test_research_path_rejects_escapes(workspace, research_path, escape):
    with pytest.raises(ValueError):
        research_path(*escape, mkdir_parent=False)


def test_research_workspaces_do_not_overlap():
    """Each isolated exploration is a sibling, not nested inside another --
    otherwise one workspace's research_path() could silently write into
    another's."""
    all_workspaces = [PRESEASON_WORKSPACE, ROSTER_TALENT_WORKSPACE, NPI_CRITIQUE_WORKSPACE,
                      WOMENS_COMPARISON_WORKSPACE]
    for i, a in enumerate(all_workspaces):
        for b in all_workspaces[i + 1:]:
            assert a not in b.parents
            assert b not in a.parents
