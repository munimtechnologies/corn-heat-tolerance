# Pre-registration 0.8.0: is corn's reported rise in heat sensitivity a matter of yield scale?

PREREG-MARKER: corn-heat-tolerance-0.8.0-rcx-prereg

Registered by MV2, Munim, Inc. (mv2@munimtech.com) on 2026-11-27. The code (`rcx.py`), its
tests (`test_rcx.py`) and this file are committed together. No result of this project exists
yet: every earlier job (0.1.0-0.4.0, 0.6.0, 0.7.0, 0.7.1) is still waiting for compute, and
none of their outputs has been seen. The job's first step checks that this file is public; if
it is not, the job stops without reading data. Made with AI agents working in MV2's name. Text
CC BY 4.0, code Apache-2.0. Earlier pre-registrations are unchanged and will be graded exactly
as written. (0.5.0 stays reserved for the FSA practice-yield step.)

## Why this step exists

Two published results point in opposite directions:

- A. Raghuram and E. D. Coffel, "Rising corn yield sensitivity to heat in the US Midwest",
  *Environ. Res. Lett.* 21, 124041 (2026), doi:10.1088/1748-9326/ae7c89. Code and intermediate
  data: doi:10.5281/zenodo.20185245 (CC BY 4.0). Sensitivity to killing degree days (KDD, above
  29 °C) **rose by nearly 20%** from the 1960-1989 window to the 1990-2019 window.
- Yu, Miao and Khanna, "Maladaptation of U.S. corn and soybeans to a changing
  climate", *Sci. Rep.* 11, 12351 (2021), doi:10.1038/s41598-021-91192-5. In log yields, the loss
  per overheating degree day **fell by 58%** (corn) between 1958-62 and 2013-17.

Steps 0.6.0 and 0.7.0/0.7.1 test each claim on its own terms. On 2026-11-27 we re-read Raghuram
and Coffel's Methods closely and found a difference that neither of those steps isolates:
**their yields are in levels, not logs.** Per grid cell, yields are "linearly detrended" once
over 1960-2019 and "standardized using the local (grid-cell specific) standard deviation"; the
OLS of that standardized anomaly on detrended KDD and GDD (9-29 °C) anomalies is re-estimated in
31 overlapping 30-year windows, and the KDD coefficients are averaged over cells. Logs are never
used. Their counterfactual converts back with the cell's standard deviation into kg/ha.

That matters because Midwest corn yields roughly tripled over the period. **If an extra degree
day costs the same share of the crop in every decade, the level loss per degree day grows in
proportion to trend yield**, and that grew about 1.5- to 1.8-fold between the midpoints of the
first and last windows. A level estimator would then show a large "rise" while the crop's
proportional sensitivity stays the same. A 20% rise in levels would correspond to a **fall** in
proportional terms, which is the direction Yu et al. report. The general point that heat losses
in levels and in percentages can disagree is known (e.g. Anderson et al., *Environ. Res. Lett.*
10, 124001, 2015, doi:10.1088/1748-9326/10/12/124001). Our searches on 2026-11-27 (below) found
no published test of whether it explains the 2026 rise.

**The "wow" if it works:** the two contradicting results would be reconciled by one change of
units. In that case the June 2026 rise means growing bushels at stake per hot day, not corn
becoming more fragile, and models that carry the rise forward as a trait would overstate future
losses. If the rise survives on a proportional scale, the 2026 finding becomes much stronger
than its own analysis could show, because it would hold up under the most obvious objection.

## What is run (`rcx.py`)

The Raghuram-Coffel estimator, applied to this project's county data and changed **only in the
yield scale**:

- **level** (their form): detrended yield divided by its full-series SD;
- **relative**: detrended yield divided by its own fitted trend value, then by its full-series SD;
- **log**: detrended log yield divided by its full-series SD.

Common to all three forms:
- NASS county corn yields from the shared tables. Counties are those in the 12 Census Midwest
  states (IL, IN, IA, KS, MI, MN, MO, NE, ND, OH, SD, WI) east of 100° W. A county needs at least
  20 yield years in **every** window, and the same counties are used for all three forms.
- Weather is nClimGrid-Daily, single-sine degree days. KDD = degree days above 29 °C, GDD =
  degree days between 9 and 29 °C, April-September (the cached season closest to the Sacks
  calendar). KDD and GDD are linearly detrended over the county's full series.
