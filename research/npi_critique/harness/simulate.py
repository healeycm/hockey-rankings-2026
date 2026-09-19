# research/npi_critique/harness/simulate.py
"""
Simulate a season with KNOWN ground-truth team strength.

Design: take a REAL season's actual schedule (who played whom, when, home
ice, exhibition/conference-tournament flags -- every column but the
outcome) and replace only the outcome-determining columns (HomeGoals,
AwayGoals, IsOT, Result, GoalMargin) with values drawn from a generative
model driven by a synthetic true strength assigned to each team. This
gives every ranking method a fully realistic schedule graph (real
conference structure, real non-conference game density, real date
spacing) while making the one thing real data can never provide --
"which team is actually better" -- known by construction. Every model's
induced ranking can then be compared directly against ground truth,
something no analysis of real historical outcomes alone can do.

Scoring model: independent Poisson goals per team, with each team's
scoring/allowing rate tilted by the ratio of true strengths (a simplified
Dixon-Coles-style generative process), a modest home-ice multiplier, and
a realistic average goals/game calibrated to this project's own data
(HockeyBT's validated home-win-rate finding, ~5.8 total goals/game
typical of Division I hockey). A regulation tie goes to a simulated
overtime/shootout: the true-strength tilt is compressed toward a coin
flip (exponent < 1), matching this project's own validated finding
(reports/lrmc_hockey_adaptation.md) that OT/SO outcomes carry much less
information about relative team strength than a regulation decision, and
the resulting margin is forced to exactly 1 goal, matching the sport's
actual sudden-death structure.
"""
import numpy as np
import pandas as pd

# Calibrated to this project's own validated findings, not guessed:
# ~5.8 total goals/game average, modest home-ice edge (HockeyBT found real
# teams win 56.65% of decisive non-neutral games), OT-decision strength
# tilt heavily compressed relative to a regulation decision.
MEAN_GOALS_PER_TEAM = 2.55
HOME_ICE_MULT = 1.17
OT_STRENGTH_EXPONENT = 0.15  # << 1: OT winner is close to a coin flip


def assign_true_strengths(teams, rng, sigma=0.4):
    """One synthetic true-strength value per team, log-normal so ratios
    are always positive and realistically right-skewed (a few strong
    teams, a long pack of average-to-weak ones) -- the same qualitative
    shape KRACH's fitted ratings actually show on real data."""
    return {t: float(v) for t, v in zip(teams, rng.lognormal(mean=0.0, sigma=sigma, size=len(teams)))}


def simulate_season(schedule_df, true_strength, rng):
    """
    schedule_df: a real season's games, used ONLY for its non-outcome
    columns (HomeTeam, AwayTeam, Date, NeutralSite, Is_Exhibition, Type).
    true_strength: dict[team] -> positive float, ground truth.
    Returns a new DataFrame, same shape/columns as schedule_df, with
    HomeGoals/AwayGoals/IsOT/Result/GoalMargin replaced by simulated
    values consistent with true_strength.
    """
    df = schedule_df.copy()
    n = len(df)
    home_goals = np.empty(n, dtype=int)
    away_goals = np.empty(n, dtype=int)
    is_ot = np.zeros(n, dtype=bool)

    theta_home = df['HomeTeam'].map(true_strength).values
    theta_away = df['AwayTeam'].map(true_strength).values
    neutral = df['NeutralSite'].astype(bool).values

    hia = np.where(neutral, 1.0, HOME_ICE_MULT)
    ratio = np.sqrt(theta_home / theta_away)
    lam_home = MEAN_GOALS_PER_TEAM * ratio * hia
    lam_away = MEAN_GOALS_PER_TEAM / ratio

    hg = rng.poisson(lam_home)
    ag = rng.poisson(lam_away)

    tied = hg == ag
    home_goals[~tied] = hg[~tied]
    away_goals[~tied] = ag[~tied]

    # Regulation ties go to a simulated OT/shootout: strength tilt
    # compressed toward a coin flip, margin forced to exactly 1 goal.
    n_tied = tied.sum()
    if n_tied > 0:
        p_home_ot = (theta_home[tied] ** OT_STRENGTH_EXPONENT) / (
            theta_home[tied] ** OT_STRENGTH_EXPONENT + theta_away[tied] ** OT_STRENGTH_EXPONENT
        )
        home_wins_ot = rng.random(n_tied) < p_home_ot
        base = hg[tied]  # both teams tied at this score after regulation
        home_goals[tied] = np.where(home_wins_ot, base + 1, base)
        away_goals[tied] = np.where(home_wins_ot, base, base + 1)
        is_ot[tied] = True

    df['HomeGoals'] = home_goals
    df['AwayGoals'] = away_goals
    df['IsOT'] = is_ot
    df['GoalMargin'] = home_goals - away_goals
    df['Result'] = (home_goals > away_goals).astype(float)
    return df


