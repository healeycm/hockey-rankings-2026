# scripts/daily_update.py
"""
Single entry point for an unattended in-season run: scrape the latest
scores, reprocess data, and regenerate rankings/projections/sensitivity/
simulations for men's hockey (and women's, once its 2026-27 schedule is
being scraped — see the --women flag below). Designed to be idempotent and
safe to re-run (re-scraping/re-processing an already-current day just
reproduces the same output) — this is what scripts/register_task.ps1
schedules to run daily during the season.

Exit code is non-zero if ANY model failed for ANY division run, so Task
Scheduler (or any other caller) can detect a bad run instead of it going
unnoticed the way silent per-model exception-catching used to allow — see
reports/in_season_revamp_plan.md.

After every division succeeds, this also builds the static site
(src/site/build_site.py) and, unless --no-publish is passed, commits and
pushes site_build/ to the public GitHub Pages repo configured via
--site-repo (or the SITE_REPO_PATH env var). If ANY model failed, the site
is deliberately NOT rebuilt/published: the last good site stays live
instead of a run with missing/partial data overwriting it.

Usage:
    python -m scripts.daily_update                        # men's only, build + publish
    python -m scripts.daily_update --women                 # men's + women's
    python -m scripts.daily_update --women-only            # women's only
    python -m scripts.daily_update --no-publish            # build the site locally, don't push
    python -m scripts.daily_update --site-repo D:/path/to/hockey-rankings-site
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def run_division(division: str) -> bool:
    """Runs src.run_system for one division as a subprocess (keeps this
    script simple and gives each division's run a clean process/module
    state). Returns True if every model in that run succeeded."""
    print(f"\n{'=' * 60}\n[daily_update] Running division={division}\n{'=' * 60}")
    result = subprocess.run(
        [sys.executable, "-m", "src.run_system", "--division", division],
        cwd=ROOT_DIR,
    )
    if result.returncode != 0:
        print(f"[daily_update] run_system exited non-zero for division={division}.")
        return False

    manifest_path = ROOT_DIR / "output" / division_subdir(division) / "last_run.json" \
        if division == "women" else ROOT_DIR / "output" / "last_run.json"
    if not manifest_path.exists():
        print(f"[daily_update] WARNING: no manifest found at {manifest_path} — "
              f"treating as a failure since run_system.py should always write one.")
        return False

    with open(manifest_path) as f:
        manifest = json.load(f)
    failed = [m for m, r in manifest.get("models", {}).items() if r.get("status") == "error"]
    if failed:
        print(f"[daily_update] division={division}: models failed: {failed}")
        return False

    print(f"[daily_update] division={division}: all models succeeded.")
    return True


def division_subdir(division: str) -> str:
    return "women" if division == "women" else ""


def build_site(women: bool) -> bool:
    """Runs src.site.build_site into site_build/. Returns True on success."""
    print(f"\n{'=' * 60}\n[daily_update] Building static site\n{'=' * 60}")
    cmd = [sys.executable, "-m", "src.site.build_site"]
    if women:
        cmd.append("--women")
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print("[daily_update] Site build failed.")
        return False
    return True


def publish_site(site_repo: str) -> bool:
    """
    Copies site_build/ into a clone of the public Pages repo (site_repo)
    and pushes it. site_repo must already be a git clone with a remote and
    working credentials (gh auth login, or an SSH remote) -- this script
    only does the copy/commit/push, not first-time repo setup.
    """
    site_repo_path = Path(site_repo)
    if not site_repo_path.exists() or not (site_repo_path / ".git").exists():
        print(f"[daily_update] --site-repo '{site_repo}' doesn't look like a git repo "
              f"(no .git found) -- skipping publish. Clone the Pages repo there first.")
        return False

    print(f"\n{'=' * 60}\n[daily_update] Publishing to {site_repo_path}\n{'=' * 60}")
    src = ROOT_DIR / "site_build"
    if not src.exists():
        print("[daily_update] No site_build/ directory found -- did build_site run?")
        return False

    # Mirror site_build/ into the repo, removing anything the repo has that
    # the new build doesn't (a page for a team/model that's since dropped
    # out of active_models), except .git itself.
    for item in site_repo_path.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in src.iterdir():
        dest = site_repo_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    today = datetime.date.today().isoformat()
    commands = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", f"Update rankings ({today})", "--allow-empty-message"],
        ["git", "push"],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, cwd=site_repo_path)
        if result.returncode != 0 and cmd[1] != "commit":
            print(f"[daily_update] '{' '.join(cmd)}' failed.")
            return False
    print("[daily_update] Site published.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Unattended daily scrape+run for the ranking system.")
    parser.add_argument('--women', action='store_true', help="Also run the women's division after men's.")
    parser.add_argument('--women-only', action='store_true', help="Run only the women's division.")
    parser.add_argument('--no-publish', action='store_true', help="Build the site but don't push it.")
    parser.add_argument('--site-repo', type=str, default=os.environ.get("SITE_REPO_PATH"),
                         help="Path to a local clone of the public Pages repo. Also settable via "
                              "the SITE_REPO_PATH environment variable.")
    args = parser.parse_args()

    divisions = []
    if args.women_only:
        divisions = ["women"]
    else:
        divisions = ["men"]
        if args.women:
            divisions.append("women")

    print(f"[daily_update] {datetime.datetime.now().isoformat(timespec='seconds')} "
          f"starting run for: {divisions}")

    all_ok = True
    for division in divisions:
        ok = run_division(division)
        all_ok = all_ok and ok

    if not all_ok:
        print("\n[daily_update] One or more divisions had a model failure. "
              "Skipping site build/publish -- see last_run.json manifests above.")
        sys.exit(1)

    print("\n[daily_update] All divisions completed successfully.")

    site_ok = build_site(women=("women" in divisions))
    if not site_ok:
        print("[daily_update] Site build failed; not publishing.")
        sys.exit(1)

    if args.no_publish:
        print("[daily_update] --no-publish set; leaving site_build/ unpushed.")
        return

    if not args.site_repo:
        print("[daily_update] No --site-repo / SITE_REPO_PATH set; leaving site_build/ unpushed. "
              "Pass --site-repo <path to a clone of the public Pages repo> to publish automatically.")
        return

    if not publish_site(args.site_repo):
        sys.exit(1)


if __name__ == "__main__":
    main()
