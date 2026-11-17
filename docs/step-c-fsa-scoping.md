# Step (c) scoping: FSA ARC-County yields by irrigation practice

Status: scoping only (2026-11-17). No FSA yield has been read, and no model has been fitted.
Made with AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com). Text
CC BY 4.0, code Apache-2.0.

## Why this step exists

Pre-registration 0.4.0 ([PREREG-IRR.md](../PREREG-IRR.md)) compares dryland and irrigated
corn in the same Nebraska and Kansas counties. Its post-2010 era stops in 2018, because
NASS stopped publishing county yields by irrigation practice with the 2019 crop. Those
eight years cover the period when drought-tolerant (DT) corn adoption was still rising.

USDA's Farm Service Agency (FSA) publishes county yields for the Agriculture Risk
Coverage, County option (ARC-CO). They are split into irrigated and non-irrigated practice
where a county has at least 10% of each. In recent years they are built mostly from
federal crop insurance (RMA) records, not from the NASS survey. These files could
extend the dryland-versus-irrigated comparison through 2025, after DT adoption had
levelled off. Because the method differs from NASS's, any such test will be a **separate
pre-registration**, and FSA years will not be joined onto the NASS series.

## What the inspection job does

`inspect_fsa.py` (with `test_inspect_fsa.py`) downloads the ARC-County Benchmark Yields
and Revenues workbooks and the "Detailed ARC-CO NASS and RMA County Yields" file from
FSA's ARC/PLC program-data page. For each sheet it reports only:

- header rows, column names and the yield years each file carries;
- the practice and crop labels used;
- for Nebraska and Kansas, the number of corn and soybean county-practice rows and the
  number of non-empty cells in each numeric column.

It never prints, stores or summarises a yield value. The pre-registration is written
from this structure report, before any FSA yield is analysed.

## Decisions fixed now, before the structure is known

1. Sample: Nebraska and Kansas counties in the 0.1.0 spatial sample (centroid east of
   100° W); corn and soybeans; irrigated and non-irrigated practice only (no "all
   practices" rows).
2. Weather: the same nClimGrid-Daily county degree days as 0.1.0-0.4.0 (29 °C corn,
   30 °C soybeans, March-August).
3. Source-agreement gate before any heat model: county-practice-years that are in both
   NASS (to 2018) and FSA must agree closely. The exact thresholds go in the
   pre-registration. If the gate fails, the heat test is not run and the disagreement
   is published.
4. The contrast is the same as in 0.4.0: dryland minus irrigated, corn net of soybeans,
   comparing an early window of low DT adoption with a late window after adoption
   levelled off. The adoption-ramp years are excluded from both windows. Year-clustered
   inference and a pre-period placebo are used wherever the FSA years allow one.
