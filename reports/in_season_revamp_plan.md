# In-Season Calculations Revamp — Plan and Results

**Date:** 2026-09-07
**Status:** Phases 1, 2, 4, and 5 complete and verified below. Phase 3 (active-model trim) applied with a stated default the user can override in one line — see §3.

## 0. Motivation

The in-season pipeline (rankings, sensitivity/impact analysis, simulations) had accumulated four structural problems: two independently-maintained model dispatch tables that had already drifted apart and were silently dropping models from sensitivity analysis; sensitivity analysis doing roughly 2x the necessary model refits; a simulator re-predicting constant values on every iteration; and zero automation (no scheduled runs, no failure visibility). This revamp addresses all four, cuts per-model sensitivity-analysis cost by ~4x, and adds a run manifest so a failing model is reported instead of silently vanishing from the website.

## 1. One registry, one dispatch

**The bug, confirmed on disk before any code changed:** [`src/analysis/interpreter.py`](../src/analysis/interpreter.py)'s old `_get_model_class` mapping was missing `HockeyBT`, `RPI`, `HockeyLRMC`, `DixonColes`, `Keener`, `Glicko2`, and `Ensemble` — all of which were present in [`run_system.py`](../src/run_system.py)'s separate if/elif dispatch and (for the first three) in `config.yaml`'s `active_models`. Since `find_impact_games` silently returns an empty DataFrame for an unrecognized model, `output/analysis/` had no `HockeyBT`/`RPI`/`HockeyLRMC` directories despite all three running rankings/projections successfully — zero sensitivity analysis, no error anywhere.

**Fix:** [`src/rankings/registry.py`](../src/rankings/registry.py) is now the single source of truth: `resolve_model(model_key)` → `(class, config_ref, needs_history)`. `run_system.py` and `interpreter.py` both import it; a model added to the registry is automatically available in both places. `validate_active_models()` is called once at startup and **raises immediately** on an unrecognized `active_models` entry (previously: `print(f"-> Skipping unknown: {model_key}")` and silently continuing).

`src/generate_womens_rankings.py`, the standalone script that duplicated a slice of this pipeline for women's hockey (rankings only — no projections, sensitivity, or simulations), is retired to a thin deprecation wrapper around `python -m src.run_system --division women`. One entry point now covers both divisions and all four output types.

## 2. Performance

- **Leave-One-Out sensitivity analysis** ([`interpreter.py`](../src/analysis/interpreter.py)): rewritten from a per-(team, game) loop to a per-game loop — dropping one game updates ratings for both its teams at once, so the number of refits is roughly halved — and parallelized with joblib (previously fully serial). **Verified byte-identical** to the old per-team method on real 2025-26 data (5 spot-checked teams, all rating-impact values matched to 6 decimals) and via a dedicated regression test ([`test_interpreter_loo.py`](../tests/unit/test_interpreter_loo.py)) across KRACH/Massey/ELO on synthetic data. Measured: **8.1s (batched, parallel) vs. 31.2s (extrapolated serial, old method)** for all 63 teams in the 2025-26 season under Massey — roughly **3.8x faster**.
- **Monte Carlo simulator** ([`simulator.py`](../src/analysis/simulator.py)): the baseline win-probability prediction for every upcoming game is now computed once in `run()` and cached, instead of being recomputed inside every one of `num_iterations` (default 500) loop passes.

