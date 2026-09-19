import pandas as pd
from pathlib import Path

# Imports
from src.data.loader import DataLoader
from src.backtesting.backtest_engine import BacktestEngine
from src.utils.config import load_config

# Import Models
from src.rankings.krach import KRACH
from src.rankings.lrmc import LRMC
from src.rankings.elo import ELO
from src.rankings.npi import NPI
from src.rankings.colley import Colley
from src.rankings.massey import Massey
from src.rankings.markov import Markov
from src.rankings.gw_lrmc import gwLRMC

# --- OVERTIME WEIGHTING CONFIGURATION ---
# Options:
#   "regulation": Win=1.0, Loss=0.0 (Standard Binary)
#   "weighted":   Win=0.6, Loss=0.4 (Common for analysis)
#   "tie":        Win=0.5, Loss=0.5 (Treat OT as draws)
#   "custom":     Set your own values below

OT_MODE = "weighted"

# Define the weights (Win Weight, Loss Weight)
OT_CONFIGS = {
    "regulation": (1.0, 0.0),
    "weighted": (0.6, 0.4),
    "tie": (0.5, 0.5),
    "custom": (0.55, 0.45)
}

# --- MODEL CONFIGURATION ---
MODELS_TO_TEST = {
    "KRACH": KRACH,
    "ELO": ELO,
    "NPI": NPI,
    "LRMC_Classic": LRMC,
    #"LRMC_Robust": LRMC,
    "LRMC_xG": LRMC,
    "LRMC_F": LRMC,
    "LRMC_Bayesian": LRMC,
    "LRMC_Zero": LRMC,
    "Massey": Massey,
    "Colley": Colley,
    "Markov": Markov,
    "gwLRMC": gwLRMC
}


def main():
    print("--- Initializing Validation Run ---")

    # 1. Load System Config (for Model hyperparameters)
    try:
        sys_config = load_config()
        model_configs = sys_config.get('models', {})

        # Helper to construct the config dictionary expected by BacktestEngine
        # The engine expects a dict { "ModelName": {config_dict} }
        # We need to map our specific keys (LRMC_Classic) to their configs in YAML

        # Start with LRMC configs
        full_configs = model_configs.get('lrmc', {}).copy()

        # Add ELO and NPI configs
        full_configs['ELO'] = model_configs.get('elo', {})
        full_configs['NPI'] = model_configs.get('npi', {})

        # KRACH usually has no config, but we can pass empty dict
        full_configs['KRACH'] = {}

    except Exception as e:
        print(f"Warning: Config loading failed ({e}). Using defaults.")
        full_configs = {}

    # 2. Determine OT Weights
    ot_weights = OT_CONFIGS.get(OT_MODE, (1.0, 0.0))
    print(f"Overtime Mode: {OT_MODE} -> Weights: {ot_weights}")

    # 3. Define Seasons (Last 9 Non-Covid)
    target_seasons = [
        20242025
        #20242025, 20232024, 20222023, 20212022,  # Post-Covid
        # 20202021 Skipped
        #20192020, 20182019, 20172018, 20162017, 20152016, 20142015, 20132014, 20122013  # Pre-Covid
    ]
    cutoffs = ['Jan']

    # 4. Load Data
    print("Loading historical data...")
    loader = DataLoader()
    try:
        history_df = loader.get_history()
    except Exception as e:
        print(f"Error loading history: {e}")
        return

    # Set Output Directory
    output_dir = Path(__file__).resolve().parents[2] / "data" / "validation" / "backtest_results"

    # 5. Initialize Engine with Flexible Weights
    engine = BacktestEngine(
        history_df,
        output_dir,
        ot_win_weight=ot_weights[0],
        ot_loss_weight=ot_weights[1]
    )

    # 6. Run Backtest
    # Note: We pass full_configs so the engine can look up "LRMC_Classic" config
    # when iterating through MODELS_TO_TEST keys.
    engine.run(
        seasons=target_seasons,
        cutoffs=cutoffs,
        model_factory=MODELS_TO_TEST,
        model_configs=full_configs
    )

    engine.save_results()


if __name__ == "__main__":
    main()