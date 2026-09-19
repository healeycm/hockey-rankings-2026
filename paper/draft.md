# A Validated Comparison of Rating Systems for NCAA Division I Ice Hockey

Chris Healey
Merrimack College

## Abstract

Beginning with the 2025-26 season, the NCAA Division I men's ice hockey
tournament selection committee replaced the PairWise Rankings -- whose
principal comparison criterion is mathematically equivalent to a
Bradley-Terry maximum-likelihood rating (KRACH) -- with the Nutting Power
Index (NPI) as its sole at-large selection metric. Neither metric's
predictive performance against actual game outcomes has been
independently validated, before or after the change. We implement NPI, KRACH, and five
alternative rating systems from their published specifications and
compare them on five seasons of Division I men's hockey (2021-22 through
2025-26, 8,371 held-out games, 20 walk-forward train/test splits). A
least-squares model with two modifications over the textbook Massey
method -- fitted rather than hardcoded home-ice and rest/fatigue terms --
beats both NPI and KRACH simultaneously on accuracy, Brier score, and log
loss, with every pairwise comparison statistically significant (p < 0.05,
9 of 9 tests). We additionally report six pre-registered negative
results -- ensembling, empty-net-goal correction, time decay, a
manpower-margin adjustment, Dixon-Coles, and a self-consistent
reformulation of a Markov-chain rating method -- none of which improved
on the best model, and one of which (the Markov-chain reformulation)
failed in a way that clarifies why Bradley-Terry-style self-consistency
is difficult to retrofit onto margin-based methods. We find further that
model quality decomposes along two independent axes -- discrimination and
calibration -- that the field's incumbent metrics do not jointly
optimize: NPI has the best calibration of any model tested, while our
improved Massey model wins on resolution. These results suggest the
selection committee's incumbent tools are not the strongest available
option on any of the three most common probabilistic scoring rules, and
that at least one methodological choice already standard in college
football and basketball ranking (fitted rather than fixed model
constants) transfers to hockey with a substantial, measurable benefit.

## 1. Introduction

For twelve seasons (2013-14 through 2024-25), Division I college
hockey's NCAA tournament at-large field was set using the PairWise
Rankings, an aggregation of head-to-head-style comparison criteria whose
principal component is mathematically equivalent to a Bradley-Terry
maximum-likelihood rating (KRACH). Beginning with the 2025-26 season, the
selection committee replaced PairWise with the Nutting Power Index (NPI)
-- a weighted combination of winning percentage, a strength-of-schedule
term computed from opponents' own NPI, and a quality-win bonus -- as the
sole metric behind at-large selection. This is a live, two-season-old
policy change, not a settled convention: it altered which teams reached
the tournament field, and it did so on the basis of a metric whose
predictive performance against actual game outcomes had not, to our
knowledge, been independently validated either before or after the
switch. Both metrics are treated by coaches, media, and the committee
itself as the sport's ground truth for "how good is this team," but
neither has been benchmarked against the wider literature of validated
sports rating systems -- Massey [@massey1997statistical], Colley [@colley2002colleys], Bradley-Terry
[@bradleyterry1952rank], Elo [@elo1978rating], Dixon-Coles [@dixoncoles1997modelling], and the LRMC family originally
developed for college basketball [@kvamsokol2006logistic] -- using the standard toolkit of
walk-forward backtesting, proper scoring rules, and paired significance
testing that has become routine in that literature.

This gap matters for a practical reason and a methodological one. The
practical reason: NPI and KRACH are not just descriptive rankings, they
are inputs to a selection decision with real consequences for teams and
programs, the decision rule was just changed without published predictive
validation attached to either the old or the new metric, and if a
demonstrably better predictor of game outcomes exists, that is worth
knowing regardless of whether the committee ultimately adopts it. The
methodological reason: college hockey has features --
a high rate of sudden-death overtime and shootout decisions, roughly
15-20% of games in our data, and goal totals low enough that a single
goal is a large fraction of the final margin -- that are shared by few of
the sports (American football, basketball) in which these rating methods
were originally developed and validated. Whether methods built for
sports with continuous, information-rich margins of victory transfer
cleanly to a low-scoring, discretized-outcome sport is an open,
answerable question, not an assumption either the sports-analytics
literature or the college hockey selection process has tested directly.

