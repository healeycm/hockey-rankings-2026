# Empty-Net Goals: Real Data vs. the Blind Proxy

## Summary

Two sessions ago, `HockeyLRMC` shipped with a *blind* empty-net heuristic
(shrink any 2-goal margin toward 1.75, whether or not an empty-net goal
actually happened) that showed no measurable backtest benefit. That result
was ambiguous: "empty-net correction doesn't matter" or "the proxy was just
a bad guess"? We then scraped **real** empty-net-goal data from CHN box
scores to settle it.

**Answer: it genuinely doesn't help.** With real per-game empty-net-goal
counts, the correction still doesn't improve the model — it very slightly
*hurts*, consistently across two independent test harnesses. This is the
stronger negative result the exercise was designed to produce.

## The data

`extract_empty_net_goals()` in
[src/data/advanced_metrics_scraper.py](../src/data/advanced_metrics_scraper.py)
parses CHN's `<div id="scoring">` goal-by-goal table, using each row's
`vscore`/`hscore` CSS class to attribute the goal (the team-name text is
inconsistently an abbreviation or a full name) and the second `<td>`'s
situation tag (`EN`) to identify empty-netters.
[src/data/backfill_eng.py](../src/data/backfill_eng.py) backfilled the
existing scrapes via their stored box-score URLs.

Coverage (CHN advanced-stats seasons only):

| Season | Games | With ENG data |
|---|---|---|
| 2024-25 | 1170 | 1055 |
| 2025-26 | 1143 | 521 |

**27% of covered games (424/1576) had at least one empty-net goal**, mean
0.289 per game — a real, non-trivial signal, not a rounding error.

## The ablation

Three arms, run on the two ENG-covered seasons only (including 2021-24 would
dilute the comparison with three seasons where all arms are identical),
4 cutoffs each = 8 splits:

- `ENG_none` — no empty-net correction
- `ENG_proxy` — the old blind 2-goal-margin heuristic
- `ENG_real` — subtract actual empty-net goals from the margin before capping

| Arm | Accuracy | Brier | LogLoss |
|---|---|---|---|
| ENG_none | **62.97%** | 0.18256 | **0.68236** |
| ENG_proxy | 63.03% | **0.18255** | 0.68239 |
| ENG_real | 62.86% | 0.18315 | 0.68389 |

`ENG_real` is **worst on all three metrics**, winning only 3 of 8 splits.

An independent paired per-game test (own harness, n=3,097 pooled test games,
both target conventions, both pooled and split-averaged weighting) agreed
and gave it statistical teeth: real-ENG was **significantly worse** than no
correction (Brier diff +0.00048, paired t=4.72, **p<0.0001**; LogLoss diff
+0.00108, p<0.0001).

## Why it doesn't help

`margin_cap=3` already absorbs most empty-net inflation. An empty-net goal
typically turns a 1-goal game into a 2-goal game, or a 2 into a 3 — all
inside the cap, in the region where the fitted logistic is fairly flat
(β≈0.15–0.19, so a one-goal shift moves the vote probability by only ~4pp).
Meanwhile, subtracting empty-netters compresses many games toward 0–1 goal
margins, discarding genuine signal: a team that was up 2 and iced an
empty-netter *was* in fact controlling that game. Net, the correction
removes about as much real signal as noise.

## Shipped

`use_real_eng` defaults to **False** in
[src/rankings/hockey_lrmc.py](../src/rankings/hockey_lrmc.py) — a config
flag was added specifically so this could be ablated cleanly (it had
previously been unconditionally applied whenever the columns existed, which
made a clean comparison impossible). The scraping, backfill, and loader
plumbing all stay — the data is real, correct, and now available for any
future use (e.g. an xG-style model where raw margin matters more, or a
different margin treatment where the cap isn't doing this much work).

Regression tests
([tests/unit/test_hockey_lrmc.py](../tests/unit/test_hockey_lrmc.py)):
the correction math is verified when explicitly enabled, and a companion
test pins the off-by-default behavior so it can't silently flip back.

## Bug found along the way: BacktestEngine ignored `history_df`

While reconciling a disagreement between two harnesses, found that
`BacktestEngine.run()` instantiated every model as
`ModelClass(train_df, config=config)` — **never passing `history_df`**. Any
config specifying `fit_source: 'history'` (which every LRMC-family config in
this project does) silently fell back to season-only fitting inside the
model. Every LRMC/HockeyLRMC backtest number reported in this project prior
to this fix was therefore produced by a mis-configured harness.

Fixed in [src/backtesting/backtest_engine.py](../src/backtesting/backtest_engine.py),
passing history **truncated to before the cutoff date** — passing the full
history would leak test-window games into the model's α/β fit and flatter
every history-fitted model. (Note: my own scratch harness did have that
leak; since both arms shared it, the ENG comparison itself stayed valid, but
the engine is the authoritative harness going forward.)

Re-ran the headline 5-year backtest with the fix. Conclusions unchanged,
numbers now faithful:

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| KRACH | **63.80%** | 0.1840 | 0.6682 |
| NPI | 62.44% | **0.1764** | **0.6452** |
| HockeyLRMC | 62.39% | 0.1891 | 0.7050 |
| LRMC_Classic | 59.02% | 0.1930 | 0.7143 |

HockeyLRMC's advantage over LRMC_Classic actually *widens* to +3.4pp with
the harness fixed (LRMC_Classic was the model most flattered by the
accidental season-only fitting).

## Running it

```
python -m analysis.exploratory.five_year_backtest      # headline 5-model comparison
```
The ENG ablation script is in the session scratchpad; its three arms are
just `use_real_eng` / `empty_net_shrink` toggles on `HockeyLRMC` over
seasons `[20242025, 20252026]`.
