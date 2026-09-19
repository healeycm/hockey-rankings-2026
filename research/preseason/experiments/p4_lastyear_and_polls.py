# research/preseason/experiments/p4_lastyear_and_polls.py
"""
How informative is (a) last season's final rating alone, (b) the USCHO
preseason poll alone, and (c) a combination of the two -- as standalone
predictors, with NO in-season fitting at all (no games this season enter
the prediction whatsoever). This is deliberately NOT the same question P1/
P1b asked (how much should an in-season model like ELO/Massey lean on a
prior while it's also fitting real games) -- it isolates the preseason
information itself, answering "how much does knowing nothing about this
season, only last season's result and the preseason poll, get you."

Method: three small logistic regressions (soft-label cross-entropy on the
existing 0.6/0.4 OT-weighted target, fit via scipy.optimize.minimize --
same fitting style already used elsewhere in this codebase, e.g. massey.py/
rpi.py's calibration steps, not a new sklearn dependency):
  1. poll_only:     p = sigmoid(b0 + b1*poll_diff + b2*home_dummy)
  2. lastyear_only:  p = sigmoid(b0 + b1*lastyear_diff + b2*home_dummy)
  3. combined:       p = sigmoid(b0 + b1*poll_diff + b2*lastyear_diff + b3*home_dummy)
where poll_diff/lastyear_diff are HOME-minus-AWAY, poll_diff uses
(21 - USCHO preseason rank) for ranked teams and 0 for unranked (an
unranked-vs-unranked game gets zero poll signal, which is honest -- the
poll genuinely doesn't distinguish them), and lastyear_diff uses each
team's final ELO rating from a PRODUCTION ELO fit on the immediately
preceding season's complete games (a new program with no prior season
gets that season's mean rating).

Coefficients are fit ONCE on all tune-season games pooled (not per-cutoff
-- these predictors don't change during a season, so there's no cutoff-
specific fitting to do), then evaluated on holdout at the SAME 6 cutoffs'
14-day test windows P1 used (for direct comparison against ELO_none from
research/preseason/results/p1_history_prior/predictions.csv), AND across
the whole holdout season split into monthly bins, to show how the
informativeness of "preseason-only" information decays as the season
progresses.

PRE-REGISTRATION: expect (a) both poll and last-year to beat a coin flip
by a wide margin at Oct/Nov, (b) the combination to beat each alone (they
plausibly carry different information -- roster/coaching for the poll,
program-strength persistence for last year's rating), (c) all three to
fade toward in-season-model performance (ELO_none) as the season
progresses and (d) preseason-only information to eventually be dominated
by ELO_none once enough real games accumulate -- if it never fades, that
itself would be a notable finding worth a closer look.

Run from the project root:
    python -m research.preseason.experiments.p4_lastyear_and_polls
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "webpage"))

from src.rankings.elo import ELO  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from utils.data_loader import get_canonical_name  # noqa: E402

from research.preseason.harness.paths import research_path  # noqa: E402
from research.preseason.harness.eval import weighted_result, game_level_metrics  # noqa: E402
from research.preseason.models.priors_research import shift_season_code  # noqa: E402

EXPERIMENT = "p4_lastyear_and_polls"
CUTOFFS = ['Oct1', 'Oct15', 'Nov1', 'Nov15', 'Dec1', 'Jan1']
TEST_WINDOW_DAYS = 14
RIDGE_LAMBDA = 0.01  # small L2 penalty on non-intercept coefficients, for numerical stability only


def load_archive():
    df = pd.read_csv(PROJECT_ROOT / "research" / "preseason" / "data" / "extended_archive.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    return df


def load_poll(season):
    path = research_path("data", "polls", f"poll_{season}.csv", mkdir_parent=False)
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    df['CanonicalTeam'] = df['Team'].apply(get_canonical_name)
    return dict(zip(df['CanonicalTeam'], 21 - df['Rank']))  # rank1 -> 20, rank20 -> 1


def build_lastyear_ratings(history_df, seasons, elo_conf):
    """{season: {team: last_season's final ELO rating}}, fit once per
    season on that PRIOR season's complete games (production ELO,
    unmodified)."""
    out = {}
    for season in seasons:
        prior_season = shift_season_code(season, 1)
        prior_df = history_df[history_df['Season'] == prior_season]
        if prior_df.empty:
            out[season] = {}
            continue
        model = ELO(prior_df, config=elo_conf)
        model.fit()
        out[season] = dict(model.ratings)
    return out


def build_feature_df(history_df, seasons, lastyear_ratings, min_poll_rank=20):
    rows = []
    for season in seasons:
        season_df = history_df[history_df['Season'] == season].copy()
        if season_df.empty:
            continue
        poll = load_poll(season)
        lastyear = lastyear_ratings.get(season, {})
        lastyear_mean = np.mean(list(lastyear.values())) if lastyear else 1000.0

        for _, row in season_df.iterrows():
            home, away = row['HomeTeam'], row['AwayTeam']
            poll_home = poll.get(home, 0)
            poll_away = poll.get(away, 0)
            ly_home = lastyear.get(home, lastyear_mean)
            ly_away = lastyear.get(away, lastyear_mean)
            rows.append({
                'Season': season, 'Date': row['Date'], 'HomeTeam': home, 'AwayTeam': away,
                'Result': row['Result'], 'IsOT': row.get('IsOT', False),
                'NeutralSite': row.get('NeutralSite', False),
                'poll_diff': poll_home - poll_away,
                'lastyear_diff': (ly_home - ly_away) / 400.0,  # scaled to be logistic-regression-friendly
                'has_poll': bool(poll),
            })
    df = pd.DataFrame(rows)
    df['WeightedResult'] = weighted_result(df)
    df['home_dummy'] = (~df['NeutralSite'].astype(bool)).astype(float)
    return df


def fit_logistic(df, feature_cols):
    X = df[feature_cols].values.astype(float)
    y = df['WeightedResult'].values.astype(float)
    n, k = X.shape

    def nll(beta):
        z = X @ beta
        p = 1.0 / (1.0 + np.exp(-z))
        p = np.clip(p, 1e-12, 1 - 1e-12)
        loss = -(y * np.log(p) + (1 - y) * np.log(1 - p)).sum()
        reg = RIDGE_LAMBDA * np.sum(beta[1:] ** 2)  # don't penalize the intercept (beta[0])
        return loss + reg

    x0 = np.zeros(k)
    res = minimize(nll, x0, method='BFGS')
    return dict(zip(feature_cols, res.x))


def predict(df, coefs, feature_cols):
    X = df[feature_cols].values.astype(float)
    beta = np.array([coefs[c] for c in feature_cols])
    z = X @ beta
    return 1.0 / (1.0 + np.exp(-z))


def season_split(seasons):
    seasons = sorted(seasons)
    holdout = [s for s in seasons if s >= 20212022]
    tune = [s for s in seasons if s not in holdout]
    return tune, holdout


def main():
    print("Loading archive, config, priors...")
    history_df = load_archive()
    all_seasons = history_df['Season'].unique().tolist()
    tune_seasons, holdout_seasons = season_split(all_seasons)

    config = load_config()
    elo_conf = config['models'].get('elo', {})

    lastyear_ratings = build_lastyear_ratings(history_df, tune_seasons + holdout_seasons, elo_conf)

    print("Building feature table (poll + last-year rating per game)...")
    tune_df = build_feature_df(history_df, tune_seasons, lastyear_ratings)
    holdout_df = build_feature_df(history_df, holdout_seasons, lastyear_ratings)

    # Only fit/evaluate on games where a poll actually exists for that
    # season, so poll_only and combined are judged on a consistent game
    # set (2008-09 has no poll -- see collect_uscho_polls.py's log --
    # so it's naturally excluded here rather than silently zero-filled).
    tune_with_poll = tune_df[tune_df['has_poll']].copy()
    holdout_with_poll = holdout_df[holdout_df['has_poll']].copy()

    print(f"Tune games with poll data: {len(tune_with_poll)} (seasons: {sorted(tune_with_poll['Season'].unique())})")
    print(f"Holdout games with poll data: {len(holdout_with_poll)} (seasons: {sorted(holdout_with_poll['Season'].unique())})")

    arms = {
        'poll_only': ['poll_diff', 'home_dummy'],
        'lastyear_only': ['lastyear_diff', 'home_dummy'],
        'combined': ['poll_diff', 'lastyear_diff', 'home_dummy'],
    }
    # Every arm gets an intercept column.
    for cols in arms.values():
        pass
    tune_with_poll['intercept'] = 1.0
    holdout_with_poll['intercept'] = 1.0

    coefs_by_arm = {}
    for arm_name, cols in arms.items():
        full_cols = ['intercept'] + cols
        coefs = fit_logistic(tune_with_poll, full_cols)
        coefs_by_arm[arm_name] = (coefs, full_cols)
        print(f"  {arm_name}: {coefs}")

    write_report(holdout_with_poll, coefs_by_arm)


def write_report(holdout_with_poll, coefs_by_arm):
    p1_preds_path = research_path("results", "p1_history_prior", "predictions.csv", mkdir_parent=False)
    p1_preds = None
    if p1_preds_path.exists():
        p1_preds = pd.read_csv(p1_preds_path)
        # BUG FIX: p1_history_prior.py saves Date via to_csv, which comes
        # back as a plain string on reload, not a Timestamp. Joining that
        # against this script's Timestamp-typed Date (via a MultiIndex
        # .join(), as an earlier version of this script did) doesn't raise
        # an error -- pandas silently matches only on the OTHER index
        # levels and fills every row's HomeWinProb with NaN, which then
        # silently produced Accuracy=0.000/Brier=nan for the ELO_none
        # reference row (calculate_accuracy's "0.0 on an empty non-tie
        # slice" fallback, since every "matched" WeightedResult still
        # looked normal but HomeWinProb was NaN throughout). Parsing this
        # back to a real Timestamp, and using an explicit pd.merge (not an
        # index .join()) below, fixes both the silent mismatch and removes
        # the class of bug entirely for any future caller.
        p1_preds['Date'] = pd.to_datetime(p1_preds['Date'])

    report = []
    report.append("# P4: how informative are last year's rating and the preseason poll, alone and combined?\n")
    report.append(
        "See this experiment's module docstring for the full pre-registration and method. Three static "
        "(no in-season updates) logistic-regression predictors, fit once on tune-season games with a "
        "preseason poll available, evaluated on holdout.\n"
    )
    report.append("**Fitted coefficients (tune seasons):**\n")
    for arm_name, (coefs, cols) in coefs_by_arm.items():
        report.append(f"- `{arm_name}`: " + ", ".join(f"{c}={coefs[c]:+.4f}" for c in cols))

    report.append(
        "\n\n*`poll_diff`/`lastyear_diff` coefficients are the change in log-odds per unit of that "
        "feature (poll: 1 rank position; last-year rating: 400 Elo points). A near-zero coefficient "
        "means that arm found little independent signal once its other feature(s) are in the model.*\n"
    )

    report.append("\n## Holdout: same 6 cutoffs used in P1/P1b (14-day test windows)\n")
    report.append("| Arm | Cutoff | N | Accuracy | Brier | LogLoss |")
    report.append("|---|---|---|---|---|---|")

    engine_cutoffs = _resolve_cutoff_dates(holdout_with_poll)
    for arm_name, (coefs, cols) in coefs_by_arm.items():
        holdout_with_poll[f'pred_{arm_name}'] = predict(holdout_with_poll, coefs, cols)

    for cutoff_name in CUTOFFS:
        cutoff_dates = engine_cutoffs[cutoff_name]
        window = holdout_with_poll[holdout_with_poll.apply(
            lambda r: r['Date'] >= cutoff_dates[r['Season']] and
                      r['Date'] < cutoff_dates[r['Season']] + pd.Timedelta(days=TEST_WINDOW_DAYS)
            if r['Season'] in cutoff_dates else False, axis=1)]
        if window.empty:
            continue
        for arm_name in coefs_by_arm:
            m = game_level_metrics(window[f'pred_{arm_name}'].values, window['WeightedResult'].values)
            report.append(f"| {arm_name} | {cutoff_name} | {len(window)} | {m['Accuracy']:.3f} | {m['Brier']:.4f} | {m['LogLoss']:.4f} |")
        if p1_preds is not None:
            elo_none = p1_preds[(p1_preds['Arm'] == 'ELO_none') & (p1_preds['Cutoff'] == cutoff_name) &
                                 (p1_preds['SeasonSet'] == 'holdout')]
            key = ['Season', 'Date', 'HomeTeam', 'AwayTeam']
            joined = window[key + ['WeightedResult']].merge(
                elo_none[key + ['HomeWinProb']], on=key, how='inner')
            if not joined.empty:
                m = game_level_metrics(joined['HomeWinProb'].values, joined['WeightedResult'].values)
                report.append(f"| ELO_none (in-season, from P1, reference) | {cutoff_name} | {len(joined)} | {m['Accuracy']:.3f} | {m['Brier']:.4f} | {m['LogLoss']:.4f} |")

    report.append("\n## Holdout: whole-season decay, by month\n")
    report.append("| Arm | Month | N | Accuracy | Brier | LogLoss |")
    report.append("|---|---|---|---|---|---|")
    holdout_with_poll['Month'] = holdout_with_poll['Date'].dt.strftime('%Y-%m')
    holdout_with_poll['MonthLabel'] = holdout_with_poll['Date'].dt.strftime('%b')
    for month_label, month_group in holdout_with_poll.groupby(holdout_with_poll['Date'].dt.month, sort=True):
        label = month_group['MonthLabel'].iloc[0]
        for arm_name in coefs_by_arm:
            m = game_level_metrics(month_group[f'pred_{arm_name}'].values, month_group['WeightedResult'].values)
            report.append(f"| {arm_name} | {label} | {len(month_group)} | {m['Accuracy']:.3f} | {m['Brier']:.4f} | {m['LogLoss']:.4f} |")

    out_path = research_path("reports", f"{EXPERIMENT}.md")
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\nReport written to {out_path}")


def _resolve_cutoff_dates(df):
    """{cutoff_name: {season: Timestamp}} using the same Oct/Nov/Dec/Jan
    resolution as BacktestEngine._get_cutoff_date (re-derived here directly
    since it's a pure date calculation with no games/history dependency)."""
    from src.backtesting.backtest_engine import BacktestEngine
    dummy = pd.DataFrame({'Date': [pd.Timestamp('2020-01-01')], 'Season': [20202021]})
    engine = BacktestEngine(dummy, research_path("results", EXPERIMENT, "_scratch.csv").parent)
    out = {}
    for cutoff_name in CUTOFFS:
        out[cutoff_name] = {season: engine._get_cutoff_date(season, cutoff_name) for season in df['Season'].unique()}
    return out


if __name__ == "__main__":
    main()
