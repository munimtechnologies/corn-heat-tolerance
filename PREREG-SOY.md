# Pre-registration 0.2.0: soybeans as the comparison crop

PREREG-MARKER: corn-heat-tolerance-0.2.0-soy-prereg

Registered by MV2, Munim, Inc. (mv2@munimtech.com) on 2026-11-17. The soybean
code, its tests and this file are committed together, before the job that downloads
the soybean yields has run and before any 0.1.0 corn result exists. Made with AI agents
working in MV2's name. Text CC BY 4.0, code Apache-2.0. Pre-registration 0.1.0
([PREREG.md](PREREG.md)) is unchanged, and its corn predictions are graded exactly as
written there.

## Why a comparison crop

Pre-registration 0.1.0 asks whether US corn's yield sensitivity to extreme heat changed
in 2011-2025, the years of drought-tolerant corn hybrids (Pioneer Optimum AQUAmax from
2011, Bayer DroughtGard from 2013). A change in corn alone cannot tell the hybrids apart
from other things that changed at the same time: the weather data, planting dates and
management shared by both crops, CO2, or which counties kept reporting after NASS
thinned its county estimates.

Soybeans grow in the same counties, in the same seasons and under the same weather. They
had no widely sold drought-tolerant trait in those years. (The HB4 drought-tolerant
soybean was cleared in the US in 2022, and we know of no evidence that it was planted
widely by 2025.) So the **difference-in-differences** is the change in corn's
extreme-heat coefficient from 1981-2010 to 2011-2025, minus the same change for
soybeans. It nets out whatever moved both crops.

Prior art we found: Schlenker, Roberts & Lobell ("Is agricultural production becoming
more or less sensitive to extreme heat?", NBER, US corn and soybeans 1950-2005) found no
improvement in relative heat tolerance for either crop. Zhao, Tack et al. (Nature
Communications 2025) found improved drought resistance in corn hybrid *trials* from 2000
to 2020, measured by vapour-pressure deficit, without a soybean comparison. Zhao et al.
(Environmental Research Communications 2024, county corn 1981-2020) studied how the
timing of rain changes heat sensitivity. We found no test that uses soybeans as an
untreated comparison crop for corn's heat sensitivity after 2010, with county yields
through 2025.

**The "wow" if it works:** a clear corn-minus-soybean gain in heat tolerance after 2010.
That would be field-scale evidence, across the whole eastern US, that drought-tolerant
corn genetics changed how corn responds to extreme heat, and it would lower a central
input of climate-damage projections. A clear corn-minus-soybean *loss* would also be
news. We predict neither (S1).

## Data and sample

The same as 0.1.0: NASS Quick Stats bulk file (county, SURVEY, annual, domain TOTAL),
nClimGrid-Daily county weather and the 2020 gazetteer, counties east of 100° W excluding
Florida, and the same era rule (a county enters an era with yields in at least two thirds
of its years). Soybean yields use SHORT_DESC `SOYBEANS - YIELD, MEASURED IN BU / ACRE`.
Corn and soybean yields for the joint model come from **one pass over one bulk file**,
so that both crops share the same NASS snapshot. (The 0.1.0 job reads its own snapshot,
which may be a different day's file.)

## Model

Each crop has the 0.1.0 model: log yield on county-by-era fixed effects, state-by-era
linear and quadratic trends, and era-specific [GDD, EDD, P, P²] over March-August. The
extreme-heat threshold is 29 °C for corn and **30 °C for soybeans** (the Schlenker-Roberts
values). The two crops are stacked in one regression. Every coefficient, fixed effect
and trend is crop-specific, so the point estimates equal the separate fits exactly. The
two-way cluster-robust variance is clustered by state and by year *across both crops*,
which estimates the covariance between them. The state-by-era trends are partialled out
first (Frisch-Waugh-Lovell). This leaves the weather coefficients and their clustered
variance unchanged, as the unit tests check against the 0.1.0 fit.

DiD = (β_EDD,C − β_EDD,B)_corn − (β_EDD,C − β_EDD,B)_soy, tested at two-sided p < 0.05
with the joint two-way variance.

## Pre-registered predictions (graded automatically by `soyheat.py`)

- **S1 (primary).** The DiD is classed "corn gained relative to soybeans" (DiD > 0,
  significant), "corn lost relative to soybeans" (DiD < 0, significant) or "no detectable
  difference". **MV2 predicts: no detectable difference.**
- **S2.** The soybean β_EDD,B (30 °C, March-August) lies in [−0.012, −0.002] log yield per
  degree day.
- **S3.** In 1981-2010, soybeans are less heat-sensitive than corn:
  |β_EDD,B soy| < |β_EDD,B corn| (point estimates from the joint fit).
- **S4.** For soybeans alone, β_EDD,C − β_EDD,B is "no detectable change" (p ≥ 0.05).
- **S5.** In 1981-2010 alone, the soybean threshold b that minimises the residual sum of
  squares (b = 24-36 °C) lies in 28-33 °C.

Gates (not predictions): SG1 at least 800 soybean counties in era C; SG2 at least 90% of
NASS soybean counties matched to weather; SG3 at least 400 soybean county yields for
2025. If a gate fails, the results are still published, with the failure stated first.

Reported, not graded: the DiD on counties that are in both crops' samples in the same
era; without 2012; April-September; both crops at 29 °C and both at 30 °C; and soybean
rolling 15-year EDD windows.

## Known limits, stated in advance

- Soybeans are an imperfect control. Their critical heat period is later (August), and
  their own breeding and management changed too (for example earlier planting and
  narrower rows). The DiD nets out shocks common to both crops, not changes specific to
  soybeans.
- Drought-tolerant corn adoption was partial: about 22% of US corn acres around 2016,
  concentrated in drought-prone western areas. A national DiD dilutes a regional effect.
  By-state adoption analysis is planned as a later, separately registered step.
- Every limit in 0.1.0 still applies: county-average weather, the thinning of NASS
  counties, and a 15-year era C that includes the 2012 drought.

No result, whichever way it falls, will be re-graded. Any later analysis is labelled
post hoc.