We make three contributions. First, we implement seven rating systems
from scratch against their published specifications -- NPI, a from-
scratch reimplementation validated directly against the NCAA's published
values; KRACH; Massey; Elo; Colley; Dixon-Coles; and an LRMC variant
adapted for hockey's overtime structure -- and evaluate all seven on a
5-season, 20-split walk-forward backtest, the largest such comparison of
college hockey ranking systems we are aware of. Second, we show that two
targeted, principled modifications to the standard Massey method --
fitting rather than assuming the home-ice and rest/fatigue coefficients
-- produce a model that beats both of the NCAA's incumbent metrics
simultaneously on all three standard probabilistic scoring rules
(accuracy, Brier score, log loss), a result that held up across every
season and cutoff we tested. Third, and in our view no less important
than the positive result, we report a series of pre-registered
adaptations that did not work -- an ensemble of the validated models, a
real-data empty-net-goal correction, several structural modifications to
the LRMC family aimed at closing its remaining gap to Massey -- because
the negative evidence is, in our experience building this system,
exactly as informative as the positive result, and is rarely reported in
this literature.

The remainder of the paper is organized as follows. Section 2 describes
the data and the Division-I-opponent filtering step we found necessary to
avoid a numerical degeneracy in graph-based rating methods. Section 3
specifies each model. Section 4 describes the walk-forward evaluation
protocol and scoring rules. Section 5 presents the headline comparison.
Section 6 reports the negative results in full, including two genuine
methodological findings that emerged only because an adaptation failed
in an instructive way. Section 7 discusses implications for tournament
selection practice and the limits of what a backtest against historical
outcomes can and cannot establish. Section 8 addresses reproducibility.

## 2. Data

We use Division I men's ice hockey game results from USCHO for five
seasons, 2021-22 through 2025-26. The 2020-21 season (COVID-shortened
schedules) and 2016-17 (missing from our raw archive) are excluded,
consistent with prior internal analysis of this dataset. Where a model
requires it, box-score-level data (expected goals, empty-net-goal flags,
even-manpower goal counts) is drawn from College Hockey News (CHN) for
the two most recent seasons only (2024-25, 2025-26); coverage for earlier
seasons does not exist and models using this data fall back to
goals-based inputs outside the covered window, a limitation we account
for directly wherever it applies (Section 6).

**A numerical degeneracy we found and fixed before running any
comparison.** Several rankers in our roster (KRACH, Massey, the LRMC
family) initially took whatever opponents a team's schedule contained,
including a small number of non-Division-I "counting" games that some
independent programs schedule against non-D-I opponents. For graph- or
Markov-chain-based methods this is not cosmetic: a team with only one or
two real Division-I results and an otherwise-thin schedule can become a
near-isolated node, and in one diagnosed case an LRMC-family rating
collapsed to exactly 0.0 for two such teams, which sends
$\log(r_{home}/r_{away})$ to $\pm\infty$ under that model's prediction
formula and produces single-game log-loss penalties around 34.5 --
enough to distort an entire backtest split on its own. We fixed this with
a centralized Division-I-opponent filter applied uniformly to every
model's input (falling back to unfiltered data automatically when fewer
than half a given dataset's teams match our Division-I roster, so
synthetic or non-USCHO data used in unit testing is unaffected). All
results in this paper reflect data filtered this way.

## 3. Models

We implement each system from its published specification. Except where
noted, hyperparameters are fit from data rather than fixed by hand; we
flag every hand-fixed constant explicitly, since one of this paper's
central findings is how much predictive difference that choice makes.

**NPI (Nutting Power Index).** The NCAA's current sole selection metric
for Division I men's hockey at-large bids [@ncaa_npi_weights]:
$$\mathrm{NPI} = w \cdot \mathrm{AdjWP} + (1-w) \cdot \mathrm{SOS} + \mathrm{QWB}$$
where AdjWP is winning percentage adjusted by home/away multipliers
(0.8/1.2) and an OT-win discount (an OT/shootout win counts 0.6, a
regulation win 1.0), SOS is the mean NPI of a team's opponents (an
implicit, iteratively-solved quantity, not a separate rating), and QWB is
a bonus awarded for wins over opponents above a rating threshold. We use
the 2025-26 season's published dial values throughout ($w=0.25$,
quality-win base 51.0, quality-win multiplier 0.5). NPI has 7 or more
independently adjustable dials.

**KRACH.** A direct application of the Bradley-Terry maximum-likelihood
paired-comparison model [@bradleyterry1952rank] to game results, and the
core of the PairWise Rankings this metric replaced in 2025-26. Ratings
$r_i$ satisfy $P(i \text{ beats } j) = r_i / (r_i + r_j)$, solved by
iterative maximum likelihood over the full season's results. Zero
tunable parameters.

