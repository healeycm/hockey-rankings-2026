import yaml
import itertools
import pandas as pd
from pathlib import Path

# Project Imports
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine

# Models
from src.rankings.krach import KRACH
from src.rankings.lrmc import LRMC
from src.rankings.elo import ELO
from src.rankings.npi import NPI

# --- UPDATED CLASS MAP ---
# Map the string names from YAML to the actual Python Classes
CLASS_MAP = {
    "KRACH": KRACH,
    "ELO": ELO,
    "NPI": NPI,

    # Map all LRMC variants to the main LRMC class
    "LRMC_Classic": LRMC,
    "LRMC_Zero": LRMC,
    "LRMC_F": LRMC,
    "LRMC_Bayesian": LRMC,
    "LRMC_xG": LRMC
}

OT_CONFIGS = {
    "regulation": (1.0, 0.0),
    "weighted": (0.6, 0.4),
    "tie": (0.5, 0.5)
}


def load_tuning_config():
    root = Path(__file__).resolve().parents[2]
    path = root / "tuning_config.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path}")
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def generate_grid_combinations(model_name, settings):
    """
    Generates a list of (UniqueName, ConfigDict) tuples.
    """
    base = settings.get('base_config', {})
    grid = settings.get('grid', {})

    if not grid:
        return [(f"{model_name}_Base", base)]

    param_names = list(grid.keys())
    param_values = list(grid.values())

    combinations = []

    for combination in itertools.product(*param_values):
        specific_conf = base.copy()
        name_parts = [model_name]

        for i, param in enumerate(param_names):
            val = combination[i]
            specific_conf[param] = val

            # Shorten name: min_common_opponents -> opps2
            # use_ncaa_weights -> wtsTrue
            # margin_power -> pow0.5
            short_key = param.split('_')[-1][:4]
            name_parts.append(f"{short_key}{val}")

        unique_name = "_".join(name_parts)
        combinations.append((unique_name, specific_conf))

    return combinations


def main():
    print("--- Starting Batch Hyperparameter Tuning ---")

    # 1. Load Config
    config = load_tuning_config()
    exp_settings = config['experiment']

    # 2. Load Data
    print("Loading History...")
    loader = DataLoader()
    history_df = loader.get_history()

    # 3. Initialize Engine
    ot_mode = exp_settings.get('ot_mode', 'weighted')
    w_win, w_loss = OT_CONFIGS.get(ot_mode, (0.6, 0.4))

    output_dir = Path(__file__).resolve().parents[2] / "data" / "validation" / "tuning_batch"
    engine = BacktestEngine(
        history_df,
        output_dir,
        ot_win_weight=w_win,
        ot_loss_weight=w_loss
    )

    # 4. Generate Model Queue
    run_factory = {}
    run_configs = {}

    print("\nGenerating Experiment Grid:")

    for model_type, settings in config['models'].items():
        if not settings.get('enabled', False):
            continue

        if model_type not in CLASS_MAP:
            print(f"Warning: Unknown model type '{model_type}' in config. Skipping.")
            continue

        ModelClass = CLASS_MAP[model_type]
        combos = generate_grid_combinations(model_type, settings)

        for unique_name, conf in combos:
            run_factory[unique_name] = ModelClass
            run_configs[unique_name] = conf

            # NPI Logic helper
            if model_type == 'NPI' and 'weight_wp' in conf:
                conf['weight_sos'] = 1.0 - conf['weight_wp']

    print(f"  -> Queueing {len(run_factory)} separate model configurations.")

    # 5. Run Batch
    seasons = exp_settings['seasons']
    cutoffs = exp_settings['cutoffs']

    engine.run(seasons, cutoffs, run_factory, run_configs)

    # 6. Save & Report
    engine.save_results()

    # 7. Print Leaderboard
    agg_path = output_dir / "backtest_aggregate.csv"
    if agg_path.exists():
        df = pd.read_csv(agg_path)
        df = df.sort_values("Brier", ascending=True)

        print("\n" + "=" * 60)
        print("TUNING LEADERBOARD (Top 10 Configurations)")
        print("=" * 60)
        print(df[['Model', 'Brier', 'Accuracy', 'LogLoss']].head(10).to_string(index=False))
        print("=" * 60)
        print(f"Full results saved to: {output_dir}")


if __name__ == "__main__":
    main()