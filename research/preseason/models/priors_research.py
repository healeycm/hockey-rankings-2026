# research/preseason/models/priors_research.py
"""
Research-only extension of src/rankings/priors.py (imported for its
build_model/shift_season_code helpers, never modified). Fixes G5 from
PLAN.md: production's build_prior() returns {} entirely whenever s-1 is
missing, even if s-2 exists -- this is why the 2016-17 gap season silently
zeroed out 2017-18's prior in the original backtest. Here, if s-1 is
missing we fall back to using s-2 alone (with s-1's weight added to r2's,
same "renormalize toward whatever's actually available" principle
production already uses for a team-level missing component).

This module intentionally reproduces production's blend formula rather than
importing it, since research/preseason must never import FROM production in
directions that would make production depend on research, and the reverse
(research importing a production function) is fine and already the pattern
here for build_model/shift_season_code -- but the blend math itself is
small enough, and different enough (fixes G5, may take a strength weight
directly instead of reading config.yaml), that a clean copy is clearer than
threading extra parameters through the production function's signature.
"""
import numpy as np

from src.rankings.priors import shift_season_code, _fit_prior_season_ratings  # noqa: F401 (re-exported)


def build_prior_research(full_history, target_season, model_key, models_config, r1, r2, new_team_percentile=0.20):
    """
    Same blend as production's build_prior(), but:
      - takes r1/r2 directly (for sweeping) instead of reading config.yaml
      - fixes G5: falls back to s-2 alone if s-1 is missing, instead of
        giving up entirely
      - no poll support (research doesn't need it yet; see PLAN.md P4)

    Returns ({team: prior_rating}, meta).
    """
    season_s1 = shift_season_code(target_season, 1)
    season_s2 = shift_season_code(target_season, 2)

    R1 = _fit_prior_season_ratings(full_history, season_s1, model_key, models_config)
    R2 = _fit_prior_season_ratings(full_history, season_s2, model_key, models_config)

    meta = {"season_s1_used": R1 is not None, "season_s2_used": R2 is not None}

    # G5 fix: if s-1 is missing but s-2 exists, use s-2 alone (folding r1's
    # weight into r2) instead of returning {} and losing the season entirely.
    if R1 is None and R2 is not None:
        R1, r1 = R2, r1 + r2
        R2, r2 = None, 0.0
        meta["s1_fallback_to_s2"] = True

    if R1 is None:
        return {}, meta  # genuinely no history available (both missing)

    vals1 = np.array(list(R1.values()), dtype=float)
    mu = float(np.mean(vals1))
    new_team_rating = mu + np.quantile(vals1 - mu, new_team_percentile)

    all_teams = set(R1.keys()) | set(R2.keys() if R2 else set())
    prior = {}
    for team in all_teams:
        components, weights = [], []
        if team in R1:
            components.append(R1[team] - mu)
            weights.append(r1)
        if R2 and team in R2:
            components.append(R2[team] - mu)
            weights.append(r2)

        if not components:
            prior[team] = new_team_rating
            continue

        weights_arr = np.array(weights)
        components_arr = np.array(components)
        total_w = weights_arr.sum()
        prior[team] = mu + float(np.dot(weights_arr, components_arr) / total_w) if total_w > 0 else mu

    return prior, meta
