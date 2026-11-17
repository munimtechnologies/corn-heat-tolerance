# Pre-registration 0.4.0: dryland versus irrigated fields in the same county

PREREG-MARKER: corn-heat-tolerance-0.4.0-irrigation-prereg

Registered by MV2, Munim, Inc. (mv2@munimtech.com) on 2026-11-17. The code
(`irrpractice.py`), its tests and this file are committed together. At that point no
result of 0.1.0, 0.2.0 or 0.3.0 exists, and no irrigated or non-irrigated yield has been
read. The job's first action checks that this file is public; if it is not, the job
stops without reading data. Made with AI agents working in MV2's name. Text CC BY 4.0,
code Apache-2.0. Pre-registrations 0.1.0 ([PREREG.md](PREREG.md)), 0.2.0
([PREREG-SOY.md](PREREG-SOY.md)) and 0.3.0 ([PREREG-DT.md](PREREG-DT.md)) are unchanged
and are graded exactly as written.

## Why

Step 0.3.0 compares states. Nebraska and Kansas differ from the eastern Corn Belt in
many ways besides drought-tolerant (DT) corn, and with only two high-adoption states it
can find only a strong, clean pattern. A sharper contrast exists **inside the same
county**. USDA's Economic Research Service (J. McFadden, Chart of Note "Drought-tolerant
corn varieties often planted on non-irrigated fields", 29 July 2019; 2016 ARMS) reports:

- "nearly 31 percent of Nebraska's irrigated fields were planted with DT varieties";
- "60 percent of non-irrigated fields in Nebraska were planted with DT varieties";
- "most of the main U.S. corn producing States generally had higher levels of DT use on
  dryland fields."

Until the 2018 crop, NASS published separate county yields for irrigated and
non-irrigated corn and soybeans. Dryland and irrigated fields in one county share the
same weather record, the same year, the same prices and much of the same management, so
comparing them removes most of what a comparison between states cannot.

**The "wow" if it works:** after 2010, dryland corn's extreme-heat sensitivity improves
relative to irrigated corn in the same counties, soybeans show no such dryland gain, and
the 1981-2010 placebo is clean. That would be within-county field evidence that the
hybrids planted on dryland (where DT seed went) changed corn's response to heat. It would
bear on every climate-damage projection that holds corn's heat sensitivity fixed. A
*loss* would also be news.

## Data and sample

- Yields: NASS Quick Stats bulk file (newest `qs.crops_YYYYMMDD.txt.gz`), county-level,
  SURVEY, annual, domain TOTAL, with exactly these SHORT_DESC values:
  `CORN, GRAIN, NON-IRRIGATED - YIELD, MEASURED IN BU / ACRE`,
  `CORN, GRAIN, IRRIGATED - YIELD, MEASURED IN BU / ACRE`,
  `SOYBEANS, NON-IRRIGATED - YIELD, MEASURED IN BU / ACRE`,
  `SOYBEANS, IRRIGATED - YIELD, MEASURED IN BU / ACRE`
  (and the matching `- ACRES HARVESTED` rows, used only to report irrigated shares). If
  any of the four yield series has no rows, the job stops before any yield is joined to
  weather. It writes every irrigation-related SHORT_DESC it saw, and a corrected string
  can only be used in a labelled amendment committed before the model runs.
- Weather: the same nClimGrid-Daily county tables as 0.1.0-0.3.0 (single-sine degree
  days; 29 °C for corn, 30 °C for soybeans; March-August; precipitation and its square).
- Sample: counties of **Nebraska and Kansas** in the 0.1.0 spatial sample (centroid east
  of 100° W). Years 1981-2018.
- **Eras:** B = 1981-2010 and C = 2011-2018. NASS stopped county estimates by
  irrigation practice with the 2019 crop (NASS notice of 13 February 2020), so era C has
  only eight years, and they cover the years when DT adoption was rising (2% of US corn
  acres in 2012, 22% in 2016).
- The 0.1.0 era rule applies to each crop × practice: a county is in an era only if it
  has yields in at least two-thirds of the era's years (20 of 30 in B, 6 of 8 in C).
  **Pairing:** a county-era is kept for a crop only if both its dryland and its irrigated
  series pass that rule.

