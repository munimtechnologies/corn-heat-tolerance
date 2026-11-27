# rcx.py - step 0.8.0: is the reported rise in corn's heat sensitivity a matter of
# yield scale? (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-RCX.md (marker corn-heat-tolerance-0.8.0-rcx-prereg),
# written on 2026-11-27 before any result of this project existed.
#
# Raghuram & Coffel (Environ. Res. Lett. 21, 124041, 2026) report that the
# sensitivity of US Midwest corn to killing degree days (KDD, > 29 C) rose by
# nearly 20% from the 1960-1989 to the 1990-2019 rolling window. Their Methods
# (re-read 2026-11-27) model yields in LEVELS: per grid cell, yields are linearly
# detrended once over 1960-2019 and divided by one full-series standard deviation;
# KDD and GDD (9-29 C) are linearly detrended; an OLS of the standardized yield
# anomaly on the KDD and GDD anomalies is re-estimated in each 30-year window, and
# the KDD coefficients are averaged over cells. Logs are never used.
#
# If a degree day costs the same SHARE of yield in every decade, the level loss per
# degree day grows in proportion to trend yield, which rose about 1.5-1.8-fold between
# the midpoints of the first and last windows. A level estimator would then show a
# "rise" of that size with no change in the crop's proportional sensitivity. Yu, Miao
# & Khanna (Sci. Rep. 2021), working in log yields, report a FALL. This module runs
# the Raghuram-Coffel estimator on this project's county data three ways, changing
# only the yield scale:
#   level     their form: detrended yield / its full-series SD
#   relative  detrended yield / its own trend value, then / its full-series SD
#   log       detrended log yield / its full-series SD
# and grades X1-X5 (see PREREG-RCX.md). Everything else is held fixed.
#
# The published project modules (dtstate, run_cornheat, soyheat) are imported only
# inside main(), so the estimator and its tests need nothing but the standard library.

import argparse
import json
import math
import os
import random
import sys

PREREG_MARKER = "corn-heat-tolerance-0.8.0-rcx-prereg"
MW12 = ("17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55")
WIN = 30
PRIMARY = (1960, 2019)          # 31 windows: 1960-1989 ... 1990-2019 (their windows)
EXTENDED = (1960, 2025)         # 37 windows: last one 1996-2025
SEASON = "AprSep"               # closest of the cached seasons to the Sacks calendar
GDD_LO = 9                      # their GDD band is 9-29 C
B_CORN = 29
B_SOY = 30                      # Schlenker-Roberts soybean threshold, as in 0.2.0
MIN_PER_WINDOW = 20             # a county needs >= 20 yield years in EVERY window
FORMS = ("level", "relative", "log")
BOOT_B = 500
BOOT_SEED = 20261127
RC_REPORTED_RATIO = 1.2         # "nearly 20% increase" first -> last window


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ small algebra
def linfit(xs, ys):
    """OLS of ys on (1, xs): returns (intercept, slope)."""
    n = len(xs)
    if n < 2 or n != len(ys):
        raise ValueError("linfit needs >= 2 paired points")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        raise ValueError("linfit: no spread in x")
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def detrend(xs, ys):
    """Residuals from a linear trend, and the fitted trend values."""
    a, b = linfit(xs, ys)
    fit = [a + b * x for x in xs]
    return [y - f for y, f in zip(ys, fit)], fit


def sd(v):
    """Sample standard deviation (n - 1), as R's sd()."""
    n = len(v)
    if n < 2:
        raise ValueError("sd needs >= 2 values")
    m = sum(v) / n
    return math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))


def ols_kdd(z, k, g):
    """Slopes of z on k and g with an intercept (centred two-regressor OLS).
    Returns (b_kdd, b_gdd)."""
    n = len(z)
    if n < 4 or len(k) != n or len(g) != n:
        raise ValueError("ols_kdd needs >= 4 paired years")
    mk, mg, mz = sum(k) / n, sum(g) / n, sum(z) / n
    skk = sgg = skg = skz = sgz = 0.0
    for zi, ki, gi in zip(z, k, g):
        a, c, d = ki - mk, gi - mg, zi - mz
        skk += a * a
        sgg += c * c
        skg += a * c
        skz += a * d
        sgz += c * d
    det = skk * sgg - skg * skg
    if skk <= 0 or sgg <= 0 or det <= 1e-12 * skk * sgg:
        raise ValueError("constant or collinear regressors")
    return (sgg * skz - skg * sgz) / det, (skk * sgz - skg * skz) / det


