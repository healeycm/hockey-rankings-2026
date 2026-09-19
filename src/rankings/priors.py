# src/rankings/priors.py
"""
Preseason priors: builds a {team: rating} dict on a given model's OWN rating
scale, derived from that model fit on the previous 1-2 seasons (regressed
toward the mean), optionally blended with a hand-entered preseason poll.
Used to seed ELO's starting ratings and to pull Massey's ridge target away
from zero for the first few weeks of a season -- see config.yaml's
`preseason:` block and reports/preseason_priors_results.md (the backtest
that should validate r1/r2/lambda before trusting the defaults there).

Deliberately NOT applied to NPI (it replicates the official
selection-committee formula, which has no such prior) and, by default, not
to KRACH either -- see this module's `apply_to_krach` note below.

This is a first, carryover-only cut. `w_poll` blending is wired but the poll
CSV itself (data/preseason/polls_<season>.csv) has to be hand-entered each
year from the USCHO/coaches' preseason poll; until that file exists for a
season, poll blending is a no-op regardless of `w_poll`.
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.rankings.registry import build_model

PRESEASON_DIR = Path(__file__).resolve().parents[2] / "data" / "preseason"


def shift_season_code(season_code, years_back):
    """20262027, 1 -> 20252026. Assumes the YYYYYYYY (start*10000+end) format
    used throughout this codebase (src/utils/season.py)."""
    code = int(season_code)
    start, end = code // 10000, code % 10000
    start -= years_back
    end -= years_back
    return start * 10000 + end


def _fit_prior_season_ratings(full_history, season_code, model_key, models_config):
    """Fits `model_key` on one prior season's games (if present in
    full_history) and returns its {team: rating} dict, or None if that
    season has no data (e.g. the missing 2016-17 gap season, or a season
    older than the archive)."""
    season_df = full_history[full_history['Season'] == season_code].copy()
    if season_df.empty:
        return None
    model, _, _ = build_model(model_key, season_df, models_config, history_df=full_history)
    model.fit()
    if not model.ratings:
        return None
    return dict(model.ratings)


def build_prior(full_history, target_season, model_key, config):
    """
    Returns ({team: prior_rating}, meta) where meta records what actually
    went into the blend (which prior seasons were found, whether a poll was
    used) -- useful for the site to show "preseason rating, not yet fit on
    real games" transparently rather than silently.

    prior_rating = mu + r1*(R1 - mu) + r2*(R2 - mu) [+ w_poll*(Poll - mu)]
    where mu is the mean rating of the season-1-ago fit (the most reliable
    anchor available), R1/R2 are a team's ratings in seasons s-1/s-2, and
    weights are renormalized when a component is missing for a team (no
    history at all -> percentile-based rating instead, see below).
    """
    ps_conf = config.get('models', {}).get('preseason', {}) if 'models' in config else config
    r1_w = ps_conf.get('r1', 0.6)
    r2_w = ps_conf.get('r2', 0.15)
    w_poll = ps_conf.get('w_poll', 0.0)
    new_team_pct = ps_conf.get('new_team_percentile', 0.20)
    models_config = config.get('models', config)

    season_s1 = shift_season_code(target_season, 1)
    season_s2 = shift_season_code(target_season, 2)

    R1 = _fit_prior_season_ratings(full_history, season_s1, model_key, models_config)
    R2 = _fit_prior_season_ratings(full_history, season_s2, model_key, models_config)

    meta = {"season_s1_used": R1 is not None, "season_s2_used": R2 is not None, "poll_used": False}

    if R1 is None:
        # No prior-season data at all (first season on record for this
        # program, or archive doesn't go back far enough) -- nothing to
        # carry over.
        return {}, meta

    vals1 = np.array(list(R1.values()), dtype=float)
    mu = float(np.mean(vals1))
    sigma = float(np.std(vals1)) or 1.0
    new_team_rating = mu + np.quantile(vals1 - mu, new_team_pct)

    poll_ratings = {}
    if w_poll > 0:
        poll_ratings = _load_poll_as_ratings(target_season, mu, sigma)
        meta["poll_used"] = bool(poll_ratings)

    all_teams = set(R1.keys()) | set(R2.keys() if R2 else set()) | set(poll_ratings.keys())
    prior = {}
    for team in all_teams:
        components, weights = [], []
        if team in R1:
            components.append(R1[team] - mu)
            weights.append(r1_w)
        if R2 and team in R2:
            components.append(R2[team] - mu)
            weights.append(r2_w)
        if team in poll_ratings:
            components.append(poll_ratings[team] - mu)
            weights.append(w_poll)

        if not components:
            prior[team] = new_team_rating
            continue

        # Renormalize so a team missing a component (e.g. no s-2 data) isn't
        # penalized toward the mean just for that -- keep the SHAPE of the
        # blend the same, scaled up to use the full carryover weight
        # available for that team.
        weights = np.array(weights)
        components = np.array(components)
        total_w = weights.sum()
        prior[team] = mu + float(np.dot(weights, components) / total_w) if total_w > 0 else mu

    return prior, meta


def _load_poll_as_ratings(target_season, mu, sigma):
    """
    Reads data/preseason/polls_<season>.csv (columns: Team, Rank, Points --
    the standard USCHO/coaches' poll format) and converts it to the target
    model's rating scale via a simple z-scored linear map (points ->
    z-score across the field -> mu + z*sigma). This is a placeholder
    conversion -- reports/preseason_priors_results.md's backtest should
    replace it with a fitted regression once enough historical polls are
    collected (see the plan's caveat on this).
    """
    poll_path = PRESEASON_DIR / f"polls_{target_season}.csv"
    if not poll_path.exists():
        return {}
    try:
        df = pd.read_csv(poll_path)
    except Exception:
        return {}
    if 'Team' not in df.columns or 'Points' not in df.columns or df.empty:
        return {}

    points = df['Points'].astype(float)
    p_mu, p_sigma = points.mean(), (points.std() or 1.0)
    z = (points - p_mu) / p_sigma
    ratings = mu + z * sigma
    return dict(zip(df['Team'], ratings))
