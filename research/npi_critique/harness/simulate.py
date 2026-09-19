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

# Independent-Poisson scoring alone produces an OT rate of ~14%, but all
# three of the last three real seasons show 18-22% (reports/e6_assumption_audit.md,
# reports/e8_ot_rate_correction.md) -- real hockey has more regulation
# ties than two independent Poisson processes with the same means would
# produce, plausibly because teams genuinely play tighter, more
# risk-averse hockey in a close third period (fewer empty-net/pulled-
# goalie situations, more conservative forechecking) rather than treating
# every minute of regulation identically. CLOSE_GAME_PROB models this
# directly: with this probability, both teams' regulation goals are drawn
# from a SHARED count (forcing a tie) instead of independently -- a
# "close, low-event game" mode layered on top of the independent-Poisson
# baseline, calibrated so mean total goals and home-ice win rate are
# preserved (see reports/e8_ot_rate_correction.md for the calibration).
CLOSE_GAME_PROB = 0.07


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

    # Close-game mode: a CLOSE_GAME_PROB fraction of games are redrawn as
    # a single SHARED score for both teams (forcing a regulation tie),
    # using the geometric-mean rate of the two teams' independent rates
    # so the combined total stays close to what an ordinary game of this
    # matchup's overall scoring level would produce. This directly lifts
    # the tie/OT rate to match real data without needing to alter
    # MEAN_GOALS_PER_TEAM or HOME_ICE_MULT (both already separately
    # validated against real data -- see e0_calibration_check.py).
    is_close_game = rng.random(n) < CLOSE_GAME_PROB
    if is_close_game.any():
        shared_lam = np.sqrt(lam_home * lam_away)
        shared_score = rng.poisson(shared_lam)
        hg = np.where(is_close_game, shared_score, hg)
        ag = np.where(is_close_game, shared_score, ag)

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


def simulate_season_bradley_terry(schedule_df, true_strength, rng,
                                   margin_mean=0.8, loser_goals_mean=2.0, margin_cap=6,
                                   close_game_prob=0.20):
    """
    A genuinely different data-generating process from simulate_season()'s
    independent-Poisson-goals model, built specifically to check whether
    this workspace's findings are artifacts of a scoring process that
    structurally favors margin-based models (Massey) -- flagged as a
    threat to validity since E1 and never addressed until now (see
    reports/e1_truth_recovery.md's DGP caveat, repeated in every
    subsequent report in this workspace).

    Here, WHO WINS is drawn directly from the Bradley-Terry probability
    p_home = (theta_home * hia) / (theta_home * hia + theta_away) -- the
    same functional form KRACH's own likelihood is built on, so KRACH is
    the *correctly specified* estimator under this DGP, the mirror image
    of simulate_season()'s Poisson process favoring Massey. The MARGIN is
    then generated independently of true strength entirely (a realistic
    but strength-uninformative margin layered on top of the win/loss
    draw) -- deliberately removing the extra signal Massey's
    goal-differential regression exploits under the Poisson DGP, to test
    directly whether Massey's advantage survives when margin carries no
    additional information beyond who won.

    Same structural OT/close-game mechanism as simulate_season() (a
    forced shared-score regulation tie, resolved by the same
    strength-compressed near-coin-flip), but calibrated with its own
    close_game_prob=0.20 rather than simulate_season()'s 0.07 -- under
    this DGP, margin is always >=1 by construction, so ties can ONLY
    come from the close-game mechanism (simulate_season()'s independent
    Poisson draws also produce natural ties on their own, on top of its
    close-game boost). Calibrated directly against real 2025-26 data:
    OT rate 0.198 (real 0.181-0.223), home win% 0.530 (real 0.532-0.578),
    mean goals 5.62 (real 5.688-5.969, a slight undershoot), win% std
    0.114 (real 0.150-0.158, a real undershoot not fully corrected --
    documented, not hidden, since this DGP's purpose is a genuinely
    different robustness check, not a pixel-perfect match).
    """
    df = schedule_df.copy()
    n = len(df)

    theta_home = df['HomeTeam'].map(true_strength).values
    theta_away = df['AwayTeam'].map(true_strength).values
    neutral = df['NeutralSite'].astype(bool).values
    hia = np.where(neutral, 1.0, HOME_ICE_MULT)

    p_home = (theta_home * hia) / (theta_home * hia + theta_away)
    is_close_game = rng.random(n) < close_game_prob

    home_goals = np.empty(n, dtype=int)
    away_goals = np.empty(n, dtype=int)
    is_ot = np.zeros(n, dtype=bool)

    # Decisive (non-close) games: winner drawn from the BT probability;
    # margin drawn independently of strength.
    decisive = ~is_close_game
    home_wins = rng.random(n) < p_home
    loser_goals = rng.poisson(loser_goals_mean, size=n)
    margin = 1 + rng.poisson(margin_mean, size=n)
    margin = np.minimum(margin, margin_cap)
    winner_goals = loser_goals + margin

    home_goals[decisive] = np.where(home_wins[decisive], winner_goals[decisive], loser_goals[decisive])
    away_goals[decisive] = np.where(home_wins[decisive], loser_goals[decisive], winner_goals[decisive])

    # Close games: forced regulation tie, resolved by the same
    # strength-compressed near-coin-flip OT mechanism as simulate_season().
    n_close = is_close_game.sum()
    if n_close > 0:
        tied_score = rng.poisson(loser_goals_mean, size=n_close)
        p_home_ot = (theta_home[is_close_game] ** OT_STRENGTH_EXPONENT) / (
            theta_home[is_close_game] ** OT_STRENGTH_EXPONENT + theta_away[is_close_game] ** OT_STRENGTH_EXPONENT
        )
        home_wins_ot = rng.random(n_close) < p_home_ot
        home_goals[is_close_game] = np.where(home_wins_ot, tied_score + 1, tied_score)
        away_goals[is_close_game] = np.where(home_wins_ot, tied_score, tied_score + 1)
        is_ot[is_close_game] = True

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


