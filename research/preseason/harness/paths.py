# research/preseason/harness/paths.py
"""
Safe output paths for preseason research. Every experiment writes results,
reports, and collected data through research_path() so nothing can land in
production locations (output/, data/processed/, data/preseason/, reports/,
config.yaml, site_build/) by accident.
"""
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]      # research/preseason/
PROJECT_ROOT = WORKSPACE.parents[1]

RESULTS_DIR = WORKSPACE / "results"
REPORTS_DIR = WORKSPACE / "reports"
DATA_DIR = WORKSPACE / "data"


def research_path(*parts, mkdir_parent=True):
    """Resolves a path inside research/preseason/ and raises if it escapes
    the workspace (e.g. via '..' or an absolute path)."""
    path = WORKSPACE.joinpath(*parts).resolve()
    if WORKSPACE != path and WORKSPACE not in path.parents:
        raise ValueError(f"Refusing to write outside the research workspace: {path}")
    if mkdir_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def results_path(experiment, filename):
    """research/preseason/results/<experiment>/<filename>"""
    return research_path("results", experiment, filename)


def report_path(experiment):
    """research/preseason/reports/<experiment>.md"""
    return research_path("reports", f"{experiment}.md")