def quantile(xs, q):
    v = sorted(x for x in xs if x is not None and math.isfinite(x))
    if not v:
        return None
    pos = q * (len(v) - 1)
    i = int(math.floor(pos))
    j = min(i + 1, len(v) - 1)
    return v[i] + (v[j] - v[i]) * (pos - i)


def starts_for(y0, y1, win=WIN):
    """Start years of every full `win`-year window inside [y0, y1]."""
    return list(range(y0, y1 - win + 2))


# ------------------------------------------------------------------ panel -> series
def county_series(rows, y0, y1, b, season=SEASON, lo=GDD_LO, states=MW12, drop_years=()):
    """fips -> {year: (yield level, KDD > b, GDD lo..b)} from load_panels rows
    (which carry log yield and the cached degree-day vector for each season)."""
    out = {}
    for r in rows:
        yr = int(r["year"])
        if not y0 <= yr <= y1 or yr in drop_years:
            continue
        if states is not None and r["state"] not in states:
            continue
        dd = r["dd"][season]
        kdd = float(dd[b])
        gdd = float(dd[lo]) - float(dd[b])
        if not (math.isfinite(kdd) and math.isfinite(gdd)):
            continue
        out.setdefault(r["fips"], {})[yr] = (math.exp(float(r["logy"])), kdd, gdd)
    return out


def anomalies(ser, form):
    """year -> (standardized yield anomaly, KDD anomaly, GDD anomaly) for one county.
    Detrending and standardization use the county's whole series, once."""
    years = sorted(ser)
    Y = [ser[t][0] for t in years]
    K = [ser[t][1] for t in years]
    G = [ser[t][2] for t in years]
    if form == "level":
        u, _ = detrend(years, Y)
    elif form == "relative":
        u0, fit = detrend(years, Y)
        if min(fit) <= 0:
            raise ValueError("non-positive trend yield")
        u = [a / f for a, f in zip(u0, fit)]
    elif form == "log":
        if min(Y) <= 0:
            raise ValueError("non-positive yield")
        u, _ = detrend(years, [math.log(y) for y in Y])
    else:
        raise ValueError("unknown form %r" % form)
    s = sd(u)
    if s <= 0:
        raise ValueError("no yield variation")
    k, _ = detrend(years, K)
    g, _ = detrend(years, G)
    return {t: (ui / s, ki, gi) for t, ui, ki, gi in zip(years, u, k, g)}


def county_window_betas(anom, starts, win=WIN, min_n=MIN_PER_WINDOW):
    """KDD coefficient in each window, or None if any window has < min_n years."""
    out = []
    for s in starts:
        ys = [t for t in sorted(anom) if s <= t <= s + win - 1]
        if len(ys) < min_n:
            return None
        out.append(ols_kdd([anom[t][0] for t in ys], [anom[t][1] for t in ys],
                           [anom[t][2] for t in ys])[0])
    return out


def form_betas(series, form, starts, win=WIN, min_n=MIN_PER_WINDOW):
    betas, dropped = {}, {"few_years": 0, "fit": 0}
    for f in sorted(series):
        try:
            b = county_window_betas(anomalies(series[f], form), starts, win, min_n)
        except (ValueError, ZeroDivisionError, OverflowError):
            dropped["fit"] += 1
            continue
        if b is None:
            dropped["few_years"] += 1
            continue
        betas[f] = b
    return betas, dropped


