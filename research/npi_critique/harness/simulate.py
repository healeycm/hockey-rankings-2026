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
