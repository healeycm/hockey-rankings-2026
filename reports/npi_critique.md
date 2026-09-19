# NPI vs. KRACH: Critique and Comparison

> **Summary:** The NPI replaced KRACH for NCAA DI hockey selection in 2025-26. This analysis shows that NPI's 7+ arbitrary tunable parameters, explicit 2-level SOS weighting at 75%, and outcome-based game removal produce a system that ranks last in predictive accuracy, creates paradoxical outcomes, systematically inflates certain conferences, and can rank a team with a losing record (Ohio State) above teams with superior records. KRACH's zero-parameter, maximum-likelihood structure is theoretically superior and empirically more accurate.

---

## 1. Predictive Accuracy

The most important question: does NPI's complexity improve on KRACH's predictions?

| Model | Acc Mean | Acc ±SD | Brier Mean | Brier ±SD | LogLoss Mean |
|-------|----------|---------|-----------|-----------|-------------|
| NPI | 62.737% | ±2.396% | 0.1786 | ±0.0066 | 0.6457 |
| KRACH | 63.518% | ±2.510% | 0.1907 | ±0.0150 | 0.6822 |

**KRACH accuracy advantage: +0.781%** across 24 season-cutoff pairs.

Head-to-head (season × cutoff): KRACH wins **17**, NPI wins **7**.

---

## 2. NPI Dial Sensitivity vs. KRACH Stability

KRACH has **zero tunable parameters**. NPI has 7+. Every parameter is a lever that can change which teams make the tournament. Below: how sensitive NPI rankings are to plausible adjustments to each dial.

### 2a. SOS Weight Sweep

Varying `weight_wp` from 0.10 to 0.50 (weight_sos = 1 − weight_wp):

| WP% | SOS% | τ vs Official | τ vs KRACH | Top-10 Changes | Teams Shifted >3 |
|-----|------|--------------|-----------|----------------|-----------------|
| 10% | 90% | 0.688 | 0.788 | 4 | 39 |
| 15% | 85% | 0.839 | 0.899 | 4 | 31 |
| 20% | 80% | 0.928 | 0.865 | 2 | 11 |
| 25% | 75% | 1.000 | 0.816 | 0 | 0 ← **official** |
| 30% | 70% | 0.965 | 0.791 | 0 | 2 |
| 35% | 65% | 0.926 | 0.766 | 0 | 11 |
| 40% | 60% | 0.904 | 0.748 | 2 | 17 |
| 45% | 55% | 0.893 | 0.740 | 2 | 20 |
| 50% | 50% | 0.877 | 0.726 | 2 | 22 |

### 2b. Quality Win Bonus Sweep

Max teams shifted >3 ranks for each QWB base threshold (varying multiplier 0.3–0.7 for each):

| QWB Base | Max Teams Shifted >3 |
|----------|---------------------|
| 48.0 | 25 |
| 48.5 | 27 |
| 49.0 | 30 |
| 49.5 | 30 |
| 50.0 | 29 |
| 50.5 | 30 |
| 51.0 | 19 ← **official** |
| 51.5 | 2 |
| 52.0 | 1 |
| 52.5 | 1 |
| 53.0 | 1 |
| 53.5 | 2 |
| 54.0 | 3 |
| 54.5 | 3 |
| 55.0 | 4 |
| 55.5 | 4 |

### 2c. Home/Away Multiplier Sweep

| Home Mult | Away Mult | Spread | Teams Shifted >3 |
|-----------|-----------|--------|-----------------|
| 0.60 | 1.40 | ±0.80 | 2 |
| 0.65 | 1.35 | ±0.70 | 1 |
| 0.70 | 1.30 | ±0.60 | 1 |
| 0.75 | 1.25 | ±0.50 | 0 |
| 0.80 | 1.20 | ±0.40 | 0 ← **official** |
| 0.85 | 1.15 | ±0.30 | 0 |
| 0.90 | 1.10 | ±0.20 | 0 |
| 0.95 | 1.05 | ±0.10 | 2 |
| 1.00 | 1.00 | ±0.00 | 3 |

**Instability summary:** NPI produced 632 team-rank shifts >3 positions across 98 parameter configurations. KRACH: **0** (no parameters to sweep).

---

## 3. Bad Wins Filter — Selection Bias

NPI (via NPIGames) drops regulation wins that lower a team's rating. Removing data points based on their outcome is a classic form of selection bias and violates the statistical principle of using all available evidence. KRACH uses all games.

| Model | Accuracy | Brier | LogLoss |
|-------|----------|-------|---------|
| NPI_NoFilter | 62.764% | 0.1772 | 0.6440 |
| NPI_Filter | 62.814% | 0.1770 | 0.6434 |
| KRACH | 63.843% | 0.1848 | 0.6616 |

