# src/site/build_site.py
"""
Builds a static site (site_build/) from the latest output/ CSVs, for
publishing to GitHub Pages -- see the plan this implements
(scripts/daily_update.py calls this after a successful run, then pushes
site_build/ to the public Pages repo).

Deliberately reuses webpage/utils/data_loader.py's loaders (load_rankings,
get_team_schedule, load_team_analysis, load_rank_distribution,
get_canonical_name, get_logo_url) rather than re-deriving the same file-glob
logic a second time -- this module is a second CONSUMER of that data layer,
same as the Dash app in webpage/app.py, not a competing implementation.

Usage:
    python -m src.site.build_site                 # men's only
    python -m src.site.build_site --women          # men's + women's
    python -m src.site.build_site --out /path/dir  # custom output dir
"""
import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "webpage"))  # webpage/ isn't a package; app.py does this too

from utils.data_loader import (  # noqa: E402
    load_records, load_rankings, get_team_schedule, load_team_analysis,
    load_rank_distribution, get_canonical_name, get_logo_url, get_available_models,
)

import yaml  # noqa: E402

from src.rankings.priors import shift_season_code  # noqa: E402


def _format_season(season_code):
    """20252026 -> '2025-26' (matches how USCHO/the site refers to a season elsewhere)."""
    s = str(season_code)
    return f"{s[:4]}-{s[6:]}" if len(s) == 8 else s

DEFAULT_OUT = ROOT_DIR / "site_build"


def _config():
    with open(ROOT_DIR / "config.yaml") as f:
        return yaml.safe_load(f)


def _safe_name(team):
    return team.replace(" ", "_").replace(".", "").replace("&", "and").replace("/", "-")


def _read_manifest(division):
    path = ROOT_DIR / "output" / "last_run.json" if division == "men" else ROOT_DIR / "output" / "women" / "last_run.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


# The stylesheet itself lives at src/site/assets/style.css (a real .css
# file, not a Python string) -- main() copies it into out_dir/assets/.
STYLE_CSS_PATH = Path(__file__).resolve().parent / "assets" / "style.css"

PAGE_SHELL = """<!doctype html>
<html lang="en" data-theme="light" data-division="{division}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body data-division="{division}">
<header class="site-header">
  <a class="brand" href="{root}index.html">College Hockey Rankings</a>
  <nav>
    <a href="{root}index.html"{men_cur}>Men's</a>
    <a href="{root}women/index.html"{women_cur}>Women's</a>
    <a href="{root}methodology.html"{meth_cur}>Methodology</a>
  </nav>
</header>
<main class="container">
{body}
</main>
<footer class="site-footer">
  <p>Built from {model_count} featured models. Not affiliated with USCHO, the NCAA, or any conference.</p>
</footer>
</body>
</html>
"""


def _page_shell(title, root, body, model_count, division="", current=""):
    """Renders PAGE_SHELL. `division` is 'men'/'women'/'' (methodology,
    which isn't division-scoped and falls back to the men's-blue accent --
    see style.css). `current` marks the active nav link ('men'/'women'/
    'methodology') for a visual "you are here" state."""
    return PAGE_SHELL.format(
        title=title, root=root, body=body, model_count=model_count, division=division,
        men_cur=' class="current"' if current == "men" else "",
        women_cur=' class="current"' if current == "women" else "",
        meth_cur=' class="current"' if current == "methodology" else "",
    )


def _displayed_season(manifest, target_season):
    """The season these rankings actually reflect, for the h1 tag. Mirrors
    _banner_html's own fallback logic (0-games-played target season ->
    the prior season's numbers) so the two never say different seasons."""
    games = manifest.get("games_played_this_season")
    target_fmt = _format_season(target_season) if target_season else None
    if games is not None and games == 0 and target_season:
        return _format_season(shift_season_code(target_season, 1))
    manifest_season = manifest.get("target_season")
    if manifest_season:
        return _format_season(manifest_season)
    return target_fmt or "current season"