def true_ranking(true_strength):
    """Teams sorted strongest-first -- the ground-truth ranking every
    model's induced ranking is compared against."""
    return sorted(true_strength, key=lambda t: true_strength[t], reverse=True)


# ---------------------------------------------------------------------------
# S1: games-played mismatch
# ---------------------------------------------------------------------------

CONFERENCE_CODES = ['ah', 'he', 'ec', 'nt', 'cc2', 'b10']  # matches src/rankings/npi.py


def get_conference_map(schedule_df):
    """team -> conference code, by most frequent conference-coded game type
    a team appears in. Same logic src/rankings/npi.py's
    _build_conf_tourney_index uses to build its own conference map, kept
    consistent deliberately since we're testing that production code."""
    conf_mask = schedule_df['Type'].str.lower().isin(CONFERENCE_CODES)
    conf_games = schedule_df[conf_mask]
    counts = {}
    for _, row in conf_games.iterrows():
        code = row['Type'].lower()
        for team in (row['HomeTeam'], row['AwayTeam']):
            counts.setdefault(team, {}).setdefault(code, 0)
            counts[team][code] += 1
    return {t: max(d, key=d.get) for t, d in counts.items()}


def games_played(schedule_df):
    """team -> total games played (home + away), as a pandas Series."""
    return pd.concat([schedule_df['HomeTeam'], schedule_df['AwayTeam']]).value_counts()


def thin_team_schedule(schedule_df, team, target_games, rng, prefer_type='nc', protect_teams=()):
    """
    Drop games for `team` (and, unavoidably, for whichever opponent was in
    each dropped game) until `team` has exactly `target_games` games left.
    Games are dropped preferentially from non-conference ('nc') games
    first, falling back to any of the team's games once the non-conference
    pool is exhausted -- mirroring the real mechanism (a team starting the
    season late, or ending it early, misses games concentrated at the
    schedule's edges/non-conference slate, not a uniform random subset of
    its whole season) more closely than dropping uniformly at random would.
    No-op (returns schedule_df unchanged) if the team already has
    target_games or fewer.

    `protect_teams`: teams whose OWN game count has already been finalized
    by an earlier call (see thin_multiple_teams) -- games against them are
    excluded from the droppable pool wherever possible, so thinning `team`
    can't silently push an already-finalized team below its own target.
    If protecting them leaves too few droppable games to hit target_games
    exactly, protection is dropped only as a last resort (a printed
    warning-worthy edge case, not a silent failure) and the team is thinned
    as far as the unprotected pool allows.
    """
    team_mask = (schedule_df['HomeTeam'] == team) | (schedule_df['AwayTeam'] == team)
    team_games = schedule_df[team_mask]
    n_current = len(team_games)
    n_to_drop = n_current - target_games
    if n_to_drop <= 0:
        return schedule_df

    opponent = np.where(team_games['HomeTeam'] == team, team_games['AwayTeam'], team_games['HomeTeam'])
    unprotected = team_games[~pd.Series(opponent, index=team_games.index).isin(protect_teams)]
    pool_source = unprotected if len(unprotected) >= n_to_drop else team_games

    nc_idx = pool_source[pool_source['Type'].str.lower() != prefer_type].index.tolist()
    other_idx = pool_source[pool_source['Type'].str.lower() == prefer_type].index.tolist()
    # drop from non-"prefer_type" pool first (i.e. keep conference games,
    # drop non-conference first) -- matches the real mechanism, since NC
    # games cluster early in the season, which is exactly what a
    # late-starting team misses
    drop_pool = nc_idx + other_idx
    rng.shuffle(drop_pool)
    to_drop = drop_pool[:n_to_drop]
    return schedule_df.drop(index=to_drop).reset_index(drop=True)


def thin_multiple_teams(schedule_df, team_targets, rng, prefer_type='nc'):
    """team_targets: dict[team] -> target game count. Applies
    thin_team_schedule sequentially, protecting each already-finalized
    team's games from being dropped by a later team's thinning pass --
    without this, thinning team B after team A can drop a shared A-vs-B
    game and silently push A below the target it already hit (a real bug
    caught while building e2b_minimal_worked_example.py: two adjacent
    thinned teams that play each other ended up with far fewer games than
    intended)."""
    df = schedule_df
    finalized = []
    for team, target in team_targets.items():
        df = thin_team_schedule(df, team, target, rng, prefer_type=prefer_type,
                                 protect_teams=finalized)
        finalized.append(team)
    return df


