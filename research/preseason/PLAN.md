# Preseason rankings: research plan

**Goal:** make ratings and projections for the four featured models (ELO, Massey, KRACH, NPI) useful from opening night through about Thanksgiving, by borrowing the approaches that work in college football and at 538.

**Isolation:** every experiment lives in `research/preseason/` and follows the rules in [README.md](README.md):
- Production code never imports it; a unit test enforces this.
- Experiments write only inside this workspace.
- Each experiment gets its own self-contained report.
- Nothing is promoted to production or the site without an explicit decision from you.

---

## 1. What we're borrowing, and the hockey equivalent

| Source approach | How it works there | Hockey equivalent | Data we have? |
|---|---|---|---|
| **538 long-run Elo** | Elo runs continuously across seasons and is never reset. Each offseason, every team is pulled a fixed fraction (roughly 1/4–1/3) back toward the league mean. The prior is automatically a long-run program value. MOV multiplier includes an autocorrelation correction. | A continuous Elo from 2011-12 to the present, with an offseason reversion fraction and a choice of reversion target (league mean vs. conference mean) | ✅ |
| **SP+ recent history** | Weighted average of the last several seasons' ratings, most recent weighted heaviest | Weighted s-1…s-4 ratings (today's production prior only uses s-1 and s-2) | ✅ |
| **SP+ offense/defense split** | Separate offensive and defensive ratings, so team-level signals (goaltending collapse, high-event offense) land on the side they affect | Offensive and defensive Massey ratings (goals-for and goals-against components), or Dixon-Coles attack/defense (`src/rankings/dixon_coles.py` already exists) | ✅ |
| **Polls (AP/Coaches)** | Human consensus, used as an input or a benchmark | USCHO preseason poll (top 20) | ⚠️ best-effort, see §1a |
| **SP+ prior fade** | Preseason weight is phased out over roughly the first half of the season | Massey's λ pseudo-games fade naturally as games accumulate. Test explicit fade schedules for all models. | ✅ |