def _banner_html(manifest, target_season):
    games = manifest.get("games_played_this_season")
    last_date = manifest.get("last_final_game_date")
    if games is not None and games == 0:
        # New season hasn't started -- rankings/records below are the LAST
        # completed season's real final numbers (see load_records()'s
        # fallback), not placeholders, so say that plainly instead of the
        # more alarming "no data" framing this used to have.
        prior_season = _format_season(shift_season_code(target_season, 1)) if target_season else "last season"
        return (f'<div class="banner">The {_format_season(target_season)} season hasn\'t started yet. '
                f'Showing final {prior_season} rankings.</div>')
    if last_date:
        return f'<div class="subtitle">Last updated {last_date} &middot; {games} games played this season.</div>'
    return ""


def _rankings_table_html(model_name, df, division, root):
    val_col = f"{model_name}_Val"
    rank_col = f"{model_name}_Rank"
    if rank_col not in df.columns:
        return "<p>No data yet for this model.</p>"
    d = df.dropna(subset=[rank_col]).sort_values(rank_col)
    rows = []
    for _, r in d.iterrows():
        team = r.get("Team", "")
        slug = _safe_name(team)
        logo = get_logo_url(team, division=division)
        conf = r.get("Conference", "") or ""
        record = r.get("Record", "") or ""
        val = r.get(val_col)
        val_str = f"{val:.2f}" if isinstance(val, (int, float)) else ""
        team_href = f"{root}women/team/{slug}.html" if division == "women" else f"{root}team/{slug}.html"
        rows.append(
            f'<tr><td class="num">{int(r[rank_col])}</td>'
            f'<td><a class="team-link" href="{team_href}">'
            f'<img class="logo" src="{root}{logo.lstrip("/")}" loading="lazy" alt=""> {html.escape(str(team))}</a></td>'
            f'<td>{html.escape(str(conf))}</td><td>{html.escape(str(record))}</td>'
            f'<td class="num">{val_str}</td></tr>'
        )
    return (
        '<div class="table-wrap"><table><thead><tr><th>#</th><th>Team</th><th>Conf</th><th>Record</th>'
        f'<th>{html.escape(model_name)} rating</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def build_rankings_page(division, active_models, out_dir, root):
    config = _config()
    target_season = config['system'].get('season', '')
    manifest = _read_manifest(division)
    available = set(get_available_models(division=division))
    models_here = [m for m in active_models if m in available] or active_models

    panels = []
    tabs = []
    for i, model in enumerate(models_here):
        df = load_rankings(model, division=division)
        active_cls = " active" if i == 0 else ""
        hidden = "" if i == 0 else " hidden"
        tabs.append(f'<button class="tab-btn{active_cls}" data-tab="{model}" onclick="showTab(\'{model}\')">{html.escape(model)}</button>')
        panels.append(f'<div class="tab-panel" id="panel-{model}"{hidden}>{_rankings_table_html(model, df, division, root)}</div>')

    section_title = "Women's D-I Rankings" if division == "women" else "Men's D-I Rankings"
    season_label = _displayed_season(manifest, target_season)
    body = f"""
<h1>{section_title} <span class="season-tag">{season_label}</span></h1>
{_banner_html(manifest, target_season)}
<div class="tabs">{''.join(tabs)}</div>
{''.join(panels)}
<script>
function showTab(name) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.hidden = (p.id !== 'panel-' + name));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
}}
</script>
"""
    html_out = _page_shell(
        title=f"{'Women' if division == 'women' else 'Men'}'s Rankings — {season_label}",
        root=root, body=body, model_count=len(models_here), division=division, current=division,
    )
    fname = "index.html" if division == "men" else "women/index.html"
    (out_dir / fname).parent.mkdir(parents=True, exist_ok=True)
    (out_dir / fname).write_text(html_out, encoding="utf-8")
    return models_here


def _game_row_html(row):
    opp = html.escape(str(row.get("Opponent", "")))
    loc = row.get("Location", "")
    date = str(row.get("Date", ""))[:10]
    prob = row.get("WinProb")
    prob_str = f"{prob:.0%}" if isinstance(prob, (int, float)) else ""
    return f"<li>{date} &middot; {loc} {opp} &mdash; win prob {prob_str}</li>"


def build_team_page(team, division, active_models, out_dir, root):
    schedule_model = active_models[0] if active_models else "Massey"
    schedule = get_team_schedule(team, model=schedule_model, division=division)
    logo = get_logo_url(team, division=division)

    if schedule is not None and not schedule.empty:
        rows = [_game_row_html(r) for _, r in schedule.head(15).iterrows()]
        upcoming_html = f'<ul class="plain">{"".join(rows)}</ul>'
    elif division == "women":
        # Distinguish "the pipeline doesn't produce this for women's yet"
        # from "no games left this season" (men's) -- saying the wrong one
        # here reads as a bug, not an honest gap. See the plan's Phase 1
        # note: women's has no output/women/projections/ tree at all.
        upcoming_html = "<p>Schedule projections aren't run for women's D-I yet.</p>"
    else:
        upcoming_html = "<p>No upcoming games scheduled.</p>"

    # Games/WinPct/SOS_Rating are team-level facts, identical across every
    # model's season_summary.csv (confirmed: they don't vary by model) --
    # shown ONCE in the overview card, not repeated inside every model's
    # section below (that was the "team pages are a little off" bug: each
    # model card used to repeat an identical "Win% ..." line, and the first
    # model's whole best-wins/losses/chart block was wrongly nested a
    # second level deep inside the overview card instead of appearing
    # alongside the other models' cards).
    overview_html = "<p>No data.</p>"
    for model in active_models:
        analysis = load_team_analysis(team, model=model, division=division)
        stats = analysis.get("stats") if analysis else None
        if stats:
            games = stats.get("Games")
            wp = stats.get("WinPct")
            sos = stats.get("SOS_Rating")
            lines = []
            if isinstance(games, (int, float)):
                lines.append(f"<li>Games played: {int(games)}</li>")
            if isinstance(wp, (int, float)):
                lines.append(f"<li>Win%: {wp:.3f}</li>")
            if isinstance(sos, (int, float)):
                lines.append(f"<li>Strength of schedule: {sos:.1f}</li>")
            if lines:
                overview_html = f"<ul class='plain'>{''.join(lines)}</ul>"
            break

    model_sections = []
    for model in active_models:
        analysis = load_team_analysis(team, model=model, division=division)
        dist_df = load_rank_distribution(team, model=model, division=division)
        parts = [f"<h2>{html.escape(model)}</h2>"]
        has_content = False
        if analysis:
            wins = analysis.get("top_wins")
            losses = analysis.get("worst_losses")
            if wins is not None and not wins.empty:
                has_content = True
                items = "".join(f"<li>{html.escape(str(r.get('Opponent', '')))}</li>" for _, r in wins.iterrows())
                parts.append(f"<h3>Best wins</h3><ul class='plain'>{items}</ul>")
            if losses is not None and not losses.empty:
                has_content = True
                items = "".join(f"<li>{html.escape(str(r.get('Opponent', '')))}</li>" for _, r in losses.iterrows())
                parts.append(f"<h3>Toughest losses</h3><ul class='plain'>{items}</ul>")
        if dist_df is not None and not dist_df.empty and len(dist_df) > 1:
            # Skip the chart when only one outcome is even possible (e.g. a
            # completed season simulated with zero games remaining) -- a
            # single 100%-probability bar isn't informative.
            has_content = True
            labels = json.dumps(dist_df['Rank'].astype(int).tolist())
            probs = json.dumps([round(float(p), 4) for p in dist_df['Probability']])
            parts.append(
                f"<h3>Projected finish</h3>"
                f'<canvas id="dist-{model}" height="140"></canvas>'
                f"<script>renderDist('dist-{model}', {labels}, {probs});</script>"
            )
        if has_content:
            model_sections.append(f'<div class="card">{"".join(parts)}</div>')

    body = f"""
<h1><img class="logo" src="{root}{logo.lstrip('/')}" style="width:32px;height:32px;vertical-align:middle;"> {html.escape(team)}</h1>
<div class="grid-2">
  <div class="card"><h2>Upcoming schedule</h2>{upcoming_html}</div>
  <div class="card"><h2>Season overview</h2>{overview_html}</div>
</div>
{"".join(model_sections)}
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<script>
function renderDist(canvasId, labels, probs) {{
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return;
  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#1d4ed8';
  new Chart(ctx, {{
    type: 'bar',
    data: {{ labels: labels, datasets: [{{ label: 'Probability', data: probs, backgroundColor: accent }}] }},
    options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ title: {{ display: true, text: 'Final rank' }} }} }} }}
  }});
}}
</script>
"""
    html_out = _page_shell(title=f"{team}", root=root, body=body, model_count=len(active_models), division=division)
    rel = f"team/{_safe_name(team)}.html" if division == "men" else f"women/team/{_safe_name(team)}.html"
    path = out_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_out, encoding="utf-8")