**A real bug found while making this change, not introduced by it:** simulated future games' `Date` field is built as `pd.Timestamp`, while `current_games_df`'s `Date` column (as loaded from CSV, unchanged) stays a plain string. Concatenating the two left a mixed-dtype `Date` column; any model that sorts by Date (Massey's `fit_beta`, which builds a temporal holdout split via `df.sort_values('Date')`) crashed with `TypeError: '<' not supported between Timestamp and str`. This was previously invisible — `run_system.py`'s broad per-model `except Exception: continue` swallowed it with no record of which model failed. It only surfaced because the new run manifest (§4) reports per-model failures explicitly; confirmed via an end-to-end smoke run (`python -m src.run_system`, active_models trimmed to `[KRACH, Massey, NPI]`, `run_simulations: true`) which failed exactly this way before the fix. **Fixed:** `MonteCarloSimulator.__init__` now normalizes `current_games_df['Date']` to datetime. Regression test added ([`test_simulator.py`](../tests/unit/test_simulator.py)) reproducing the exact scenario (string-dated `current_games_df` + Massey with `fit_beta`) — confirmed failing before the fix, passing after.

## 3. Active-model trim (Phase 3)

`config.yaml`'s `active_models` is trimmed from 12 models to the 6 this project's own validation reports actually support running in production:

- **Massey** — best model overall (Accuracy/Brier/LogLoss, all 9 backtest comparisons significant)
- **HockeyBT** — beats KRACH on calibration and NPI on accuracy simultaneously
- **KRACH, NPI** — kept as the incumbent/selection-committee-relevant methods
- **RPI** — kept for its diagnostic value versus NPI, not because it's a top model

Removed: `Colley`, `Markov`, `LRMC_Classic`, `LRMC_Zero`, `LRMC_F`, `HockeyLRMC` — none of these beat Massey in this project's backtests (or, for Colley/Markov, were never head-to-head validated against it at all). **This is a judgment call, not a technical necessity** — every removed model is still fully implemented and configured in `config.yaml`, just commented out of the active list; adding one back is a one-line edit. Sensitivity analysis and simulation cost both scale linearly with this list's length, so this is the single biggest lever on total run time.

`config.yaml` also gains `models.active_models_women` (the 5-model set from `reports/womens_hockey_import.md`'s backtest) and `system.division` (`"men"` default; `--division` on the CLI overrides it).

## 4. Automation

- **Run manifest** ([`run_system.py`](../src/run_system.py)): every run writes `output/last_run.json` (or `output/women/last_run.json`) recording division, season, run date, and per-model status/steps-completed/elapsed-time/error. The final console summary now explicitly lists succeeded vs. failed models instead of only the timestamp-coincidence the website previously relied on to infer completeness.
- **[`scripts/daily_update.py`](../scripts/daily_update.py)**: scrape → process → run, for one or both divisions, checking the manifest afterward and exiting non-zero if any model failed.
- **[`scripts/register_task.ps1`](../scripts/register_task.ps1)**: registers a Windows Task Scheduler job (`HockeyRankingsDailyUpdate`, daily 6:00 AM) running `daily_update.py` under this project's conda environment. Not run automatically — the user runs it once, from an elevated PowerShell prompt, to opt in.

## 5. Verification

- Full unit suite: **104/104 passing** (83 pre-existing + 21 new: `test_registry.py`, `test_interpreter_loo.py`, `test_simulator.py`).
- Batched LOO vs. old per-team LOO: verified identical on real 2025-26 data and via regression test on synthetic data.
- End-to-end smoke test, men's division, real 2025-26 season data, 3 models (KRACH/Massey/NPI), full pipeline (rankings + projections + analysis + simulations): all 3 succeeded, manifest correctly recorded 0 failures. Ran again with the Massey/simulator bug present (before the fix) to confirm the manifest actually surfaces it, then again after the fix to confirm it's resolved.
- End-to-end smoke test, women's division: rankings + projections + analysis all ran through `run_system.py --division women` (simulations correctly skipped — the 2026-27 women's schedule isn't scraped yet, so there's nothing to simulate); confirmed the automatic season fallback (falls back to the most recent season with real data when the configured season has none) fires for women's and does NOT change men's "no data" warning behavior.
- All test-run output artifacts (dated 2026-09-07) were deleted after verification; pre-existing historical outputs (2025-12 through 2026-03-31) were left untouched.

## 6. Open items

- **HockeyLRMC/gwLRMC/LRMC-family + MonteCarloSimulator**: the simulator's `model_class(full_season, config=...)` call never passes `history_df`, so time-decay/history-dependent LRMC variants were already unsupported in simulation before this revamp (not a regression — just not exercised or fixed here, since none of them are in the trimmed `active_models`).
- **Fit-caching across steps** (rankings → projections → sensitivity → simulation reusing one baseline fit per model) — mentioned in the original plan, not implemented in this pass; each step still fits its own baseline model. Given the actual per-fit costs measured (16-134ms), this wasn't worth the added complexity right now; revisit if a future model's fit cost changes that calculus.
- `scripts/register_task.ps1` has not been run — registering the scheduled task is the user's call, not something to do unprompted.
- Conference data, women's team-detail pages, and the other items already logged in `reports/womens_hockey_import.md` remain open from that phase and are unaffected by this one.