## Model

Four blocks are fitted in one stacked regression: corn dryland, corn irrigated, soybeans
dryland and soybeans irrigated. Each block has its own era-specific weather
coefficients, county-by-era fixed effects and state-by-era quadratic trends. Clusters are
shared across blocks. (In the code these are `dtstate.ddd_fit`'s blocks, with H =
dryland and L = irrigated.)

DiD(p) = (β_EDD,C − β_EDD,B)_corn,p − (β_EDD,C − β_EDD,B)_soy,p for practice p.

**T = DiD(dryland) − DiD(irrigated).**

Inference: year-clustered variance (38 year clusters, which captures weather shocks
shared across space). Only two states are in the sample, so state clusters are not used
for decisions.

**Placebo (pre-trend) check:** the same T with B′ = 1981-1995 and C′ = 1996-2010, before
any DT hybrid was sold.

Classification of the primary T:
- "dryland corn gained" (T > 0) or "dryland corn lost" (T < 0): year-clustered
  two-sided p < 0.05 **and** placebo year-clustered p ≥ 0.10;
- "not interpretable (placebo failed)": p < 0.05 but the placebo has p < 0.10 or could
  not be fitted;
- otherwise "no detectable difference".

## Pre-registered predictions (graded automatically by `irrpractice.py`)

- **I1 (primary).** T is classed **"no detectable difference"** (MV2's prediction).
  Suppose DT hybrids cut dryland corn's heat sensitivity (about −0.01 log yield per degree
  day) by a fifth on the acres where they were planted. The gap in DT share between
  dryland and irrigated fields (about 29 points in Nebraska in 2016, less on average over
  2011-2018) would then move T by only about 0.0003-0.0006. That is probably below what
  eight years can detect.
- **I2.** The point estimate of T is positive.
- **I3.** In 1981-2010, dryland corn is more heat-sensitive than irrigated corn:
  β_EDD,B (corn dryland) < β_EDD,B (corn irrigated).
- **I4.** The same holds for soybeans: β_EDD,B (soy dryland) < β_EDD,B (soy irrigated).
- **I5.** Irrigation removes most of corn's heat damage: |β_EDD,B corn irrigated| <
  0.5 × |β_EDD,B corn dryland|.
- **I6.** The placebo is clean: placebo year-clustered p ≥ 0.10.

Gates (not predictions): G1 at least 40 paired corn counties in era C; G2 at least 25
paired soybean counties in era C; G3 at least 40 paired corn counties in era B; G4 NASS
has dryland and irrigated corn rows for Nebraska or Kansas in every year 2011-2018. If a
gate fails, the results are still published, with the failure stated first.

Reported, not graded: the two group DiDs; the two-way clustered p (with only two states,
for completeness); unpaired samples; T without 2012; T for April-September; era C limited
to 2014-2018; Nebraska only; Kansas only; all eastern-sample states that have both
practices (two-way clustered p); the irrigated share of harvested acres by crop and era;
and the NASS SHORT_DESC census.

## Known limits, stated in advance

- Era C is short (8 years) and ends in 2018, during the adoption ramp. Extending it needs
  a different source. FSA ARC-CO practice yields (2014 on, built from RMA data) are a
  possible later step, but only as a separate, labelled pre-registration, because their
  method differs from NASS's.
- ERS gives the dryland and irrigated DT shares for Nebraska only (one year, 2016), and
  for other states only as a general statement.
- Which fields are irrigated changes over time (new pivots, wells taken out of use under
  groundwater rules). This shifts both practices' samples, and the soybean contrast
  removes only what affects both crops alike.
- Only the eastern parts of Nebraska and Kansas are in the sample, because the 0.1.0
  sample rule is kept. Most of western Kansas's irrigated corn is outside it.
- Every limit of 0.1.0-0.3.0 still applies.

Related method: Tack, Barkley & Hendricks (2017) compared irrigated and dryland Kansas
wheat yields under warming. We know of no test of whether dryland corn's heat
sensitivity changed relative to irrigated corn after DT hybrids, with soybeans as the
control. No result, whichever way it falls, will be re-graded. Any later analysis is
labelled post hoc.