- In each window, an OLS of the standardized anomaly on KDD and GDD anomalies with an intercept.
  The regional value per window is the **unweighted mean** of the county KDD coefficients.
- Primary: series 1960-2019, 31 windows (1960-1989 ... 1990-2019). Extended: series 1960-2025,
  37 windows (last 1996-2025).
- **Ratio** R = (mean coefficient, last window) / (mean coefficient, first window). R > 1 means
  more loss per degree day later (a "rise"). The paper's figure is R ≈ 1.2.

## Pre-registered tests and predictions (graded automatically by `rcx.py`)

- **X1 (their form replicates).** R_level > 1. **MV2 predicts: holds.**
- **X2 (scale shrinks the rise).** R_relative < R_level and R_log < R_level. **Predicts: holds.**
- **X3 (the reconciliation).** R_relative < 1: per unit of yield, sensitivity did not rise.
  **Predicts: holds.**
- **X4 (same in logs).** R_log < 1. **Predicts: holds.**
- **X5 (to 2025).** R_relative < 1 on the extended series. **Predicts: holds.**

Gates (not predictions): XG1 at least 300 counties in the primary sample; XG2 the level-form
first-window coefficient is negative; XG3 the relative-form one is too. If a gate fails, the
results are still published, with the failure stated first.

**Verdict rule (fixed now):** X1 false gives "no-level-rise". X1 and X3 true give "scale: the
rise appears in yield levels only". X1 true and X3 false give "proportional-rise: the rise
survives on a proportional scale".

Reported, not graded: the trend-yield ratio (the rise a level estimator shows if shares stay
constant), compared with R_level / R_relative; the trend-based change (linear slope over the
window series, as the paper also reports); a paired county bootstrap of every ratio (500 draws;
it ignores weather shared between counties, so its intervals are too narrow and are not used
for grading); and the same three forms for March-August, without 2012, for all counties east of
100° W, and for soybeans (30 °C) on the primary and extended series.

## Next, on the authors' own data (0.8.1, registered before it runs)

A structure-only job (`rcz-inspect-v1`) downloads the authors' Zenodo archive, checks its md5,
and lists its files and R object classes without printing yield values. It also copies their
notebook so their exact steps (detrending, standardization, degree-day method) can be checked.
Pre-registration 0.8.1 will then fix these rules: run their pipeline unchanged as a gate (it must
give a rise between 10% and 30%), then change only the yield scale, with X1-X4 as above.

## Known limits, stated in advance

- County NASS yields and nClimGrid weather, not their 0.45° grid with ERA5. We use all counties
  in those states, not only rainfed cells (irrigated share under 10%). A fixed April-September
  season, not the Sacks calendar. Any of these can move R_level away from 1.2; X2-X4 compare
  forms on the same data, so they do not depend on matching it.
- The relative form divides by a linear trend, which misfits a curved yield path at the ends of
  the series. The log form is the cross-check.
- Unweighted county means, as the paper averages grid cells. Production weighting is not
  graded.
- Overlapping windows are not independent; first-versus-last is a description, not a test with
  a p-value. The grading uses point estimates, as the paper's headline does.
- This tests one explanation of the rise. It does not test why proportional sensitivity changed.

## Prior-art searches (2026-11-27)

1. "Raghuram Coffel 2026 Environmental Research Letters maize heat sensitivity increasing
   Midwest": the paper itself and earlier AGU/EGU abstracts by the authors; no comment or reply.
2. "Rising corn yield sensitivity to heat" with comment, reply or critique: none found.
3. Level versus log yields as an artifact in heat-sensitivity trends: the Schlenker-Roberts line
   of work uses log yields throughout (Roberts and Schlenker, NBER c11988; Schlenker and Roberts,
   PNAS 2009). No test of the level effect on a time trend was found.
4. Absolute versus relative losses scaling with mean yield: Anderson et al. (ERL 2015) note the
   level/percentage distinction for the shape of the response. Schauberger et al. (Nat. Commun.
   2017) use relative responses. Neither looks at a trend over time.
5. Reconciling Raghuram and Coffel with Yu, Miao and Khanna: nothing found.

No result, whichever way it falls, will be re-graded. Any later analysis is labelled post hoc.
