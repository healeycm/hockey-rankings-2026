# Plan: A Hockey-Specific Ranking Model to Beat KRACH and NPI

> Results of executing this plan are in
> [reports/hockey_bt_results.md](hockey_bt_results.md).

## The opening: neither incumbent wins on both axes

From the 5-year/20-split backtest:

| Model | Accuracy | Brier | LogLoss |
|---|---|---|---|
| KRACH | **63.80%** | 0.1840 | 0.6682 |
| NPI | 62.44% | **0.1764** | **0.6452** |

**KRACH ranks best but is poorly calibrated; NPI calibrates best but ranks
worse.** That split is the opportunity — and it's explained by rating
spread: KRACH's ratings span 1.01–1298 (**1284x**), producing overconfident
probabilities, while NPI's bounded 0–100 scale spans 39–65 (**1.67x**). The
target is a model with KRACH's ordering and NPI's calibration.

## Three verified gaps in KRACH

1. **KRACH models zero home-ice advantage.** Its own docstring says so:
   `predict()` is just `K_h/(K_h+K_a)`. In the 5 backtest seasons, home
   teams win **56.65%** of decisive non-neutral games (logit 0.267). KRACH
   models that as a coin flip.
2. **KRACH treats OT wins as full wins.** OT/SO games are **20.2%** of all
   games — one in five.
3. **The outcome structure is genuinely three-state, and KRACH's
   Bradley-Terry core assumes two.** Regulation is ~46%/34% home/away win
   with ~0% ties; **99.3% of ties occur in OT**, and 37% of OT games end as
   official ties. Overall tie rate 7.5%, stable across seasons (6.4–8.5%).

That third point is the real insight: NCAA hockey isn't a win/loss sport,
it's a **win/tie/loss** sport with the ties concentrated in a distinct game
state.

## The proposed model: Davidson–Beaver (Bradley-Terry + ties + order effect)

An established extension of exactly the model KRACH already uses — not an
invention:

```
P(i beats j)  =  Kᵢ·θ / (Kᵢ·θ + Kⱼ + ν·√(Kᵢ·θ·Kⱼ))
P(tie)        =  ν·√(Kᵢ·θ·Kⱼ) / (Kᵢ·θ + Kⱼ + ν·√(Kᵢ·θ·Kⱼ))
```

- **θ** — home-ice order effect (θ=1 at neutral sites), fit by MLE
- **ν** — tie propensity, fit by MLE
- **κ** — a mild prior (MAP rather than MLE) for regularization

Why this should beat both:

- **vs. KRACH:** adds the three things it verifiably lacks (home ice, tie/OT
  structure, regularization), *inside* KRACH's own framework — so it keeps
  every KRACH virtue: maximum-likelihood self-consistency, no paradoxes
  (beating anyone always helps), order-invariance, no committee dials.
- **vs. NPI:** parameters are fit from data, not chosen by committee. No 75%
  SOS weight to amplify conferences (NPI's echo-chamber ρ=0.886), no
  outcome-based bad-wins filter (selection bias), no paradoxes.
- **The calibration fix:** replacing KRACH's crude `max(points, 0.1)`
  winless-team hack with a proper prior addresses both the divergence
  problem *and* the 1284x spread that wrecks its Brier/LogLoss.

**Bonus capability:** it predicts P(tie) natively.

## Build as strictly nested variants, each independently ablatable

| Variant | Adds | Hypothesis |
|---|---|---|
| **K0** | KRACH reproduction | Correctness check — with θ=1, ν=0, no prior, must reproduce KRACH's ratings exactly |
| **K1** | + home-ice θ | Highest confidence — modeling a 56.65% effect currently modeled as 50% |
| **K2** | + tie parameter ν | Second highest — 20% of games, 7.5% ties |
| **K3** | + MAP prior κ | Targets the calibration gap specifically (Brier/LogLoss vs NPI) |
| **K4** | + recency weighting λ | Speculative — ablate, expect to reject |

K0 as a nested-model correctness test is important: it proves the new
solver is right before trusting any of its extensions.

## Implementation

- `src/rankings/hockey_bt.py`, subclassing `BaseRanker` (inherits the DI
  filter automatically).
- Solver: `scipy.optimize.minimize` (L-BFGS-B) on the negative
  log-likelihood over log-ratings + log θ + log ν.
- **Deliberately NOT included:**
  - No margin of victory — proved twice this project it doesn't help in
    hockey, and it's indefensible for selection use.
  - No outcome-based game filtering — NPI's bad-wins filter is selection
    bias for negligible gain.

## Pre-registered success criteria

- Must beat KRACH accuracy (> 63.80%)
- Must beat NPI on Brier (< 0.1764) **and** LogLoss (< 0.6452)
- Paired per-game significance tests, not just split means
- Ablation must show which components earn their keep

**Honest expectation going in:** K1 near-certain to help. K2 well-founded.
K3 the one aimed at the NPI calibration gap and most likely to disappoint.
Beating KRACH on accuracy looked achievable; beating NPI on both calibration
metrics looked like even odds.

**Fallback:** even a partial win ("KRACH + home ice + tie modeling" beats
plain KRACH) would be a worthwhile result on its own.
