# src/rankings/npi.py
import numpy as np
import pandas as pd
from src.rankings.base_ranker import BaseRanker
from src.utils.season import conf_tourney_cutoff, get_current_season_code


class NPI(BaseRanker):
    def __init__(self, games_df, config=None):
        # BaseRanker.__init__ already filters to Division I opponents only
        # (data/teams/team_info.csv) — this used to be duplicated here with
        # its own try/except; now centralized so every ranker gets the same
        # protection. See base_ranker.py's _apply_di_filter docstring.
        super().__init__(games_df)

        # Default NCAA DI dials, set for 2025-26 season; carried forward until
        # re-tuned/re-validated against a newer official NPI snapshot.
        self.conf = {
            'weight_wp': 0.25,
            'weight_sos': 0.75,
            'home_multiplier': 0.8,
            'away_multiplier': 1.2,
            'quality_win_base': 51.0,
            'quality_win_mult': 0.5
        }
        if config:
            self.conf.update(config)

        # Filter Exhibition Games
        if 'Is_Exhibition' in self.games.columns:
             # Convert to boolean if needed, or assume True/False/1/0
             self.games = self.games[~self.games['Is_Exhibition'].isin([True, 'True', 1, '1'])].copy()
             self.teams = sorted(list(set(self.games['HomeTeam']).union(set(self.games['AwayTeam']))))

        # Build conference map and identify conference tournament games
        self._conf_tourney_idx = self._build_conf_tourney_index()

    def _build_conf_tourney_index(self):
        """
        Identifies conference tournament games by building a conference map
        from regular-season game types, then flagging same-conference matchups
        with Type='nc' after March 1. Regular conference-coded games (he, ec, etc.)
        in March are still regular-season. CHN treats conference tournament games
        as postseason: neutral weighting AND full OT credit (no 60/40 split).
        """
        conf_codes = ['ah', 'he', 'ec', 'nt', 'cc2', 'b10']

        # Build conference map vectorized: team -> most frequent conference code
        conf_mask = self.games['Type'].str.lower().isin(conf_codes)
        conf_games = self.games[conf_mask]
        if not conf_games.empty:
            home_conf = conf_games[['HomeTeam', 'Type']].rename(columns={'HomeTeam': 'Team'})
            away_conf = conf_games[['AwayTeam', 'Type']].rename(columns={'AwayTeam': 'Team'})
            all_conf = pd.concat([home_conf, away_conf], ignore_index=True)
            all_conf['Type'] = all_conf['Type'].str.lower()
            conference_map = (
                all_conf.groupby('Team')['Type']
                .agg(lambda x: x.value_counts().index[0])
                .to_dict()
            )
        else:
            conference_map = {}

        # Identify conference tournament games vectorized
        dates = pd.to_datetime(self.games['Date'])
        is_nc = self.games['Type'].str.lower() == 'nc'
        if 'Season' in self.games.columns and not self.games.empty:
            season = self.games['Season'].mode().iloc[0]
        else:
            season = get_current_season_code()
        is_march = dates >= conf_tourney_cutoff(season)
        h_conf = self.games['HomeTeam'].map(conference_map)
        a_conf = self.games['AwayTeam'].map(conference_map)
        same_conf = (h_conf == a_conf) & h_conf.notna() & a_conf.notna()
        conf_tourney_idx = set(self.games.index[is_nc & is_march & same_conf])

        return conf_tourney_idx

    def _calculate_game_points(self, row, team_role):
        """
        Calculates weighted points for a single team in a game.
        Conference tournament games get postseason treatment: neutral weighting
        and full OT credit (no 60/40 split).
        """
        is_ot = row.get('IsOT', False)
        is_postseason = row['Type'].upper() in ['POST', 'NCAA']
        is_conf_tourney = row.name in self._conf_tourney_idx

        # Conference tournament games get postseason treatment for NPI
        is_neutral_for_npi = row['NeutralSite'] or is_postseason or is_conf_tourney

        is_winner = (team_role == 'Home' and row['Result'] == 1.0) or \
                    (team_role == 'Away' and row['Result'] == 0.0)
        is_loser = (team_role == 'Home' and row['Result'] == 0.0) or \
                   (team_role == 'Away' and row['Result'] == 1.0)
        is_tie = row['Result'] == 0.5

        HM = self.conf['home_multiplier']
        AM = self.conf['away_multiplier']

        # Determine location multipliers
        if is_neutral_for_npi:
            win_mult = 1.0
            loss_mult = 1.0
        else:
            win_mult = HM if team_role == 'Home' else AM
            loss_mult = AM if team_role == 'Home' else HM

        if not is_ot or is_conf_tourney:
            # Regulation games OR conference tournament (full credit, no 60/40 split)
            if is_winner:
                pts = win_mult
                weight = win_mult
            elif is_loser:
                pts = 0.0
                weight = loss_mult
            else:
                # Tie: half-win credit at win_mult, weight = 1.0
                pts = 0.5 * win_mult
                weight = 1.0
        else:
            # Non-tournament OT: CHN formula pts = (0.4 * mult) + 0.2
            # "Only regulation receives location weighting; OT portions are unweighted"
            weight = 1.0
            if is_winner:
                pts = (0.4 * win_mult) + 0.2
            elif is_loser:
                # Complementary: Loser Pts = Weight - Winner Pts
                opp_win_mult = AM if team_role == 'Home' else HM
                if is_neutral_for_npi:
                    opp_win_mult = 1.0
                winner_pts = (0.4 * opp_win_mult) + 0.2
                pts = weight - winner_pts
            else:
                # OT Tie
                pts = 0.5 * win_mult

        return pts, weight

    def _compute_game_points_vectorized(self):
        """
        Vectorized computation of pts and weight for every game from both
        home and away perspectives. Returns flat arrays indexed by game record.
        """
        df = self.games
        HM = self.conf['home_multiplier']
        AM = self.conf['away_multiplier']

        is_postseason = df['Type'].str.upper().isin(['POST', 'NCAA'])
        is_conf_tourney = df.index.isin(self._conf_tourney_idx)
        is_neutral_for_npi = df['NeutralSite'].astype(bool) | is_postseason | is_conf_tourney
        is_ot = df['IsOT'].fillna(False).astype(bool)
        is_reg = ~is_ot | is_conf_tourney  # regulation-style scoring

        result = df['Result'].values
        neutral = is_neutral_for_npi.values
        reg = is_reg.values

        # Home perspective
        h_is_win  = result == 1.0
        h_is_loss = result == 0.0
        h_win_mult  = np.where(neutral, 1.0, HM)
        h_loss_mult = np.where(neutral, 1.0, AM)

        h_pts_reg = np.where(h_is_win, h_win_mult,
                    np.where(h_is_loss, 0.0, 0.5 * h_win_mult))
        h_wgt_reg = np.where(h_is_win, h_win_mult,
                    np.where(h_is_loss, h_loss_mult, 1.0))

        h_opp_win_mult  = np.where(neutral, 1.0, AM)
        h_pts_ot = np.where(h_is_win,  0.4 * h_win_mult + 0.2,
                   np.where(h_is_loss, 1.0 - (0.4 * h_opp_win_mult + 0.2),
                                       0.5 * h_win_mult))

        h_pts = np.where(reg, h_pts_reg, h_pts_ot)
        h_wgt = np.where(reg, h_wgt_reg, 1.0)

        # Away perspective
        a_is_win  = result == 0.0
        a_is_loss = result == 1.0
        a_win_mult  = np.where(neutral, 1.0, AM)
        a_loss_mult = np.where(neutral, 1.0, HM)

        a_pts_reg = np.where(a_is_win, a_win_mult,
                    np.where(a_is_loss, 0.0, 0.5 * a_win_mult))
        a_wgt_reg = np.where(a_is_win, a_win_mult,
                    np.where(a_is_loss, a_loss_mult, 1.0))

        a_opp_win_mult  = np.where(neutral, 1.0, HM)
        a_pts_ot = np.where(a_is_win,  0.4 * a_win_mult + 0.2,
                   np.where(a_is_loss, 1.0 - (0.4 * a_opp_win_mult + 0.2),
                                       0.5 * a_win_mult))

        a_pts = np.where(reg, a_pts_reg, a_pts_ot)
        a_wgt = np.where(reg, a_wgt_reg, 1.0)

        return h_pts, h_wgt, a_pts, a_wgt

    def fit(self, max_iterations=100, tolerance=1e-5, initial_ratings=None):
        if not hasattr(self, 'details'):
            self.details = {}

        n = len(self.teams)
        team_idx = {t: i for i, t in enumerate(self.teams)}

        # Vectorized pts/wgt for all games
        h_pts, h_wgt, a_pts, a_wgt = self._compute_game_points_vectorized()

        # Build flat record arrays: one entry per (team, game) pair
        h_team = self.games['HomeTeam'].map(team_idx).values
        h_opp  = self.games['AwayTeam'].map(team_idx).values
        a_team = self.games['AwayTeam'].map(team_idx).values
        a_opp  = self.games['HomeTeam'].map(team_idx).values

        team_ids = np.concatenate([h_team, a_team])
        opp_ids  = np.concatenate([h_opp,  a_opp])
        pts_arr  = np.concatenate([h_pts,  a_pts])
        wgt_arr  = np.concatenate([h_wgt,  a_wgt])

        # Initial ratings: raw WP per team
        raw_pts = np.zeros(n)
        raw_wgt = np.zeros(n)
        np.add.at(raw_pts, team_ids, pts_arr)
        np.add.at(raw_wgt, team_ids, wgt_arr)
        ratings = np.where(raw_wgt > 0, raw_pts / raw_wgt * 100, 50.0)

        if initial_ratings:
            print(f"Seeding NPI with {len(initial_ratings)} provided ratings.")
            for t, r in initial_ratings.items():
                if t in team_idx:
                    ratings[team_idx[t]] = r

        QWB_BASE = self.conf['quality_win_base']
        QWB_MULT = self.conf['quality_win_mult']

        # Precompute fixed WP contribution (constant across iterations)
        wp_contrib = 0.25 * pts_arr * 100  # = 0.25 * game_wp * wgt

        for _ in range(max_iterations):
            opp_ratings = ratings[opp_ids]

            # Per-game NPI contribution * wgt:
            # = 0.25*pts*100 + 0.75*opp_npi*wgt + (opp_npi-BASE)*MULT*pts [if pts>0 & opp>BASE]
            qwb_contrib = np.where(
                (pts_arr > 0) & (opp_ratings > QWB_BASE),
                (opp_ratings - QWB_BASE) * QWB_MULT * pts_arr,
                0.0
            )
            game_npi_wgt = wp_contrib + 0.75 * opp_ratings * wgt_arr + qwb_contrib

            numer = np.zeros(n)
            denom = np.zeros(n)
            np.add.at(numer, team_ids, game_npi_wgt)
            np.add.at(denom, team_ids, wgt_arr)

            new_ratings = np.where(denom > 0, numer / denom, ratings)
            max_diff = np.max(np.abs(new_ratings - ratings))
            ratings = new_ratings

            if max_diff < tolerance:
                break

        # Compute final details (SOS, QWB, adj_wp)
        opp_ratings = ratings[opp_ids]
        sos_numer = np.zeros(n)
        np.add.at(sos_numer, team_ids, opp_ratings * wgt_arr)
        total_wgt = np.zeros(n)
        np.add.at(total_wgt, team_ids, wgt_arr)

        qwb_final = np.where(
            (pts_arr > 0) & (opp_ratings > QWB_BASE),
            (opp_ratings - QWB_BASE) * QWB_MULT * pts_arr,
            0.0
        )
        qwb_numer = np.zeros(n)
        np.add.at(qwb_numer, team_ids, qwb_final)

        sos    = np.where(total_wgt > 0, sos_numer / total_wgt, 0.0)
        qwb    = np.where(total_wgt > 0, qwb_numer / total_wgt, 0.0)
        adj_wp = np.where(total_wgt > 0, raw_pts / raw_wgt * 100, 0.0)

        for i, team in enumerate(self.teams):
            if team not in self.details:
                self.details[team] = {}
            self.details[team].update({
                'npi': ratings[i],
                'adj_wp': adj_wp[i],
                'raw_adj_wp': adj_wp[i],
                'sos': sos[i],
                'qwb': qwb[i],
            })

        self.ratings = {t: ratings[team_idx[t]] for t in self.teams}

    def predict(self, home, away, is_neutral=False):
        r_home = self.ratings.get(home, 50)
        r_away = self.ratings.get(away, 50)
        scale = 15.0
        diff = r_home - r_away + (5.0 if not is_neutral else 0)
        return 1.0 / (1.0 + np.exp(-diff / scale))