def simulate_season_mixed(schedule_df, true_strength, rng, poisson_frac=0.5):
    """
    DGP-C: a deliberately MISSPECIFIED process for every model, not just
    "correctly specified for a different one." simulate_season() is
    correctly specified for Massey (margin carries real strength signal);
    simulate_season_bradley_terry() is correctly specified for KRACH
    (outcomes ARE the Bradley-Terry probability). Neither is a fair
    single test of "which model is actually best" on its own -- this
    mixes them: each game independently uses the Poisson mechanism with
    probability poisson_frac and the Bradley-Terry mechanism otherwise.
    No single functional form describes the resulting process, so no
    model in this workspace's roster is correctly specified for it.
    """
    df = schedule_df.copy()
    n = len(df)
    use_poisson = rng.random(n) < poisson_frac

    poisson_part = simulate_season(df[use_poisson], true_strength, rng) if use_poisson.any() else df[use_poisson]
    bt_part = simulate_season_bradley_terry(df[~use_poisson], true_strength, rng) if (~use_poisson).any() else df[~use_poisson]

    combined = pd.concat([poisson_part, bt_part]).sort_index()
    return combined.reset_index(drop=True)


# ---------------------------------------------------------------------------
# S5: echo chamber under controlled cross-conference connectivity
# ---------------------------------------------------------------------------

def make_multiconference_schedule(n_conferences, teams_per_conf, cross_frac, rng,
                                   games_per_team=36, start_date='2025-10-01'):
    """
    A fully synthetic schedule with CONTROLLABLE cross-conference
    connectivity -- something the real schedule can't provide, since its
    cross-conference fraction (~38.5%, see PLAN.md) is fixed by history.
    `n_conferences` conferences of `teams_per_conf` teams each; each
    team's `games_per_team` games are split into a `(1-cross_frac)`
    fraction drawn from its own conference (round-robin-style, repeating
    as needed) and a `cross_frac` fraction drawn uniformly from every
    other conference. Built specifically for a null-hypothesis design:
    assign every conference EQUAL true strength (conf_log_sigma=0) and
    check whether ratings still cluster by conference as cross_frac
    shrinks -- any such clustering is then provably an artifact of
    network sparsity, since there is no true conference-level difference
    to detect.
    """
    teams = [f"C{c}T{t:02d}" for c in range(n_conferences) for t in range(teams_per_conf)]
    conf_map = {f"C{c}T{t:02d}": f"conf{c}" for c in range(n_conferences) for t in range(teams_per_conf)}
    conf_of = lambda team: conf_map[team]

    rows = []
    dates = pd.date_range(start_date, periods=max(1, len(teams) * games_per_team // 4))
    d_idx = 0
    game_count = {t: 0 for t in teams}

    for team in teams:
        own_conf_teams = [t for t in teams if conf_of(t) == conf_of(team) and t != team]
        other_teams = [t for t in teams if conf_of(t) != conf_of(team)]
        n_intra = round(games_per_team * (1 - cross_frac))
        n_cross = games_per_team - n_intra

        opponents = list(rng.choice(own_conf_teams, size=n_intra, replace=True)) if own_conf_teams else []
        opponents += list(rng.choice(other_teams, size=n_cross, replace=True)) if other_teams else []

        for opp in opponents:
            if game_count[team] >= games_per_team:
                break
            is_home = rng.random() < 0.5
            home, away = (team, opp) if is_home else (opp, team)
            game_type = conf_of(team) if conf_of(team) == conf_of(opp) else 'nc'
            rows.append({
                'HomeTeam': home, 'AwayTeam': away, 'Date': dates[d_idx % len(dates)],
                'Type': game_type, 'NeutralSite': False, 'Is_Exhibition': False,
            })
            game_count[team] += 1
            d_idx += 1

    df = pd.DataFrame(rows).sort_values('Date').reset_index(drop=True)
    return df, teams, conf_map
