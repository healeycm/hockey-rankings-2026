import pandas as pd
import numpy as np
import datetime
import json
import argparse
import time
import sys
from pathlib import Path

# Module Imports
from src.utils.config import load_config
from src.data.processor import process_data
from src.data.scraper import scrape_seasons, get_current_season_code
from src.analysis.interpreter import RankInterpreter
from src.analysis.simulator import MonteCarloSimulator
from src.rankings.base_ranker import using_di_team_path
from src.rankings.registry import build_model, validate_active_models
from src.rankings.priors import build_prior

TEAMS_DIR = Path(__file__).resolve().parents[1] / "data" / "teams"
WOMENS_TEAM_INFO = TEAMS_DIR / "team_info_women.csv"


def get_run_date(config_date_str):
    if not config_date_str:
        return datetime.date.today().strftime("%Y-%m-%d")
    return config_date_str


def generate_team_files(pred_df, model_name, base_output_dir):
    team_out_dir = base_output_dir / "team_projections" / model_name
    team_out_dir.mkdir(parents=True, exist_ok=True)
    teams = set(pred_df['HomeTeam']).union(set(pred_df['AwayTeam']))

    for team in teams:
        if "/" in team: continue
        team_schedule = pred_df[(pred_df['HomeTeam'] == team) | (pred_df['AwayTeam'] == team)].copy()
        if team_schedule.empty: continue
        team_schedule = team_schedule.sort_values('Date')
        safe_name = team.replace(" ", "_").replace(".", "").replace("&", "and")
        team_schedule.to_csv(team_out_dir / f"{safe_name}.csv", index=False)


def run_impact_analysis(season_df, full_history, model_key, model_config, output_dir, run_date):
    """
    Runs analysis: Season Summary (SOS/Win%) and Leave-One-Out impact for
    every team, in one batched pass (see RankInterpreter.compute_all_impacts
    for why this is ~2x faster than the old per-team refit loop).
    Saves to output/analysis/{Model}/{Date}/
    """
    print(f"  [Analysis] Starting Analysis for {model_key}...")

    season_id = season_df['Season'].iloc[0]
    interpreter = RankInterpreter(full_history, season_id)

    analysis_dir = output_dir / "analysis" / model_key / run_date
    analysis_dir.mkdir(parents=True, exist_ok=True)

    print("    -> Calculating Season Summary (Win%, SOS)...")
    summary_df = interpreter.generate_season_summary()
    summary_path = analysis_dir / "season_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"    -> Saved summary stats to {summary_path.name}")

    print("    -> Calculating Leave-One-Out Impact for all teams (one batched pass)...")
    all_impacts = interpreter.compute_all_impacts(model_name=model_key, model_config=model_config)

    count = 0
    for team, impact_df in all_impacts.items():
        if "/" in team:
            continue
        if impact_df.empty:
            continue
        safe_name = team.replace(" ", "_").replace(".", "").replace("&", "and")
        impact_df.to_csv(analysis_dir / f"{safe_name}.csv", index=False)
        count += 1

    print(f"  [Analysis] Completed ({count} team files). Saved reports to {analysis_dir}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the ranking/projection/analysis/simulation pipeline.")
    parser.add_argument('--division', type=str, default=None, choices=['men', 'women'],
                         help="Which division to run. Defaults to config.yaml's system.division, or 'men' if unset.")
    return parser.parse_args()


