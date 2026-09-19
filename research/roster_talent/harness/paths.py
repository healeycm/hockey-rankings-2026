# research/roster_talent/harness/paths.py
"""
Safe output paths for the roster/draft/returning-production exploration.
Same pattern as research/preseason/harness/paths.py (a sibling, isolated
exploration, not a shared module -- see research/roster_talent/README.md)
-- every scraper/experiment writes through research_path() so nothing can
land outside this workspace (data/, output/, config.yaml, the production
src/ tree, or research/preseason/'s own workspace) by accident.
"""
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]  # research/roster_talent/
PROJECT_ROOT = WORKSPACE.parents[1]


def research_path(*parts, mkdir_parent=True):
    """Resolves a path inside research/roster_talent/ and raises if it
    escapes the workspace."""
    path = WORKSPACE.joinpath(*parts).resolve()
    if WORKSPACE != path and WORKSPACE not in path.parents:
        raise ValueError(f"Refusing to write outside the roster_talent research workspace: {path}")
    if mkdir_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path
