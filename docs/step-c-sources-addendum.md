# Step (c) addendum: where the post-2018 practice yields come from, and four rules fixed before reading them

Status: design note, 2026-11-18. No FSA or RMA yield has been read, and no model has been fitted.
The structure-only inspection job described in [step-c-fsa-scoping.md](step-c-fsa-scoping.md)
has not returned yet. Made with AI agents working in MV2's name (MV2, Munim, Inc.,
mv2@munimtech.com). Text CC BY 4.0.

## What changes the design

1. **A source break sits inside the FSA series.** For the 2014-2018 crop years, FSA's
   ARC-County yields were built from NASS county estimates first, with crop-insurance
   (RMA) data only where NASS had none. The 2018 Farm Bill (section 1107) reversed the
   order: from the 2019 crop, RMA insurance data are the primary source and NASS is the
   fallback (FSA Notice ARCPLC-91; CRS report R45730). The Congressional Research Service
   notes that RMA yields often ran higher than NASS yields. So an FSA series that starts
   before 2019 and ends after it changes source in the middle of the period this study
   cares about.
2. **The benchmark numbers are not yields of one year.** ARC-CO benchmarks are Olympic
   averages of five earlier years. Since the 2018 Farm Bill they are trend-adjusted, and
   any year below a plug (80% of the 10-year county average) is replaced by the plug. The
   plug replaces the worst years, which are often the hottest ones, so it would erase
   the very losses this study measures.
3. **FSA has already published both sources side by side** for 2009-2017 ("Detailed
   ARC-CO NASS and RMA County Yields 2009-2017", corn, soybeans and wheat). The
   inspection job downloads it.

## Rules fixed now (they carry into PREREG-FSA, version 0.5.0)

- **R1. Actual-year yields only.** Only a county's actual yield for a single crop year is
  used. Benchmark yields, Olympic averages, trend-adjusted values and plug-replaced
  values are never used. If a year exists only inside a benchmark, that year is dropped.
- **R2. One source on both sides of the comparison.** The primary analysis uses
  RMA-based yields in the early window (from the 2009-2017 detailed file) and in the
  late window (FSA actual yields from 2019 on). This avoids a NASS-to-RMA switch at the
  same moment as the era change. 2018 (NASS-based in the ARC data) is left out of the
  primary analysis. A NASS-early/RMA-late splice may be shown only as a labelled
  secondary analysis.
- **R3. A heat-dependence gate on the source difference.** On the overlap years
  2009-2017, for each county-crop-year with both practices, compute
  g = [log RMA − log NASS](dryland) − [log RMA − log NASS](irrigated). Before any heat
  model, regress g on extreme-heat degree days with year-clustered errors. If the
  RMA-minus-NASS gap depends on heat differently for dryland and irrigated fields, a
  source effect could look like a change in heat sensitivity. In that case the heat test
  is not run, and the gap is published instead. The numerical bounds (slope and mean)
  are written into PREREG-FSA from the structure report, before any value is read. The
  per-crop-and-practice agreement checks already promised in the scoping note still
  apply.
- **R4. Flag yields that RMA or FSA set by rule.** County-years where RMA or the FSA
  State Committee set the yield from a neighbouring county, a district or "best data
  available" (listed in RMA Product Management bulletins and FSA's data-source files)
  are excluded wherever the files mark them. The share excluded is reported.

## Windows (unchanged in spirit, now concrete)

The early window is 2009-2012, when drought-tolerant corn was new or not yet sold. The
late window is 2017 plus 2019-2025, after adoption had levelled off. The ramp years
2013-2016 and the NASS-based 2018 are left out. The early window is short, only four
years, though it includes the 2012 drought. The pre-registration will therefore state
its power honestly and will not claim more than four early years can support.

## Not a second, independent test

RMA also publishes its own area-plan final county yields by practice (ARPI and SCO,
irrigated and non-irrigated), through its Actuarial Data Master files and its
Information Reporting System. These come from the same insurance records as FSA's
2019+ yields, so they are not independent evidence. They are a fallback source only, in
case the FSA files turn out to be incomplete. A structure-only inspection would come
first, as with FSA.

## Sources

- FSA ARC/PLC program data: https://www.fsa.usda.gov/resources/programs/arc-plc/program-data
- FSA Notice ARCPLC-91: https://www.fsa.usda.gov/Internet/FSA_Notice/arcplc91.pdf
- CRS R45730, Farm Commodity Provisions in the 2018 Farm Bill: https://www.congress.gov/crs-product/R45730
- farmdoc daily, 2024 county corn and soybean yields from RMA (2025-06-17):
  https://farmdocdaily.illinois.edu/2025/06/2024-county-corn-and-soybean-yields-from-the-risk-management-agency.html
