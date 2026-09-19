# Follow-up Paper Plan: A Critique of the NCAA Power Index

## Relationship to the comparative paper

`paper/draft.md` ("A Validated Comparison of Rating Systems for NCAA
Division I Ice Hockey") treats NPI as one entry in a roster of models
and spends roughly one Discussion subsection on its policy implications.
This follow-up inverts that: NPI is the sole subject, and the model
comparison becomes supporting evidence rather than the main event. Justified
as its own paper (not a longer Discussion section in the first one)
because NPI is the sport's actual, current, live selection metric --
adopted 2025-26, no independent predictive validation on record either
before or after the switch -- and that policy relevance supports a
treatment deeper than a comparative paper's scope allows.

Sequencing: submit/post the comparative paper first (it's ready sooner
and this one leans on some of its results -- e.g. the NPI-vs-RPI and
NPI-vs-Massey comparisons). This paper can cite it once it has a
DOI/arXiv number, and should stand alone regardless (a reader coming to
the NPI critique cold shouldn't need the first paper to follow it).

## What already exists to draw on

`reports/npi_critique.md` is most of the empirical backbone already:

1. **Predictive accuracy** — NPI vs. KRACH head-to-head (24 season-cutoff
   pairs, KRACH wins 17/24)
2. **Dial sensitivity** — sweeps of `weight_wp`/`weight_sos`,
   quality-win-bonus base/multiplier, and home/away multipliers; 632
   rank-shifts >3 positions across 98 configurations vs. KRACH's 0 (zero
   parameters to sweep)
3. **The bad-wins filter as selection bias** — dropping outcome-selected
   data points, with a direct comparison (filtered vs. unfiltered vs.
   KRACH)
4. **The Ohio State case study** — a losing record (14-13-8) ranked above
   a hypothetical .500-with-average-SOS team, with a leave-one-out
   breakdown of which specific games drive it
5. **NPI paradoxes** — 20 documented games where a team's win *lowered*
   its own NPI; contrasted with KRACH's zero-by-construction guarantee
6. **Conference-level distortion** — the "elite-team halo" effect
   (removing a conference's top team and measuring conference-mates' rank
   drop, by conference) and the cross-conference "echo chamber" (ρ=0.886
   between conference non-conference win% and average conference SOS)
7. **Concrete, minimal-disruption fixes** — reducing SOS weight from 0.75
   to 0.66 (the norm elsewhere) and home/away multiplier spread, with
   before/after accuracy numbers for each

Plus, from the comparative paper once it's out: the direct Massey-vs-NPI
and RPI-vs-NPI pairwise tests (`reports/massey_vs_npi_direct_comparison.md`,
`reports/rpi_results.md`) as the "does the successor beat the
predecessor" evidence.

## What this paper needs that doesn't exist yet

1. **A literature/history section** placing NPI in context: RPI ->
   PairWise -> NPI, why the NCAA made each transition, and how this
   compares to analogous metrics in other NCAA sports (NPI is used
   beyond hockey -- D3 hockey, lacrosse per the PWR/NPI comparison paper
   found during citation-building this session). Needs research, not
   just this codebase's existing output.
2. **A closer reading of the committee's own stated rationale** for
   adopting NPI over PairWise in 2025-26 -- what problem was NPI meant to
   solve? (Transparency? Simplicity for non-statisticians? Something
   PairWise couldn't do?) This paper's critique is much stronger if it
   engages with the actual stated goals rather than only measuring
   outcomes the committee may not have been optimizing for.
3. **A more rigorous dial-sensitivity treatment** than the existing sweep
   — e.g., a formal sensitivity/elasticity analysis (bootstrap or
   jackknife over seasons) rather than the current single-season sweep,
   to make the "7+ arbitrary parameters" claim more statistically
   airtight.
4. **A tournament-selection-specific evaluation**, not just game-level
   accuracy — e.g., how often does NPI's field differ from KRACH's or
   Massey's *at the selection margin specifically* (the bubble teams),
   since that's where the metric's practical consequences actually land,
   not in games between the #1 and #60 teams where every metric agrees.
   This is flagged as an open item in `reports/calibration_metrics.md`
   ("no rank-stability or bubble-team-accuracy metric was formalized")
   and would need to be built.
5. **A response to the obvious counterargument**: that NPI was never
   designed to be a pure predictive model, so criticizing it on
   predictive grounds may be attacking a straw man. The paper needs to
   engage this directly -- e.g., by arguing (a) predictive accuracy is
   nonetheless the most defensible objective proxy available for "which
   teams are actually good," which is what selection is supposed to
   answer, and (b) the paradox/selection-bias/dial-instability findings
   are objections on NPI's *own terms* (internal consistency, freedom
   from arbitrary-parameter sensitivity) independent of the predictive
   framing.

## Proposed structure

1. Introduction — NPI's adoption, why it matters now, this paper's thesis
2. History — RPI -> PairWise -> NPI, stated rationale for each change
3. Predictive performance — NPI vs. its predecessor (RPI) and vs.
   principled alternatives (KRACH, Massey), at the bubble specifically
4. Structural critique — paradoxes, dial sensitivity, selection bias from
   the bad-wins filter
5. Distributional critique — conference-level effects (halo, echo chamber)
6. Addressing the "not meant to be predictive" objection
7. Recommendations — minimal-disruption dial changes vs. a case for
   returning to a principled zero-parameter method
8. Conclusion

## Not started

This is a plan only -- no drafting has begun. Say the word when you want
me to start on the Introduction/History section (item 2 above needs real
research into the committee's stated rationale before I can write it
honestly, so that's the natural first step rather than jumping straight
to the parts already backed by `npi_critique.md`).
