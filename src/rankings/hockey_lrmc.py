# src/rankings/hockey_lrmc.py
"""
HockeyLRMC: an LRMC variant adapted to hockey's specific scoring structure,
rather than the basketball assumptions (~150 points/game resolution) the
base LRMC (Kvam & Sokol) was designed around.

Motivating diagnosis (see reports/lrmc_hockey_adaptation.md for full detail):
LRMC_Classic systematically under-ranks teams that win a lot of close,
low-margin games relative to KRACH — e.g. on the 2025-26 season, Cornell
(22-12) ranked #14 by KRACH but #40 by LRMC_Classic; Dartmouth similarly
dropped ~27 spots. This is NOT a normalization bug (games-played denominators
check out correctly) — it's two real, hockey-specific modeling gaps:

1. The base LRMC fits a single alpha/beta logistic relating goal margin to
   "the home team is truly better", where alpha correctly discounts a
   home win for the built-in home-ice edge (verified: fitted alpha is
   negative, so e.g. a 1-goal home win nets prob_home_better < 0.5 — this
   is the intended Kvam-Sokol home discount, not a sign bug). But OT/SO
   games ALWAYS end with a goal margin of exactly 1 (sudden death), and
   that margin carries far less information about true team strength than
   the same margin in regulation (OT outcomes are close to a coin flip).
   The base implementation runs OT games through the exact same
   margin-sensitive alpha/beta as a razor-thin regulation win, which
   over-punishes/over-credits OT results. Hockey has a much higher rate of
   OT/SO decisions than most sports LRMC has been applied to, so this
   matters more here than it would elsewhere.
2. Conference-silo connectivity: ECAC/Ivy teams play a large fraction of
   their schedule within a semi-isolated sub-conference, so #1's mis-scoring
   of in-conference games (heavy on close/OT results) compounds with fewer
   cross-conference "bridge" games to correct it. NOTE: this turned out to
   be a consequence of #1, not an independent problem — see the
   `prior_weight` config note below. A uniform-shrinkage attempt at
   addressing connectivity directly was tried and backtested off (it made
   things worse); fixing #1 turned out to be the real fix for both.

Net effect (see reports/lrmc_hockey_adaptation.md for full backtest tables):
this variant beats LRMC_Classic on every tested season/cutoff (accuracy
+2.7 to +4.6pp, better Brier/LogLoss too) and roughly halves the ECAC/Ivy
mean-rank gap to KRACH, though it does not fully close the gap to KRACH/NPI.
"""
import numpy as np
import pandas as pd
from scipy.linalg import eig

from src.rankings.lrmc import LRMC


