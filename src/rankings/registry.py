# src/rankings/registry.py
"""
Single source of truth mapping a model_key (as it appears in config.yaml's
active_models list) to its class, config location, and whether it needs the
full multi-season history_df (the LRMC family's time-decay / cross-season
fitting needs this; everything else only needs the current season).

Before this file existed, src/run_system.py's model-dispatch if/elif chain
and src/analysis/interpreter.py's RankInterpreter._get_model_class had two
SEPARATELY maintained copies of this mapping, and they had already drifted:
interpreter.py's copy was missing HockeyBT, RPI, HockeyLRMC, DixonColes,
Keener, Glicko2, and Ensemble. Since find_impact_games() silently returns an
empty DataFrame for an unrecognized model_name, those models were getting
ZERO Leave-One-Out sensitivity analysis with no error anywhere — confirmed
on disk: output/analysis/ had no HockeyBT/RPI/HockeyLRMC directories despite
all three being in active_models. See reports/in_season_revamp_plan.md.

Both run_system.py and interpreter.py now import THIS mapping, so a model
added here is automatically available in both places, and an unrecognized
model_key raises immediately instead of being silently skipped.
"""
from src.rankings.krach import KRACH
from src.rankings.elo import ELO
from src.rankings.npi import NPI
from src.rankings.colley import Colley
from src.rankings.massey import Massey
from src.rankings.markov import Markov
from src.rankings.hockey_bt import HockeyBT
from src.rankings.rpi import RPI
from src.rankings.dixon_coles import DixonColes
from src.rankings.ensemble import Ensemble
from src.rankings.keener import Keener
from src.rankings.glicko2 import Glicko2
from src.rankings.lrmc import LRMC
from src.rankings.gw_lrmc import gwLRMC
from src.rankings.hockey_lrmc import HockeyLRMC

# Exact model_key -> (class, config_section, needs_history).
# config_section names a key under config.yaml's `models:` section; None
# means no config section exists for this model (KRACH is parameter-free).
_EXACT = {
    "KRACH":      (KRACH, None, False),
    "ELO":        (ELO, "elo", False),
    "NPI":        (NPI, "npi", False),
    "Massey":     (Massey, "massey", False),
    "Colley":     (Colley, "colley", False),
    "Markov":     (Markov, "markov", False),
    "HockeyBT":   (HockeyBT, "hockey_bt", False),
    "RPI":        (RPI, "rpi", False),
    "DixonColes": (DixonColes, "dixon_coles", False),
    "Ensemble":   (Ensemble, "ensemble", False),
    "Keener":     (Keener, "keener", False),
    "Glicko2":    (Glicko2, "glicko2", False),
}

# Prefix-based families: model_key must start with the prefix. Each
# variant's config lives at config['models'][section][model_key] (e.g.
# "LRMC_Classic" resolves to config['models']['lrmc']['LRMC_Classic']),
# mirroring the flexibility the old startswith()-based dispatch had: adding
# a brand-new LRMC_* variant only requires a config.yaml entry, no code
# change. Order matters — check the more specific prefixes first, though in
# practice "HockeyLRMC"/"gwLRMC" don't collide with the bare "LRMC" prefix
# since neither starts with the literal substring "LRMC".
_PREFIX_FAMILIES = [
    ("HockeyLRMC", HockeyLRMC, "hockey_lrmc", True),
    ("gwLRMC", gwLRMC, "gw_lrmc", True),
    ("LRMC", LRMC, "lrmc", True),
]


def resolve_model(model_key):
    """
    Returns (ModelClass, config_ref, needs_history) for a given model_key,
    or None if no rule recognizes it. config_ref is either a plain section
    name (str), a (section, variant_key) tuple for prefix families, or None.
    """
    if model_key in _EXACT:
        return _EXACT[model_key]
    for prefix, cls, section, needs_history in _PREFIX_FAMILIES:
        if model_key.startswith(prefix):
            return cls, (section, model_key), needs_history
    return None


def known_model_keys():
    """All model_keys resolvable without needing a prefix-family config.yaml entry."""
    return sorted(_EXACT.keys())


def validate_active_models(active_models):
    """
    Raises ValueError listing every unrecognized model_key, instead of the
    old behavior of silently printing '-> Skipping unknown: X' and moving
    on. Call this once at startup so a typo in config.yaml's active_models
    fails loudly before any (possibly expensive) work runs.
    """
    unknown = [m for m in active_models if resolve_model(m) is None]
    if unknown:
        raise ValueError(
            f"Unknown model_key(s) in config.yaml active_models: {unknown}. "
            f"Known exact keys: {known_model_keys()}. "
            f"Prefix families (need a matching config.yaml entry too): "
            f"{[p for p, *_ in _PREFIX_FAMILIES]}."
        )


def get_model_config(model_key, models_config):
    """
    Resolves a model_key's config dict from config['models'] without
    constructing the model. Used by callers (e.g. RankInterpreter) that
    need the config but instantiate the model themselves.
    """
    resolved = resolve_model(model_key)
    if resolved is None:
        raise KeyError(f"Unknown model_key '{model_key}' — not in registry (src/rankings/registry.py).")
    _, config_ref, _ = resolved
    if config_ref is None:
        return {}
    if isinstance(config_ref, tuple):
        section, variant_key = config_ref
        return models_config.get(section, {}).get(variant_key, {})
    return models_config.get(config_ref, {})


# model_keys whose __init__ accepts a `prior` kwarg (see
# src/rankings/priors.py). Anything not listed here silently ignores a
# passed-in prior rather than erroring, so build_model can always attempt
# to pass one without every model needing to support it.
_ACCEPTS_PRIOR = {"ELO", "Massey"}


def build_model(model_key, season_df, models_config, history_df=None, prior=None):
    """
    Instantiates a model from its config.yaml active_models key.

    `models_config` is config['models'] (the whole `models:` section of
    config.yaml). Returns (model_instance, resolved_config_dict, needs_history)
    so callers that need to pass the same config elsewhere (e.g. into the
    Monte Carlo simulator or the LOO sensitivity analysis) don't have to
    re-resolve it.

    `prior`, if given, is a {team: prior_rating} dict (see
    src/rankings/priors.py) forwarded only to models in _ACCEPTS_PRIOR --
    passing one for a model that doesn't support it is a silent no-op, not
    an error, so callers don't need to special-case each model.
    """
    resolved = resolve_model(model_key)
    if resolved is None:
        raise KeyError(f"Unknown model_key '{model_key}' — not in registry (src/rankings/registry.py).")
    ModelClass, _, needs_history = resolved
    current_config = get_model_config(model_key, models_config)

    kwargs = {"config": current_config}
    if needs_history:
        kwargs["history_df"] = history_df
    if prior is not None and model_key in _ACCEPTS_PRIOR:
        kwargs["prior"] = prior

    return ModelClass(season_df, **kwargs), current_config, needs_history