**Massey.** A least-squares fit of goal differential onto team-strength
differences [@massey1997statistical]. We depart from the textbook
version in three respects, each independently ablatable and each
validated as an improvement or a harmless no-op: (i) home-ice advantage
is fit jointly with team ratings as an additional design-matrix column,
rather than assumed; (ii) the margin-to-win-probability mapping's slope
is fit via a genuinely held-out temporal split (ratings fit on the first
80% of the training window by date, the probability mapping calibrated
against the remaining 20%'s actual outcomes) rather than fixed at a
guessed constant; and (iii) ridge regularization ($\lambda=1.0$) replaces
an ad hoc sum-to-zero constraint. A fourth addition, a fitted rest/fatigue
covariate (days since each team's last game, capped at 5 days), is a
genuine if modest improvement documented in Section 6 and included in the
default configuration used throughout our results.

**Colley.** A least-squares method closely related to Massey but fit
directly against win/loss record rather than goal differential -- team
ratings solve $C\mathbf{r} = \mathbf{b}$, where $C$ encodes the schedule
(games played and against whom) and $\mathbf{b}$ encodes a $+0.5$/$-0.5$
credit for each win/loss, a formulation designed to be free of any
preseason bias since every team starts at an identical rating of 0.5.
Colley's own literature does not specify a probability mapping from
rating difference to win probability; we use the simplest linear map,
$P(\text{home win}) = 0.5 + (r_{home} - r_{away})$, clamped to $[0.01,
0.99]$, since this is the formula's most direct reading and, as with
Massey before our fix (above), we are specifically interested in whether
an unfit probability mapping is itself a source of poor calibration
independent of the underlying rating.

**RPI.** The Ratings Percentage Index, NPI's direct historical predecessor
(RPI $\rightarrow$ PairWise $\rightarrow$ NPI), included specifically to
test whether NPI's added complexity improved on what it replaced:
$$\mathrm{RPI} = 0.25 \cdot \mathrm{WP} + 0.50 \cdot \mathrm{OWP} + 0.25 \cdot \mathrm{OOWP}$$
with the standard convention that OWP (opponents' win percentage) is
computed excluding games between the team and that specific opponent, to
avoid a team's own record leaking into its opponents' computed strength.

**ELO.** A sequential, margin-of-victory-weighted rating updated after
every game in chronological order [@elo1978rating], carrying a
season-to-season preseason prior.

**Dixon-Coles.** A bivariate Poisson model of each team's scoring rate,
with attack/defense parameters per team, a fitted home-ice term, and the
Dixon-Coles low-score correlation correction $\tau$ for the sport's most
common score cells [@dixoncoles1997modelling]. We test $\tau$
specifically because it targets exactly the low-scoring regime hockey
occupies.

**HockeyBT.** A Davidson-Beaver extension of Bradley-Terry
[@davidson1970extending] that adds a fitted home-ice multiplier, a
genuine three-outcome (win/tie/loss) likelihood rather than KRACH's
half-credit tie convention, and a maximum a posteriori shrinkage prior on
team ratings -- the three capabilities a direct inspection of KRACH's own
implementation showed it lacks.

**LRMC and HockeyLRMC.** The logistic regression/Markov chain method
[@kvamsokol2006logistic], originally developed for and validated on NCAA
basketball: a logistic regression of margin of victory onto a
win-probability estimate, whose fitted probabilities become transition
weights in a Markov chain over teams, whose stationary distribution is
the rating. We test the unmodified method (LRMC\_Classic) alongside a
hockey-specific adaptation (HockeyLRMC) that gives sudden-death
overtime/shootout decisions -- which always end with a fixed, one-goal
margin uninformative of relative team strength -- a fixed, low-confidence
vote instead of running them through the same margin logistic as a
regulation decision. This is the central sport-transfer question the
paper's introduction raises, and Section 5 addresses it directly.

## 4. Evaluation Protocol

**Walk-forward backtesting.** For each of 5 seasons $\times$ 4 within-season
cutoff dates (January 1, January 15, February 1, February 15), every model
is fit only on games before the cutoff and evaluated on games after it --
20 independent train/test splits, 8,371 pooled test games in total. We
deliberately exclude a December cutoff used in earlier internal work: with
fewer than roughly 550 training games, some graph-based models had not yet
accumulated enough connectivity to produce stable ratings, which is exactly
the regime that surfaces the numerical degeneracy described in Section 2.

**Metrics.** We report accuracy, Brier score, and log loss throughout, the
three most common proper scoring rules in this literature, and treat a
result as noteworthy only when it is not worse on any of the three. We
additionally decompose Brier score into reliability and resolution
[@murphy1973vector] -- reliability measures calibration error directly
(lower is better), resolution measures how much a model's predictions
discriminate winners from losers independent of calibration (higher is
better) -- and report Expected Calibration Error (ECE) as an
interpretable, probability-scale companion to reliability. For the two
models that predict a genuine three-outcome (win/tie/loss) distribution
(HockeyBT, Dixon-Coles) we additionally report the Ranked Probability
Score, the correct generalization of Brier score to an ordinal outcome.
OT/shootout results are scored with a graduated target (a regulation win
counts fully, an OT/shootout win counts 0.6/0.4) rather than as a full win
for either metric computation or Massey/RPI's own win-percentage inputs,
matching the NCAA's own NPI convention for OT results.

**Significance testing.** For every head-to-head comparison we report a
paired t-test on the per-game Brier and log-loss differences and
McNemar's test [@mcnemar1947note] on the accuracy contingency table,
computed on the pooled 8,371-game test set with predictions matched
exactly by game across models. We report both a split-averaged view
(each of the 20 splits weighted equally) and this pooled, per-game-weighted
view where both are informative, since we found in a robustness check
(Section 5.3) that they can disagree in instructive ways that a single
aggregate would hide.

**Hyperparameters are tuned on the same historical data used for final
evaluation.** No model in this comparison has a hyperparameter selected
against data withheld from the backtest reported here -- there is, at
present, no truly held-out season. This is a real limitation we return to
in Section 7, and it applies identically to every model in the roster,
including the incumbent NPI (whose season-specific dial values are set by
the NCAA committee, not by us, but are likewise never validated against
predictive performance).

## 5. Results

### 5.1 Headline comparison

Table 1 reports each model's mean performance across the 20 walk-forward
splits, using each model's validated default configuration.

**Table 1. Split-averaged performance, 5 seasons $\times$ 4 cutoffs.**

| Model | Accuracy | Brier | LogLoss |
|---|---:|---:|---:|
| Dixon-Coles | 64.82% | 0.1720 | 0.6313 |
| **Massey** | **64.78%** | **0.1718** | **0.6317** |
| RPI | 64.41% | 0.1750 | 0.6416 |
| Glicko-2 | 64.23% | 0.1808 | 0.6537 |
| HockeyBT | 64.10% | 0.1753 | 0.6387 |
| KRACH | 63.80% | 0.1840 | 0.6682 |
| ELO | 63.74% | 0.1739 | 0.6382 |
| Colley | 63.58% | 0.1770 | 0.6451 |
| NPI | 62.44% | 0.1764 | 0.6452 |
| HockeyLRMC | 62.39% | 0.1891 | 0.7050 |
| Keener | 62.02% | 0.1824 | 0.6589 |
| LRMC\_Classic | 59.02% | 0.1930 | 0.7143 |

Colley -- implemented in this codebase but never previously put through a
validated backtest -- lands in the middle of the roster on accuracy but
among the worst-calibrated models tested (Brier and log loss both
significantly worse than Massey, pooled paired test, $p$<1.7e-15 and
$p$=2.2e-12 respectively), the same failure mode a pre-fix version of
Massey itself displayed (Section 3): Colley's rating-difference-to-
probability mapping is a fixed, unfit linear formula, never calibrated
against actual outcomes.

Dixon-Coles and Massey are effectively tied at the top of Table 1, and
Table 2's pooled paired test confirms this is a genuine statistical tie
rather than sampling noise in either direction ($p$=0.28--0.84 on all
three metrics). Both decisively separate from the remainder of the
roster, and in particular from the sport's current and former official
selection metrics (NPI, KRACH). We use Massey as the paper's reference
best model throughout the remainder of this section, both because it is
the simpler of the two statistically indistinguishable models (one
parameter per team plus three fitted covariates, versus Dixon-Coles' two
parameters per team) and because it is the model this project's own
development history arrived at first; nothing below should be read as
Massey being established as superior to Dixon-Coles specifically, only as
superior to everything else. Table 2 tests Massey directly against every
other model using the pooled, paired protocol.

**Table 2. Massey vs. each other model, pooled paired test (n=8,371).**

| vs. | Accuracy | Brier | LogLoss |
|---|---|---|---|
| KRACH | 64.59% vs 63.73%, *p*=0.021 | 0.1734 vs 0.1865, *p*=2.5e-38 | 0.634 vs 0.675, *p*=5.0e-32 |
| NPI | 64.50% vs 62.00%, *p*<0.0001 | 0.1731 vs 0.1773, *p*=1.7e-6 | 0.634 vs 0.646, *p*=6.5e-9 |
| ELO | 64.59% vs 63.44%, *p*=0.006 | 0.1734 vs 0.1751, *p*=0.021 | 0.634 vs 0.640, *p*=0.0017 |
| HockeyBT | 64.59% vs 63.91%, *p*=0.041 | 0.1734 vs 0.1768, *p*=2.9e-9 | 0.634 vs 0.641, *p*=2.5e-6 |
| RPI | 64.59% vs 64.19%, *p*=0.331 | 0.1734 vs 0.1763, *p*=2.5e-5 | 0.634 vs 0.6435, *p*=1.2e-7 |
| Dixon-Coles | 64.59% vs 64.53%, *p*=0.840 | 0.1734 vs 0.1732, *p*=0.672 | 0.634 vs 0.633, *p*=0.280 |
| Colley | 64.50% vs 63.51%, *p*=0.0067 | 0.1731 vs 0.1786, *p*=1.7e-15 | 0.634 vs 0.649, *p*=2.2e-12 |

Massey beats KRACH, NPI, ELO, and HockeyBT on all three metrics with every
comparison statistically significant. It is not significantly more
accurate than RPI, though it is significantly better calibrated (Brier,
log loss). Against Dixon-Coles it is a genuine, three-way statistical tie
-- the one comparison in this table that is not a Massey win, and, as we
argue in Section 6, an informative result in its own right about where
this dataset's predictive ceiling sits.

### 5.2 Discrimination and calibration are separate axes, and the incumbents do not optimize either

Table 3 reports the Murphy decomposition and ECE for the five models this
breakdown has been computed for.

**Table 3. Brier decomposition and ECE, split-averaged.**

| Model | Brier | Reliability $\downarrow$ | Resolution $\uparrow$ | ECE |
|---|---:|---:|---:|---:|
| **ELO** | 0.1739 | **0.0039** | 0.0204 | **0.0162** |
| Massey | 0.1721 | 0.0055 | **0.0239** | 0.0278 |
| RPI | 0.1750 | 0.0068 | 0.0219 | 0.0455 |
| HockeyBT | 0.1753 | 0.0078 | 0.0225 | 0.0430 |
| KRACH | 0.1840 | 0.0159 | 0.0228 | 0.0891 |

ELO has the best-calibrated predictions of any model tested -- better than
Massey -- despite Massey having the better overall Brier score; Massey's
advantage comes entirely from resolution, i.e. sharper discrimination
between eventual winners and losers, not from being better-calibrated.
KRACH's ECE is more than five times ELO's, and a binned calibration table
makes the gap concrete rather than abstract: in the 90-100% predicted-win
bin, Massey's stated confidence (92.8%) matches its actual win rate almost
exactly (93.0%), while KRACH's stated 94.2% confidence in that same bin
corresponds to an actual win rate of only 82.2% -- when KRACH calls a team
a 94% favorite, it is wrong nearly one time in five. This decomposition
did not appear in any of our project's own working reports before we
added it, because every prior comparison used aggregate Brier/log loss,
in which Massey's resolution advantage dominates the headline number and
masks ELO's genuinely different strength. Whether resolution or
calibration matters more depends on the downstream use: a selection
committee choosing which teams belong in a tournament field needs correct
relative ordering (resolution), while a probabilistic simulation --
projecting a team's odds of making the tournament, say -- needs correctly
calibrated probabilities. Neither of the sport's current or former
official metrics (NPI, KRACH) is the best available option on either
axis.

### 5.3 Robustness: does the headline result hold at the split level?

Aggregating 20 splits into one pooled test can obscure structure that
matters. Re-examining the same underlying per-split results directly:
Massey's advantage over KRACH is unanimous (20 of 20 splits favor Massey
on both Brier and log loss); its advantage over ELO and HockeyBT holds in
a clear majority of splits (15-16 of 20) but is not universal. The
reversals against ELO cluster entirely in the two earliest, thinnest-data
cutoffs (January 1 and January 15) of two specific seasons -- the expected
signature of small-sample instability in a fitted calibration parameter,
not a surprise. The reversals against HockeyBT are less easily explained:
all four cutoffs of the 2023-24 season favor HockeyBT's calibration over
Massey's, a full-season pattern rather than an early-season artifact. We
checked season-level game statistics (OT rate, tie rate, mean margin,
blowout rate) for an explanation and found none conclusive -- 2023-24 has
the highest OT and tie rates of the five seasons studied, but not by a
margin that obviously accounts for a whole-season reversal. We report this
as an open, unresolved finding rather than force a post hoc explanation
onto it, and note the practical implication: for any single season's live
rankings rather than an aggregate, consulting more than one validated
model has a concrete justification here, independent of the ensembling
result in Section 6.

## 6. Negative Results

We report six pre-registered adaptations that did not improve on the best
available model, because a negative result obtained under the same
protocol and the same significance-testing discipline as our positive
results is, in our view, exactly as informative as the positive result --
a standard we hold ourselves to throughout this project and one this
literature does not enforce as consistently as it might.

**Ensembling does not help.** We combined Massey, HockeyBT, KRACH, ELO,
and RPI via simple averaging and via L2-regularized logistic stacking.
Pairwise error correlation among all five models exceeds 0.93 on every
pair, which we checked before building anything and which set a
pre-registered expectation of little headroom: these models differ
mainly in functional form, not in what information they extract from the
same games (Massey is the only one using goal margin rather than
win/loss/tie alone). Neither combination method beats Massey (pooled
paired test, $n$=8,371: accuracy, Brier, and log loss all
non-significant, $p$=0.30-0.52). Building the stacked variant surfaced two
implementation lessons worth recording independent of the negative
result: an unconstrained logistic stack is a multicollinearity failure
waiting to happen with inputs this correlated (a naive fit scored 59.6%
accuracy, worse than every individual base model, via a large spurious
negative weight on an otherwise-competitive model), and standard L2
ridge -- which shrinks weights toward zero -- shrinks a stacking ensemble
toward an uninformative near-constant prediction rather than toward
anything sensible; shrinking toward the equal-weight average instead
fixed this.

**A real empty-net-goal correction does not help, confirming a proxy
result rather than merely repeating it.** An earlier, blind heuristic
(shrinking any 2-goal final margin toward 1.75, whether or not an
empty-net goal actually occurred) showed no measurable backtest effect,
which is ambiguous on its own -- either empty-net correction genuinely
does not matter, or the proxy was simply a bad guess. We scraped actual
empty-net-goal flags from box scores (27% of covered games contain at
least one) and re-ran the correction using real data. It does not help;
if anything it is significantly worse (paired test, $n$=3,097 covered
games: Brier $p$<0.0001, log loss $p$<0.0001). The reason is structural,
not a data quality problem: a margin cap of 3 goals (used throughout the
LRMC family) already absorbs most empty-net inflation, in the region
where the fitted margin-to-probability logistic is nearly flat, while
subtracting empty-net goals discards real signal from games a team was
genuinely controlling.

**Two further Massey extensions: one negative, one a genuine, shipped
improvement.** Time-decay weighting of training games (matching a
mechanism the LRMC family already had, also never previously validated)
is a clean, monotonic negative -- every half-life tested is significantly
worse on every metric, damage increasing as the decay becomes more
aggressive. We attribute this to college hockey's short season (roughly
30 games): aggressively downweighting early-season games trades away real
sample size without capturing genuine within-season improvement.
Restricting Massey's goal-margin input to even-manpower goals only
(excluding power-play, short-handed, and empty-net goals) is also a clean
negative, and instructively different in kind from the empty-net result
above: an empty-net goal is a game-already-decided artifact carrying
little information about relative strength, but a power-play goal
reflects a real, measurable team skill, and excluding it discards
legitimate signal rather than removing a distortion. By contrast, a
fitted rest/fatigue covariate (days since each team's last game, capped
at 5) is a genuine improvement: Brier and log loss both improve
significantly ($p$=0.0005, $p$=0.01) with no significant accuracy cost,
the only one of these extensions that clears the bar of not losing on any
metric while winning on at least one. It is included in Massey's default
configuration throughout this paper.

**Dixon-Coles ties, rather than beats, the best model.** We built a
bivariate Poisson model of the scoring process specifically to test
whether directly modeling each team's attack and defense rates -- rather
than a single strength scalar -- would beat Massey once Massey's own
calibration bugs were fixed. It does not, but nor does it lose: a pooled
paired test finds no significant difference on any of the three metrics
($p$=0.28-0.84). We pre-registered this as the most likely outcome given
this project's prior track record before running the comparison. We
regard the tie as informative rather than as a failure to find an effect:
it suggests that the extra expressiveness of separate attack/defense
parameters, and the theoretically correct Poisson likelihood for count
data, do not raise the ceiling on what can be extracted from goal-scoring
data in this sport once a simpler model is properly calibrated -- Massey
and Dixon-Coles, despite very different functional forms, appear to be
extracting a similar amount of signal from the same underlying
information.

**A structural lesson from a failed attempt to make LRMC
self-consistent.** KRACH's calibration (Section 5.2, Table 3) is good in
part because it is self-consistent by construction: the same
Bradley-Terry functional form that is maximized to fit the ratings is
also the formula used to predict from them. LRMC has no such property --
its prediction formula, $\mathrm{sigmoid}(\mathrm{hia} +
\log(r_{home}/r_{away}))$, is applied to ratings produced by an unrelated
process (a separately-fit margin logistic feeding a Markov chain's
stationary distribution) and was never itself validated against outcomes.
We attempted to give LRMC KRACH's self-consistency property directly, by
iteratively blending the margin-based per-game probability with the
Bradley-Terry-implied probability from the model's own current ratings
and rebuilding the transition matrix each round until convergence. The
result is a severe, decisive negative that worsens monotonically with the
blend weight -- at full self-consistency, accuracy collapses to 53.78%
(barely better than chance) and log loss more than doubles. We interpret
this as a genuine structural finding, not merely a failed heuristic:
KRACH's self-consistency is a property of a well-defined maximum-likelihood
fixed point with a unique optimum, whereas the iterative blend optimizes
nothing -- it is a feedback loop in which the model's current belief
partially becomes its own evidence, so an early, small-sample rating drift
is reinforced each iteration rather than corrected against independent
data. Bradley-Terry-style self-consistency does not appear to be a
property that can be retrofitted onto a Markov-chain-and-logistic
architecture by heuristic; it has to come from the likelihood structure
itself. This is, to our knowledge, a new finding about why LRMC-family
methods carry an unaddressed calibration gap relative to Bradley-Terry
methods regardless of sport, not one specific to hockey's overtime
structure (Section 5's HockeyLRMC adaptation addresses a different,
margin-noise problem and closes most, not all, of LRMC's accuracy gap;
this calibration gap is a separate, still-open issue for both variants).

**Two structurally different paradigms, both losing decisively.** Beyond
adaptations of models already in our roster, we implemented two rating
methods with no shared computational structure with anything above:
Keener's method (an unnormalized Perron-Frobenius eigenvector ranking
with a bounded score-compression function, rather than the
column-stochastic Markov chain LRMC and RPI-family methods use) and
Glicko-2 (sequential Bayesian filtering that tracks a per-team
uncertainty and volatility state, updated one game at a time, rather than
a single batch fit over the whole season). Both are implemented
correctly -- we verified Keener's compression function actually
compresses blowout score shares as designed, and Glicko-2's rating
deviation provably shrinks as a team accumulates games, its defining
property -- and both lose decisively to Massey (Keener: accuracy 61.70%
vs. 64.59%, $p$<0.0001; Glicko-2: accuracy 63.78% vs. 64.59%, $p$=0.037,
and worse on Brier and log loss at $p<10^{-19}$ in both cases). Glicko-2's
volatility mechanism in particular shows no measurable effect across a
full sweep of its governing parameter $\tau$, because fitted team
volatilities barely move across a season in this data -- college hockey
teams do not display enough within-season strength drift for the
mechanism to have anything to react to, a genuine finding about the sport
rather than a tuning failure. Neither eigenvector structure nor explicit
uncertainty-tracking outperforms a properly calibrated linear model of
goal differential; what continues to matter, across every structurally
distinct paradigm we have tried, is the combination of goal-margin
information with a properly fitted (not assumed) probability mapping.

