# corn-heat-tolerance

An open, pre-registered test of one question: **has the sensitivity of US corn yields
to extreme heat changed in the drought-tolerant-hybrid era (2011-2025)?** Earlier work
found that corn's heat tolerance peaked around 1960 and has declined since. Their data
end between 2005 and 2016. This project extends the test through the 2025 harvest
using public county data.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name.
Code Apache-2.0; text and derived tables CC BY 4.0.

- Pre-registration 0.1.0 (corn): [PREREG.md](PREREG.md), committed before any data were read.
- Pre-registration 0.2.0 (soybeans as the comparison crop): [PREREG-SOY.md](PREREG-SOY.md),
  committed before any soybean data were read and before any corn result existed.
- Pre-registration 0.3.0 (where drought-tolerant corn was adopted most):
  [PREREG-DT.md](PREREG-DT.md), committed before any result of 0.1.0 or 0.2.0 existed.
- Data: USDA NASS Quick Stats county corn and soybean yields (public domain), NOAA
  nClimGrid-Daily county averages, and the 2020 Census county gazetteer. State adoption
  groups come from USDA ERS (EIB-204, 2019; 2016 ARMS).
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

## Run

```
pip install numpy
python -m unittest -v test_cornheat test_soyheat test_dtstate
python run_cornheat.py --data-dir /data --out-dir /out
python soyheat.py --data-dir /data --out-dir /out
python dtstate.py --data-dir /data --out-dir /out
```

The scripts stream the roughly 1 GB NASS bulk file and about 1,600 monthly nClimGrid
files without keeping them. They cache only small derived tables under
`<data-dir>/cornheat/`, which all three scripts share. Results go to
`<out-dir>/cornheat_results.json`, `soyheat_results.json` and `dtstate_results.json`,
each with the automatic grading of its pre-registered predictions.

## Files

- `cornheat_data.py`: degree days, nClimGrid / NASS / gazetteer parsers (stdlib)
- `cornheat_model.py`: fixed-effects panel regression with two-way clustering (numpy)
- `run_cornheat.py`: the corn pipeline and the 0.1.0 grading
- `soyheat.py`: the soybean pipeline, joint corn-soybean model and the 0.2.0 grading
- `dtstate.py`: the adoption-group triple difference, randomization inference and the 0.3.0 grading
- `fetch_deps.py`, `fetch_deps_dt.py`: fetch the earlier modules at their pre-registration
  commits; the second also refuses to run until PREREG-DT.md is public
- `test_cornheat.py`, `test_soyheat.py`, `test_dtstate.py`: hand-checked unit tests and
  synthetic-panel recovery tests

## Status

Pre-registered 2026-11-17 (0.1.0 corn, then 0.2.0 soybeans, then 0.3.0 adoption groups).
Results will be added here once the jobs have run. Whichever way they fall, they will not
be re-graded.