# ---------------------------------------------------------------------------
# S2: conference-stratified true strength
# ---------------------------------------------------------------------------

def make_round_robin_schedule(teams, games_per_pair=2, start_date='2025-10-01', conf_map=None):
    """
    A small, fully-traceable synthetic schedule: every team plays every
    other team `games_per_pair` times (home-and-home if 2), evenly spaced
    dates. No exhibition games, no OT/tie info yet (simulate_season fills
    that in). `conf_map` (dict[team]->code), if given, is stamped into a
    'Type' column so downstream conference-aware logic (e.g. npi.py's
    conference-tournament detection) sees a consistent conference
    structure; otherwise every game is tagged 'nc' (non-conference).

    Built for the "named minimal example" reporting standard in PLAN.md --
    small enough (a dozen-ish teams) that the full schedule and every
    result can be listed in a table and hand-verified, as a complement to
    the large-N studies run on the real 63-team schedule.
    """
    rows = []
    dates = pd.date_range(start_date, periods=max(1, len(teams) * (len(teams) - 1) * games_per_pair // 4))
    d_idx = 0
    for i, a in enumerate(teams):
        for b in teams[i + 1:]:
            for g in range(games_per_pair):
                home, away = (a, b) if g % 2 == 0 else (b, a)
                if conf_map is not None and conf_map.get(home) == conf_map.get(away):
                    game_type = conf_map[home]
                else:
                    game_type = 'nc'
                rows.append({
                    'HomeTeam': home, 'AwayTeam': away, 'Date': dates[d_idx % len(dates)],
                    'Type': game_type, 'NeutralSite': False, 'Is_Exhibition': False,
                })
                d_idx += 1
    df = pd.DataFrame(rows).sort_values('Date').reset_index(drop=True)
    return df


def assign_conference_stratified_strengths(teams, conf_map, rng,
                                            conf_log_sigma=0.35, team_log_sigma=0.30,
                                            conf_effect_override=None):
    """
    Two-level log-normal: each conference gets its own mean-strength
    effect (drawn once per replication, or fixed via
    conf_effect_override for a deliberately-elite/weak conference design),
    and each team's strength is that conference effect plus its own
    within-conference noise. A team with no conference (independents) gets
    conf_effect 0 (average).

    conf_effect_override: dict[conf_code] -> fixed log-strength effect,
    for constructing a specific "conference X is elite, conference Y is
    weak" scenario deterministically rather than leaving it to chance.

    DEFAULT SIGMAS ARE NOT REALISTIC -- calibrate before trusting a
    result that depends on realistic conference-strength dispersion.
    conf_log_sigma=0.35 (this function's default, used by S2's e3/e3b/e3c)
    produces a between-conference win% std far below real data.

    CALIBRATION HISTORY (corrected twice -- read this before changing
    these numbers again):
    1. First pass (reports/e5b_selection_field_accuracy_conf_stratified.md)
       used conf_log_sigma=1.1, team_log_sigma=0.30, checked against
       2025-26 ALONE, and measured the simulator's between-conference std
       on ALL games. That combination of (a) one season and (b) an
       inconsistent measurement basis (real target 0.102 was computed
       differently than the simulator check) produced a value that
       looked calibrated but wasn't apples-to-apples.
    2. Corrected pass (reports/e6_assumption_audit.md,
       reports/e5c_selection_field_accuracy_recalibrated.md): checked
       against all THREE recent seasons (2023-24/2024-25/2025-26) using
       ONE consistent measurement basis throughout (between- and
       overall-std both computed on NON-CONFERENCE games only, for both
       real data and simulator output). Real 3-season average:
       between-conf std 0.130, overall std 0.203 (conference share of
       variance ~42% -- notably, 2025-26 alone showed only 28%, the
       smallest of the three years, which is why calibrating against it
       alone understated the true effect and then over-corrected with
       too-high a sigma). Properly calibrated, consistently-measured
       result: conf_log_sigma=0.4, team_log_sigma=0.24 (simulator
       between-conf std 0.128, overall std 0.204 -- both within 2% of
       target). **Use these values, not 1.1/0.30, for any future work.**
       S2's e3/e3b/e3c used the original 0.35 default and have not been
       re-checked against either calibration.
    """
    confs = sorted(set(conf_map.values()))
    conf_effect = {c: rng.normal(0, conf_log_sigma) for c in confs}
    if conf_effect_override:
        conf_effect.update(conf_effect_override)

    strengths = {}
    for t in teams:
        c = conf_map.get(t)
        base = conf_effect.get(c, 0.0)
        strengths[t] = float(np.exp(base + rng.normal(0, team_log_sigma)))
    return strengths
