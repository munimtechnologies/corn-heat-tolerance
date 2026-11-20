# Pre-registration 0.7.0: rising or falling? Reconciling two published answers on US corn's heat sensitivity

PREREG-MARKER: corn-heat-tolerance-0.7.0-ld-prereg

Project: corn-heat-tolerance (MV2, Munim, Inc.). Code: `ldiff.py`, tests: `test_ldiff.py`.
Written on 2026-11-20, before any yield or weather data of this project has been read by any step
(the jobs for 0.1.0-0.6.0 are queued and none has run). Made with AI agents working in MV2's name;
no human expert has reviewed this design yet. Licence: text CC BY 4.0, code Apache-2.0.

## 1. Why this step exists

Two published studies of the same crop, the same country and overlapping years point in opposite
directions:

| Study | Method | Finding for corn |
|---|---|---|
| Yu, Miao & Khanna, *Scientific Reports* 11:12351 (2021), doi 10.1038/s41598-021-91192-5 | "flexible long differences": two 5-year-average periods per county, 1951-2017, 2,480 rain-fed counties east of 100 W, overheating degree days > 29 C | yield loss per overheating degree day **fell** 58% from 1958-62 to 2013-17 (soybeans: 55%); 43.5% on average over 20-year gaps |
| Raghuram & Coffel, *Environ. Res. Lett.* 21:124041 (2026), doi 10.1088/1748-9326/ae7c89 | year-to-year variation within 30-year rolling windows, 12 Midwest states, killing degree days > 29 C | yield loss per killing degree day **rose** nearly 20% from 1960 to 2019 |

Step 0.6.0 (`PREREG-RC.md`) tests the second finding. This step tests the first on the same counties,
weather and yields, and asks why the two disagree. Burke & Emerick (AEJ: Policy 2016) compared long
differences with panel estimates for corn and found little adaptation; Ghanem, Pretis & Schuurman
(arXiv:2607.22028, July 2026) show in general that LD-versus-FE comparisons can mislead. As far as we
could find, no one has re-examined how the flexible long difference identifies its "change in
sensitivity", and no one has put these two specific results side by side on one dataset.

## 2. The identity behind the hypothesis

With two periods (t = 0, 1), county fixed effects and a period dummy interacted with each weather
variable (as we read Yu et al.'s Methods), the model is equivalent to one cross-section of counties:

    dy_c = delta + beta . dw_c + eta . w1_c + e_c

where dy is the change in mean log yield, dw the change in mean weather and w1 the mean weather of the
later period. The "change in heat sensitivity" eta_EDD is identified from whether counties with more
extreme heat in the later period had faster yield growth over the decades. Hot counties are mostly in
the southern and western parts of the corn area, where yields started lower. **Hypothesis H-LD:** much
of the positive eta_EDD is between-state yield convergence (catch-up), not heat adaptation. If so,
it should shrink when each county is compared only with counties of its own state (state fixed
effects delta_s). The synthetic test `test_convergence_fakes_a_fall_only_without_state_effects` shows
the mechanism: with no true change in sensitivity, state-level catch-up that is larger in hotter states
produces a "fall" under model A and exactly none under model B.

## 3. Data and sample (fixed now)

* Same inputs as 0.1.0-0.6.0: NASS county SURVEY yields (corn grain; soybeans), nClimGrid daily county
  weather, March-August season, degree days above 10 C to b (GDD) and above b (EDD) with b = 29 C for
  corn and 30 C for soybeans, precipitation and its square (decimetres). Counties east of 100 W, not
  Florida (the project's pre-registered sample). Unweighted.
* Primary periods: **1958-1962 and 2013-2017** (Yu et al.'s 55-year model). A county enters if it has a
  yield in at least 3 of the 5 years of each period; its period values are means of log yield and of the
  four weather variables over those years.
* Inference: standard errors clustered by state.

## 4. Models

* **Model A** (Yu-style): dy on dw (4) and w1 (4) with one intercept.
* **Model B** (within-state): the same with state fixed effects.
* eta/beta for EDD is the proportional change in the loss per degree day (Yu et al. report -0.58 for
  corn and -0.55 for soybeans in this 55-year comparison).

## 5. Predictions (MV2's own expectations, graded mechanically by `grade_ld`)

| ID | Prediction | Holds if |
|---|---|---|
| LD1 | Model A replicates the direction of Yu et al. for corn | beta_EDD < 0 and eta_EDD > 0 |
| LD2 | Same for soybeans | beta_EDD < 0 and eta_EDD > 0 |
| LD3 | For corn, state fixed effects remove at least half of the fall | eta_EDD(A) > 0 and eta_EDD(B) < 0.5 x eta_EDD(A) |
| LD4 | Same for soybeans | as LD3 |
| LD5 | Within states, corn shows no detectable fall in heat sensitivity | not (eta_EDD(B) > 0 and p < 0.05) |

Gates (a failed gate is reported next to the grades; predictions are still graded): LG1 corn counties
>= 800; LG2 soybean counties >= 400; LG3 corn model B has >= 15 state clusters.

**Joint verdict with 0.6.0** (`reconcile`, using RC1 of `rcheck_results.json` and LD1/LD3 here):
"reconciled: the long-difference fall is between-state" if RC1, LD1 and LD3 all hold; "conflict
persists within states" if RC1 and LD1 hold but LD3 does not; otherwise "no conflict on this data"
(with which finding failed to replicate) or "neither published direction on this data". MV2 predicts
**reconciled**.

## 6. Reported, not graded

Extended comparison 1958-62 vs 2021-25; the four 20-year pairs (start periods centred on 1960, 1970,
1980, 1990) and their mean eta/beta under A and B; a Yu-match specification (April-September, 29 C for
both crops); the standard long difference without w1 (Burke & Emerick style) under A and B; model A
with initial log yield added; the 12 Midwest states only; counties with both crops; county counts by
state; mean change in EDD.

## 7. What each outcome would mean

* LD1 and LD3 hold: the published 55-year "fall" in corn's heat sensitivity is mostly regional catch-up
  in yields; within states, the data do not show corn becoming less heat-sensitive. Combined with an
  RC1 rise, the two literatures stop contradicting each other.
* LD1 holds, LD3 fails: the fall survives within states, so the conflict with the rolling-window rise is
  real and must come from the difference between slow (decadal) and fast (year-to-year) heat responses,
  which is evidence of genuine long-run adaptation.
* LD1 fails: on this independent weather dataset the long-difference fall does not replicate.

## 8. Limits known now

State fixed effects also absorb real state-level adaptation (for example irrigation spread or
state-specific hybrid adoption), so a shrink under B does not prove that no adaptation happened; it shows
that the cross-state contrast cannot separate adaptation from other causes of regional yield growth.
Within-state variation in extreme heat is smaller than across states, so model B is noisier; LD5 is a
"no detectable" prediction and must be read with its confidence interval. Our weather (nClimGrid county
means) and season (March-August) differ from Yu et al.'s (PRISM-based Schlenker-Roberts data,
April-September); the Yu-match row reports the closer specification. We could not confirm whether Yu et
al. weighted counties.

## 9. Procedure

`fetch_deps_ld.py` refuses to run until this file, with its marker, is public on the main branch; it then
fetches the shared modules exactly as published in commit 6771a70f. `ldiff.py` writes
`ldiff_results.json` with the grades. The result note will report every prediction whichever way it
falls, and will say which findings are post hoc.