# Full methodology copy, one entry per model this project runs (whether or
# not it's in either division's current active_models list -- unlisted
# ones are marked "implemented, not currently featured" rather than
# omitted, so this page is a complete map of what's in src/rankings/, not
# just a gloss on the 1-2 rosters currently live). Ordered by how the page
# presents them: the 4 shared/legacy methods first, then the 2 that were
# added specifically to beat NPI.
#
# `example` uses real numbers pulled from this project's own latest output
# CSVs (not illustrative placeholders) -- see the comment on each entry for
# which two teams/season. External links are general references for the
# method itself, not endorsements of this project; verify they still
# resolve before treating this list as final.
MODEL_DOCS = [
    {
        "key": "ELO",
        "summary": "A sequential rating that updates after every single game, the way chess "
                    "and most competitive-game rating systems work.",
        "how": "Every team starts at a baseline rating. After each game, the winner takes rating "
               "points from the loser -- more points for a bigger upset (beating a much "
               "higher-rated team), fewer for beating a team you were already expected to beat. "
               "The exchange is also scaled by margin of victory and adjusted for home ice, so a "
               "5-goal road win moves the ratings more than a 1-goal home win.",
        "example": "Our most recent final men's ratings had Michigan at 1188.7 and North Dakota "
                   "at 1176.1. Elo's own win-probability formula, 1 / (1 + 10^(-diff/400)), turns "
                   "that 12.6-point gap into a roughly 52% chance for Michigan on a neutral "
                   "sheet of ice -- illustrating how close Elo says these two teams actually are, "
                   "despite the rating gap looking larger in isolation.",
        "strengths": "Reacts fast to a team's current form (a hot or cold streak shows up "
                     "immediately) and is cheap to recompute after each night's games. In our "
                     "men's-hockey calibration testing it's the best-calibrated model we run -- "
                     "its stated win probabilities match actual outcomes more closely than any "
                     "other model here, including Massey (reports/calibration_metrics.md).",
        "caveats": "Purely sequential, so it has no real memory of a full season's context -- "
                    "two teams with identical records can end up at different ratings just "
                    "because of the order they played their games in.",
        "cross_division": "The calibration result above does NOT transfer to women's hockey: in "
                           "the separate women's-hockey backtest, ELO is not the best-calibrated "
                           "model -- HockeyBT is (ELO's ECE is 0.0706 vs. HockeyBT's 0.0568; see "
                           "reports/womens_hockey_import.md). We haven't re-run the men's "
                           "calibration report's full methodology on women's data, so treat this "
                           "as a real, evidenced difference, not a gap in testing.",
        "links": [
            ("Wikipedia: Elo rating system", "https://en.wikipedia.org/wiki/Elo_rating_system"),
            ("FiveThirtyEight: How our NFL predictions work (Elo primer)",
             "https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/"),
        ],
    },
    {
        "key": "Massey",
        "summary": "A least-squares rating: the set of team ratings that, together, best explain "
                    "every game's actual goal differential.",
        "how": "Solves a system of linear equations -- one per game, each saying roughly "
               "'winner's rating minus loser's rating should predict this goal margin' -- for the "
               "single set of ratings that minimizes the total prediction error across every game "
               "played. On top of Kenneth Massey's original method we add a fitted home-ice term, "
               "a fitted rest/fatigue adjustment (penalizing a team playing on short rest), and "
               "ridge regularization so teams with thin schedules don't get wild ratings.",
        "example": "Same two men's teams as above: Michigan's Massey rating was 1.918 to North "
                   "Dakota's 1.797, a 0.12-goal gap -- Massey's native scale is predicted goal "
                   "margin, so that's a razor-thin expected difference before the home-ice and "
                   "rest adjustments are applied to an actual matchup.",
        "strengths": "The best model we run overall on men's hockey: it beats KRACH, Elo, and "
                     "HockeyBT on accuracy, Brier score, and log loss simultaneously, with all 9 "
                     "of those head-to-head comparisons statistically significant (reports/"
                     "massey_calibration_results.md).",
        "caveats": "On men's hockey, wins on resolution (how sharply it separates good teams "
                    "from bad) rather than calibration -- Elo's stated probabilities are actually "
                    "closer to true frequencies there (reports/calibration_metrics.md).",
        "cross_division": "The headline finding does transfer: Massey is also the single best "
                           "model on accuracy, Brier score, AND log loss in the separate 5-year "
                           "women's-hockey backtest (0.7544 accuracy vs. HockeyBT's 0.7473, "
                           "KRACH's 0.7450, ELO's 0.7428, RPI's 0.7279 -- reports/"
                           "womens_hockey_import.md). That backtest hasn't yet run the same "
                           "paired-significance tests (paired t-test/McNemar's) as the men's one "
                           "has, so we can say Massey is ahead on women's data but not yet claim "
                           "statistical significance the way we can for men's.",
        "links": [
            ("Kenneth Massey's rating site", "https://masseyratings.com/"),
            ("Langville & Meyer, Who's #1? (the standard reference for Massey/Colley/Keener)",
             "https://press.princeton.edu/books/paperback/9780691162231/whos-1"),
        ],
    },
    {
        "key": "KRACH",
        "summary": "Bradley-Terry maximum-likelihood ratings -- the same family of model behind "
                    "the NCAA hockey selection committee's own comparison tool.",
        "how": "Iteratively solves for a rating per team such that each team's *expected* win "
               "total against its actual opponents (summing rating_A / (rating_A + rating_B) "
               "over every game) matches its *actual* win total. Fit purely from this season's "
               "results -- no home ice, no margin of victory, no other adjustments.",
        "example": "Michigan's men's KRACH rating (576.9) against North Dakota's (351.5) gives a "
                   "textbook Bradley-Terry win probability of 576.9 / (576.9 + 351.5) ≈ 62%.",
        "strengths": "Transparent and already recognized by the sport -- it's the model the "
                     "NCAA hockey selection committee itself consults. We deliberately keep our "
                     "KRACH implementation \"pure\" (no home-ice or margin additions) so it's "
                     "directly cross-checkable against published KRACH numbers elsewhere.",
        "caveats": "Ignoring home ice and margin of victory throws away real information the "
                    "other models use. Bradley-Terry ratings can also become unstable when two "
                    "parts of the schedule graph are only thinly connected (few common "
                    "opponents) -- a genuine structural weakness of this whole model family that "
                    "our own men's-hockey audit found actually favors NPI in that specific "
                    "scenario (reports/npi_critique.md, \"connectivity limits\").",
        "cross_division": "That connectivity finding is men's-hockey-specific (the audit behind "
                           "it never touched women's data) and hasn't been separately checked "
                           "against women's D-I's smaller, differently-shaped schedule graph -- "
                           "we don't know whether it applies the same way there.",
        "links": [
            ("USCHO: understanding KRACH", "https://www.uscho.com/rankings/mens-di-krach/"),
            ("Wikipedia: Bradley-Terry model", "https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model"),
        ],
    },
    {
        "key": "NPI",
        "summary": "Our from-scratch reimplementation of the NCAA's own official selection-"
                    "committee formula.",
        "how": "Combines a team's winning percentage (with road wins weighted more than home "
               "wins) with its strength of schedule (opponents' winning percentage) and a "
               "\"quality win bonus\" for beating strong opponents, into the single index the "
               "committee uses at-large and seeding. Purely this-season results.",
        "example": "On the NPI scale, Michigan's men's rating of 59.50 vs. North Dakota's 58.75 "
                   "is a 0.75-point gap -- NPI is a selection-committee index, not a predictive "
                   "model, so unlike the others above this number isn't meant to convert into a "
                   "win probability.",
        "strengths": "It's the actual formula that determines the tournament field, so it's the "
                     "one number on this page with direct bracket implications. Our men's-hockey "
                     "reimplementation matches the NCAA's own published numbers after we found "
                     "and fixed a date-cutoff and a strength-of-schedule filter bug (reports/"
                     "npi_investigation_2026.md).",
        "caveats": "Our own multi-part critique of men's-hockey NPI found real weaknesses "
                    "relative to the other models here: worse predictive accuracy than Massey or "
                    "even plain RPI, and the same schedule-connectivity sensitivity as KRACH "
                    "(reports/npi_critique.md). We publish NPI because it's the committee's own "
                    "formula, not because our research rates it as the best predictor.",
        "cross_division": "None of the critique above has been re-run on women's data -- our "
                           "women's-hockey backtest (reports/womens_hockey_import.md) never "
                           "included NPI, so we don't have women's-specific evidence for or "
                           "against it. The women's NPI ratings shown on this site were computed "
                           "fresh on 2026-09-20 for display parity with men's, but they have not "
                           "been cross-checked against the NCAA's own published women's NPI "
                           "numbers the way the men's numbers were.",
        "links": [
            ("NCAA Division I Ice Hockey selection criteria (official)",
             "https://www.ncaa.com/news/icehockey-men/article/ncaa-di-mens-hockey-championship-selection-process"),
            ("USCHO: understanding the NPI", "https://www.uscho.com/rankings/mens-di-npi/"),
        ],
    },
    {
        "key": "HockeyBT",
        "summary": "An extended Bradley-Terry model (Davidson-Beaver) -- KRACH's exact same "
                    "engine, plus a fitted home-ice term and a genuine three-outcome (win/tie/"
                    "loss) treatment of overtime games.",
        "how": "KRACH's plain Bradley-Terry math assumes only two outcomes and no home ice. "
               "HockeyBT adds two fitted parameters on top of that same core: theta (home-ice "
               "advantage, fit from the data rather than assumed) and nu (a Davidson tie term, "
               "since roughly a fifth of NCAA hockey games are decided in overtime/shootout and "
               "are statistically closer to a draw than a clean regulation win). MAP "
               "regularization keeps thinly-scheduled teams' ratings from blowing up, the same "
               "problem plain KRACH has.",
        "example": "In this season's women's ratings, Ohio State's HockeyBT rating (821.0) vs. "
                   "Wisconsin's (738.7) gives an approximate 52.6% Bradley-Terry win probability "
                   "before HockeyBT's home-ice and tie terms are applied to a specific matchup.",
        "strengths": "In a men's-hockey 5-year, 20-split backtest, beats KRACH on calibration "
                     "(Brier score, log loss) and beats NPI on accuracy at the same time (reports/"
                     "hockey_bt_results.md).",
        "caveats": "The 'beats NPI' comparison above is men's-hockey-only -- our women's-hockey "
                    "backtest never included NPI, so we can't say HockeyBT beats NPI on women's "
                    "data, only that both are computed for women's now. On women's data "
                    "specifically, HockeyBT is the best-calibrated model of the 5 we backtested "
                    "(lowest ECE) but is NOT the most accurate -- Massey is (reports/"
                    "womens_hockey_import.md).",
        "links": [
            ("Wikipedia: Bradley-Terry model (Davidson tie extension is covered under "
             "\"ties\")", "https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model"),
        ],
    },
    {
        "key": "RPI",
        "summary": "The classic Ratings Percentage Index: a weighted blend of a team's own "
                    "record, its opponents' records, and its opponents' opponents' records.",
        "how": "RPI = 0.25 × (own winning percentage) + 0.50 × (opponents' average "
               "winning percentage) + 0.25 × (opponents' opponents' average winning "
               "percentage), using the same road-win-weighted/home-win-discounted convention as "
               "NPI. This is the formula NPI itself replaced in NCAA hockey selection years ago "
               "with committee-tuned weights and a quality-win bonus.",
        "example": "This season's women's RPI has Ohio State at 0.6346 and Wisconsin at 0.6169 "
                   "-- RPI's native scale is a 0-1 percentage-like index, not goals or a "
                   "probability.",
        "strengths": "Beats NPI on accuracy in our men's-hockey backtest (reports/"
                     "rpi_results.md) -- the second independent confirmation, after HockeyBT, "
                     "that NPI underperforms simpler alternatives on men's-hockey predictive "
                     "accuracy.",
        "caveats": "Loses to Massey on every metric we track, on both men's and women's data -- "
                    "RPI is the lowest-accuracy model of the 5 backtested for women's hockey too "
                    "(0.7279, reports/womens_hockey_import.md). We keep it running mainly for "
                    "its diagnostic value as an NPI comparison, not because it's a top model in "
                    "its own right.",
        "cross_division": "The 'beats NPI' finding above is men's-only -- our women's-hockey "
                           "backtest never included NPI, so we have no women's-specific evidence "
                           "that RPI beats NPI there.",
        "links": [
            ("Wikipedia: Ratings Percentage Index", "https://en.wikipedia.org/wiki/Rating_percentage_index"),
        ],
    },
]


