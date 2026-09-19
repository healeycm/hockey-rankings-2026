import pandas as pd
import numpy as np
from joblib import Parallel, delayed
from src.rankings.krach import KRACH
from src.rankings.registry import build_model, resolve_model


class RankInterpreter:
    def __init__(self, history_df, season):
        self.full_df = history_df.copy()
        self.season_df = self.full_df[self.full_df['Season'] == season].copy()
        self.season = season
        self.summary_cache = None  # Cache for efficiency

    def generate_season_summary(self):
        """
        Calculates Win%, Win% Rank, SOS, and SOS Rank for ALL teams in the season.
        Returns a DataFrame.
        """
        if self.summary_cache is not None:
            return self.summary_cache

        # 1. Establish Opponent Strength (Using KRACH as the 'Objective' Measure)
        # Even if we are analyzing NPI, KRACH is the standard for "True SOS".
        base_model = KRACH(self.season_df)
        base_model.fit()
        krach_ratings = base_model.ratings  # {Team: Rating}

        teams = sorted(list(set(self.season_df['HomeTeam']).union(set(self.season_df['AwayTeam']))))
        stats = []

        for team in teams:
            # Get games for this team
            games = self.season_df[
                (self.season_df['HomeTeam'] == team) |
                (self.season_df['AwayTeam'] == team)
                ]

            if games.empty: continue

            wins = 0.0
            n_games = 0
            opp_ratings = []

            for _, row in games.iterrows():
                is_home = row['HomeTeam'] == team

                # Win Calculation (1.0, 0.5, 0.0)
                res = row['Result'] if is_home else (1.0 - row['Result'])
                wins += res
                n_games += 1

                # Opponent Strength
                opp = row['AwayTeam'] if is_home else row['HomeTeam']
                opp_ratings.append(krach_ratings.get(opp, 0))

            win_pct = wins / n_games if n_games > 0 else 0.0
            sos = np.mean(opp_ratings) if opp_ratings else 0.0

            stats.append({
                'Team': team,
                'Games': n_games,
                'Wins_Weighted': wins,
                'WinPct': win_pct,
                'SOS_Rating': sos
            })

        df = pd.DataFrame(stats)

        # Calculate Ranks (Descending: Higher is better)
        df['WinPct_Rank'] = df['WinPct'].rank(ascending=False, method='min')
        df['SOS_Rank'] = df['SOS_Rating'].rank(ascending=False, method='min')

        # Reorder columns
        df = df[['Team', 'Games', 'Wins_Weighted', 'WinPct', 'WinPct_Rank', 'SOS_Rating', 'SOS_Rank']]
        df = df.sort_values('WinPct_Rank')

        self.summary_cache = df
        return df

    def get_component_analysis(self, team):
        """
        Returns dictionary of stats for a specific team.
        """
        df_summary = self.generate_season_summary()
        row = df_summary[df_summary['Team'] == team]

        if row.empty: return {}

        row = row.iloc[0]

        # Generate Explanation
        pct_rank = row['WinPct_Rank']
        sos_rank = row['SOS_Rank']
        total_teams = len(df_summary)

        explanation = "Balanced profile."
        if pct_rank < (total_teams * 0.2) and sos_rank > (total_teams * 0.6):
            explanation = "Excellent record, but Strength of Schedule is weak. Rankings may penalize you."
        elif pct_rank > (total_teams * 0.5) and sos_rank < (total_teams * 0.2):
            explanation = "Record is average/below average, but played a very difficult schedule. Rankings may boost you."

        return {
            "Win %": f"{row['WinPct']:.3f} (Rank: {int(row['WinPct_Rank'])})",
            "SOS": f"{row['SOS_Rating']:.1f} (Rank: {int(row['SOS_Rank'])})",
            "Explanation": explanation
        }

    @staticmethod
    def _drop_one_game(idx, season_df, model_key, model_config, history_df, needs_history):
        """
        Worker for one Leave-One-Out refit (one dropped game, not one
        team). Returns the game's row plus the resulting rating for BOTH
        teams involved, so a single refit yields impact data for two teams
        at once — see compute_all_impacts()'s docstring for why this halves
        the refit count versus the old per-(team, game) loop.
        """
        row = season_df.loc[idx]
        modified_df = season_df.drop(idx)
        kwargs = {"config": model_config}
        if needs_history:
            kwargs["history_df"] = history_df
        ModelClass, _, _ = resolve_model(model_key)
        try:
            new_model = ModelClass(modified_df, **kwargs)
            new_model.fit()
            return idx, new_model.ratings
        except Exception:
            return idx, None

    def compute_all_impacts(self, model_name="KRACH", model_config=None, n_jobs=-1):
        """
        Leave-One-Out sensitivity analysis for EVERY team in the season, in
        one pass.

        The old implementation looped over (team, game) pairs and refit the
        model once per pair — for a team's own N games that's N refits,
        repeated independently for every team, even though dropping game G
        (between team A and team B) changes ratings for BOTH A and B
        simultaneously. This loops over GAMES instead: one refit per game
        in the season (roughly half as many total refits as before, since
        almost every game involves two teams each of whom would otherwise
        have triggered their own refit of it), parallelized with joblib to
        match the Monte Carlo simulator's approach.

        Returns: dict {Team: DataFrame[Date, Opponent, Result, Rating Impact]},
        sorted descending by Rating Impact within each team — same shape as
        the old per-team find_impact_games() output, so callers (and the
        website's load_team_analysis()) don't need to change.
        """
        resolved = resolve_model(model_name)
        if resolved is None:
            raise KeyError(f"Unknown model_name '{model_name}' — not in registry (src/rankings/registry.py).")
        ModelClass, _, needs_history = resolved
        config = model_config or {}

        kwargs = {"config": config}
        if needs_history:
            kwargs["history_df"] = self.full_df

        base_model = ModelClass(self.season_df, **kwargs)
        base_model.fit()
        base_ratings = base_model.ratings

        indices = list(self.season_df.index)
        results = Parallel(n_jobs=n_jobs)(
            delayed(RankInterpreter._drop_one_game)(
                idx, self.season_df, model_name, config, self.full_df, needs_history
            )
            for idx in indices
        )

        per_team_impacts = {team: [] for team in base_ratings}

        for idx, new_ratings in results:
            if new_ratings is None:
                continue
            row = self.season_df.loc[idx]
            home, away = row['HomeTeam'], row['AwayTeam']

            for team, opponent, is_home in [(home, away, True), (away, home, False)]:
                if team not in base_ratings or team not in per_team_impacts:
                    continue
                current_rating = base_ratings[team]
                new_rating = new_ratings.get(team, 0)
                impact = current_rating - new_rating

                res = row['Result'] if is_home else (1.0 - row['Result'])
                if res == 0.5:
                    res_str = "Tie"
                elif res > 0.5:
                    res_str = "Win"
                else:
                    res_str = "Loss"

                per_team_impacts[team].append({
                    'Date': row['Date'],
                    'Opponent': opponent,
                    'Result': res_str,
                    'Rating Impact': impact
                })

        output = {}
        for team, records in per_team_impacts.items():
            df = pd.DataFrame(records)
            if not df.empty:
                df = df.sort_values('Rating Impact', ascending=False)
            output[team] = df
        return output

    def find_impact_games(self, team, model_name="KRACH", model_config=None):
        """
        Single-team Leave-One-Out impact analysis. Kept for callers that
        only need one team; internally still refits once per game the team
        played (not the whole season), so this remains the right choice
        when only a handful of teams are needed. For "every team in the
        season" (run_system.py's use case), call compute_all_impacts()
        instead — it shares refits across teams and is roughly 2x faster
        in aggregate.
        """
        resolved = resolve_model(model_name)
        if resolved is None:
            return pd.DataFrame()
        ModelClass, _, needs_history = resolved
        config = model_config or {}

        kwargs = {"config": config}
        if needs_history:
            kwargs["history_df"] = self.full_df

        base_model = ModelClass(self.season_df, **kwargs)
        base_model.fit()
        base_ranks = base_model.get_rankings().set_index('Team')

        if team not in base_ranks.index:
            return pd.DataFrame()
        current_rating = base_ranks.loc[team, 'Rating']

        team_indices = self.season_df[
            (self.season_df['HomeTeam'] == team) |
            (self.season_df['AwayTeam'] == team)
            ].index.tolist()

        impacts = []
        for idx in team_indices:
            modified_df = self.season_df.drop(idx)
            new_model = ModelClass(modified_df, **kwargs)
            try:
                new_model.fit()
                new_rating = new_model.ratings.get(team, 0)
                impact = current_rating - new_rating

                row = self.season_df.loc[idx]
                opponent = row['AwayTeam'] if row['HomeTeam'] == team else row['HomeTeam']

                if row['Result'] == 0.5:
                    res_str = "Tie"
                elif (row['HomeTeam'] == team and row['Result'] > 0.5) or \
                        (row['AwayTeam'] == team and row['Result'] < 0.5):
                    res_str = "Win"
                else:
                    res_str = "Loss"

                impacts.append({
                    'Date': row['Date'],
                    'Opponent': opponent,
                    'Result': res_str,
                    'Rating Impact': impact
                })
            except Exception:
                continue

        df_impact = pd.DataFrame(impacts)
        if not df_impact.empty:
            df_impact = df_impact.sort_values('Rating Impact', ascending=False)

        return df_impact
