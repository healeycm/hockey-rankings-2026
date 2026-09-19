# src/utils/config.py
import yaml
from pathlib import Path


def load_config(config_path="config.yaml"):
    """
    Loads the YAML configuration file from the project root.
    """
    # Resolve path relative to the project root
    # src/utils/config.py -> ... -> hockey_rankings/
    root_dir = Path(__file__).resolve().parents[2]
    full_path = root_dir / config_path

    if not full_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {full_path}")

    with open(full_path, "r") as f:
        try:
            config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML config: {exc}")