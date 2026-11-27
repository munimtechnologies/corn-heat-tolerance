# corn-heat-tolerance

An open, pre-registered test of one question: **has the sensitivity of US corn yields
to extreme heat changed in the drought-tolerant-hybrid era (2011-2025)?** Earlier work
found that corn's heat tolerance peaked around 1960 and has declined since. Their data
end between 2005 and 2019. This project extends the test through the 2025 harvest
using public county data. Published studies also disagree about the direction: a 2021
long-difference study in log yields reports that corn's loss per extreme-heat degree day
fell by about half since 1960, and a 2026 rolling-window study in yield levels reports
that it rose by about 20%. Steps 0.6.0, 0.7.0 and 0.7.1 test both on the same data, and
step 0.8.0 tests whether the difference in yield scale (levels versus proportions)
explains the contradiction.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name.
Code Apache-2.0; text and derived tables CC BY 4.0.

- Pre-registration 0.1.0 (corn): [PREREG.md](PREREG.md), committed before any data were read.
- Pre-registration 0.2.0 (soybeans as the comparison crop): [PREREG-SOY.md](PREREG-SOY.md),
  committed before any soybean data were read and before any corn result existed.
- Pre-registration 0.3.0 (where drought-tolerant corn was adopted most):
  [PREREG-DT.md](PREREG-DT.md), committed before any result of 0.1.0 or 0.2.0 existed.
- Pre-registration 0.4.0 (dryland versus irrigated fields in the same county):
  [PREREG-IRR.md](PREREG-IRR.md), committed before any earlier result existed and before
  any irrigated or non-irrigated yield was read.
- Pre-registration 0.6.0 (replication of Raghuram & Coffel, *Environ. Res. Lett.* 2026):
  [PREREG-RC.md](PREREG-RC.md), committed before any result of this project existed. It
  tests whether their reported rise in corn's heat sensitivity (1960-1989 vs 1990-2019)
  appears with independent weather data, whether it is specific to corn (soybeans as the
  control), whether it persists with 2020-2025 added, and whether it follows local
  warming. Version 0.5.0 is reserved for the FSA practice-yield step
  ([docs/step-c-sources-addendum.md](docs/step-c-sources-addendum.md)).
- Pre-registration 0.7.0 (reconciliation with Yu, Miao & Khanna, *Sci. Rep.* 2021):
  [PREREG-LD.md](PREREG-LD.md), committed before any result of this project existed. Their
  "flexible long difference" (1958-62 vs 2013-17) identifies a change in heat sensitivity
  from whether hotter counties' yields grew faster. The step tests whether that fall
  replicates, and whether it shrinks when counties are compared only within their own
  state (regional catch-up rather than heat adaptation), for corn and soybeans.