def summarise(betas, counties, starts):
    """Unweighted mean KDD coefficient over `counties` in each window (as the paper
    averages over grid cells), the last/first ratio and the linear-trend change."""
    n = len(counties)
    if n == 0:
        raise ValueError("no counties")
    mean_w = [sum(betas[f][i] for f in counties) / n for i in range(len(starts))]
    _, slope = linfit(starts, mean_w)
    first, last = mean_w[0], mean_w[-1]
    return {"counties": n, "starts": list(starts), "mean_by_window": mean_w,
            "first": first, "last": last,
            "ratio_last_first": (last / first) if first != 0 else None,
            "trend_change": (slope * (starts[-1] - starts[0]) / first) if first != 0 else None}


def trend_yield_ratio(series, counties, starts, win=WIN):
    """Mean fitted linear-trend yield at the midpoint of the last window over that of
    the first window: the rise a level estimator shows with constant shares."""
    mid0 = starts[0] + (win - 1) / 2.0
    mid1 = starts[-1] + (win - 1) / 2.0
    v0 = v1 = 0.0
    for f in counties:
        ser = series[f]
        years = sorted(ser)
        a, b = linfit(years, [ser[t][0] for t in years])
        v0 += a + b * mid0
        v1 += a + b * mid1
    return v1 / v0 if v0 != 0 else None


def boot_ratios(betas_by_form, counties, B=BOOT_B, seed=BOOT_SEED):
    """Paired county bootstrap (same draw for every form) of the last/first ratio.
    Counties share weather, so this understates the uncertainty; reported only."""
    rng = random.Random(seed)
    cs = sorted(counties)
    n = len(cs)
    draws = {form: [] for form in betas_by_form}
    gap = []
    for _ in range(B):
        pick = [cs[rng.randrange(n)] for _ in range(n)]
        r = {}
        for form, bt in betas_by_form.items():
            f0 = sum(bt[c][0] for c in pick) / n
            f1 = sum(bt[c][-1] for c in pick) / n
            r[form] = f1 / f0 if f0 != 0 else float("nan")
            draws[form].append(r[form])
        if "level" in r and "relative" in r and r["level"] > 0 and r["relative"] > 0:
            gap.append(math.log(r["level"]) - math.log(r["relative"]))
    out = {"B": B, "seed": seed, "counties": n,
           "note": "county resampling ignores shared weather; intervals are too narrow"}
    for form, d in draws.items():
        out[form] = {"p05": quantile(d, 0.05), "p50": quantile(d, 0.5), "p95": quantile(d, 0.95)}
    out["log_level_minus_log_relative"] = {"p05": quantile(gap, 0.05), "p50": quantile(gap, 0.5),
                                           "p95": quantile(gap, 0.95)}
    return out


def run_forms(series, y0, y1, boot=True):
    """All three forms on the SAME counties (those every form can estimate)."""
    starts = starts_for(y0, y1)
    betas, dropped = {}, {}
    for form in FORMS:
        betas[form], dropped[form] = form_betas(series, form, starts)
    common = sorted(set.intersection(*[set(b) for b in betas.values()]))
    out = {"years": [y0, y1], "windows": len(starts), "counties_in_panel": len(series),
           "counties_common": len(common), "dropped": dropped}
    for form in FORMS:
        out[form] = summarise(betas[form], common, starts)
    out["trend_yield_ratio"] = trend_yield_ratio(series, common, starts)
    if boot:
        out["bootstrap"] = boot_ratios(betas, common)
    return out


# ------------------------------------------------------------------ grading
PRED_KEYS = ("X1_holds_level_rise", "X2_holds_scale_shrinks_rise", "X3_holds_relative_no_rise",
             "X4_holds_log_no_rise", "X5_holds_relative_no_rise_to_2025")


def _r(block):
    return block.get("ratio_last_first")


def verdict(g):
    if not g["X1_holds_level_rise"]:
        return "no-level-rise: the rise does not appear in this data even in the paper's level form"
    if g["X3_holds_relative_no_rise"]:
        return "scale: the rise appears in yield levels only; per unit of yield, sensitivity did not rise"
    return "proportional-rise: the rise survives when yields are put on a proportional scale"


