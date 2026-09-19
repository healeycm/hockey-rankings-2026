# S7: Blocked — A Third Dead-Config-Dial Bug Found in NPI

## S7's design assumed a live dial. It isn't one.

S7's plan: sweep NPI's OT-win/OT-loss credit dial (`config.yaml`'s
`ot_win_weight: 0.6` / `ot_loss_weight: 0.4`) against known ground
truth, on the premise that this might be one dial NPI actually gets
right -- a fair-minded, cheap test explicitly included so the critique
doesn't only look for NPI's failures.

**It can't be run as designed.** `grep -n "ot_win_weight\|ot_loss_weight"
src/rankings/npi.py` returns zero matches. `NPI.fit()`'s OT-game credit
formula is hardcoded:

```python
h_pts_ot = np.where(h_is_win,  0.4 * h_win_mult + 0.2, ...)
```

`0.4` and `0.2` are literal constants -- not read from `self.conf` at
all. (For a neutral-site OT win, `h_win_mult=1.0`, so
`0.4*1.0+0.2=0.6`, which happens to match the *intended* 0.6 dial value
-- but only by coincidence of these specific hardcoded numbers, not
because the config is consulted. Changing `ot_win_weight` in
`config.yaml` does nothing.)

## This is not a new class of finding -- it's the same bug, a second time

`reports/e1_truth_recovery.md` already found and documented this exact
pattern for `weight_wp`/`weight_sos` (also hardcoded, 0.25/0.75, also
silently ignoring config) and reused `src/analysis/npi_vs_krach.py`'s
existing `reweight_npi()` workaround, which recombines already-converged
components post-hoc rather than re-running the iteration. **That
workaround does not apply here.** `weight_wp`/`weight_sos` only affect
the *final linear combination* of already-computed adj_wp/sos/qwb
components, which is why a post-hoc recombination could substitute for
a true re-fit. OT credit is different: it feeds into each game's
`h_pts`/`a_pts` values *before* the outer iterative fixed-point
computation even starts -- changing it changes what every team's
rating converges to, not just how three already-final numbers get
blended. There is no post-hoc shortcut available.

## What would be needed to actually test this

Either (a) a production fix to `npi.py` making the OT credit formula
read `self.conf['ot_win_weight']`/`ot_loss_weight` genuinely (out of
scope for this research workspace, which reads production code but
never edits it -- see `research/npi_critique/README.md`'s isolation
rules), or (b) a full, independent reimplementation of NPI's iterative
solver in research code with a parameterized OT credit, which risks
fidelity drift from the actual production formula being critiqued and
was judged not worth the risk for a "fair-minded, cheap" test that was
supposed to be low-effort by design. Neither was done here.

## Net effect on the critique

**A second, independent instance of the same production bug class
strengthens rather than weakens the "NPI's dials aren't what they
appear to be" critique** -- two of NPI's seven-plus advertised tunable
parameters (`weight_wp`/`weight_sos`, and now `ot_win_weight`/`ot_loss_weight`)
turn out not to be live at all in the shipped `fit()` implementation.
This is worth stating in the paper's Discussion alongside the dial-
sensitivity findings in `reports/npi_critique.md`: some of the
"instability from too many arbitrary parameters" critique's own
sensitivity sweeps may themselves have exercised a dead code path for
these two dials specifically, which should be checked before citing
those specific sweep results without this caveat.

## Shipped

No code, no experiment script -- this report documents a blocker, not a
result.

## Open items

1. ~~Check whether `reports/npi_critique.md`'s original dial-sensitivity
   sweep used a live or dead code path for `weight_wp`/`weight_sos`~~ --
   **checked, it's fine.** `src/analysis/npi_vs_krach.py`'s
   `phase7_minimal_improvements` explicitly documents the hardcoding and
   uses `reweight_npi()` deliberately: *"The NPI source hard-codes
   0.25/0.75 in the iterative loop, so weight changes only affect the
   FINAL aggregation step... we reweight the final aggregation."* That
   sweep's numbers stand as reported; this bug does not retroactively
   undermine them.
2. **Flag both dead-dial findings to whoever maintains the production
   codebase** -- this is a real bug independent of anything about the
   critique's conclusions, and fixing it would make `config.yaml`'s own
   inline comments (which describe these as tunable) accurate again.
3. **S7 remains untestable without either a production fix or a
   from-scratch reimplementation** -- not attempted in this pass.