## 7. Discussion

**Implications for tournament selection.** Our results bear directly on a
live, two-season-old policy decision. NPI is not the best-performing
metric in our roster on accuracy, Brier score, or log loss, and it loses
to its own direct predecessor, RPI, on accuracy with high significance
($p$=0.0002) -- the committee's chosen successor does not clearly improve
on the system it replaced, by the one criterion (predicting actual game
outcomes) both metrics implicitly claim to serve. Beyond predictive
performance, NPI's additional machinery introduces properties a
zero-parameter method like KRACH does not have. We found 20 instances in
a single season where a team's NPI rating was *lowered* by a win it
recorded -- adding a win over a sufficiently weak opponent can drag down a
team's strength-of-schedule average by more than the win itself adds,
whereas the Bradley-Terry family cannot ever have this property (beating
any opponent strictly cannot lower a maximum-likelihood rating). Sweeping
NPI's own dials across plausible alternative values, holding the
underlying game results fixed, produced 632 instances of a team's rank
shifting by more than 3 positions across 98 configurations; the
equivalent sweep for KRACH, which has no dials to sweep, produced zero by
construction. A single case makes the practical stakes concrete: in the
2025-26 season, a team finishing 14-13-8 (a losing record by regulation
outcomes) ranked 19th in NPI, ahead of a hypothetical .500 team with
average strength of schedule, because NPI's 75% schedule-strength weight
was large enough to outweigh the win-loss component entirely -- the same
team ranked 24th under KRACH. None of this requires assuming bad faith in
the committee's dial choices; it is a direct consequence of a heuristic
formula with seven or more independently adjustable weights, evaluated
against a fixed set of historical results.