**Out of scope, by decision:** SP+'s returning-production and recruiting inputs are player/roster-level. Per the user's 2026-09-13 direction ("let's avoid player-based approaches"), this plan does **not** pursue them — not as a data-availability gap to fill later, but as a deliberate scope boundary. Everything above works from team-level game results only (`games_archive.csv`, plus CHN's team-level shot/xG/EN-goal data where available). That covers most of what SP+ actually contributes beyond raw history anyway: the O/D split (P2) is the mechanism SP+ uses to let roster-level information land asymmetrically, and it's just as useful as a way to let *team-level* signals (a team's own goals-for/against trend, poll movement) land asymmetrically — it doesn't require player data to be worth building.

### 1a. Data sources and how far back they go (2026-09-13)

**Game results (`games_archive.csv`, from USCHO):** 14 usable seasons, **2011-12 through 2025-26** (2026-27 is in progress, 0 finals yet). Checked directly against the archive:

| Issue | Detail |
|---|---|
| **Missing season** | 2016-17 has no raw file at all — a real gap, not a data-quality issue. Any s-1/s-2/s-3 history feature must handle it by falling back to the next available season, never by crashing or silently zero-filling. |
| **2019-20 (COVID)** | Season cut short: last game 2020-03-08, no NCAA tournament. Otherwise a normal-length regular season (1083 games). |
| **2020-21 (COVID)** | Badly shortened: 617 games vs. ~1150 typical (about 54%). Several conferences/teams played partial or no non-conference schedules. Treat as a noisy source season for any prior built from it — this is already flagged in `reports/preseason_priors_results.md`'s conclusion. |
| **Everything else** | 2011-12 through 2015-16 and 2017-18 through 2018-19 and 2021-22 through 2025-26 all look like normal ~1100-1250 game seasons, no anomalies found. |

**CHN team-level advanced stats (shots/xG/empty-net/even-manpower goals):** only 2 seasons currently scraped (2024-25, 2025-26) — `src/data/advanced_metrics_scraper.py`'s `SEASONS` is hardcoded to "current + previous." Extending this further back is possible in principle (same scrape logic, older season codes) but untested and would need its own skip-and-log run in the research workspace before being trusted for P2's O/D features.

**Tested (2026-09-13):** `research/preseason/experiments/probe_pre2011_scrape.py`, full writeup in `research/preseason/reports/probe_pre2011_scrape.md`. **Result: 2001-02 through 2008-09, plus 2010-11, scrape cleanly (9 extra seasons) — but 2009-10 must be excluded** (USCHO silently aliases that URL to the 2010-11 schedule; not a formatting quirk, a wrong answer that looks like a right one). 2000-01 and earlier hard-fail (no archive content at all). Net: the tuning-season pool for P1/P2 can grow from 7 to potentially 16 seasons by adding this range, once someone decides to actually pull it into `research/preseason/data/` for real use (the probe only fetched enough to characterize the boundary, not to build a permanent research dataset yet).

That same investigation also surfaced an unplanned, production-side finding: **2011-12 through 2020-21 (9 of today's 14 production seasons) contain a consistent ~3% duplicate-game-row rate that disappears entirely from 2021-22 onward.** This is unrelated to going further back — it's already in the archive every current report is built on. Left unfixed here per the research-isolation rule; see the probe report's last section for detail and the (separate, small) production fix this would need if you want it addressed.

## 2. How each featured model uses preseason information

Published ratings and research projections stay separate:

| Model | Published rating (production, unchanged) | Where preseason information goes in research |
|---|---|---|
| **ELO** | Refit carryover prior (validated) | Compete against 538-style continuous Elo; test an early-season K boost |
| **Massey** | Ridge toward the prior (validated) | λ and fade schedules; an O/D-split variant that receives O/D-specific priors |
| **KRACH** | Pure | KRACH+prior for projections only. Generalize HockeyBT's MAP penalty (`hockey_bt.py:170-172`, `κ·Σ log r²`) to `κ·Σ (log r − log r_prior)²` inside a research subclass. |
| **NPI** | Pure (official formula) | **Projected final NPI:** simulate the season with the best predictor, then compute NPI on the simulated results |

## 3. Known gaps in current code (fixed in research, not in production)

These get research-side wrappers. Production is only patched through the promotion step.
- **G1** The production prior values were one guess and were never swept. The gain persisting to January suggests the prior is under-weighted.
- **G2** `MonteCarloSimulator` fits its baseline without the prior (`src/analysis/simulator.py:84`).
- **G3** The simulator uses the same model to generate outcomes and to rank, so NPI projections come from NPI's own weak `predict()`.
- **G4** With 0 games played there is nothing to fit, so no true opening-night projection exists.
- **G5** `build_prior()` returns `{}` when s-1 is missing, even if s-2 exists (this is why 2017-18 got no prior).
- **G6** ELO's K was fixed at 20 in the prior backtest; K and prior strength interact.

## 4. Phases

Each phase gets its own module, results folder, and report:
- `experiments/pN_<name>.py`
- `results/pN_<name>/`
- `reports/pN_<name>.md`

Every report is **pre-registered**: the hypothesis, the expected direction, and the ship gate are written *before* the run and left unedited afterwards. Results and the decision are appended below them.

### P0: Harness (`harness/`)
- **Runner:** takes named arms (model factory × prior builder) and cutoffs; returns game-level predictions plus a snapshot of the ranking at each cutoff.
- **Research prior builder:** `models/priors_research.py`, a copy-and-extend of production's `priors.py`. It fixes G5 and supports s-1…s-4, conference-mean reversion, and O/D priors. Production's `priors.py` is left untouched.
- **Cutoffs:** `Oct1` (near zero games, the pure-prior test), `Oct15`, `Nov1`, `Nov15`, `Dec1`, `Jan1`, `Feb1`, `Mar1`.
- **Game-level metrics:** accuracy, Brier, LogLoss, and ECE on the 14 days after each cutoff.
- **Ranking-level metrics:** Spearman/Kendall between the ranking at each cutoff and each model's **final** ranking (final KRACH, final NPI).
- **Standard baselines in every report:**
  - (a) no prior
  - (b) last season's final ranking, unchanged
  - (c) the current production carryover prior
  - (d) the USCHO poll, once collected
- **Report template:** `harness/report.py` fills in the pre-registration header, tables, and a decision block.
- **Gate:** reproduce `reports/preseason_priors_results.md`'s holdout numbers exactly with the new harness before anything else.

### P1: History-only priors (`p1_history_prior`)
- **Arm A: refit blend.** Today's approach with weights swept: r1…r4 on SP+-style decaying weights, and reversion to the global vs. conference mean.
- **Arm B: 538 continuous Elo.** A research `models/continuous_elo.py`, run from 2011-12 onward with no resets. Sweep offseason reversion ∈ {0.15, 0.25, 0.33, 0.5}, reversion target (global/conference), K ∈ {15, 20, 30}, and 538-style MOV autocorrelation correction on/off.
- **Arm C: Massey λ × fade.** λ ∈ {1, 2, 4, 8, 16}, crossed with fade schedules: natural, linear to zero by Dec1, linear to zero by Jan1.
- **Arm D: ELO early-K boost.** Higher K for each team's first N games, crossed with the prior weight.
- **Selection:** pick one configuration per model on the tuning seasons, then run holdout once with a Holm correction.
- **Gate:** at least as good as production at every holdout cutoff, and better at Oct and Nov.

**Status (2026-09-13): RUN.** Arms A and B completed (`reports/p1_history_prior.md`, extended to `reports/p1b_continuous_elo_power.md` for a direct vs.-no-prior comparison with season-level bootstrap power). Arms C (Massey λ×fade) and D (ELO early-K boost) were deferred, not run, given time budget — noted explicitly in the report rather than silently skipped.

**Result:** Arm A (refit-blend strength sweep) found production's shipped values already near-optimal — no config change justified. Arm B (538 continuous Elo) is the actual finding: decisively beats "no prior" (season-level bootstrap significant at every measurable holdout cutoff) and beats today's shipped ELO prior at 2/5 holdout cutoffs directly, with a consistent favorable direction at the rest and stronger significance in a larger 23-season descriptive check. **Continuous Elo is now an active promotion candidate for ELO** (not yet promoted — needs a promotion-quality review of edge cases: the 2016-17 gap season, the shortened 2020-21 season, and whether conference-aware reversion, originally deferred, turns out to matter before shipping).

### P2: Offense/defense split ratings (`p2_od_split`)
- **Model:** research `models/massey_od.py`, where each team gets an offensive and a defensive rating fit to goals for/against (the classic Massey O/D decomposition).
- **Comparison:** check it against Dixon-Coles attack/defense as the alternative carrier.
- **Why:** a team-level offensive collapse (returning goalie situation aside, purely from goals-against trend) or a high-event offense shows up asymmetrically — an overall rating blends both together and can miss which side is actually driving a team's early results. It also gives P4/P5 a place for a poll-implied signal to land on the side it's actually about, if a future poll-residual diagnostic suggests one.
- **Gate:** the O/D model with an O/D history prior must be **no worse** than overall Massey with its P1 prior. It doesn't need to win; it's infrastructure for P4/P5.

### P3: Projection layer (`p3_projections`)
- **Model:** research `models/projection_simulator.py`, which wraps the existing simulator's approach with:
  - a separate `outcome_model` (best predictor with prior) and `ranking_model` (ELO, Massey, KRACH, or NPI), which fixes G3
  - a prior passed into the outcome model, which fixes G2
  - prior-only fitting at 0 games, which fixes G4
- **KRACH+prior:** `models/krach_prior.py` (a subclass of HockeyBT with the prior-centered penalty) goes in as a candidate outcome model and as a projected-KRACH ranking.
- **Outputs:** expected final rank, and P(top 16) / P(top 4) per ranking model.
- **Evaluation:** Brier score of P(top-16 in final NPI); Spearman of expected final rank against actual.
- **Gate:** beats baseline (b) at Oct1 and Nov1 on holdout.

### P4: Polls, best-effort (`p4_polls`)
- **Collect:** USCHO's own preseason poll into `data/polls/<season>.csv`, starting with the most recent 5-6 seasons (reliable, current site structure) and extending backward only as far as scraping stays clean. **Every collection run must record which seasons succeeded and which were skipped** (`data/polls/collection_log.csv`) — a season that fails to parse is logged and skipped, never allowed to crash the run or silently produce garbage rows. Conference coaches' polls are a stretch goal, not a requirement, since they'd need per-conference source-hunting.
- **Diagnostic first (pre-registered):** does poll rank explain the **residual** of the best P1 prior (early-season realized strength minus prior)? If it doesn't, stop — don't force a blend that the diagnostic didn't support.
- **Test:** fit a poll-points-to-rating map on whatever tuning-season polls were actually collected, then blend `w_poll` ∈ {0, 0.2, 0.4, 0.6}. Polls are also baseline (d) everywhere they exist.
- **Gate:** holdout improvement over the best P1 configuration, not just over no prior. If only 5-6 seasons were collectible, say so plainly in the report rather than implying a full 14-season validation.

**Status (2026-09-13): polls collected, informativeness measured — RAN, not the originally-planned diagnostic.** Collection turned out much better than expected: **Wikipedia's per-season "NCAA Division I men's ice hockey rankings" pages** (not USCHO.com directly) have a clean, static-HTML, consistently-structured USCHO preseason-poll table going back to 2000-01 — no Selenium needed. `research/preseason/experiments/collect_uscho_polls.py` collected **22 of 23 archived seasons** (only 2008-09 failed to parse), far exceeding the "5-6 seasons, best-effort" expectation. Log: `research/preseason/data/polls/_log.csv`.

Rather than the originally-planned "residual of the P1 prior" diagnostic, ran a more direct, more useful question instead (prompted by the user asking specifically how informative last year's rating and the poll are, alone and combined): `research/preseason/experiments/p4_lastyear_and_polls.py` fits three static (no in-season updates at all) logistic-regression predictors — poll alone, last year's final ELO rating alone, and a combination — and compares them against P1's `ELO_none` (fresh in-season fit, no prior) on the identical holdout game set. Result (`reports/p4_lastyear_and_polls.md`): last year's rating is consistently more informative than the poll alone at every cutoff; the combination is best or tied-best throughout; and preseason-only information beats a fresh in-season fit through Nov1, roughly ties at Nov15, and is clearly overtaken by Dec1/Jan1 — a clean fade curve consistent with P1/P1b's findings from a different angle. Practical implication: a future poll-blended prior should be a modest addition on top of the history-based prior, not a replacement for it (the poll's coefficient shrinks a lot, but not to zero, once last year's rating is already in the model).

### P5: Composite prior (`p5_composite`)
- **Model:** SP+-style regression of preseason O/D ratings on the team-level inputs that actually cleared their gates — P1 (history/538-style Elo) and P4 (polls, best-effort), whichever won. Fit on tuning seasons only, with per-team prior uncertainty (weaker prior for a team whose rating swung a lot between seasons, or a new program).
- **Evaluate:** the whole stack against the best single-signal prior; report calibration of projection distributions (ECE on P(top-16)).
- **Gate:** holdout improvement over the best earlier phase. That sets the promotion candidate.

**Not pursued, by decision:** player-level signals (returning production, incoming recruiting/transfer talent) are explicitly out of scope — see §1's "Out of scope, by decision" note. This isn't a numbering gap; P5 is deliberately the next phase after P4.

## 5. Evaluation protocol (all phases)
- **Seasons:**
  - **Tune:** 2012-13 → 2020-21.
  - **Holdout:** 2021-22 → 2025-26.
  - **Recent-regime check:** 2024-25 and 2025-26 reported separately. The sample is small, so treat it as directional only.
- **Special cases:**
  - **COVID:** 2020-21 as a source season. Report 2021-22 with and without it.
  - **New programs:** reported separately.
- **Statistical tests:**
  - Paired t-test for Brier and LogLoss.
  - McNemar's test for accuracy.
  - Season-level bootstrap confidence intervals for rank correlations.
  - Holm correction within each holdout table.
- **Holdout discipline:** it is looked at **once per phase**, after the configuration is frozen on tuning seasons.

## 6. Order and effort

| Phase | Effort | Needs new data | Depends on |
|---|---|---|---|
| P0 harness | ~½–1 day | no | none |
| P1 history (538 + SP+ history) | ~1 day | no | P0 |
| P3 projections | ~1–2 days | no | P0 (better after P1) |
| P2 O/D split | ~1 day | no | P0 |
| P4 polls (best-effort) | ~½–1 day scrape + ½ day analysis | yes, USCHO-only, however far back it scrapes cleanly | P1 |
| P5 composite | ~1 day | no | P1, P4 |

**Recommended start:** P0 → P1. Both use existing data, directly test the 538 continuous-Elo idea against today's production prior, and produce the harness every later phase reuses.

## 7. Decisions needed from you
1. **Poll scraping scope:** OK to attempt USCHO preseason polls starting from recent seasons and expanding backward opportunistically (skip-and-log on failure, no guarantee of full 14-season coverage)? This is the only remaining open item from §1a's data-source review.
2. **Older-season game data (§1a):** want me to test whether USCHO's archive scrapes cleanly before 2011-12? Read-only, research-workspace only, no effect on the production archive either way.
3. **Version control:** the project isn't a git repo. A private repo (under your personal account) would make "research didn't change production" provable by diff, on top of the isolation test. Recommended before P0.