def _method_tags(key, active_men, active_women):
    tags = []
    if key in active_men:
        tags.append('<span class="tag men">Men\'s</span>')
    if key in active_women:
        tags.append('<span class="tag women">Women\'s</span>')
    if not tags:
        tags.append('<span class="tag">Implemented, not currently featured</span>')
    return f'<div class="tag-row">{"".join(tags)}</div>'


def build_methodology_page(out_dir, root):
    # NOTE: deliberately says nothing about preseason priors (src/rankings/priors.py)
    # -- per an explicit request to keep that out of the published site for
    # now, even though it validated well (reports/preseason_priors_results.md).
    # Revisit this copy if/when that's ready to be public.
    config = _config()
    active_men = config['models']['active_models']
    active_women = config['models'].get('active_models_women', active_men)

    cards = []
    for doc in MODEL_DOCS:
        links_html = "".join(f'<a href="{href}" rel="noopener" target="_blank">{html.escape(text)}</a>'
                              for text, href in doc["links"])
        cross_html = ""
        if doc.get("cross_division"):
            cross_html = (f'<h3>Men\'s vs. women\'s</h3>'
                          f'<div class="example-block cross-division">{doc["cross_division"]}</div>')
        cards.append(f"""
<div class="card">
<div class="card-head"><h2>{html.escape(doc['key'])}</h2>{_method_tags(doc['key'], active_men, active_women)}</div>
<p>{doc['summary']}</p>
<h3>How it works</h3>
<p>{doc['how']}</p>
<div class="example-block"><strong>Worked example:</strong> {doc['example']}</div>
<h3>Strengths</h3>
<p>{doc['strengths']}</p>
<h3>Caveats</h3>
<p>{doc['caveats']}</p>
{cross_html}
<div class="links-row">{links_html}</div>
</div>""")

    body = f"""
<h1>Methodology</h1>
<p class="subtitle">Six ranking models, run for both divisions. Every model below is fit fresh
from this season's actual game results -- none of them use a human poll, recruiting rankings, or
last season's finish as an input (preseason priors are used for early-season stability on
ELO/Massey but are kept off this public page for now). Running the same model for both divisions
is not the same claim as having tested it on both -- see each card's "Men's vs. women's" note
where the two diverge or where we simply don't have evidence yet for one division.</p>

<div class="card">
<h2>How to read these rankings</h2>
<p>Each division's rankings page shows every model that division currently runs, as tabs over the
same team list. The models don't always agree -- that disagreement is informative, not a bug:
Elo reacts fastest to recent form, Massey is our most accurate model on both men's and women's
data, KRACH and NPI are the two "official"/committee-recognized formulas, and HockeyBT/RPI were
built specifically to stress-test NPI against genuine alternatives. Our research (the reports/
directory, and the "papers" linked from the project README) was written primarily from a
men's-hockey vantage point -- more teams, more games, a longer backtest history -- and several
of its headline comparisons (HockeyBT beats NPI, RPI beats NPI) have never been re-run with NPI
included in a women's-hockey backtest. Where a finding is men's-only, known to differ for
women's, or simply untested for one division, we say so explicitly below rather than implying it
transfers.</p>
</div>

{"".join(cards)}

<div class="card">
<h2>What we've validated</h2>
<p>Every performance claim above is backed by a written report with real backtest numbers, not
just an assertion, and each is scoped to the division it was actually tested on. The full set
(accuracy, Brier score, log loss, calibration/ECE, and the specific model-vs-model comparisons)
lives in this project's <code>reports/</code> directory, including
<code>massey_calibration_results.md</code>, <code>hockey_bt_results.md</code>,
<code>rpi_results.md</code>, <code>npi_critique.md</code>, <code>npi_investigation_2026.md</code>,
<code>calibration_metrics.md</code>, and the separate <code>womens_hockey_import.md</code> (the
only report that backtests women's hockey specifically -- it covers Massey, HockeyBT, KRACH,
ELO, and RPI, not NPI). Two honest gaps: (1) HockeyBT and RPI were added to the men's site roster
and NPI to the women's roster on 2026-09-20 for site parity -- their ratings are freshly computed
for every division, but the specific model-vs-model comparisons involving NPI have only been
backtested for men's; (2) the women's backtest hasn't yet run the same paired-significance tests
(paired t-test, McNemar's) that the men's backtests have, so where we say a women's-hockey result
is "ahead" rather than "significantly better," that's why.</p>
</div>
"""
    html_out = _page_shell(title="Methodology", root=root, body=body, model_count=len(MODEL_DOCS), division="", current="methodology")
    (out_dir / "methodology.html").write_text(html_out, encoding="utf-8")