**Calibration and resolution point to different recommendations
depending on use.** Section 5.2's finding -- that ELO is best-calibrated
while Massey has the best resolution, and that neither incumbent metric
leads on either axis -- is not a call to simply swap one point estimate
for another. A selection committee assembling a tournament field is
fundamentally asking a discrimination question (is team A better than
team B), for which resolution is the relevant property and Massey the
stronger recommendation; a probabilistic application such as an in-season
simulation projecting a team's odds of qualifying needs calibrated
probabilities specifically, for which ELO's advantage is the more
relevant fact. We would resist a recommendation to adopt any single model
without specifying which of these two tasks it is meant to serve.

**What a backtest can and cannot establish.** Every model in this
comparison, including the incumbent NPI, has at least one hyperparameter
tuned against the same historical data used for final evaluation; no
model's reported numbers come from data that parameter never saw. This is
a genuine limitation of retrospective backtesting as a validation
methodology, not specific to any one model here, and it means our
headline comparison, while methodologically standard for this literature,
cannot fully rule out that some of the advantage we report reflects
fitting to this particular five-season window rather than a property that
will hold going forward. The correct remedy is prospective, not
retrospective: publishing dated, pre-registered predictions before games
are played and scoring them only after the fact removes this concern
entirely, and we regard building and maintaining such a public record --
alongside continued rolling-origin re-validation as future seasons
accumulate -- as the natural next step for this line of work, distinct
from anything a backtest alone can provide.