def main():
    print("--- Initializing System ---")
    args = parse_args()
    try:
        config = load_config()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

    division = args.division or config['system'].get('division', 'men')

    root_dir = Path(__file__).resolve().parents[1]
    processed_dir = root_dir / "data" / "processed" if division == 'men' else root_dir / "data" / "processed" / "women"
    output_dir = (root_dir / config['output']['base_dir']) if division == 'men' \
        else (root_dir / config['output']['base_dir'] / "women")

    run_date = get_run_date(config['system']['run_date'])
    target_season = config['system'].get('season')
    if division == 'men' and not target_season:
        target_season = int(get_current_season_code())
        print(f"[Config] system.season not set; auto-derived {target_season} from today's date.")

    active_models = config['models']['active_models']
    if division == 'women':
        # Women's hockey doesn't (yet) have the full validated model roster
        # men's hockey does -- reports/womens_hockey_import.md's 5-model
        # backtest is what's actually been checked. `models.active_models_women`
        # in config.yaml lets that list be tuned without touching this file;
        # if it's absent, fall back to the same validated set
        # generate_womens_rankings.py (now retired in favor of this single
        # entry point) used.
        active_models = config['models'].get(
            'active_models_women', ["Massey", "HockeyBT", "KRACH", "ELO", "RPI"]
        )

    # Fail loudly on an unrecognized model_key instead of silently skipping
    # it later in the loop -- see src/rankings/registry.py's module
    # docstring for the bug this replaced.
    try:
        validate_active_models(active_models)
    except ValueError as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

    manifest = {
        "division": division,
        "run_date": run_date,
        "target_season": target_season,
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "models": {},
    }

    di_context = using_di_team_path(WOMENS_TEAM_INFO) if division == 'women' else _null_context()
    with di_context:
        _run_division(config, division, processed_dir, output_dir, run_date, target_season, active_models, manifest)

    manifest["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    manifest_path = output_dir / "last_run.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    _print_final_summary(manifest, manifest_path)


def _null_context():
    import contextlib
    return contextlib.nullcontext()


def _print_final_summary(manifest, manifest_path):
    succeeded = [m for m, r in manifest["models"].items() if r["status"] == "ok"]
    failed = [m for m, r in manifest["models"].items() if r["status"] == "error"]
    print("\n--- System Run Complete ---")
    print(f"  Division: {manifest['division']}  Season: {manifest['target_season']}  Date: {manifest['run_date']}")
    print(f"  Succeeded ({len(succeeded)}): {', '.join(succeeded) if succeeded else '(none)'}")
    if failed:
        print(f"  FAILED ({len(failed)}): {', '.join(failed)} -- see {manifest_path} for error details.")
    print(f"  Manifest written to {manifest_path}")


def _run_division(config, division, processed_dir, output_dir, run_date, target_season, active_models, manifest):
    # Scraper Update
    if config['data'].get('scrape_latest', False):
        print("\n[Data] Scraping latest scores...")
        try:
            current_code = get_current_season_code()
            scrape_seasons([current_code], division=division)
        except Exception as e:
            print(f"Scraping Failed: {e}")

    # Data Pipeline
    if config['data']['update_processed_data']:
        print("\n[Data] Updating processed datasets...")
        try:
            process_data(division=division)
        except Exception as e:
            print(f"Data Processing Failed: {e}")
            sys.exit(1)

    # Load Data
    archive_path = processed_dir / "games_archive.csv"
    schedule_path = processed_dir / "upcoming_schedule.csv"

    # NOTE: Date is intentionally left as read by pandas (not coerced to
    # datetime here) -- unchanged from the pre-refactor behavior. Some
    # models (LRMC family) do their own pd.to_datetime()/`.dt` handling
    # internally only when time_decay_halflife is actually enabled; forcing
    # it here would change the dtype written back out through
    # projections/team-file CSVs (Timestamp repr vs. the original string),
    # which isn't part of this refactor's scope.
    full_history = pd.read_csv(archive_path)
    season_df = full_history[full_history['Season'] == target_season].copy()

    if season_df.empty:
        if division == 'women':
            # Women's hockey doesn't reliably have a scraped schedule for
            # "the current" season yet (see reports/womens_hockey_import.md) --
            # fall back to the most recently completed season with real data,
            # same choice generate_womens_rankings.py made explicitly.
            target_season = int(full_history['Season'].max())
            season_df = full_history[full_history['Season'] == target_season].copy()
            manifest["target_season"] = target_season
            print(f"[Config] No women's games for the configured season; "
                  f"falling back to most recent available season {target_season}.")
        if season_df.empty:
            print(f"Warning: No data found for season {target_season}.")
            # Still record 0-games-played so the site can show an accurate
            # preseason banner instead of an old manifest's stale numbers.
            manifest["games_played_this_season"] = 0
            manifest["last_final_game_date"] = None
            return

    # Staleness/preseason indicators for the site (see the plan's "let the
    # site show a preseason banner instead of silently looking stale" goal).
    # Read directly off season_df rather than any model's fitted state, so
    # it's available even if every model happens to fail this run.
    manifest["games_played_this_season"] = int(len(season_df))
    manifest["last_final_game_date"] = (
        str(season_df['Date'].max()) if 'Date' in season_df.columns and not season_df.empty else None
    )

    should_run_analysis = config['output'].get('run_analysis', False)
    models_config = config.get('models', {})

    schedule_df = None
    if schedule_path.exists():
        schedule_df = pd.read_csv(schedule_path)
        schedule_df = schedule_df[schedule_df['Season'] == target_season].copy()

    preseason_conf = models_config.get('preseason', {})
    preseason_enabled = preseason_conf.get('enabled', False)
    preseason_apply_to = set(preseason_conf.get('apply_to', []))

    for model_key in active_models:
        print(f"\n--- Running {model_key} ({division}) ---")
        t0 = time.time()
        model_result = {"status": "ok", "steps": [], "error": None}

        try:
            prior = None
            if preseason_enabled and model_key in preseason_apply_to:
                prior, prior_meta = build_prior(full_history, target_season, model_key, config)
                if prior:
                    print(f"  [Preseason] Built prior for {len(prior)} teams "
                          f"(s-1 used: {prior_meta['season_s1_used']}, "
                          f"s-2 used: {prior_meta['season_s2_used']}, "
                          f"poll used: {prior_meta['poll_used']})")
                    model_result["preseason_prior"] = prior_meta

            model, current_config, _ = build_model(
                model_key, season_df, models_config, history_df=full_history, prior=prior
            )
            model.fit()

            # Rankings
            rankings = model.get_rankings()
            rank_out_dir = output_dir / "rankings" / model_key
            rank_out_dir.mkdir(parents=True, exist_ok=True)
            rankings.to_csv(rank_out_dir / f"rankings_{model_key}_{run_date}.csv", index=True, index_label="Rank")
            print(f"  Saved rankings.")
            model_result["steps"].append("rankings")

            # Projections
            if schedule_df is not None and not schedule_df.empty:
                preds = []
                for _, row in schedule_df.iterrows():
                    h, a = row['HomeTeam'], row['AwayTeam']
                    is_neutral = row.get('NeutralSite', False)
                    try:
                        prob = model.predict(h, a, is_neutral=is_neutral)
                    except Exception:
                        prob = 0.5
                    preds.append({
                        'Date': row['Date'], 'HomeTeam': h, 'AwayTeam': a, 'NeutralSite': is_neutral,
                        'HomeWinProb': round(prob, 3), 'ProjectedWinner': h if prob > 0.5 else a
                    })

                pred_df = pd.DataFrame(preds)
                proj_out_dir = output_dir / "projections" / model_key
                proj_out_dir.mkdir(parents=True, exist_ok=True)
                pred_df.to_csv(proj_out_dir / f"projections_{model_key}_{run_date}.csv", index=False)
                generate_team_files(pred_df, model_key, output_dir)
                print(f"  Saved projections.")
                model_result["steps"].append("projections")

            # --- RUN ANALYSIS ---
            if should_run_analysis:
                run_impact_analysis(
                    season_df, full_history, model_key, current_config, output_dir, run_date
                )
                model_result["steps"].append("analysis")

            # --- RUN SIMULATIONS ---
            if config['output'].get('run_simulations', False) and schedule_df is not None and not schedule_df.empty:
                from src.rankings.registry import resolve_model
                model_cls, _, _ = resolve_model(model_key)
                sim = MonteCarloSimulator(
                    model_class=model_cls,
                    model_config=current_config,
                    current_games_df=season_df,
                    upcoming_schedule_df=schedule_df
                )
                num_iters = config['output'].get('mc_iterations', 100)
                sim.run(num_iterations=num_iters)

                sim_out_dir = output_dir / "simulator" / model_key
                sim.save_results(sim_out_dir / f"rank_distributions_{run_date}.csv")
                model_result["steps"].append("simulations")

        except Exception as e:
            print(f"  -> Error executing {model_key}: {e}")
            import traceback
            traceback.print_exc()
            model_result["status"] = "error"
            model_result["error"] = str(e)

        model_result["elapsed_sec"] = round(time.time() - t0, 2)
        manifest["models"][model_key] = model_result


if __name__ == "__main__":
    main()
