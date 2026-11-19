# Pre-registration 0.6.0: is corn's rising heat sensitivity real, corn-specific, and still rising?

PREREG-MARKER: corn-heat-tolerance-0.6.0-rc-prereg

Registered by MV2, Munim, Inc. (mv2@munimtech.com) on 2026-11-19. The code (`rcheck.py`),
its tests and this file are committed together. No result of this project exists yet: the
jobs for 0.1.0-0.4.0 were still queued for compute when this was written, and none of
their outputs has been seen. The job's first action checks that this file is public; if
it is not, the job stops without reading data. Made with AI agents working in MV2's name.
Text CC BY 4.0, code Apache-2.0. Pre-registrations 0.1.0-0.4.0 are unchanged and will be
graded exactly as written. (Version 0.5.0 is reserved for the FSA practice-yield step
described in `docs/step-c-sources-addendum.md`.)

## Why this step exists

After 0.1.0-0.4.0 were registered, we found the closest prior work, published in June
2026: A. Raghuram and E. D. Coffel, "Rising corn yield sensitivity to heat in the US
Midwest", *Environmental Research Letters* 21, 124041 (2026),
doi:10.1088/1748-9326/ae7c89. As we read it, they:

- use NASS county corn yields for 12 Midwest states, 1960-2019, on a 0.45° grid, keeping
  rainfed cells (irrigated cropland under 10%), with ERA5 daily temperatures;
- define sensitivity as the change in standardized, detrended yield per killing degree
  day (above 29 °C), estimated in 31 overlapping 30-year windows;
- report that sensitivity **rose by nearly 20% between 1960 and 2019**, falling in
  northern states and rising in southern ones;
- find that places where daily maximum temperature warmed tended to become more
  sensitive (the fit explains a bit over 10% of the variance).

They do not use a comparison crop, and their data stop in 2019, so they barely reach the
drought-tolerant (DT) hybrid era. Their result matters to this project in three ways:

1. **Replication.** Our 0.1.0 prediction P2 (sensitivity higher in 1981-2010 than in
   1951-1980) points the same way. Their claim deserves a direct test with independent
   weather data (NOAA nClimGrid county daily data rather than ERA5 reanalysis) and our
   model, on their own windows.
2. **Is it about corn?** If corn became more heat-sensitive because of what was bred into
   it, as the genetic-tradeoff work of Kusmec et al. (PLOS Genetics, 2023) suggests,
   soybeans grown in the same counties under the same weather should not show the same
   rise. If soybeans rose just as much, the rise is probably about something both crops
   share (weather data, management, where crops are grown), not about corn genetics.
3. **A competing explanation for 0.3.0.** If sensitivity follows local warming, a
   difference in warming between Nebraska/Kansas and the eastern Corn Belt could imitate
   or hide a DT effect.

**The "wow" if it works:** this is the first test of the June 2026 finding that nets out a
comparison crop. Either answer is news. If corn's rise is specific to corn, that is
field-scale evidence that modern corn traded heat tolerance for yield. If soybeans rose
just as much, the published rise is not about corn genetics, and climate-damage models
that build it in as a crop trait would be misreading it. Adding 2020-2025 also shows
whether the rise continued into the DT era.

## Sample, data and model

- Data, weather, degree days, sample rule, model and clustering are those of 0.1.0/0.2.0:
  NASS county yields (one snapshot for both crops), nClimGrid-Daily county weather,
  counties east of 100° W excluding Florida, March-August, 29 °C for corn and 30 °C for
  soybeans, log yield, county-by-window fixed effects, state-by-window quadratic trends,
  and two-way (state, year) clustered errors. A county enters a window only if it has
  yields in at least 20 of its 30 years.
- **States (primary):** the 12 Census Midwest states (IL, IN, IA, KS, MI, MN, MO, NE, ND,
  OH, SD, WI), counties east of 100° W only. The paper does not list its 12 states; the
  ones it names (Iowa, Illinois, Kansas, Minnesota, Wisconsin, Michigan, the Dakotas)
  are all in this set.
