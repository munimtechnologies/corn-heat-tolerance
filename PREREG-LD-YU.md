# Pre-registration 0.7.1: Yu, Miao & Khanna's exact specification, within and across states

PREREG-MARKER: corn-heat-tolerance-0.7.1-yu-prereg

Project: corn-heat-tolerance (MV2, Munim, Inc.). Code: `ldiff_yu.py`, tests: `test_ldiff_yu.py`.
Addendum to [PREREG-LD.md](PREREG-LD.md) (0.7.0). Written on 2026-11-25, before any yield or weather
data of this project has been read by any step: none of the queued jobs for 0.1.0-0.7.0 has run yet.
Made with AI agents working in MV2's name; no human expert has reviewed this design yet. Licence: text
CC BY 4.0, code Apache-2.0. Nothing in 0.7.0 changes: its predictions LD1-LD5, gates and joint verdict
with 0.6.0 stay exactly as committed in 1bc5f3bd, and are graded by `ldiff.py`.

## 1. Why this addendum exists

0.7.0 tests the long-difference "fall" in corn's heat sensitivity (Yu, Miao & Khanna, *Scientific
Reports* 11:12351, 2021, [doi 10.1038/s41598-021-91192-5](https://doi.org/10.1038/s41598-021-91192-5))
with this project's own weather variables. Re-reading their Methods
([open text](https://pmc.ncbi.nlm.nih.gov/articles/PMC8196191/)) on 2026-11-25 showed four
differences from our variables, one of which our planned "Yu-match" row did not cover:

| Item | Yu et al. (as written in their Methods) | 0.7.0 primary | 0.7.0 "Yu-match" row | 0.7.1 (this step) |
|---|---|---|---|---|
| Season | April 1 - September 30 | March-August | April-September | April-September |
| Normal degree days | "GDD between 0 and 29 C" | 10 C to b | 10 C to 29 C | **0 C to 29 C** |
| Extreme degree days | "GDD above 29 C", both crops | > 29 C corn, > 30 C soy | > 29 C | > 29 C, both crops |
| Precipitation | two hinge terms around p0 = 42 cm: "max{-delta,0}" and "max{delta,0}" | P and P squared | P and P squared | **shortfall below 42 cm and excess above 42 cm**, per year, then averaged |
| Inclusion | "we exclude counties that produce corn or soybeans in only one period" | >= 3 of 5 years per period | >= 3 of 5 | **>= 1 year per period** (>= 3 reported) |
| Regression weights | none stated (planted acreage only weights the reported averages) | none | none | none |
| Standard errors | not stated | state-clustered | state-clustered | state-clustered |
| Weather | Schlenker-Roberts (PRISM-based) | nClimGrid-Daily county means | same | same (cannot be matched) |

Their "change in responsiveness" (their Fig. 2) is sign(eta) x |eta / beta|; a fall of 58% for corn
and 55% for soybeans (1958-62 vs 2013-17) is -0.58 and -0.55 in this project's eta/beta convention.

So that a failure to replicate, or a within-state shrink, cannot be blamed on our choice of
variables, this step grades the replication and the within-state test on their variables.

## 2. Models (unchanged from 0.7.0)

Per county, means over the years with a yield in each period of log yield and of the four Yu
variables. Model A: dy on dw (4) and w1 (4) with one intercept (identical to their county fixed effects
plus period-interacted weather with two periods). Model B: the same with state fixed effects. Both are
fit by `ldiff.fit_ld`, unweighted, state-clustered. Sample: counties east of 100 W, not Florida (the
project's sample; Yu et al. report 2,480 rain-fed counties east of the 100th meridian).

## 3. Predictions (MV2's own expectations, graded mechanically by `grade_yu`)

Primary: 1958-62 vs 2013-17, inclusion >= 1 year per period.

| ID | Prediction | Holds if |
|---|---|---|
| YX1 | Corn model A replicates the size of Yu et al.'s fall | beta_EDD < 0, eta_EDD > 0 and eta/beta in [-0.90, -0.30] |
| YX2 | Same for soybeans | as YX1 |
| YX3 | Corn: state fixed effects remove at least half of the fall | eta_EDD(A) > 0 and eta_EDD(B) < 0.5 x eta_EDD(A) |
| YX4 | Same for soybeans | as YX3 |
| YX5 | Corn, mean over the four 20-year pairs of 0.7.0 (their 20-year models average a 43.5% fall) | mean eta/beta under A < 0 and mean under B > 0.5 x mean under A |

Gates (reported next to the grades): YG1 corn counties >= 800; YG2 soybean counties >= 400; YG3 corn
model B has >= 15 state clusters. MV2 predicts all five hold. The 0.7.0 joint verdict is not
changed by this step; if 0.7.0 and 0.7.1 disagree, both are reported and the disagreement is
attributed to the variable definitions.

## 4. Reported, not graded

Inclusion >= 3 years per period; 1958-62 vs 2021-25; the 12 Midwest states; every coefficient and
the county counts by state.

## 5. Prior work checked on 2026-11-25

Searches: arXiv, Google Scholar-style web search, SSRN, journal sites, GitHub, for long-difference
and rolling-window estimates of changing heat sensitivity of US corn and soybeans. Closest work, none
of which tests the within-state version of the flexible long difference:
Yu, Miao & Khanna (2021); Raghuram & Coffel, *Environ. Res. Lett.* 21:124041 (2026),
[doi 10.1088/1748-9326/ae7c89](https://doi.org/10.1088/1748-9326/ae7c89); Burke & Emerick, *AEJ:
Economic Policy* (2016); Ghanem, Pretis & Schuurman, [arXiv:2607.22028](https://arxiv.org/abs/2607.22028)
(2026, long differences vs fixed effects, simulation); Valente, "Extreme Heat and the Distribution of
Crop Yield Losses Across US Counties",
[SSRN 6898120](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6898120) (2026, long differences
and causal forests for how corn's heat loss differs across counties; it does not test change over time
or state effects).

## 6. Procedure

`fetch_deps_yu.py` refuses to run until this file, with its marker, is public on main; it fetches the
shared modules as published in commit 6771a70f and `ldiff.py` from main. `ldiff_yu.py` never builds the
shared data tables itself: it waits for the earlier jobs to build them and stops (exit 3, nothing
read) if they are not there. It writes `ldiff_yu_results.json` with the grades. The result note will
report every prediction whichever way it falls, and will say which findings are post hoc.
