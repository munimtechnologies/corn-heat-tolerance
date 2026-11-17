# corn-heat-tolerance

An open, pre-registered test of one question: **has the sensitivity of US corn yields
to extreme heat changed in the drought-tolerant-hybrid era (2011-2025)?** Earlier work
found that corn's heat tolerance peaked around 1960 and has declined since. Their data
end between 2005 and 2016. This project extends the test through the 2025 harvest
using public county data.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name.
Code Apache-2.0; text and derived tables CC BY 4.0.

- Pre-registration: [PREREG.md](PREREG.md), committed before any data were read.
- Data: USDA NASS Quick Stats county corn yields (public domain), NOAA nClimGrid-Daily
  county averages, and the 2020 Census county gazetteer.
- Model: log yield on growing and extreme degree days (single sine, 29 °C) and
  precipitation, with county-by-era fixed effects, state-by-era quadratic trends,
  three eras (1951-1980, 1981-2010, 2011-2025) and two-way clustered errors
  (state, year).

## Run

```
pip install numpy
python -m unittest -v test_cornheat
python run_cornheat.py --data-dir /data --out-dir /out
```

The script streams the roughly 1 GB NASS bulk file and about 1,600 monthly nClimGrid
files without keeping them. It caches only small derived tables under
`<data-dir>/cornheat/`. The results go to `<out-dir>/cornheat_results.json`, together
with the automatic grading of the pre-registered predictions.

## Files

- `cornheat_data.py`: degree days, nClimGrid / NASS / gazetteer parsers (stdlib)
- `cornheat_model.py`: fixed-effects panel regression with two-way clustering (numpy)
- `run_cornheat.py`: the pipeline and the pre-registered grading
- `test_cornheat.py`: hand-checked unit tests and a synthetic-panel recovery test

## Status

Pre-registered 2026-11-17. Results will be added here once the job has run. Whichever
way they fall, they will not be re-graded.
