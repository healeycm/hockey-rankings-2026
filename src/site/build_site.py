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
    path = ROOT_DIR / "output" / ("women" if division == "women" else "") / "last_run.json"
    path = ROOT_DIR / "output" / "last_run.json" if division == "men" else ROOT_DIR / "output" / "women" / "last_run.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


PAGE_SHELL = """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{root}index.html">College Hockey Rankings</a>
  <nav>
    <a href="{root}index.html">Men's</a>
    <a href="{root}women/index.html">Women's</a>
    <a href="{root}methodology.html">Methodology</a>
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

STYLE_CSS = """
:root {
  --bg: #f7f7f5; --panel: #ffffff; --text: #1b1b1f; --muted: #6b6b76;
  --border: #e3e3e8; --accent: #7a3ff2; --accent-bg: #f1eafe;
  --banner-bg: #fff4e5; --banner-border: #f0c987; --banner-text: #7a4a00;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #16161a; --panel: #1e1e24; --text: #eceef1; --muted: #9a9aa5;
    --border: #302f38; --accent: #b18bff; --accent-bg: #2a2140;
    --banner-bg: #3a2c10; --banner-border: #7a5a20; --banner-text: #f0cf8f;
  }
}
:root[data-theme="dark"] {
  --bg: #16161a; --panel: #1e1e24; --text: #eceef1; --muted: #9a9aa5;
  --border: #302f38; --accent: #b18bff; --accent-bg: #2a2140;
  --banner-bg: #3a2c10; --banner-border: #7a5a20; --banner-text: #f0cf8f;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, Segoe UI, Roboto, sans-serif; }
.container { max-width: 980px; margin: 0 auto; padding: 8px 16px 48px; }
.site-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border); background: var(--panel); flex-wrap: wrap; gap: 8px; }
.site-header .brand { font-weight: 700; color: var(--text); text-decoration: none; font-size: 1.1rem; }
.site-header nav a { color: var(--muted); text-decoration: none; margin-left: 18px; font-size: .95rem; }
.site-header nav a:hover { color: var(--accent); }
.site-footer { text-align: center; color: var(--muted); font-size: .8rem; padding: 24px 16px; }
h1 { font-size: 1.5rem; margin: 18px 0 6px; }
h2 { font-size: 1.15rem; margin: 24px 0 8px; }
.subtitle { color: var(--muted); font-size: .9rem; margin-bottom: 16px; }
.banner { background: var(--banner-bg); border: 1px solid var(--banner-border); color: var(--banner-text); border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: .9rem; }
.tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.tab-btn { border: 1px solid var(--border); background: var(--panel); color: var(--text); border-radius: 999px; padding: 6px 14px; font-size: .85rem; cursor: pointer; }
.tab-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.table-wrap { overflow-x: auto; border-radius: 8px; }
table { width: 100%; min-width: 480px; border-collapse: collapse; background: var(--panel); border: 1px solid var(--border); }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); font-size: .9rem; }
th { color: var(--muted); font-weight: 600; cursor: pointer; user-select: none; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--accent-bg); }
.team-link { display: flex; align-items: center; gap: 8px; color: var(--text); text-decoration: none; }
.team-link:hover { color: var(--accent); }
.logo { width: 22px; height: 22px; object-fit: contain; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .grid-2 { grid-template-columns: 1fr; } }
.win { color: #1a7f37; } .loss { color: #cf222e; }
ul.plain { list-style: none; padding: 0; margin: 0; }
ul.plain li { padding: 4px 0; border-bottom: 1px solid var(--border); font-size: .88rem; }
ul.plain li:last-child { border-bottom: none; }
canvas#distChart { max-width: 100%; }
"""


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
    body = f"""
<h1>{section_title}</h1>
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
    html_out = PAGE_SHELL.format(
        title=f"{'Women' if division == 'women' else 'Men'}'s Rankings",
        root=root, body=body, model_count=len(models_here),
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
    schedule = get_team_schedule(team, model=schedule_model)
    logo = get_logo_url(team, division=division)

    upcoming_html = "<p>No upcoming games scheduled.</p>"
    if schedule is not None and not schedule.empty:
        rows = [_game_row_html(r) for _, r in schedule.head(15).iterrows()]
        upcoming_html = f'<ul class="plain">{"".join(rows)}</ul>'

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
        analysis = load_team_analysis(team, model=model)
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
        analysis = load_team_analysis(team, model=model)
        dist_df = load_rank_distribution(team, model=model)
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
  new Chart(ctx, {{
    type: 'bar',
    data: {{ labels: labels, datasets: [{{ label: 'Probability', data: probs, backgroundColor: '#7a3ff2' }}] }},
    options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ title: {{ display: true, text: 'Final rank' }} }} }} }}
  }});
}}
</script>
"""
    html_out = PAGE_SHELL.format(title=f"{team}", root=root, body=body, model_count=len(active_models))
    rel = f"team/{_safe_name(team)}.html" if division == "men" else f"women/team/{_safe_name(team)}.html"
    path = out_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_out, encoding="utf-8")


def build_methodology_page(out_dir, root):
    # NOTE: deliberately says nothing about preseason priors (src/rankings/priors.py)
    # -- per an explicit request to keep that out of the published site for
    # now, even though it validated well (reports/preseason_priors_results.md).
    # Revisit this copy if/when that's ready to be public.
    body = """
<h1>Methodology</h1>
<div class="card">
<h2>ELO</h2>
<p>Sequential rating updated after every game (margin-of-victory weighted, home-ice adjusted).</p>
</div>
<div class="card">
<h2>Massey</h2>
<p>Least-squares ratings fit to goal differential, with a fitted home-ice term, fitted rest/fatigue
adjustment, and ridge regularization. Backtested to beat KRACH/ELO/HockeyBT on accuracy, Brier
score, and log loss (see reports/massey_calibration_results.md, reports/massey_experiments_2026.md).</p>
</div>
<div class="card">
<h2>KRACH</h2>
<p>Bradley-Terry maximum-likelihood ratings (the model behind the NCAA hockey selection
committee's own comparison tool). Purely fit from this season's game results.</p>
</div>
<div class="card">
<h2>NPI</h2>
<p>A from-scratch reimplementation of the NCAA's official Nutting Power Index (winning percentage
+ strength of schedule, quality-win bonus, home/road weighting).</p>
</div>
<p class="subtitle">See the project's <code>reports/</code> folder for full backtests and validation
methodology behind every claim above.</p>
"""
    html_out = PAGE_SHELL.format(title="Methodology", root=root, body=body, model_count=4)
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
    (assets_dir / "style.css").write_text(STYLE_CSS, encoding="utf-8")

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
