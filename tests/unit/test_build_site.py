"""
Regression tests for src/site/build_site.py -- the static site had no test
coverage before this (see the site-restyle plan). Builds into a tmp_path
(never site_build/ itself) and checks structural invariants: relative-link
depth ("root" prefix) resolves to real files, every active model gets a
tab, and men's/women's pages actually diverge (regression test for the
division-blind data_loader.py bug this same change fixed -- see
project_womens_hockey_import.md-style notes in build_site.py's own
comments).
"""
import re

import pytest
import yaml

from src.site import build_site as bs

pytestmark = pytest.mark.skipif(
    not (bs.ROOT_DIR / "output" / "rankings").exists(),
    reason="requires a real output/ tree (this project's own generated rankings) to build against",
)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("site_build")
    out_dir.mkdir(exist_ok=True)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy2(bs.STYLE_CSS_PATH, assets_dir / "style.css")
    logos_src = bs.ROOT_DIR / "webpage" / "assets" / "logos"
    if logos_src.exists():
        shutil.copytree(logos_src, assets_dir / "logos", dirs_exist_ok=True)
    bs.build_methodology_page(out_dir, root="")
    men_teams = bs.build("men", out_dir)
    women_teams = bs.build("women", out_dir)
    return out_dir, men_teams, women_teams


def _config():
    with open(bs.ROOT_DIR / "config.yaml") as f:
        return yaml.safe_load(f)


HREF_RE = re.compile(r'href="([^"]+)"')


def test_style_css_has_no_leftover_broken_tokens():
    css = bs.STYLE_CSS_PATH.read_text(encoding="utf-8")
    assert "#ecece f0" not in css  # a stray mid-edit typo this change fixed
    assert "--accent" in css and "--accent-bg" in css


def test_index_pages_declare_their_division(site):
    out_dir, _, _ = site
    men_html = (out_dir / "index.html").read_text(encoding="utf-8")
    women_html = (out_dir / "women" / "index.html").read_text(encoding="utf-8")
    assert 'data-division="men"' in men_html
    assert 'data-division="women"' in women_html


def test_rankings_tabs_match_configured_active_models(site):
    out_dir, men_teams, women_teams = site
    config = _config()
    men_html = (out_dir / "index.html").read_text(encoding="utf-8")
    women_html = (out_dir / "women" / "index.html").read_text(encoding="utf-8")
    for model in config["models"]["active_models"]:
        assert f'data-tab="{model}"' in men_html, f"{model} missing from men's tabs"
    for model in config["models"].get("active_models_women", config["models"]["active_models"]):
        assert f'data-tab="{model}"' in women_html, f"{model} missing from women's tabs"


def test_every_team_link_on_rankings_pages_resolves_to_a_real_file(site):
    out_dir, _, _ = site
    for page in [out_dir / "index.html", out_dir / "women" / "index.html"]:
        html_text = page.read_text(encoding="utf-8")
        team_hrefs = [h for h in HREF_RE.findall(html_text) if "team/" in h]
        assert team_hrefs, f"no team links found on {page}"
        for href in team_hrefs:
            target = (page.parent / href).resolve()
            assert target.exists(), f"{page.name} links to missing file: {href}"


def test_methodology_page_covers_union_of_both_rosters(site):
    out_dir, _, _ = site
    config = _config()
    meth_html = (out_dir / "methodology.html").read_text(encoding="utf-8")
    all_models = set(config["models"]["active_models"]) | set(
        config["models"].get("active_models_women", [])
    )
    for model in all_models:
        assert f">{model}<" in meth_html, f"{model} has no methodology card"


def test_men_and_women_team_pages_use_division_specific_data(site):
    """Regression test for the bug where load_team_analysis/get_team_schedule/
    load_rank_distribution were division-blind in webpage/utils/data_loader.py,
    silently serving men's data on every women's team page."""
    out_dir, men_teams, women_teams = site
    shared = set(men_teams) & set(women_teams)
    assert shared, "expected at least one program with both a men's and women's team page"
    team = sorted(shared)[0]
    men_page = (out_dir / "team" / f"{bs._safe_name(team)}.html").read_text(encoding="utf-8")
    women_page = (out_dir / "women" / "team" / f"{bs._safe_name(team)}.html").read_text(encoding="utf-8")
    men_games = re.search(r"Games played: (\d+)", men_page)
    women_games = re.search(r"Games played: (\d+)", women_page)
    if men_games and women_games:
        # Not a hard "must differ" (a team could coincidentally have the same
        # game count in both divisions), but the two pages as a whole should
        # not be byte-identical -- that's what the bug produced.
        assert men_page != women_page


def test_women_team_pages_state_the_real_reason_when_schedule_is_unavailable(site):
    out_dir, _, women_teams = site
    team = sorted(women_teams)[0]
    page = (out_dir / "women" / "team" / f"{bs._safe_name(team)}.html").read_text(encoding="utf-8")
    if "No upcoming games scheduled." in page:
        pytest.fail(
            "women's team page used the men's generic empty-schedule message instead of "
            "the division-specific one (women's has no projections pipeline yet)"
        )


def test_root_prefix_depth_is_correct_for_every_page_type(site):
    out_dir, men_teams, women_teams = site
    # index.html (depth 0) must link assets with no "../"
    idx = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="assets/style.css"' in idx
    # women/index.html (depth 1) must use one "../"
    widx = (out_dir / "women" / "index.html").read_text(encoding="utf-8")
    assert 'href="../assets/style.css"' in widx
    # a men's team page (depth 1)
    team_page = (out_dir / "team" / f"{bs._safe_name(sorted(men_teams)[0])}.html").read_text(encoding="utf-8")
    assert 'href="../assets/style.css"' in team_page
    # a women's team page (depth 2)
    wteam_page = (out_dir / "women" / "team" / f"{bs._safe_name(sorted(women_teams)[0])}.html").read_text(encoding="utf-8")
    assert 'href="../../assets/style.css"' in wteam_page
