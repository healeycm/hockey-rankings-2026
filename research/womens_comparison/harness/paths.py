# research/womens_comparison/harness/paths.py
"""
Safe output paths for the men's-vs-women's comparison research workspace,
following the same pattern as research/preseason/harness/paths.py,
research/roster_talent/harness/paths.py, research/npi_critique/harness/paths.py,
and research/lrmc_hockey/harness/paths.py. Every experiment writes results
and reports through research_path() so nothing can land in production
locations (output/, data/, reports/, config.yaml, site_build/) -- or in
another research workspace -- by accident.
"""
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]      # research/womens_comparison/
PROJECT_ROOT = WORKSPACE.parents[1]

RESULTS_DIR = WORKSPACE / "results"
REPORTS_DIR = WORKSPACE / "reports"


def research_path(*parts, mkdir_parent=True):
    """Resolves a path inside research/womens_comparison/ and raises if it
    escapes the workspace (e.g. via '..' or an absolute path)."""
    path = WORKSPACE.joinpath(*parts).resolve()
    if WORKSPACE != path and WORKSPACE not in path.parents:
        raise ValueError(f"Refusing to write outside the research workspace: {path}")
    if mkdir_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def results_path(experiment, filename):
    """research/womens_comparison/results/<experiment>/<filename>"""
    return research_path("results", experiment, filename)


def report_path(experiment):
    """research/womens_comparison/reports/<experiment>.md"""
    return research_path("reports", f"{experiment}.md")