def grade_rcx(res):
    """Pre-registered predictions X1-X5 and gates XG1-XG3 (PREREG-RCX.md)."""
    p, e = res["primary"], res["extended"]
    lv, rl, lg, ex = _r(p["level"]), _r(p["relative"]), _r(p["log"]), _r(e["relative"])
    have = all(v is not None for v in (lv, rl, lg))
    g = {
        "XG1_corn_counties_ge_300": p["counties_common"] >= 300,
        "XG2_level_first_window_negative": p["level"]["first"] < 0,
        "XG3_relative_first_window_negative": p["relative"]["first"] < 0,
        "X1_holds_level_rise": lv is not None and lv > 1.0,
        "X2_holds_scale_shrinks_rise": have and rl < lv and lg < lv,
        "X3_holds_relative_no_rise": rl is not None and rl < 1.0,
        "X4_holds_log_no_rise": lg is not None and lg < 1.0,
        "X5_holds_relative_no_rise_to_2025": ex is not None and ex < 1.0,
        "ratio_level": lv, "ratio_relative": rl, "ratio_log": lg, "ratio_relative_to_2025": ex,
        "trend_yield_ratio": p["trend_yield_ratio"],
        "raghuram_coffel_reported_ratio": RC_REPORTED_RATIO,
    }
    g["predictions_held"] = sum(1 for k in PRED_KEYS if g[k])
    g["verdict"] = verdict(g)
    return g


# ------------------------------------------------------------------ pipeline
def stage(rows, census):
    res = {"census": census, "season": SEASON, "gdd_band": [GDD_LO, B_CORN], "kdd_threshold": B_CORN,
           "states_mw12": MW12, "window_years": WIN, "min_years_per_window": MIN_PER_WINDOW,
           "forms": FORMS, "prereg_marker": PREREG_MARKER,
           "units": "standardized yield anomaly (SD units) per KDD; ratios last/first window"}
    corn = rows["corn"]
    res["primary"] = run_forms(county_series(corn, PRIMARY[0], PRIMARY[1], B_CORN), *PRIMARY)
    log("primary:", json.dumps({f: res["primary"][f]["ratio_last_first"] for f in FORMS}))
    res["extended"] = run_forms(county_series(corn, EXTENDED[0], EXTENDED[1], B_CORN), *EXTENDED)
    rob = {}
    rob["corn_MarAug"] = run_forms(county_series(corn, PRIMARY[0], PRIMARY[1], B_CORN, season="MarAug"),
                                   *PRIMARY, boot=False)
    rob["corn_no2012"] = run_forms(county_series(corn, PRIMARY[0], PRIMARY[1], B_CORN, drop_years=(2012,)),
                                   *PRIMARY, boot=False)
    rob["corn_all_east"] = run_forms(county_series(corn, PRIMARY[0], PRIMARY[1], B_CORN, states=None),
                                     *PRIMARY, boot=False)
    rob["soy_mw12"] = run_forms(county_series(rows["soy"], PRIMARY[0], PRIMARY[1], B_SOY), *PRIMARY)
    rob["soy_mw12_extended"] = run_forms(county_series(rows["soy"], EXTENDED[0], EXTENDED[1], B_SOY),
                                         *EXTENDED, boot=False)
    res["robustness"] = rob
    res["grades"] = grade_rcx(res)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-wait-min", type=int, default=720)
    a = ap.parse_args(argv)
    import dtstate as DT          # published modules, fetched by fetch_deps_rcx.py
    import run_cornheat as R
    import soyheat as S
    ddir = os.path.join(a.data_dir, "cornheat")
    sdir = os.path.join(ddir, "soy")
    os.makedirs(a.out_dir, exist_ok=True)
    # Reader only: the shared tables are built by the 0.1.0/0.2.0 jobs on this volume.
    if not DT.wait_for_inputs(ddir, sdir, 1951, 2025, a.max_wait_min):
        log("inputs not ready; nothing read. Re-run after the cornheat/soyheat jobs.")
        return 3
    keep = R.east_sample(R.load_geo(R.stage_geo(ddir)))
    log("east sample counties:", len(keep))
    rows, census = S.load_panels(ddir, sdir, keep, PRIMARY[0], EXTENDED[1])
    log("panels:", census)
    res = stage(rows, census)
    with open(os.path.join(a.out_dir, "rcx_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