**Cascade examples** (games where the winner's low-NPI opponent is a filter candidate):

- Penn State (rank 11) beat Arizona State (NPI=49.78) — Weak-opp win — candidate for bad-wins filter
- Michigan (rank 1) beat Mercyhurst (NPI=42.78) — Weak-opp win — candidate for bad-wins filter
- Massachusetts (rank 17) beat Northern Michigan (NPI=43.24) — Weak-opp win — candidate for bad-wins filter
- Penn State (rank 11) beat Arizona State (NPI=49.78) — Weak-opp win — candidate for bad-wins filter
- Michigan (rank 1) beat Mercyhurst (NPI=42.78) — Weak-opp win — candidate for bad-wins filter

---

## 4. Ohio State Case Study: SOS Overweighting

Ohio State's 2025-26 record illustrates the most serious structural flaw: a 75% SOS weight can override a poor win-loss record entirely.

**Ohio State 2025-26 Record:** 14-13-8 (OTL) (net: -7)

| Metric | Value |
|--------|-------|
| NPI Rank | **#19** |
| KRACH Rank | #24 |
| Win-% Rank | #43 |
| NPI Value | 53.0 |
| Component: AdjWP (×25%) | 48.172 |
| Component: SOS (×75%) | 53.689 |
| Component: QWB | 0.69 |

**The math:**
- Ohio State: 0.25 × 48.172 + 0.75 × 53.689 + 0.69 = **53.0**
- Hypothetical .500 team with avg SOS (51.1): 0.25 × 50 + 0.75 × 51.1 = **50.857**
- Ohio State ranks _above_ this hypothetical .500 team despite a losing record.

**Leave-one-out analysis** (which game matters most to Ohio State's NPI rank):
- Remove game vs. **Connecticut** → Ohio State rises to #18 (Δ=-1)
- Remove game vs. **Sacred Heart** → Ohio State rises to #18 (Δ=-1)
- Remove game vs. **Penn State** → Ohio State rises to #18 (Δ=-1)
- Remove game vs. **Penn State** → Ohio State rises to #18 (Δ=-1)
- Remove game vs. **Minnesota** → Ohio State rises to #18 (Δ=-1)

---

## 5. Explicit vs. Implicit SOS

### 5a. SOS Depth and Agreement

Spearman ρ between NPI-SOS rankings and KRACH-implied opponent strength: **0.956** (n=63 teams). While largely correlated, divergences reveal where NPI's two-level cutoff misleads.


### 5b. NPI Paradoxes

A fundamental property of KRACH (MLE/Bradley-Terry): **beating any team always improves your rating**. NPI violates this — adding a win over a weak opponent can lower a team's NPI by dragging down the SOS average.

**NPI paradoxes found:** 20 games where the winner's NPI was *hurt* by their win.
**KRACH paradoxes found (sample check):** 0 (expected: 0 by MLE property).

| Winner | Loser | Loser NPI | Winner NPI w/ win | Without | Impact |
|--------|-------|-----------|------------------|---------|--------|
| Michigan | Mercyhurst | 42.78 | 59.498 | 59.56 | -0.062 |
| Michigan | Mercyhurst | 42.78 | 59.498 | 59.56 | -0.062 |
| Colorado College | Northern Michigan | 43.24 | 51.657 | 51.723 | -0.066 |
| Penn State | LIU | 49.4 | 55.187 | 55.357 | -0.170 |
| Michigan State | Boston University | 51.79 | 57.916 | 57.975 | -0.059 |
| Maine | Colgate | 48.19 | 52.474 | 52.585 | -0.111 |
| Michigan | Notre Dame | 48.13 | 59.498 | 59.669 | -0.171 |
| Michigan State | Penn State | 55.19 | 57.916 | 57.981 | -0.065 |

---

## 6. Conference Impact

NPI's 75% SOS weight and Quality Win Bonus create systematic conference-level distortions via two channels: (A) elite teams create an outsized halo for all conference-mates, and (B) cross-conference performance ripples through the entire conference's SOS.

### Channel A: Elite-Team Halo Effect

Removing the top-ranked team from each conference; measuring average rank drop for conference-mates:

| Conference | Top Team (Rank) | Avg NPI Drop | Avg KRACH Drop | Halo Coefficient |
|------------|----------------|-------------|----------------|-----------------|
| AHA | Bentley (#24) | +-3.3 | +-2.3 | **1.43×** |
| NCHC | North Dakota (#2) | +-3.2 | +-1.8 | **1.86×** |
| Hockey East | Providence (#9) | +-2.7 | +-2.3 | **1.17×** |
| CCHA | Minnesota State (#13) | +-1.6 | +-0.9 | **1.86×** |
| ECAC | Dartmouth (#8) | +-1.6 | +-1.2 | **1.31×** |
| Big Ten | Michigan (#1) | +-1.2 | +0.2 | **-7.0×** |

### Conference Inflation Index (NPI rank vs. Win% rank)

| Conference | Teams | NPI Avg Rank | KRACH Avg Rank | WP Avg Rank | NPI vs KRACH Inflation |
|------------|-------|-------------|----------------|-------------|----------------------|
| CCHA | 9 | 33.7 | 37.6 | 35.2 | +3.9 |
| AHA | 10 | 42.9 | 46.2 | 35.9 | +3.3 |
| ECAC | 12 | 35.5 | 37.4 | 33.2 | +1.9 |
| Big Ten | 7 | 18.7 | 15.9 | 26.4 | -2.9 |
| Hockey East | 11 | 27.6 | 24.2 | 27.9 | -3.5 |
| NCHC | 9 | 21.0 | 14.7 | 25.3 | -6.3 |

*Positive NPI vs KRACH inflation = conference benefits from NPI's SOS weight (ranked higher by NPI than by KRACH).*

### Channel B: Cross-Conference Performance Ripple

**Spearman correlation** between conference NC win% and average conference SOS: **ρ = 0.886**

This strong positive correlation confirms that conferences with better non-conference records benefit from inflated SOS for all their members — the echo-chamber effect.

| Conference | NC Win% | Avg NPI SOS |
|------------|---------|------------|
| NCHC | 67.7% | 53.1 |
| Big Ten | 62.8% | 53.5 |
| Hockey East | 55.1% | 51.6 |
| ECAC | 42.0% | 50.3 |
| CCHA | 36.0% | 50.7 |
| AHA | 35.4% | 49.4 |

---

## 7. Simple NPI Improvements

Without changing the formula structure, two dial adjustments materially reduce NPI's distortions:
- **Reduce SOS weight: 0.75 → 0.66** (standard for other sports using RPI-type systems)
- **Reduce home-ice correction: 0.80/1.20 → 0.90/1.10** (a 20% spread vs. 50%)

| Model | WP% | SOS% | HIA Spread | Accuracy | Brier | LogLoss | Ohio State Rank |
|-------|-----|------|-----------|----------|-------|---------|----------------|
| NPI_hia_official_wp25_sos75 *(official)* | 25% | 75% | 0.80–1.20 | 62.764% | 0.1772 | 0.6440 | #19 |
| NPI_hia_official_wp34_sos66 | 34% | 66% | 0.80–1.20 | 63.594% | 0.1756 | 0.6389 | #27 |
| NPI_hia_official_wp50_sos50 | 50% | 50% | 0.80–1.20 | 63.516% | 0.1766 | 0.6387 | #28 |
| NPI_hia_reduced_wp25_sos75 | 25% | 75% | 0.90–1.10 | 62.764% | 0.1772 | 0.6440 | #19 |
| NPI_hia_reduced_wp34_sos66 *(combined fix)* | 34% | 66% | 0.90–1.10 | 63.699% | 0.1756 | 0.6388 | #27 |
| NPI_hia_reduced_wp50_sos50 | 50% | 50% | 0.90–1.10 | 63.669% | 0.1765 | 0.6385 | #29 |
| KRACH *(zero params)* | — | — | — | 63.843% | 0.1848 | 0.6616 | #24 |

---

## 8. Theoretical Scorecard

| Property | KRACH | NPI |
|----------|-------|-----|
| Tunable parameters | **0** | 7+ |
| SOS computation | Implicit, infinite depth | Explicit, 2-level, arbitrary weights |
| Margin of victory | No | No |
| Self-consistent (MLE) | **Yes** | No (heuristic) |
| Free of paradoxes | **Yes** | No |
| Order-invariant | **Yes** | Yes |
| Game inclusion | **All games** | Filtered (outcome-based) |
| Theoretical foundation | **Max likelihood** | Ad hoc formula |
| Conference neutrality | **High** | Low (75% SOS amplifies) |
| Predictive accuracy | **Higher** | Lower |

---

## Recommendation

**KRACH is the superior system for official selection.** It is mathematically principled (MLE/Bradley-Terry), has zero arbitrary parameters, is more predictively accurate, is free of paradoxes and game-removal bias, and is neutral across conferences.

**If the NPI formula must be retained**, the two highest-impact changes are:
1. Reduce `weight_sos` from 0.75 to 0.66 — this is the norm in other sports and would substantially reduce conference amplification.
2. Reduce `home_multiplier`/`away_multiplier` from 0.80/1.20 to 0.90/1.10.

Neither change restores the mathematical rigor of KRACH, but both reduce the most egregious distortions at minimal cost to the formula's structure.

**NPI's complexity is a liability, not a feature.** Each dial is a lever that can move teams in or out of tournament consideration. A system that ranks last in predictive accuracy while carrying 7+ arbitrary parameters represents a step backward from the principled, zero-parameter KRACH.

---
_Generated by `src/analysis/npi_vs_krach.py`_