- **Windows:** E = 1960-1989 and L = 1990-2019, the first and last of the paper's 30-year
  windows. They are estimated together in one regression with window-specific
  coefficients. The extension uses E2 = 1966-1995 and L2 = 1996-2025.
- **Temperature trend (for RC4/RC5):** nothing beyond the cached tables is downloaded, so
  daily maximum temperature is not available. The proxy is each county's OLS trend, over
  1960-2019, of its March-August mean temperature, computed as degree days above 0 °C
  divided by 184 days, in years with a corn yield. This differs from the paper's Tmax
  trend, and that is stated in every result.

## Pre-registered tests and predictions (graded automatically by `rcheck.py`)

Sensitivity "rises" when the EDD coefficient becomes more negative (L − E < 0).

- **RC1 (replication).** Corn, Midwest-12, E vs L: classed "rise replicated" (L − E < 0,
  two-way p < 0.05), "rise in direction only", "no rise" or "fall". **MV2's prediction: L −
  E < 0** (the direction replicates). Also reported: the ratio β_L/β_E, against the paper's
  ≈ 1.2 (their yield scale is different, so this is a comparison, not a test).
- **RC2 (is it corn?).** Corn and soybeans stacked, Midwest-12, E vs L: DiD = (L − E)corn −
  (L − E)soy, two-way p, classed as in 0.2.0. **Prediction: "no detectable difference".**
  The rise, if any, will not be shown to be specific to corn.
- **RC3 (extension to 2025).** Corn, Midwest-12, E2 vs L2. **Prediction: L2 − E2 < 0.**
  With 2020-2025 added, the later 30 years are still more heat-sensitive.
- **RC4 (mechanism, corn only).** Midwest-12 counties are split by temperature trend into
  the warmest-trend third and the coolest-trend third. W4 = (L − E)corn,warm − (L −
  E)corn,cool from one stacked regression. **Prediction: W4 < 0**, the paper's direction.
- **RC5 (mechanism net of soybeans).** T4 = [(L − E)corn − (L − E)soy]warm − [the same]cool.
  **Prediction: "no detectable difference"** (two-way p ≥ 0.05).

Gates (not predictions): RG1 at least 500 Midwest-12 corn counties in L; RG2 at least 400
Midwest-12 soybean counties in L; RG3 at least 100 counties in each temperature-trend
third. If a gate fails, the results are still published, with the failure stated first.

Reported, not graded: year-clustered p for every contrast; RC1 and RC2 on all counties
east of 100° W; RC1 without 2012 and for April-September; RC2 with 30 °C for both crops;
each crop's own L − E; the E2/L2 corn-minus-soybean DiD; the counts of warm-trend and
cool-trend counties by state; 30-year rolling-window EDD coefficients for corn and
soybeans in the Midwest-12 (windows ending 1980 to 2025); and the 0.3.0 triple difference
(Nebraska and Kansas against seven Corn Belt states) restricted to counties whose
1981-2025 temperature trend lies inside the pooled interquartile range, plus the mean
trend in each group.

## How results will be read

- RC1 "rise replicated" with RC2 "corn lost relative to soybeans": the rise is real and
  specific to corn.
- RC1 rise with RC2 "no detectable difference" and similar point estimates for both crops:
  the rise is not shown to be about corn.
- RC1 "no rise" or "fall": the June 2026 finding does not replicate with county nClimGrid
  weather and this model. The differences in method listed below come first in any
  explanation.

## Known limits, stated in advance

- Our model differs from the paper's: log yield rather than standardized detrended yield,
  fixed effects and state trends rather than detrending, counties rather than grid cells,
  nClimGrid rather than ERA5, and all counties east of 100° W in those states rather than
  rainfed cells only. A non-replication may come from any of these.
- The temperature trend is a mean-temperature proxy, not daily maximum temperature.
- Two 30-year windows compare averages over long periods and cannot place a turning point.
  The rolling series is descriptive only: overlapping windows are not independent.
- Soybeans are an imperfect control: their area grew, their planting dates moved, and
  their own breeding went on. The difference-in-differences nets out only what moved both
  crops equally.
- Every limit of 0.1.0-0.4.0 applies.

No result, whichever way it falls, will be re-graded. Any later analysis is labelled
post hoc.