def _append_history(out_dir, division, models_here):
    """Appends today's #1-ranked team per model to data/history.json so the
    site can eventually show rank trend sparklines without publishing every
    dated CSV -- see the plan's rank-history note."""
    import datetime
    hist_path = out_dir / "data" / "history.json"
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    history = {}
    if hist_path.exists():
        try:
            history = json.loads(hist_path.read_text())
        except Exception:
            history = {}
    today = datetime.date.today().isoformat()
    day_key = f"{division}:{today}"
    entry = {}
    for model in models_here:
        df = load_rankings(model, division=division)
        rank_col = f"{model}_Rank"
        if rank_col in df.columns and not df.empty:
            top = df.dropna(subset=[rank_col]).sort_values(rank_col).iloc[0]
            entry[model] = top.get("Team")
    history[day_key] = entry
    hist_path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def build(division, out_dir):
    """
    Path depth (relative to out_dir/, the site root) for each page this
    builds, and hence the "root" prefix (how many "../" it takes to get
    back to out_dir/ from that page) every asset/nav link is written with:
        men:   index.html            -> depth 0 -> root=""
               team/<Team>.html      -> depth 1 -> root="../"
        women: women/index.html      -> depth 1 -> root="../"
               women/team/<Team>.html-> depth 2 -> root="../../"
    Getting this wrong doesn't 404 the page itself (that request still
    resolves), it silently breaks every RELATIVE link on the page --
    style.css, logos, and the nav bar all resolve one directory too
    shallow. That's exactly the bug this fixed (team pages had the same
    root as their division's index page, one level too few).
    """
    config = _config()
    active_models = config['models']['active_models'] if division == 'men' \
        else config['models'].get('active_models_women', config['models']['active_models'])
    index_root = "" if division == "men" else "../"
    team_root = "../" if division == "men" else "../../"

    models_here = build_rankings_page(division, active_models, out_dir, root=index_root)

    # Derive the team list from the rankings CSVs themselves, not
    # load_records() -- during preseason (0 games played yet, men's
    # target_season not final-scoped like women's fallback), load_records()
    # returns empty even though last season's rankings/team pages should
    # still be browsable, so team-page links from the rankings table above
    # don't 404.
    teams = set()
    for model in models_here:
        df = load_rankings(model, division=division)
        if 'Team' in df.columns:
            teams.update(df['Team'].dropna().unique())
    teams = sorted(teams)
    for team in teams:
        build_team_page(team, division, models_here, out_dir, root=team_root)

    _append_history(out_dir, division, models_here)
    return teams


def main():
    parser = argparse.ArgumentParser(description="Build the static rankings site.")
    parser.add_argument('--women', action='store_true', help="Also build the women's section.")
    parser.add_argument('--out', type=str, default=None, help="Output directory (default: site_build/).")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = out_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    shutil.copy2(STYLE_CSS_PATH, assets_dir / "style.css")

    logos_src = ROOT_DIR / "webpage" / "assets" / "logos"
    logos_dst = assets_dir / "logos"
    if logos_src.exists():
        shutil.copytree(logos_src, logos_dst, dirs_exist_ok=True)

    build_methodology_page(out_dir, root="")

    men_teams = build("men", out_dir)
    print(f"[build_site] Built men's section: {len(men_teams)} team pages.")

    if args.women:
        women_teams = build("women", out_dir)
        print(f"[build_site] Built women's section: {len(women_teams)} team pages.")

    print(f"[build_site] Site written to {out_dir}")


if __name__ == "__main__":
    main()
