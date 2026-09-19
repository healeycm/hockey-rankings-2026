"""
Tests for src/rankings/registry.py -- the single model-key -> class/config
mapping that replaced two separately-maintained if/elif chains (run_system.py's
dispatch and interpreter.py's _get_model_class), which had already drifted
apart (interpreter.py silently lacked HockeyBT/RPI/HockeyLRMC/DixonColes/
Keener/Glicko2/Ensemble). See reports/in_season_revamp_plan.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from src.rankings.registry import (
    resolve_model, validate_active_models, get_model_config, build_model, known_model_keys,
)
from src.rankings.hockey_bt import HockeyBT
from src.rankings.rpi import RPI
from src.rankings.keener import Keener
from src.rankings.glicko2 import Glicko2
from src.rankings.dixon_coles import DixonColes
from src.rankings.ensemble import Ensemble
from src.rankings.lrmc import LRMC
from src.rankings.hockey_lrmc import HockeyLRMC


# The exact bug this registry fixes: these model_keys are real, active
# production models (all appear in config.yaml) that interpreter.py's old
# hardcoded mapping did NOT know about, so Leave-One-Out sensitivity
# analysis silently produced nothing for them.
PREVIOUSLY_MISSING_FROM_INTERPRETER = [
    "HockeyBT", "RPI", "DixonColes", "Ensemble", "Keener", "Glicko2",
]


@pytest.mark.parametrize("model_key", PREVIOUSLY_MISSING_FROM_INTERPRETER)
def test_previously_missing_models_now_resolve(model_key):
    resolved = resolve_model(model_key)
    assert resolved is not None, f"{model_key} should be resolvable -- this is exactly the bug the registry fixes."


def test_hockey_lrmc_prefix_family_resolves():
    resolved = resolve_model("HockeyLRMC")
    assert resolved is not None
    cls, config_ref, needs_history = resolved
    assert cls is HockeyLRMC
    assert needs_history is True
    assert config_ref == ("hockey_lrmc", "HockeyLRMC")


def test_lrmc_prefix_family_resolves_variants():
    for variant in ["LRMC_Classic", "LRMC_Zero", "LRMC_F", "LRMC_Dynamic", "LRMC_SomeNewVariant"]:
        resolved = resolve_model(variant)
        assert resolved is not None, f"{variant} should resolve via the LRMC prefix family"
        cls, config_ref, needs_history = resolved
        assert cls is LRMC
        assert needs_history is True
        assert config_ref == ("lrmc", variant)


def test_unknown_model_key_does_not_resolve():
    assert resolve_model("NotARealModel") is None


def test_validate_active_models_raises_on_unknown():
    with pytest.raises(ValueError, match="NotARealModel"):
        validate_active_models(["KRACH", "NotARealModel"])


def test_validate_active_models_passes_for_known_list():
    # Should not raise.
    validate_active_models(["KRACH", "Massey", "HockeyBT", "RPI", "NPI", "ELO"])


def test_get_model_config_resolves_nested_lrmc_variant():
    models_config = {
        "lrmc": {"LRMC_Classic": {"margin_cap": 3, "variant": "classic"}},
    }
    cfg = get_model_config("LRMC_Classic", models_config)
    assert cfg == {"margin_cap": 3, "variant": "classic"}


def test_get_model_config_missing_section_returns_empty_dict():
    assert get_model_config("KRACH", {}) == {}
    assert get_model_config("Massey", {}) == {}


def test_build_model_instantiates_and_fits(tmp_path):
    import pandas as pd
    games = pd.DataFrame({
        'Season': [20252026] * 4,
        'Date': pd.to_datetime(['2025-11-01', '2025-11-02', '2025-11-08', '2025-11-09']),
        'HomeTeam': ['Wisconsin', 'Minnesota', 'Wisconsin', 'Minnesota'],
        'AwayTeam': ['Minnesota', 'Wisconsin', 'Minnesota', 'Wisconsin'],
        'HomeGoals': [3, 2, 4, 1], 'AwayGoals': [1, 2, 2, 3],
        'Result': [1.0, 0.5, 1.0, 0.0], 'IsOT': [False, False, False, False],
        'NeutralSite': [False, False, False, False],
    })
    models_config = {"massey": {"margin_cap": 3, "fit_home_ice": True, "ridge_lambda": 1.0, "fit_beta": False}}
    model, resolved_config, needs_history = build_model("Massey", games, models_config)
    model.fit()
    assert model.ratings  # populated
    assert resolved_config == models_config["massey"]
    assert needs_history is False


def test_build_model_unknown_key_raises():
    with pytest.raises(KeyError):
        build_model("NotARealModel", None, {})
