import pandas as pd
import numpy as np
from tqdm import tqdm
from joblib import Parallel, delayed
from src.utils.season import default_season_end_date

class MonteCarloSimulator:
    def __init__(self, model_class, model_config, current_games_df, upcoming_schedule_df):
        """
        model_class: The class (not instance) of the ranker (e.g. KRACH, ELO)
        model_config: Config for the model
        current_games_df: Games already played
        upcoming_schedule_df: Games to be simulated
        """
        self.model_class = model_class
        self.model_config = model_config
        self.current_games_df = current_games_df.copy()
        # Normalize to datetime so concatenating with simulated future games
        # (which use pd.Timestamp -- see _one_iteration) doesn't leave a
        # mixed str/Timestamp 'Date' column. A mixed column sorts fine for
        # models that never sort by Date, but any model that does (e.g.
        # Massey's fit_beta, which calls df.sort_values('Date') to build its
        # temporal holdout split) raises TypeError: '<' not supported
        # between Timestamp and str -- a real, previously-silent bug this
        # refactor's per-model manifest reporting surfaced (it used to be
        # swallowed by run_system.py's broad except-and-continue with no
        # record of which models it affected).
        if 'Date' in self.current_games_df.columns:
            self.current_games_df['Date'] = pd.to_datetime(self.current_games_df['Date'])
        self.upcoming_schedule_df = upcoming_schedule_df.copy()
        self.teams = sorted(list(set(current_games_df['HomeTeam']).union(set(current_games_df['AwayTeam']))))

        self.rank_history = {team: [] for team in self.teams}
        self._rows = None   # cached upcoming_schedule_df rows (order fixed across iterations)
        self._probs = None  # cached baseline win probabilities, one per row -- see run()

    def _one_iteration(self, seed):
        """Run a single Monte Carlo iteration. Designed to be called in parallel."""
        rng = np.random.default_rng(seed)

        # Baseline win probabilities are the SAME every iteration (they come
        # from the one model fit on games played so far, not from anything
        # that varies per-iteration) -- computed once in run() and cached,
        # rather than re-predicted on every single one of num_iterations
        # passes as before. Only the random draw below actually needs to
        # happen per-iteration.
        rows = self._rows
        probs = self._probs

        results = (rng.random(len(probs)) < probs).astype(float)

        sim_games = []
        for i, row in enumerate(rows):
            res = results[i]
            hg, ag = (3, 2) if res == 1.0 else (2, 3)
            # Use the game's actual scheduled date (upcoming_schedule_df carries
            # real dates) so time-decay-weighted models (e.g. LRMC_Dynamic) treat
            # simulated games at their correct point in the season. Only fall
            # back to an approximate season-end date if a row is missing one.
            row_date = getattr(row, 'Date', None)
            game_date = pd.Timestamp(row_date) if pd.notna(row_date) else default_season_end_date(row.Season)
            sim_games.append({
                'HomeTeam': row.HomeTeam,
                'AwayTeam': row.AwayTeam,
                'Result': res,
                'HomeGoals': hg,
                'AwayGoals': ag,
                'IsOT': False,
                'NeutralSite': bool(getattr(row, 'NeutralSite', False)),
                'Date': game_date,
                'Season': row.Season,
            })

        full_season = pd.concat([self.current_games_df, pd.DataFrame(sim_games)], ignore_index=True)
        it_model = self.model_class(full_season, config=self.model_config)
        it_model.fit()
        ranks_df = it_model.get_rankings()
        return {row['Team']: rank for rank, row in ranks_df.iterrows()}

    def run(self, num_iterations=1000, n_jobs=-1):
        print(f"Running {num_iterations} iterations for {self.model_class.__name__}...")

        # Fit baseline model once on current data for probability predictions
        baseline_model = self.model_class(self.current_games_df, config=self.model_config)
        baseline_model.fit()

        # Predict every upcoming game's win probability ONCE here -- these
        # don't change across iterations (they all come from this same
        # baseline fit), so the old code re-predicting them inside every one
        # of num_iterations loop passes (500 by default) was pure repeated
        # work. Cached on self so joblib's pickled worker copies carry the
        # small array, not the model object itself.
        self._rows = list(self.upcoming_schedule_df.itertuples(index=False))
        probs = []
        for row in self._rows:
            h, a = row.HomeTeam, row.AwayTeam
            is_neutral = getattr(row, 'NeutralSite', False)
            try:
                probs.append(baseline_model.predict(h, a, is_neutral=is_neutral))
            except Exception:
                probs.append(0.5)
        self._probs = np.array(probs)

        # Generate reproducible seeds for each iteration
        seeds = np.random.SeedSequence().generate_state(num_iterations)

        results = Parallel(n_jobs=n_jobs)(
            delayed(self._one_iteration)(int(seeds[i]))
            for i in tqdm(range(num_iterations))
        )

        for rank_dict in results:
            for team, rank in rank_dict.items():
                if team in self.rank_history:
                    self.rank_history[team].append(rank)

    def save_results(self, output_path):
        """
        Saves the rank frequency for each team.
        Format: Team, Rank, Frequency
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        records = []
        for team, ranks in self.rank_history.items():
            if not ranks: continue
            
            # Count frequencies of each rank
            unique, counts = np.unique(ranks, return_counts=True)
            total = len(ranks)
            for r, c in zip(unique, counts):
                records.append({
                    'Team': team,
                    'Rank': int(r),
                    'Probability': c / total
                })
        
        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False)
        print(f"Saved simulation results to {output_path}")
