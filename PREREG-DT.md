# Pre-registration 0.3.0: where drought-tolerant corn was adopted most

PREREG-MARKER: corn-heat-tolerance-0.3.0-dt-states-prereg

Registered by MV2, Munim, Inc. (mv2@munimtech.com) on 2026-11-17. The code
(`dtstate.py`), its tests and this file are committed together, before any corn or
soybean result of 0.1.0 or 0.2.0 exists and before any data are read for this step. The
job's first action checks that this file is public; if it is not, it stops without
reading data. Made with AI agents working in MV2's name. Text CC BY 4.0, code
Apache-2.0. Pre-registrations 0.1.0 ([PREREG.md](PREREG.md)) and 0.2.0
([PREREG-SOY.md](PREREG-SOY.md)) are unchanged and are graded exactly as written.

## Why

The 0.2.0 test compares corn with soybeans for the whole eastern US. Drought-tolerant
(DT) hybrids were not adopted evenly, so a national comparison dilutes any effect they
had. USDA's Economic Research Service (McFadden, Smith, Wechsler & Wallander, *Development,
Adoption, and Management of Drought-Tolerant Corn in the United States*, EIB-204, 2019;
2016 ARMS field survey) reports that DT corn grew from 2% of US corn acres in 2012 to 22%
in 2016, and that adoption was:

| Group | States | DT share of corn acres, 2016 (ERS) |
|---|---|---|
| **High** | Nebraska (42%), Kansas (39%) | 39-42% |
| Middle (reported only) | South Dakota, Texas (Colorado is outside the sample) | 20-27% |
| **Low** | Iowa, Illinois, Indiana, Ohio | 16-21% |
| **Low** | Minnesota, Wisconsin, Michigan | 14-20% |

These shares come from ERS's published text (the Amber Waves article of March 2019 and
the chart of 4 February 2019). We use only the groups above, and we fixed them before
seeing any result. If DT genetics made corn more heat-tolerant in the field, the
corn-minus-soybean gain after 2010 should be **larger where DT corn was planted most**.

**The "wow" if it works:** a corn-minus-soybean gain in heat tolerance that is
concentrated in the high-adoption states, and that is larger than in any other choice of
two states. That would tie the change to where the hybrids were actually planted, which
is much closer to field-scale causal evidence that DT genetics changed corn's heat
response than any national trend. It would bear on climate-damage projections that hold
corn's heat sensitivity fixed. A *loss* concentrated there would also be news.

## Sample and data

The sample, data and model are identical to 0.2.0. It uses one NASS snapshot for both
crops, nClimGrid-Daily county weather, counties east of 100° W excluding Florida, the
same era rule, March-August, 29 °C for corn and 30 °C for soybeans. Only the eastern
parts of Nebraska and Kansas (and of South Dakota and Texas) are in the sample, because
the 0.1.0 sample rule is kept unchanged.

## Primary test (H1): triple difference

DiD(g) = (β_EDD,C − β_EDD,B)_corn,g − (β_EDD,C − β_EDD,B)_soy,g for group g, where C is
2011-2025 and B is 1981-2010.

**T = DiD(High) − DiD(Low)**, estimated in one stacked regression with four blocks
(corn High, soybeans High, corn Low, soybeans Low). Each block has its own coefficients,
county-by-era fixed effects and state-by-era quadratic trends.

Inference: there are only two high-adoption states, so state-clustered variance is not
reliable. The decision needs **both** of the following:
1. a year-clustered two-sided p < 0.05 for T (75 year clusters, which captures weather
   shocks shared across space); and
2. randomization inference over the 9 High and Low states. T is recomputed for all 36
   ways to call two of the nine states "High" and the rest "Low". The real split must
   be the most extreme by |T|, i.e. p_RI = 1/36 ≈ 0.028. A tie or a second place
   (p_RI ≥ 2/36 ≈ 0.056) fails.

T is classed "high-adoption corn gained" (T > 0, both pass), "high-adoption corn lost"
(T < 0, both pass) or "no detectable difference".

## Secondary test (H2): dry versus wet counties

Counties in the corn 1981-2010 sample are ranked by their mean March-August precipitation
over 1981-2010 (pre-period climate, unaffected by adoption). T2 is the same triple
difference, with the driest third of counties in place of High and the wettest third in
place of Low, over the whole eastern sample. It uses the two-way (state, year) clustered
p < 0.05, because many states are in each group. ERS found adoption was highest where
drought had been worst, so this is a proxy for adoption that does not depend on state
lines.

## Pre-registered predictions (graded automatically by `dtstate.py`)

- **D1 (primary).** T is classed **"no detectable difference"** (MV2's prediction). Even
  if DT hybrids cut corn's heat sensitivity (about -0.006 log yield per degree day) by a
  fifth on the acres where they were planted, a 20-25 point gap in adoption should move
  T by only about 0.0002-0.0003. That is probably below what this design can detect.
- **D2.** The point estimate of T is positive.
- **D3.** In 1981-2010, corn in the High states is less heat-sensitive than in the Low
  states: |β_EDD,B corn High| < |β_EDD,B corn Low|. (Irrigation is widespread in
  Nebraska.)
- **D4.** T2 is classed "no detectable difference".

Gates (not predictions): G1 at least 80 High-state corn counties in era C; G2 at least
60 High-state soybean counties in era C; G3 at least 300 Low-state corn counties in era
C. If a gate fails, the results are still published, with the failure stated first.

Reported, not graded: the two-way clustered p for T; T without 2012; T for April-September;
T with era C limited to 2016-2025 (after adoption passed 20%); Middle (South Dakota,
Texas) against Low; the 36 placebo values of T; each state's own corn-minus-soybean DiD
next to its ERS adoption share; and the precipitation cut-points of H2.

## Known limits, stated in advance

- The adoption shares are for one year (2016) and come in published groups, not exact
  state figures for every state. Adoption kept changing after 2016.
- Nebraska and Kansas differ from the eastern Corn Belt in other ways that changed after
  2010: irrigation, water policy, and planting of corn on drier land. The soybean
  comparison removes only what moved both crops in the same group. Nebraska's irrigated
  fields had a lower DT share (31%) than its dryland fields (60%). This step does not
  separate irrigated from dryland yields.
- With nine states, randomization inference cannot go below p = 1/36. The test can find
  only a strong, clean pattern.
- Every limit of 0.1.0 and 0.2.0 still applies.

No result, whichever way it falls, will be re-graded. Any later analysis is labelled
post hoc.
