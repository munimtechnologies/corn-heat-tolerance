# Pre-registration: has US corn's sensitivity to extreme heat changed in the drought-tolerant-hybrid era?

PREREG-MARKER: corn-heat-tolerance-0.1.0-prereg

Registered by MV2, Munim, Inc. (mv2@munimtech.com) on 2026-11-17, before any of the
data below were downloaded or analysed by this project. The analysis code, its tests
and this file are committed together; the job that downloads the data runs only after
this commit. Made with AI agents working in MV2's name. Text CC BY 4.0, code Apache-2.0.

## The question

Schlenker and Roberts (PNAS 2009) showed that US corn yields rise with temperature up
to about 29 °C and fall steeply above it. Roberts and Schlenker (NBER, Indiana 1901-2005
and US 1950-2005) found that corn's tolerance of extreme heat peaked around 1960 and
then declined. Ortiz-Bobea and Tack (ERL 2018) and Kusmec et al. (PLOS Genetics 2023,
public yield trials) also report growing heat sensitivity. Since 2011, seed companies
have sold drought-tolerant hybrids across the Corn Belt (for example Pioneer's Optimum
AQUAmax, launched in 2011, and Bayer/Monsanto's DroughtGard in 2013).

**Has the 60-year slide in heat tolerance continued, stopped or reversed in
2011-2025?** We found no published test that uses county yields through 2025. The
answer matters because most estimates of US crop damage from climate change use
heat-sensitivity coefficients fitted to data that end in 2005-2016.

What a "wow" would be: clear evidence that US corn became *less* sensitive to extreme
heat after 2010. That would be the first reversal of a decline documented since 1960,
and it would lower a central input of climate-damage projections. A clear *worsening*
despite drought-tolerant seed would also be news. We predict neither (below).

## Data (all public)

- Yields: USDA NASS Quick Stats bulk file `qs.crops_YYYYMMDD.txt.gz` (newest on
  https://www.nass.usda.gov/datasets/ at run time). We use county-level SURVEY rows with
  SHORT_DESC `CORN, GRAIN - YIELD, MEASURED IN BU / ACRE`, REFERENCE_PERIOD `YEAR` and
  DOMAIN `TOTAL`, for 1951-2025. "Other (combined) counties" and suppressed values are
  dropped.
- Weather: NOAA nClimGrid-Daily county averages (`{tmax,tmin,prcp}-YYYYMM-cty-scaled.csv`,
  https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/). Their county codes use
  NCEI's alphabetical state numbers, so counties are mapped to FIPS through the state
  abbreviation in the name field plus the 3-digit county code.
- Location: 2020 Census county gazetteer (internal-point longitude).

## Sample

Counties whose gazetteer centroid lies east of 100° W, excluding Florida (the
Schlenker-Roberts convention for rain-fed corn). A county-year needs a NASS yield and
complete weather (no missing day) for both seasons. A county enters an era only if it
has yields in at least two thirds of that era's years (20 of 30, 20 of 30, 10 of 15).

## Variables

For each day we compute degree days above each integer threshold from 0 to 40 °C
with the single-sine method between the county-average Tmin and Tmax. Over the
primary season, March 1 to August 31:
GDD = DD(10) − DD(29) (moderate heat), EDD = DD(29) (extreme heat),
P = season precipitation in decimetres, and P².

## Model

log(yield) = county-by-era fixed effects + state-by-era linear and quadratic time trends
+ era-specific coefficients on [GDD, EDD, P, P²] + error.
The eras are A = 1951-1980, B = 1981-2010 and C = 2011-2025 (the drought-tolerant-hybrid
era). All three are fitted in one stacked regression, with two-way cluster-robust
variance by state and year (Cameron-Gelbach-Miller). If a variance comes out
non-positive, the sum of the two one-way variances is used and flagged.

## Pre-registered predictions (graded automatically by `run_cornheat.py`)

- **P1 (primary).** Let Δ = β_EDD,C − β_EDD,B, tested with the two-way variance at
  two-sided p < 0.05. The result is classed "improved" (Δ > 0, significant), "worsened"
  (Δ < 0, significant) or "no detectable change". **MV2 predicts: not "improved".**
- **P2.** The β_EDD,B point estimate is more negative than β_EDD,A, which would repeat
  the post-1960 decline.
- **P3.** β_EDD,B lies in [−0.012, −0.003] log-yield per degree day.
- **P4.** In era C the threshold b* that minimises the sum of squared residuals
  (b = 24-36 °C, each era fitted alone) lies in 27-32 °C, and |b*_C − b*_B| ≤ 2.
- **P5 (out of sample).** Take the era-B weather coefficients and form a weather index
  for every era-C county-year. Regressing era-C log yield on that index (with the same
  fixed effects and trends) gives a slope λ in [0.8, 1.3].

Data gates (not predictions): G1 at least 1,000 counties in era C; G2 at least 90% of
NASS sample counties matched to nClimGrid weather; G3 at least 500 county yields for 2025.
If a gate fails, the results are still published, with the gate failure stated first.

Reported, not graded: the same model with an April-September season; era C without 2012;
and the EDD coefficient in rolling 15-year windows (1951-1965 through 2011-2025).

## Known limits, stated in advance

- County-average daily Tmax/Tmin understate within-county heat extremes. That shifts
  coefficient levels, but it applies the same way to every era.
- NASS county coverage has thinned in recent years, and 2024 county estimates were
  nearly discontinued, so era C's counties are a self-selected set of counties that kept
  reporting.
- The data cannot separate genetics from management (planting dates, density,
  irrigation in the eastern Plains) or from CO₂.
- Era C is 15 years long and includes the 2012 drought, so a single year carries much
  of the information. This is why we report the version without 2012.

No result, whichever way it falls, will be re-graded. Any later analysis is labelled
post hoc.
