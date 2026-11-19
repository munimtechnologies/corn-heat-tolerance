# corn-heat-tolerance

An open, pre-registered test of one question: **has the sensitivity of US corn yields
to extreme heat changed in the drought-tolerant-hybrid era (2011-2025)?** Earlier work
found that corn's heat tolerance peaked around 1960 and has declined since. Their data
end between 2005 and 2019. This project extends the test through the 2025 harvest
using public county data.

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

## Run

```
pip install numpy
python -m unittest -v test_cornheat test_soyheat test_dtstate test_irrpractice test_rcheck
python run_cornheat.py --data-dir /data --out-dir /out
python soyheat.py --data-dir /data --out-dir /out
python dtstate.py --data-dir /data --out-dir /out
python irrpractice.py --data-dir /data --out-dir /out
python rcheck.py --data-dir /data --out-dir /out
```

The scripts stream the roughly 1 GB NASS bulk file and about 1,600 monthly nClimGrid
files without keeping them. They cache only small derived tables under
`<data-dir>/cornheat/`, which all the scripts share. Results go to
`<out-dir>/cornheat_results.json`, `soyheat_results.json`, `dtstate_results.json`,
`irrpractice_results.json` and `rcheck_results.json`, each with the automatic grading of
its pre-registered predictions.

## Files

- `cornheat_data.py`: degree days, nClimGrid / NASS / gazetteer parsers (stdlib)
- `cornheat_model.py`: fixed-effects panel regression with two-way clustering (numpy)
- `run_cornheat.py`: the corn pipeline and the 0.1.0 grading
- `soyheat.py`: the soybean pipeline, joint corn-soybean model and the 0.2.0 grading
- `dtstate.py`: the adoption-group triple difference, randomization inference and the 0.3.0 grading
- `irrpractice.py`: the dryland/irrigated triple difference, placebo and the 0.4.0 grading
- `rcheck.py`: the replication windows, corn-minus-soybean and warming-trend contrasts,
  and the 0.6.0 grading
- `fetch_deps.py`, `fetch_deps_dt.py`, `fetch_deps_irr.py`, `fetch_deps_rc.py`: fetch the
  earlier modules at their pre-registration commits; all but the first also refuse to run
  until their pre-registration is public
- `test_cornheat.py`, `test_soyheat.py`, `test_dtstate.py`, `test_irrpractice.py`,
  `test_rcheck.py`: hand-checked unit tests and synthetic-panel recovery tests
- `inspect_fsa.py` and `docs/`: the structure-only inspector and scoping notes for the
  FSA practice-yield step, written before any FSA yield was read

## Status

Pre-registered, in order: 0.1.0 corn, 0.2.0 soybeans, 0.3.0 adoption groups, 0.4.0
dryland versus irrigated (all 2026-11-17), and 0.6.0 replication of the June 2026
rising-sensitivity result (2026-11-19). Results will be added here once the jobs have
run. Whichever way they fall, they will not be re-graded.