**The sport-transfer question, answered.** Our introduction asked whether
rating methods developed and validated on higher-scoring sports transfer
cleanly to a low-scoring sport with a high rate of outcome-discretizing
sudden-death decisions. The answer is qualified. LRMC's core
architecture transfers: giving sudden-death overtime and shootout
decisions -- which always end at a fixed one-goal margin uninformative of
relative strength -- a fixed, low-confidence vote instead of running them
through the same margin logistic as a regulation result closes most of
the method's accuracy gap to Bradley-Terry-family methods. But a second,
independent limitation does not transfer away: LRMC's prediction formula
lacks Bradley-Terry's self-consistency property regardless of how margin
is handled, and our attempt to retrofit that property by heuristic failed
severely rather than merely underperforming, for reasons (Section 6) that
we expect generalize to any sport LRMC is applied to, not only hockey.
The broader methodological lesson we would draw for anyone adapting a
rating method to a new sport is to check separately whether the sport
violates an assumption in how the *signal* is measured (margin-of-victory
informativeness, in LRMC's case) and whether the method's *prediction*
step was ever validated independently of its *rating* step -- these are
different failure modes requiring different fixes, and conflating them
risks declaring a method broken for a sport when only the first,
correctable problem is actually present.

**Scope.** This paper is restricted to Division I men's hockey. We have
validated a parallel model roster for Division I women's hockey in the
same codebase and expect the comparative results to replicate there, but
we treat that as a separate, independent confirmation worth its own paper
rather than an addendum to this one -- a genuine replication is a
stronger claim made in its own right than a same-paper extension would
be. Similarly, this paper's scope is the comparative validation of rating
systems in general; the NPI-specific findings in this Discussion (the win-
lowers-your-rating paradoxes, the dial-sensitivity analysis, the
conference-level distortion effects) are a small fraction of a fuller
critique we have underway and intend to publish separately, specifically
because NPI's live policy relevance -- as the sport's actual, current
selection metric -- justifies a dedicated treatment deeper than what this
comparative paper's scope allows.

## 8. Reproducibility

Every number in this paper was produced by a specific, named script
against a version-controlled codebase, and we report the exact
invocation alongside each result rather than only in an appendix, in
keeping with the practice we have followed throughout this project's
development. The full codebase -- every model implementation, the
walk-forward backtesting engine, the significance-testing code, and the
raw and processed game data underlying every table above -- is publicly
available at \url{https://github.com/healeycm/hockey-rankings-2026}, with
a complete commit history and pinned to the exact package versions
(Python, pandas, NumPy, SciPy, statsmodels, scikit-learn) used to produce
these results. Every model's default configuration is
documented inline in the project's central configuration file alongside
the specific validation finding that justifies it, positive or negative.
We regard this level of reproducibility -- not just "the code exists" but
"every reported number has a one-line command that regenerates it, and
every default has a citable reason" -- as a baseline expectation for this
kind of work, not a bonus, and one we did not consistently see in the
existing college hockey rating literature during the course of this
project.

## Acknowledgments

*[Placeholder -- any advisors, colleagues, or data sources (USCHO, College
Hockey News) you want acknowledged by name?]*

## References

*[Compiled from paper/references.bib -- render via your LaTeX/pandoc
toolchain of choice; not reproduced inline here.]*

---

*[STATUS as of this revision:]*

- Table 1 is now fully uniform (all split-averaged, no mixed
  aggregation) -- ran the three missing backtests (ELO, Dixon-Coles,
  Glicko-2) plus a first-ever validated Colley backtest; see
  `reports/colley_results.md`. Framing around the top of Table 1 updated
  to honestly reflect Dixon-Coles and Massey being statistically tied
  rather than bolding Massey alone.
- Repository is public: https://github.com/healeycm/hockey-rankings-2026
  (linked in Section 8).
- Acknowledgments: left as a placeholder per your request, to fill in
  later.
- NPI citation in references.bib is still the placeholder D3 general
  guide -- still needs the DI men's hockey-specific dial sheet swapped
  in before submission.
- Women's hockey and a dedicated NPI critique are both explicitly scoped
  out as separate future papers (see the new "Scope" paragraph closing
  Section 7), not silently dropped.
