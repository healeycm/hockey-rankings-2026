import pandas as pd
import numpy as np
import datetime
from pathlib import Path

# Import Metrics
from src.validation.metrics import (
    calculate_accuracy,
    calculate_brier,
    calculate_log_loss,
    calculate_ece,
    calculate_brier_decomposition,
    calculate_rps,
    apply_ot_weighting
)


class BacktestEngine:
    def __init__(self, full_history_df, output_dir, ot_win_weight=1.0, ot_loss_weight=0.0):
        """
        Args:
            full_history_df (pd.DataFrame): Historical game data.
            output_dir (Path): Directory to save results.
            ot_win_weight (float): Value assigned to a Home OT Win (default 1.0).
            ot_loss_weight (float): Value assigned to a Home OT Loss (default 0.0).
                                    Example: For 55/45 split, use win=0.55, loss=0.45.
        """
        self.history = full_history_df.copy()
        self.history['Date'] = pd.to_datetime(self.history['Date'])
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ot_win_weight = ot_win_weight
        self.ot_loss_weight = ot_loss_weight

        self.results_summary = []
        self.all_predictions = []

    def _get_cutoff_date(self, season_code, cutoff):
        """
        Resolves a cutoff label to a concrete date within the given season.

        Accepts either:
        - A month name from the original fixed set: 'Dec' (day 1 of the
          season's start year), 'Jan'/'Feb' (day 1 of the season's end year).
        - A "MonDD" label for finer granularity, e.g. 'Jan15', 'Feb15' — any
          month name above followed by a day number. Enables denser cutoff
          sampling (more train/test splits per season) without a full
          calendar-date API.

        'Oct'/'Nov' (added for preseason-prior validation — see
        reports/preseason_priors_results.md) resolve within the season's
        START year, same as 'Dec' — USCHO D-I men's typically opens the
        first week of October, so an Oct1 cutoff can have near-zero training
        games for some seasons; that's expected, not a bug (train_df.empty
        just skips the split in run() below).
        """
        start_year = int(str(season_code)[:4])
        end_year = int(str(season_code)[4:])
        month_year = {'Oct': start_year, 'Nov': start_year, 'Dec': start_year, 'Jan': end_year, 'Feb': end_year}
        month_num = {'Oct': 10, 'Nov': 11, 'Dec': 12, 'Jan': 1, 'Feb': 2}

        month_name = cutoff[:3]
        day_str = cutoff[3:]
        day = int(day_str) if day_str else 1

        if month_name not in month_year:
            raise ValueError(f"Unknown cutoff month in '{cutoff}': expected Oct/Nov/Dec/Jan/Feb prefix.")
        return pd.Timestamp(year=month_year[month_name], month=month_num[month_name], day=day)

    def run(self, seasons, cutoffs, model_factory, model_configs=None, test_window_days=None):
        print(f"Starting Backtest on {len(seasons)} seasons x {len(cutoffs)} cutoffs...")
        print(f"  > OT Settings: Win={self.ot_win_weight}, Loss={self.ot_loss_weight}")

        for season in seasons:
            season_df = self.history[self.history['Season'] == season].copy()
            if season_df.empty: continue

            for cutoff_name in cutoffs:
                cutoff_date = self._get_cutoff_date(season, cutoff_name)

                train_df = season_df[season_df['Date'] < cutoff_date].copy()
                test_df = season_df[season_df['Date'] >= cutoff_date].copy()
                if test_window_days is not None:
                    # Score only the next N days after the cutoff instead of
                    # the rest of the season -- useful for an early (Oct/Nov)
                    # cutoff, where "rest of season" mixes in games many
                    # months later that no early-season signal (a prior
                    # included) should get credit or blame for.
                    window_end = cutoff_date + pd.Timedelta(days=test_window_days)
                    test_df = test_df[test_df['Date'] < window_end].copy()

                if train_df.empty or test_df.empty: continue

                print(f"  > {season} | {cutoff_name} | Train: {len(train_df)} | Test: {len(test_df)}")
                for model_name, ModelClass in model_factory.items():
                    try:
                        # Instantiate
                        config = model_configs.get(model_name, {}) if model_configs else {}

                        # Pass history_df to models that accept it (LRMC family).
                        # Without this, any config specifying fit_source='history'
                        # silently falls back to season-only fitting inside the
                        # model (history_df=None), i.e. the config doesn't do what
                        # it says. IMPORTANT: history is truncated to games strictly
                        # BEFORE the cutoff, otherwise the model's alpha/beta fit
                        # would see future games from the test window — leakage that
                        # would flatter every history-fitted model in the backtest.
                        history_for_fit = self.history[self.history['Date'] < cutoff_date]
                        try:
                            model = ModelClass(train_df, config=config, history_df=history_for_fit)
                        except TypeError:
                            try:
                                model = ModelClass(train_df, config=config)
                            except TypeError:
                                model = ModelClass(train_df)

                        model.fit()

                        # Predict. Also captures predict_outcomes() (native
                        # 3-outcome home/tie/away probabilities) when the
                        # model exposes it (HockeyBT, DixonColes), enabling
                        # RPS below -- every other metric here still uses
                        # the collapsed HomeWinProb scalar for comparability
                        # across all models.
                        has_outcomes = hasattr(model, 'predict_outcomes')
                        preds = []
                        for _, row in test_df.iterrows():
                            prob = model.predict(row['HomeTeam'], row['AwayTeam'], row['NeutralSite'])
                            pred_row = {
                                'Season': season,
                                'Cutoff': cutoff_name,
                                'Date': row['Date'],
                                'HomeTeam': row['HomeTeam'],
                                'AwayTeam': row['AwayTeam'],
                                'Result': row['Result'],
                                'IsOT': row.get('IsOT', False),
                                'HomeWinProb': prob,
                                'Model': model_name
                            }
                            if has_outcomes:
                                try:
                                    p_h, p_t, p_a = model.predict_outcomes(
                                        row['HomeTeam'], row['AwayTeam'], row['NeutralSite'])
                                    pred_row['P_Home'], pred_row['P_Tie'], pred_row['P_Away'] = p_h, p_t, p_a
                                except Exception:
                                    pass
                            preds.append(pred_row)

                        # Metrics
                        pred_df = pd.DataFrame(preds)
                        if not pred_df.empty:
                            # Apply Flexible OT Weighting
                            pred_df['WeightedResult'] = apply_ot_weighting(
                                pred_df,
                                ot_win_weight=self.ot_win_weight,
                                ot_loss_weight=self.ot_loss_weight
                            )
                            target_col = 'WeightedResult'

                            acc = calculate_accuracy(pred_df, target_col=target_col)
                            brier = calculate_brier(pred_df, target_col=target_col)
                            ll = calculate_log_loss(pred_df, target_col=target_col)
                            ece = calculate_ece(pred_df, target_col=target_col)
                            decomp = calculate_brier_decomposition(pred_df, target_col=target_col)

                            summary_row = {
                                'Season': season,
                                'Cutoff': cutoff_name,
                                'Model': model_name,
                                'Games_Test': len(pred_df),
                                'Accuracy': round(acc, 4),
                                'Brier': round(brier, 4),
                                'LogLoss': round(ll, 4),
                                'ECE': round(ece, 4),
                                'Reliability': round(decomp['reliability'], 4),
                                'Resolution': round(decomp['resolution'], 4),
                                'Uncertainty': round(decomp['uncertainty'], 4),
                            }

                            # RPS only when the model exposed native 3-outcome
                            # predictions (see the has_outcomes capture above);
                            # left absent (not zero) otherwise, since a
                            # collapsed-scalar model's RPS wouldn't mean the
                            # same thing and shouldn't be compared against it.
                            if has_outcomes and {'P_Home', 'P_Tie', 'P_Away'}.issubset(pred_df.columns):
                                summary_row['RPS'] = round(calculate_rps(pred_df), 4)

                            self.results_summary.append(summary_row)

                            self.all_predictions.append(pred_df)

                    except Exception as e:
                        print(f"    ! Error running {model_name}: {e}")

    def save_results(self):
        if not self.results_summary:
            print("No results to save.")
            return

        summary_df = pd.DataFrame(self.results_summary)
        summary_path = self.output_dir / "backtest_summary.csv"
        summary_df.to_csv(summary_path, index=False)

        # RPS is only present for models exposing predict_outcomes() (see
        # run()) -- include it in the aggregate when at least one row has it,
        # so its NaNs for other models are simply skipped by groupby/mean
        # rather than needing special-casing here.
        metric_cols = ['Accuracy', 'Brier', 'LogLoss', 'ECE', 'Reliability', 'Resolution', 'Uncertainty']
        if 'RPS' in summary_df.columns:
            metric_cols.append('RPS')
        agg_df = summary_df.groupby(['Model', 'Cutoff'])[metric_cols].mean()
        agg_path = self.output_dir / "backtest_aggregate.csv"
        agg_df.to_csv(agg_path)

        print("\n" + "=" * 40)
        print("BACKTEST RESULTS (Aggregate):")
        print(agg_df)
        print("=" * 40)
        print(f"Full results saved to {self.output_dir}")