- Pre-registration 0.7.1 (Yu et al.'s exact variables): [PREREG-LD-YU.md](PREREG-LD-YU.md),
  committed on 2026-11-25 before any result existed. It repeats the 0.7.0 test with
  their own definitions (April-September, degree days 0-29 C and above 29 C for both
  crops, rainfall as shortfall below and excess above 42 cm, counties kept if present in
  both periods) and grades the replication of the size of their fall.
- Pre-registration 0.8.0 (is the 2026 rise a matter of yield scale?):
  [PREREG-RCX.md](PREREG-RCX.md), committed on 2026-11-27 before any result existed.
  Raghuram & Coffel's estimator works on yields in levels, detrended and divided by one
  full-series standard deviation. If a hot degree day costs the same share of the crop
  in every decade, that estimator shows a "rise" as large as the growth in trend yield.
  The step runs their estimator (per-county OLS in 31 rolling 30-year windows, averaged
  over counties) on this project's data three ways, changing only the yield scale
  (level, relative to trend, log), and grades whether the rise disappears on a
  proportional scale. A follow-up (0.8.1) will apply the same change to the authors' own
  published code and data (doi:10.5281/zenodo.20185245).
- Data: USDA NASS Quick Stats county corn and soybean yields (public domain), NOAA
  nClimGrid-Daily county averages, and the 2020 Census county gazetteer. State adoption
  groups and the dryland/irrigated adoption gap come from USDA ERS (EIB-204, 2019; 2016
  ARMS; Chart of Note, 29 July 2019).
- Model: log yield on growing and extreme degree days (single sine; 29 °C for corn,
  30 °C for soybeans) and precipitation, with county-by-era fixed effects,
  state-by-era quadratic trends, three eras (1951-1980, 1981-2010, 2011-2025) and
  two-way clustered errors (state, year).
- Soybean step: soybeans share the counties and the weather but had no widely sold
  drought-tolerant trait, so the corn-minus-soybean change in heat sensitivity
  (a difference-in-differences from a joint, cross-crop clustered regression) nets out
  what moved both crops.
- Adoption step: the corn-minus-soybean change in the high-adoption states (Nebraska,
  Kansas: about 40% of corn acres in drought-tolerant hybrids in 2016) minus the same
  change in seven low-adoption Corn Belt states (14-21%). It is a triple difference,
  judged by year-clustered inference together with randomization inference over all 36
  two-state splits. A secondary version splits counties into the driest and wettest
  thirds by 1981-2010 rainfall.
- Irrigation step: within the same Nebraska and Kansas counties, dryland fields (60% DT
  in Nebraska in 2016) against irrigated fields (31%), each net of soybeans on the same
  practice. Eras are 1981-2010 and 2011-2018, because NASS stopped county yields by
  practice after the 2018 crop. The test is judged by year-clustered inference with a
  1981-1995 vs 1996-2010 placebo.
- Replication step: the 12 Census Midwest states, two 30-year windows (1960-1989,
  1990-2019; extension 1966-1995, 1996-2025), corn alone and corn minus soybeans, and
  the counties with the warmest and coolest growing-season temperature trends.
- Long-difference step: county means of log yield and weather over two 5-year periods,
  with one intercept (as in Yu et al.) and with state fixed effects, state-clustered
  errors; a joint verdict with the replication step is fixed in advance.
- Scale step: the rolling-window estimator in level, relative and log form on the same
  counties, the trend-yield ratio a constant-share crop would show in levels, and a
  paired county bootstrap (reported only).

## Run

```
pip install numpy
python -m unittest -v test_cornheat test_soyheat test_dtstate test_irrpractice test_rcheck test_ldiff test_ldiff_yu test_rcx
python run_cornheat.py --data-dir /data --out-dir /out
python soyheat.py --data-dir /data --out-dir /out
python dtstate.py --data-dir /data --out-dir /out
python irrpractice.py --data-dir /data --out-dir /out
python rcheck.py --data-dir /data --out-dir /out
python ldiff.py --data-dir /data --out-dir /out
python ldiff_yu.py --data-dir /data --out-dir /out
python rcx.py --data-dir /data --out-dir /out
```

The scripts stream the roughly 1 GB NASS bulk file and about 1,600 monthly nClimGrid
files without keeping them. They cache only small derived tables under
`<data-dir>/cornheat/`, which all the scripts share (`ldiff_yu.py` and `rcx.py` only read
them). Results go to `<out-dir>/cornheat_results.json`, `soyheat_results.json`,
`dtstate_results.json`, `irrpractice_results.json`, `rcheck_results.json`,
`ldiff_results.json`, `ldiff_yu_results.json` and `rcx_results.json`, each with the
automatic grading of its pre-registered predictions.

## Files

- `cornheat_data.py`: degree days, nClimGrid / NASS / gazetteer parsers (stdlib)
- `cornheat_model.py`: fixed-effects panel regression with two-way clustering (numpy)
- `run_cornheat.py`: the corn pipeline and the 0.1.0 grading
- `soyheat.py`: the soybean pipeline, joint corn-soybean model and the 0.2.0 grading
- `dtstate.py`: the adoption-group triple difference, randomization inference and the 0.3.0 grading
- `irrpractice.py`: the dryland/irrigated triple difference, placebo and the 0.4.0 grading
- `rcheck.py`: the replication windows, corn-minus-soybean and warming-trend contrasts,
  and the 0.6.0 grading
- `ldiff.py`: the flexible long differences with and without state fixed effects, the
  0.7.0 grading and the joint verdict with 0.6.0
- `ldiff_yu.py`: the same models on Yu et al.'s exact variables and the 0.7.1 grading
- `rcx.py`: the rolling-window estimator in level, relative and log form and the 0.8.0
  grading (standard library only)
- `tools/rcz_inspect.py`: structure-only check of the authors' Zenodo archive for 0.8.1
  (file list, table shapes and column names; no values)
- `fetch_deps.py`, `fetch_deps_dt.py`, `fetch_deps_irr.py`, `fetch_deps_rc.py`,
  `fetch_deps_ld.py`, `fetch_deps_yu.py`, `fetch_deps_rcx.py`: fetch the earlier modules
  at their pre-registration commits; all but the first also refuse to run until their
  pre-registration is public
- `test_cornheat.py`, `test_soyheat.py`, `test_dtstate.py`, `test_irrpractice.py`,
  `test_rcheck.py`, `test_ldiff.py`, `test_ldiff_yu.py`, `test_rcx.py`: hand-checked unit
  tests and synthetic recovery tests
- `inspect_fsa.py` and `docs/`: the structure-only inspector and scoping notes for the
  FSA practice-yield step, written before any FSA yield was read

## Prior work this project builds on

Schlenker & Roberts (PNAS 2009); Burke & Emerick (AEJ: Economic Policy 2016); Anderson et
al. (Environmental Research Letters 2015, on yield loss in levels versus percentages); Yu,
Miao & Khanna (Scientific Reports 2021); Raghuram & Coffel (Environmental Research Letters
2026; code and data doi:10.5281/zenodo.20185245, CC BY 4.0); Zhao et al. (Nature Food 2026,
crop-specific heat thresholds); Ghanem, Pretis & Schuurman (arXiv:2607.22028, 2026, on
long-difference versus fixed-effects comparisons); Valente (SSRN 6898120, 2026, county
differences in corn's heat losses from long differences).

## Status

Pre-registered, in order: 0.1.0 corn, 0.2.0 soybeans, 0.3.0 adoption groups, 0.4.0
dryland versus irrigated (all 2026-11-17), 0.6.0 replication of the June 2026
rising-sensitivity result (2026-11-19), 0.7.0 reconciliation with the 2021
falling-sensitivity result (2026-11-20), 0.7.1 the same on Yu et al.'s exact
variables (2026-11-25) and 0.8.0 the yield-scale test (2026-11-27). The analysis jobs
are queued for compute and none has run yet. Results will be added here once they
have. Whichever way they fall, they will not be re-graded.