class HockeyLRMC(LRMC):
    def __init__(self, games_df, config=None, history_df=None):
        super().__init__(games_df, config, history_df)

        hockey_defaults = {
            # Hockey games are decided by far fewer goals than a basketball
            # score line has points; a 3-goal cap is still fairly generous
            # (median margin is 1-2 goals). Kept as a tunable, not hardcoded.
            'margin_cap': 3,

            # OT/SO games get a FIXED, low-confidence vote instead of being
            # run through the regulation-fitted alpha/beta. `ot_confidence`
            # is the vote given to the OT winner above a coin flip (e.g.
            # 0.08 -> winner gets prob_home_better=0.58/0.42 rather than
            # whatever the regulation logistic would assign to a 1-goal
            # margin). A fixed constant (rather than a freshly-fit
            # alpha_ot/beta_ot) is used deliberately: OT games are too few,
            # and too structurally different (margin is always exactly 1),
            # to fit a reliable *and correctly-signed* logistic on directly
            # — see reports/lrmc_hockey_adaptation.md for why a fresh fit
            # was tried and rejected in favor of this simpler, transparent
            # rule. Tune via backtest (tests/*lrmc* sweep).
            'ot_confidence': 0.08,

            # LRMC experiment (2026, see reports/lrmc_experiments_2026.md):
            # every OT/SO game gets the SAME fixed vote above regardless of
            # how many extra periods it took to decide — a game that
            # reached 3OT or 5OT was a closer, longer coin flip than one
            # decided in the first 5 minutes of a single OT, so lumping
            # them together throws away real information the scraped data
            # already carries (the 'OT_Info' column: 'OT'/'2OT'/'3OT'/
            # '5OT'). When enabled, the vote decays toward a pure coin flip
            # as periods increase: conf(periods) = ot_confidence *
            # ot_confidence_decay^(periods-1) — e.g. with the defaults
            # below, 1OT keeps the full 0.08, 2OT gets 0.04, 3OT gets 0.02.
            # A game whose OT_Info is missing/unparseable (or the column
            # doesn't exist at all, e.g. synthetic Monte Carlo games) is
            # treated as a single OT period, so this is a strict
            # generalization of the old behavior, not a change to it —
            # confirmed by `ot_confidence_decay=1.0` reproducing the old
            # fixed-vote behavior exactly (decay^n == 1 for all n).
            # DEFAULT OFF pending backtest validation — see that report for
            # the result before flipping this on.
            'graduated_ot_confidence': False,
            'ot_confidence_decay': 0.5,

            # Empty-net correction. Two layers:
            #  1. REAL data: if Home_ENG/Away_ENG (empty-net-goal counts,
            #     scraped from CHN box scores — src/data/advanced_metrics_scraper.py
            #     extract_empty_net_goals(), backfilled via
            #     src/data/backfill_eng.py) are present for a game, those
            #     goals are subtracted from the margin before capping — an
            #     empty-net goal only happens once the trailing team has
            #     already pulled its goalie, i.e. the competitive game was
            #     already decided, so it shouldn't count as evidence of "how
            #     much better" the winner is.
            #     DEFAULT OFF. The reasoning above is sound and the data is
            #     real (not a proxy) — 27% of covered games have >=1 ENG —
            #     but it does NOT help: ablated on the two ENG-covered
            #     seasons (2024-25, 2025-26; 8 splits), it came out WORST of
            #     the three arms on accuracy/Brier/LogLoss, winning only 3
            #     of 8 splits, and an independent paired per-game test
            #     (n=3097) put it significantly BEHIND no-correction
            #     (Brier +0.00048, p<0.0001). Likely because margin_cap=3
            #     already absorbs most ENG inflation (an ENG usually turns a
            #     1-goal game into 2, or 2 into 3 — inside the cap, where
            #     the fitted logistic is fairly flat), so subtracting them
            #     discards about as much real signal as noise. See
            #     reports/lrmc_empty_net.md.
            #  2. PROXY fallback for games without real ENG data (older
            #     seasons, teams outside the CHN name mapping): the original
            #     blind heuristic (shrink a 2-goal margin toward 1.75).
            #     DEFAULT OFF — backtested pre-real-data and found
            #     statistically indistinguishable from off (<0.2pp either
            #     way). See reports/lrmc_hockey_adaptation.md for the
            #     real-data re-test results; re-validate before flipping this
            #     back on.
            'use_real_eng': False,
            'empty_net_shrink': False,
            'empty_net_shrink_factor': 0.75,  # 2 -> 1.75. See _apply_empty_net_shrink.

            # Conference-silo regularization via the base LRMC's existing
            # uniform-prior `prior_weight` blend. DEFAULT OFF (0.0, matching
            # the parent): backtested at 0.0/0.05/0.15 specifically on
            # ECAC/Ivy-involving games (where the silo problem is worst) and
            # it made accuracy monotonically WORSE at every nonzero setting
            # tested (e.g. 2025-26 season, Jan cutoff: ECAC accuracy 73.1%
            # at 0.0 -> 72.3% at 0.05 -> the trend continues down as weight
            # increases). A uniform blend toward the whole-field average
            # apparently just dilutes real signal rather than fixing the
            # actual problem — which turned out to be the OT/margin handling
            # above, not sparse connectivity per se. Left available/tunable
            # for further experimentation (e.g. a proper hierarchical
            # shrink-toward-conference-mean prior might behave differently),
            # but do not flip this default back on without re-validating.
            'prior_weight': 0.0,

            # Prediction calibration (Platt-scaling style). See
            # _calibrate_predictions() docstring: LRMC's rating estimation
            # and its predict() formula were never tied together the way
            # KRACH's are, so the raw log(r_home/r_away) isn't guaranteed to
            # already be on the right scale to use as a logit directly. That
            # diagnosis is correct (a single-slice check found the raw
            # log-ratio needed ~4.7x scaling to match KRACH's spread) but
            # the practical fix tried here — an in-sample logistic fit of
            # [is_home_ice, log_ratio] -> actual outcome, using the SAME
            # games used to estimate the ratings — does NOT hold up.
            # DEFAULT OFF: backtested (5-year/20-split, shrinkage swept
            # 0.0-1.0) and LogLoss gets monotonically WORSE with any amount
            # of calibration applied (0.704 at shrink=0 -> 0.715 at just
            # shrink=0.1 -> 0.851 at shrink=1.0, i.e. the raw unshrunk fit).
            # Brier improves marginally (~1%) up to shrink~0.2-0.3 before
            # also turning back up, but not enough to justify the LogLoss
            # cost. Root cause: in-sample Platt scaling here is fitting
            # noise already baked into the ratings, not a genuine
            # generalizable mis-scaling — a proper fix would need a true
            # held-out split (temporal holdout or k-fold) rather than
            # calibrating against the exact games the ratings were built
            # from. See reports/lrmc_calibration.md for the full sweep.
            # Left in/tunable for anyone who wants to prioritize Brier over
            # LogLoss specifically, or to build the held-out version.
            'calibrate_predictions': False,
            'calibration_shrinkage': 1.0,

            # LRMC experiment (2026, see reports/lrmc_experiments_2026.md):
            # a genuinely held-out version of the calibration above. The
            # in-sample version's failure mode was diagnosed precisely: it
            # calibrates against the SAME games used to estimate the
            # ratings, so it partly re-fits noise already baked into those
            # ratings rather than a real, generalizable mis-scaling. This
            # follows Massey's `fit_beta` pattern (see massey.py) exactly:
            # split self.games temporally, fit RATINGS on only the earlier
            # `1 - held_out_calib_frac` portion (a fresh, throwaway
            # HockeyLRMC instance), then fit the [is_home_ice, log_ratio]
            # -> outcome logistic against the later portion's ACTUAL
            # outcomes using THOSE ratings' predictions — genuinely
            # out-of-sample relative to the ratings used to generate them.
            # Independent of `calibrate_predictions`/`calibration_shrinkage`
            # above (mutually exclusive — enabling this skips the in-sample
            # path entirely rather than composing with it).
            'held_out_calibration': False,
            'held_out_calibration_frac': 0.2,
            'held_out_calibration_shrinkage': 1.0,

            # LRMC experiment (2026, see reports/lrmc_experiments_2026.md):
            # base LRMC is a strict one-pass pipeline -- fit alpha/beta on
            # margins once, build the transition matrix once from the
            # resulting per-game probabilities, take its stationary
            # distribution once. It never checks whether the resulting
            # ratings are consistent with the per-game probabilities used to
            # build them, unlike e.g. Bradley-Terry (KRACH/HockeyBT), where
            # the win-probability formula IS the model that was fit --
            # self-consistent by construction. This is the same root cause
            # already diagnosed for the calibration gap above (a decoupled,
            # never-jointly-validated rating-estimation and prediction
            # step), addressed here structurally instead of by a bolted-on
            # calibration correction.
            #
            # When enabled, each per-game probability is a blend of the
            # original margin-based evidence and the Bradley-Terry-implied
            # probability (r_home / (r_home + r_away)) from the CURRENT
            # iteration's ratings, then the transition matrix and stationary
            # distribution are recomputed from that blend, repeated until
            # ratings stop moving (or iterative_max_iter is hit).
            # `iterative_blend=0.0` collapses to the exact base LRMC
            # behavior (the blend has zero weight, so the first iteration's
            # transition matrix is unchanged from the pre-iteration one) --
            # a strict generalization, not a change, and used as this
            # feature's own regression/correctness gate.
            # DEFAULT OFF pending backtest validation — see
            # reports/lrmc_experiments_2026.md for the result before
            # flipping this on.
            'iterative_fit': False,
            'iterative_blend': 0.5,
            'iterative_max_iter': 25,
            'iterative_tol': 1e-4,
        }
        # IMPORTANT: can't use self.conf.setdefault() here. Several of these
        # keys (margin_cap, prior_weight) already exist in the PARENT
        # class's defaults (e.g. prior_weight=0.0), and the parent __init__
        # already merged the caller's config into self.conf before this
        # constructor runs. setdefault would see the key already present
        # (with the parent's generic default) and silently never apply the
        # hockey-tuned value. Instead, check the caller's raw config dict —
        # only fall back to the hockey default when the caller didn't
        # explicitly set that key.
        user_config = config or {}
        for k, v in hockey_defaults.items():
            if k not in user_config:
                self.conf[k] = v

        self.alpha_ot = 0.0
        self.beta_ot = 0.0  # unused (fixed-confidence rule instead); kept for parity/inspection

        # Calibration params for predict() (see _calibrate_predictions(),
        # which sets these for real after fit()). These are just pre-fit
        # placeholders (predict() before fit() is undefined behavior anyway,
        # same as self.ratings being empty).
        self.calib_scale = 1.0
        self.calib_hia = 0.0

    def _parse_ot_periods(self, df):
        """
        Extracts how many overtime periods a game took from the raw
        'OT_Info' column ('OT' -> 1, '2OT' -> 2, '3OT' -> 3, '5OT' -> 5,
        NaN/missing -> not applicable). Rows where the column is absent,
        null, or doesn't match the expected pattern default to 1 period —
        the same assumption the old fixed-confidence rule made implicitly
        for every OT/SO game, so this is a safe fallback, not a guess.
        """
        n = len(df)
        if 'OT_Info' not in df.columns:
            return np.ones(n)
        raw = df['OT_Info'].astype(str).str.strip()
        periods = raw.str.extract(r'^(\d*)OT$', expand=False)
        periods = pd.to_numeric(periods, errors='coerce')
        periods = periods.fillna(1)
        periods = periods.where(periods > 0, 1)
        return periods.values

    def _ot_confidence_for_games(self, df):
        """
        Returns the OT-vote confidence level (see `ot_confidence` /
        `graduated_ot_confidence` in hockey_defaults) as either a scalar
        (graduated_ot_confidence=False, matching the pre-existing fixed-vote
        behavior exactly) or a per-row array that decays toward a coin flip
        as the number of overtime periods increases.
        """
        base = self.conf.get('ot_confidence', 0.08)
        if not self.conf.get('graduated_ot_confidence', False):
            return base
        decay = self.conf.get('ot_confidence_decay', 0.5)
        periods = self._parse_ot_periods(df)
        return base * np.power(decay, periods - 1)

    def _apply_empty_net_shrink(self, margin):
        """
        PROXY fallback only (no real ENG data available for the row).
        Shrinks a signed, uncapped goal margin of magnitude 2 toward 1.75
        as an empty-net proxy. Magnitudes of 1 and 3+ are left alone:
        1-goal games can't have an empty-net-goal cushion (the game would
        have been tied without it), and margin_cap treats 3+ as equivalent
        regardless of exact score anyway.
        """
        factor = self.conf.get('empty_net_shrink_factor', 0.75)
        shrink_target = np.sign(margin) * (1.0 + factor)  # e.g. factor=0.75 -> 1.75
        return np.where(np.abs(margin) == 2, shrink_target, margin)

    def _apply_empty_net_correction(self, df, margin):
        """
        Subtracts real empty-net goals from the (uncapped) goal margin where
        available; falls back to the blind proxy heuristic (only if
        explicitly enabled via `empty_net_shrink`) for rows without real
        data. The two are independent, not chained: real data always wins
        where present, and enabling the proxy doesn't get silently
        overridden just because *some* rows in the dataset have real data.
        """
        has_real = (self.conf.get('use_real_eng', False)
                    and 'Home_ENG' in df.columns and 'Away_ENG' in df.columns)
        if has_real:
            home_eng = pd.to_numeric(df['Home_ENG'], errors='coerce').values
            away_eng = pd.to_numeric(df['Away_ENG'], errors='coerce').values
            has_data = ~np.isnan(home_eng) & ~np.isnan(away_eng)
            # Empty-net goals are always scored by the team already leading.
            leader_eng = np.where(margin >= 0, np.nan_to_num(home_eng), np.nan_to_num(away_eng))
            corrected_abs = np.maximum(np.abs(margin) - leader_eng, 0.0)
            corrected = np.sign(margin) * corrected_abs
            margin = np.where(has_data, corrected, margin)
        else:
            has_data = np.zeros(len(margin), dtype=bool)

        if self.conf.get('empty_net_shrink', False):
            proxy = self._apply_empty_net_shrink(margin)
            margin = np.where(has_data, margin, proxy)

        return margin

    def _get_adjusted_margins_vectorized(self, df):
        """
        Overrides the base LRMC's margin calculation to apply the empty-net
        correction to the RAW goal margin before capping/power-scaling (so a
        6-1 game with 2 empty-net goals is treated as a 3-1 -> capped-3
        game, not as "already capped at 3, then subtract 2"). Only applies
        to real-goal margins — if `use_xg` is enabled, xG isn't a goal count
        and empty-net subtraction doesn't make sense against it, so that
        path defers entirely to the parent implementation.
        """
        if self.conf.get('use_xg', False):
            return super()._get_adjusted_margins_vectorized(df)

        margin = df['HomeGoals'].astype(float).values - df['AwayGoals'].astype(float).values
        margin = self._apply_empty_net_correction(df, margin)

        cap = self.conf.get('margin_cap')
        if cap and cap > 0:
            margin = np.clip(margin, -cap, cap)

        power = self.conf.get('margin_power', 1.0)
        if power != 1.0:
            margin = np.sign(margin) * (np.abs(margin) ** power)

        return margin

    def _preprocess_game_values(self):
        df = self.games.copy()

        df['ProcessedMargin'] = self._get_adjusted_margins_vectorized(df)
        df['Weight'] = self._calculate_game_weights(df)

        is_ot = df['IsOT'].fillna(False).astype(bool)
        is_neutral = df['NeutralSite'].astype(bool)

        # --- Regulation games: same margin-based logistic as base LRMC ---
        should_fit = self.conf.get('auto_fit')
        if should_fit:
            fit_data = self.games
            if self.conf.get('fit_source') == 'history' and self.history_df is not None:
                fit_data = self.history_df
            # Fit alpha/beta on regulation games only, so the OT games'
            # structurally-different (always +-1) margins don't distort the
            # regulation fit.
            reg_fit_data = fit_data
            if 'IsOT' in fit_data.columns:
                reg_fit_data = fit_data[~fit_data['IsOT'].fillna(False).astype(bool)]
            self._learn_params_home_and_home(reg_fit_data)

        z_full = self.alpha + self.beta * df['ProcessedMargin']
        z_neut = self.beta * df['ProcessedMargin']
        prob_reg = 1 / (1 + np.exp(-np.where(is_neutral, z_neut, z_full)))

        # --- OT/SO games: fixed, low-confidence vote (see class docstring) ---
        conf_level = self._ot_confidence_for_games(df)
        home_won = (df['Result'] == 1.0)
        prob_ot = np.where(home_won, 0.5 + conf_level, 0.5 - conf_level)
        # Ties in OT shouldn't occur (OT/SO always produces a winner in
        # modern NCAA hockey), but guard anyway for data-quality safety.
        prob_ot = np.where(df['Result'] == 0.5, 0.5, prob_ot)

        df['prob_home_better'] = np.where(is_ot, prob_ot, prob_reg)

        return df

    def fit(self):
        if self.conf.get('iterative_fit', False):
            self._fit_iterative()
        else:
            super().fit()
        self._calibrate_predictions()

    def _build_transition_and_ratings(self, processed_games):
        """
        Builds the transition matrix and its stationary-distribution
        ratings from a processed-games DataFrame's 'prob_home_better' /
        'Weight' columns. Factored out of LRMC.fit() (duplicated here
        rather than refactoring the shared base class) so
        _fit_iterative() below can call it repeatedly with a DIFFERENT
        prob_home_better each iteration, without touching lrmc.py's fit()
        (which gwLRMC and plain LRMC_* configs also depend on) at all --
        keeps this experiment fully contained to HockeyLRMC's opt-in path.
        """
        n_teams = len(self.teams)
        team_map = {team: i for i, team in enumerate(self.teams)}
        P = np.zeros((n_teams, n_teams))
        weighted_games_played = np.zeros(n_teams)

        h_idx = processed_games['HomeTeam'].map(team_map).values
        a_idx = processed_games['AwayTeam'].map(team_map).values
        p_h = processed_games['prob_home_better'].values
        w = processed_games['Weight'].values

        np.add.at(P, (h_idx, a_idx), (1.0 - p_h) * w)
        np.add.at(P, (a_idx, h_idx), p_h * w)
        np.add.at(weighted_games_played, h_idx, w)
        np.add.at(weighted_games_played, a_idx, w)

        for i in range(n_teams):
            if weighted_games_played[i] > 0:
                P[i, :] /= weighted_games_played[i]
                row_sum = np.sum(P[i, :])
                if row_sum > 1.0:
                    P[i, :] /= row_sum
                    P[i, i] = 0.0
                else:
                    P[i, i] = 1.0 - row_sum
            else:
                P[i, i] = 1.0

        if self.conf.get('prior_weight', 0) > 0:
            prior_weight = self.conf.get('prior_weight', 0.15)
            Prior = np.ones((n_teams, n_teams)) / n_teams
            P = (1 - prior_weight) * P + (prior_weight * Prior)

        try:
            vals, vecs = eig(P.T)
            idx = np.argmin(np.abs(vals - 1))
            ratings = np.real(vecs[:, idx])
            if np.all(ratings < 0):
                ratings = -ratings
            ratings = np.abs(ratings)
            ratings = ratings / np.sum(ratings) * n_teams * 100
        except Exception:
            ratings = np.ones(n_teams) * 100

        return P, {self.teams[i]: ratings[i] for i in range(n_teams)}

    def _fit_iterative(self):
        """
        Self-consistent LRMC (see `iterative_fit` in hockey_defaults for the
        motivation). Alpha/beta and the OT-vote/empty-net adjustments are
        computed exactly once, up front, from `_preprocess_game_values()` --
        only the transition matrix and its stationary ratings are
        recomputed each iteration, blending that original margin-based
        evidence with the current iteration's Bradley-Terry-implied
        probability (r_home / (r_home + r_away)).
        """
        processed_games = self._preprocess_game_values()
        base_prob = processed_games['prob_home_better'].values.copy()
        eps = 1e-9

        P, ratings = self._build_transition_and_ratings(processed_games)
        self.transition_matrix = P
        self.ratings = ratings
        prev_vec = np.array([ratings[t] for t in self.teams])

        blend = self.conf.get('iterative_blend', 0.5)
        max_iter = self.conf.get('iterative_max_iter', 10)
        tol = self.conf.get('iterative_tol', 1e-4)

        self.iterations_run = 0
        for _ in range(max_iter):
            home_r = processed_games['HomeTeam'].map(self.ratings).values.astype(float)
            away_r = processed_games['AwayTeam'].map(self.ratings).values.astype(float)
            prob_bt = home_r / (home_r + away_r + eps)
            blended = (1 - blend) * base_prob + blend * prob_bt

            iter_games = processed_games.copy()
            iter_games['prob_home_better'] = blended
            P, new_ratings = self._build_transition_and_ratings(iter_games)

            new_vec = np.array([new_ratings[t] for t in self.teams])
            change = np.max(np.abs(new_vec - prev_vec)) / (np.max(np.abs(prev_vec)) + eps)

            self.transition_matrix = P
            self.ratings = new_ratings
            prev_vec = new_vec
            self.iterations_run += 1

            if blend <= 0.0 or change < tol:
                break

    def _calibrate_predictions(self):
        """
        Attempts to calibrate predict()'s conversion from rating-ratio to
        win probability against actual outcomes, instead of trusting the raw
        log(r_home/r_away) as an already-correctly-scaled logit. DISABLED BY
        DEFAULT (calibrate_predictions=False) — see the hockey_defaults
        config block above and reports/lrmc_calibration.md for why: the
        diagnosis this targets is real, but this particular fix doesn't
        survive backtesting.

        The diagnosis: KRACH's win-probability formula, K_i/(K_i+K_j), IS
        the Bradley-Terry model whose likelihood was maximized to fit the
        ratings in the first place — self-consistent by construction.
        LRMC's rating estimation (a margin-fit logistic feeding a Markov
        chain's stationary distribution) and its prediction formula
        (sigmoid(hia + log(r_home/r_away))) are two unrelated, never
        jointly-validated steps — nothing guarantees the raw log-ratio is on
        the right scale to use directly as a logit. Confirmed: a single-
        slice check found HockeyLRMC's predictions compressed far tighter
        around 0.5 than KRACH's (std 0.10 vs 0.24) despite a comparably fat
        overconfident tail — under-decisive on easy calls, still occasionally
        wildly wrong on hard ones.

        The fix that doesn't work: fits a 2-parameter logistic regression of
        actual game outcomes on [is_non_neutral, raw_log_ratio], using the
        SAME games used to estimate the ratings (in-sample recalibration —
        Platt scaling applied to this model's own raw score, shrunk toward
        the pre-calibration baseline via `calibration_shrinkage` to fight
        overfitting). Swept shrinkage 0.0-1.0 in a 5-year/20-split backtest:
        LogLoss got monotonically WORSE with any nonzero shrinkage (0.704 at
        0.0 -> 0.715 at 0.1 -> 0.851 at 1.0/unshrunk); Brier improved only
        marginally (~1%) up to shrink~0.2-0.3 before also reversing. Because
        the calibration data IS the rating-estimation data, this isn't a
        genuine held-out check — it mostly re-fits noise already present in
        the ratings rather than a real, generalizable mis-scaling. A proper
        fix would need an actual held-out split (temporal holdout or
        k-fold), not attempted here.
        """
        if self.conf.get('held_out_calibration', False):
            self._calibrate_predictions_held_out()
            return

        if not self.conf.get('calibrate_predictions', False):
            self.calib_scale, self.calib_hia = 1.0, abs(self.alpha)
            return

        df = self.games
        eps = 1e-6
        r_home = df['HomeTeam'].map(self.ratings).values.astype(float)
        r_away = df['AwayTeam'].map(self.ratings).values.astype(float)
        z_raw = np.log(np.clip(r_home, eps, None) / np.clip(r_away, eps, None))
        is_home_ice = (~df['NeutralSite'].astype(bool)).astype(float).values
        result = df['Result'].values

        valid = result != 0.5  # true ties essentially don't occur in modern NCAA hockey
        y = (result[valid] == 1.0).astype(int)
        X = np.column_stack([is_home_ice[valid], z_raw[valid]])

        if len(y) < 30 or len(set(y)) < 2:
            self.calib_scale, self.calib_hia = 1.0, abs(self.alpha)
            return

        params, success = self._fit_logit_safe(y, X)
        if success:
            fitted_hia, fitted_scale = float(params[0]), float(params[1])
            # Shrink the in-sample fit toward the pre-calibration baseline
            # (scale=1, hia=|alpha|). An UNSHRUNK in-sample Platt-scaling
            # fit was tried first and backtested WORSE than no calibration
            # at all (5-year/20-split: LogLoss 0.704 -> 0.851) -- the raw
            # fit (e.g. scale~4.7x) doesn't generalize; it's overfit to the
            # exact training window. `calibration_shrinkage` (0=ignore the
            # fit entirely, 1=trust it fully) controls how much of the
            # fitted correction to actually apply. See
            # reports/lrmc_calibration.md for the shrinkage sweep that
            # picked the shipped default.
            shrink = self.conf.get('calibration_shrinkage', 1.0)
            baseline_hia, baseline_scale = abs(self.alpha), 1.0
            self.calib_hia = shrink * fitted_hia + (1 - shrink) * baseline_hia
            self.calib_scale = shrink * fitted_scale + (1 - shrink) * baseline_scale
        else:
            self.calib_scale, self.calib_hia = 1.0, abs(self.alpha)

    def _calibrate_predictions_held_out(self):
        """
        Held-out version of _calibrate_predictions() -- see
        `held_out_calibration` in hockey_defaults for the motivation, and
        Massey._fit_beta (massey.py) for the pattern this mirrors: fit
        ratings on an earlier temporal slice, calibrate against actual
        outcomes on a later slice those ratings never saw.

        Falls back to the pre-calibration baseline (calib_scale=1,
        calib_hia=|alpha|) whenever there isn't enough data to do this
        safely, exactly like Massey's guard rails -- a noisy calibration
        fit on too little held-out data is worse than no calibration.
        """
        baseline_hia, baseline_scale = abs(self.alpha), 1.0
        df = self.games

        if 'Date' not in df.columns:
            self.calib_scale, self.calib_hia = baseline_scale, baseline_hia
            return

        frac = self.conf.get('held_out_calibration_frac', 0.2)
        df_sorted = df.sort_values('Date')
        n_games = len(df_sorted)
        split = int(n_games * (1 - frac))

        if split < 100 or (n_games - split) < 30:
            self.calib_scale, self.calib_hia = baseline_scale, baseline_hia
            return

        inner_train = df_sorted.iloc[:split]
        inner_holdout = df_sorted.iloc[split:]

        # Fresh, throwaway model: ratings estimated ONLY from inner_train,
        # so inner_holdout's outcomes are genuinely out-of-sample relative
        # to these ratings. calibration is disabled on it (both flags off)
        # to avoid infinite recursion and because we only need its raw
        # ratings, not its own calibrated predict().
        inner_config = dict(self.conf)
        inner_config['held_out_calibration'] = False
        inner_config['calibrate_predictions'] = False
        try:
            inner_model = HockeyLRMC(inner_train, config=inner_config, history_df=self.history_df)
            inner_model.fit()
        except Exception:
            self.calib_scale, self.calib_hia = baseline_scale, baseline_hia
            return

        eps = 1e-6
        r_home = inner_holdout['HomeTeam'].map(inner_model.ratings).values.astype(float)
        r_away = inner_holdout['AwayTeam'].map(inner_model.ratings).values.astype(float)
        # Teams inner_model never saw (e.g. a team's first game falls in the
        # holdout slice) get no rating -- map() leaves those as NaN; drop
        # them rather than guessing a rating for a team the ratings model
        # never had a chance to place.
        valid_rating = ~np.isnan(r_home) & ~np.isnan(r_away)

        z_raw = np.log(np.clip(r_home, eps, None) / np.clip(r_away, eps, None))
        is_home_ice = (~inner_holdout['NeutralSite'].astype(bool)).values.astype(float)
        result = inner_holdout['Result'].values

        valid = valid_rating & (result != 0.5)
        y = (result[valid] == 1.0).astype(int)
        X = np.column_stack([is_home_ice[valid], z_raw[valid]])

        if len(y) < 20 or len(set(y)) < 2:
            self.calib_scale, self.calib_hia = baseline_scale, baseline_hia
            return

        # max_abs_param=15.0 (vs. _fit_logit_safe's default 5.0): the raw
        # log-ratio here is independently known to need roughly a 4-5x
        # scale correction (see the method docstring / _fit_logit_safe's),
        # so a fitted scale in single digits is the expected signal, not
        # the runaway/near-separated fit that guard exists to catch.
        params, success = self._fit_logit_safe(y, X, max_abs_param=15.0)
        if not success:
            self.calib_scale, self.calib_hia = baseline_scale, baseline_hia
            return

        fitted_hia, fitted_scale = float(params[0]), float(params[1])
        shrink = self.conf.get('held_out_calibration_shrinkage', 1.0)
        self.calib_hia = shrink * fitted_hia + (1 - shrink) * baseline_hia
        self.calib_scale = shrink * fitted_scale + (1 - shrink) * baseline_scale

    def predict(self, home, away, is_neutral=False):
        """
        Predicts P(home wins) using the calibrated rating-ratio-to-probability
        conversion from _calibrate_predictions() (falls back to the parent
        LRMC's uncalibrated formula's scale if calibration didn't run/failed).
        The OT-vs-regulation distinction only affects how ratings are
        ESTIMATED (via fit), not how a specific future single game is
        predicted here, since we don't know in advance whether a given
        upcoming game will go to OT.
        """
        r_home = self.ratings.get(home, 1.0)
        r_away = self.ratings.get(away, 1.0)
        eps = 1e-6
        log_ratio = np.log(max(r_home, eps) / max(r_away, eps))
        hia_term = 0.0 if is_neutral else self.calib_hia
        z = hia_term + self.calib_scale * log_ratio
        return 1 / (1 + np.exp(-z))
