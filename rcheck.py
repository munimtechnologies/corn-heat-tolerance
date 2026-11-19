# rcheck.py - does the reported rise in corn's heat sensitivity replicate, is it
# specific to corn, and does it continue into 2020-2025? (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-RC.md (marker corn-heat-tolerance-0.6.0-rc-prereg).
# Raghuram & Coffel (Environ. Res. Lett. 21, 124041, June 2026) report that the
# yield loss of US Midwest corn per killing degree day (> 29 C) rose by nearly 20%
# between 1960 and 2019 (30-year rolling windows, ERA5 weather, rainfed grid cells),
# with declines in the north, rises in the south, and a link to local warming of
# daily maximum temperature. This module asks, with this project's independent
# data and model (nClimGrid county weather, log yield, county-by-window fixed
# effects, state-by-window quadratic trends, two-way clustered errors):
#   RC1  does corn's EDD coefficient fall (more negative) from 1960-1989 to
#        1990-2019 in the 12 Census Midwest states?
#   RC2  is that change specific to corn, i.e. different from soybeans' change
#        in the same counties and weather (difference-in-differences)?
#   RC3  does the rise still show with 2020-2025 added (1966-1995 vs 1996-2025)?
#   RC4  did corn in the counties whose growing season warmed most become more
#        heat-sensitive than corn in the counties that warmed least?
#   RC5  does that warming-county gap survive netting out soybeans?
# Reported, not graded: the same on all counties east of 100 W, without 2012,
# for April-September, 30-year rolling windows for both crops, and the 0.3.0
# drought-tolerance triple difference restricted to counties with mid-range
# temperature trends.
#
# Reuses the published cornheat_model / run_cornheat / soyheat / dtstate modules
# unchanged (commit 6771a70f) and the derived tables cached on the same volume.

import argparse
import json
import math
import os
import sys

import cornheat_model as M
import dtstate as DT
import run_cornheat as R
import soyheat as S

# Census Midwest: IL IN IA KS MI MN MO NE ND OH SD WI (east-of-100 W counties only)
MW12 = ("17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55")
E1 = ("E", 1960, 1989)
L1 = ("L", 1990, 2019)
E2 = ("E", 1966, 1995)
L2 = ("L", 1996, 2025)
PAIR1 = (E1, L1)
PAIR2 = (E2, L2)
B_CROP = S.B_CROP
SEASON = "MarAug"
log = R.log


# ------------------------------------------------------------------ contrasts
def change_weights(prefix=""):
    """EDD_L - EDD_E for one block (prefix '' for a single-crop fit)."""
    p = prefix + ":" if prefix else ""
    return {p + "EDD_L": 1.0, p + "EDD_E": -1.0}


def sub_weights(a, b):
    """Weights of contrast a minus contrast b."""
    w = dict(a)
    for k, v in b.items():
        w[k] = w.get(k, 0.0) - v
    return w


def did_weights(a, b):
    """(L-E) of block a minus (L-E) of block b."""
    return sub_weights(change_weights(a), change_weights(b))


def contrast_all(res, weights):
    """Two-way (state, year) clustered contrast, plus the year-clustered one."""
    out = S.contrast(res, weights)
    out["year"] = DT.contrast_v(res, weights, "V2")
    return out


def rise_class(t):
    """A rise in heat sensitivity is a more negative EDD coefficient: L-E < 0."""
    sig = t["p"] == t["p"] and t["p"] < 0.05
    if t["diff"] < 0:
        return "rise replicated" if sig else "rise in direction only"
    return "fall" if sig else "no rise"


def warm_class(t):
    if t["p"] == t["p"] and t["p"] < 0.05:
        return "warming counties lost" if t["diff"] < 0 else "warming counties gained"
    return "no detectable difference"


# ------------------------------------------------------------------ helpers
def in_states(rows, states):
    s = set(states)
    return [r for r in rows if r["state"] in s]


def county_count(rows, era):
    _lab, a, b = era
    return len({r["fips"] for r in rows if a <= r["year"] <= b})


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    pos = q * (len(xs) - 1)
    i = int(math.floor(pos))
    fr = pos - i
    if i + 1 < len(xs):
        return xs[i] + fr * (xs[i + 1] - xs[i])
    return xs[i]


def tbar(r, season=SEASON):
    """Season mean temperature proxy (deg C): degree days above 0 C / season days."""
    return float(r["dd"][season][0]) / R.SEASON_DAYS[season]


def temp_trends(rows, y0, y1, season=SEASON, min_years=20):
    """County OLS slope (deg C per decade) of the season mean temperature proxy on
    year, over the county's rows in y0..y1; counties with < min_years are dropped."""
    acc = {}
    for r in rows:
        if y0 <= r["year"] <= y1:
            acc.setdefault(r["fips"], {})[r["year"]] = tbar(r, season)
    out = {}
    for f, d in acc.items():
        if len(d) < min_years:
            continue
        ys = sorted(d)
        n = float(len(ys))
        mx = sum(ys) / n
        my = sum(d[y] for y in ys) / n
        sxx = sum((y - mx) ** 2 for y in ys)
        sxy = sum((y - mx) * (d[y] - my) for y in ys)
        out[f] = 10.0 * sxy / sxx
    return out


def trend_terciles(trends):
    """Warmest-trend third and coolest-trend third of counties (ties by FIPS)."""
    s = sorted((v, f) for f, v in trends.items())
    k = len(s) // 3
    cool = {f for _, f in s[:k]}
    warm = {f for _, f in s[len(s) - k:]} if k else set()
    info = {"counties": len(s), "per_tercile": k,
            "cool_max_C_per_decade": s[k - 1][0] if k else None,
            "warm_min_C_per_decade": s[len(s) - k][0] if k else None,
            "median_C_per_decade": quantile([v for v, _ in s], 0.5)}
    return warm, cool, info


# ------------------------------------------------------------------ fits
def pair_fit(rows, pair, b, season=SEASON):
    """One crop, two windows in one regression (window-specific county FE, state
    trends and weather terms). L-E with two-way and year-clustered inference."""
    eras = list(pair)
    er = R.era_filter(rows, eras)
    f = M.fit(er, eras, b=b, season=season)
    bE, sE = M.coef(f, "EDD_E")
    bL, sL = M.coef(f, "EDD_L")
    ch = contrast_all(f, change_weights())
    return {"n": f["n"], "states": f["g1"], "years": f["g2"], "fallback": f["fallback"],
            "counties": {e[0]: county_count(er, e) for e in eras},
            "windows": {e[0]: [e[1], e[2]] for e in eras},
            "EDD_E": {"b": bE, "se2way": sE}, "EDD_L": {"b": bL, "se2way": sL},
            "ratio_L_over_E": (bL / bE) if bE < 0 else None,
            "change": ch, "class": rise_class(ch)}


def pair_joint(corn, soy, pair, season=SEASON, b_corn=B_CROP["corn"], b_soy=B_CROP["soy"]):
    """Corn and soybeans stacked (crop-specific everything, shared clusters):
    each crop's L-E and the corn-minus-soybean difference-in-differences."""
    eras = list(pair)
    ec = R.era_filter(corn, eras)
    es = R.era_filter(soy, eras)
    jf = S.joint_fit([("corn", ec, eras, b_corn, season), ("soy", es, eras, b_soy, season)])
    out = {"n": jf["n"], "fallback": jf["fallback"], "coef": {},
           "counties": {"corn": {e[0]: county_count(ec, e) for e in eras},
                        "soy": {e[0]: county_count(es, e) for e in eras}}}
    for crop in ("corn", "soy"):
        for lab in ("E", "L"):
            nm = "%s:EDD_%s" % (crop, lab)
            j = jf["names"].index(nm)
            out["coef"][nm] = {"b": float(jf["beta"][j]),
                               "se2way": math.sqrt(max(0.0, float(jf["V"][j, j])))}
        out["%s_change" % crop] = contrast_all(jf, change_weights(crop))
        out["%s_class" % crop] = rise_class(out["%s_change" % crop])
    out["did"] = contrast_all(jf, did_weights("corn", "soy"))
    out["did_class"] = S.did_class(out["did"])
    return out


def mechanism(corn, soy, warm, cool, pair=PAIR1, season=SEASON):
    """Four stacked blocks (corn/soy x warming/cooling counties).
    W4 = (L-E) corn warming - (L-E) corn cooling;
    T4 = [(L-E) corn - soy] warming - [(L-E) corn - soy] cooling."""
    eras = list(pair)
    bc, bs = B_CROP["corn"], B_CROP["soy"]
    parts = []
    for pre, rows, sel, b in (("cornW", corn, warm, bc), ("cornK", corn, cool, bc),
                              ("soyW", soy, warm, bs), ("soyK", soy, cool, bs)):
        er = R.era_filter([r for r in rows if r["fips"] in sel], eras)
        if not er:
            raise ValueError("empty block %s" % pre)
        parts.append((pre, er, eras, b, season))
    jf = S.joint_fit(parts)
    w4 = contrast_all(jf, did_weights("cornW", "cornK"))
    t4 = contrast_all(jf, sub_weights(did_weights("cornW", "soyW"), did_weights("cornK", "soyK")))
    out = {"n": jf["n"], "fallback": jf["fallback"],
           "rows": {p[0]: len(p[1]) for p in parts},
           "W4": w4, "W4_class": warm_class(w4), "T4": t4, "T4_class": warm_class(t4),
           "soy_warm_minus_cool": contrast_all(jf, did_weights("soyW", "soyK")), "coef": {}}
    for p in parts:
        for lab in ("E", "L"):
            nm = "%s:EDD_%s" % (p[0], lab)
            if nm in jf["names"]:
                j = jf["names"].index(nm)
                out["coef"][nm] = float(jf["beta"][j])
    return out


def rolling30(rows, b, season=SEASON, starts=range(1951, 1997), min_rows=1000):
    """Descriptive 30-year rolling windows (one regression per window)."""
    out = []
    for s in starts:
        win = ("W", s, s + 29)
        wr = R.era_filter(rows, [win])
        if len(wr) < min_rows:
            continue
        fw = M.fit(wr, [win], b=b, season=season)
        bb, se = M.coef(fw, "EDD_W")
        out.append({"years": [s, s + 29], "EDD": bb, "se2way": se, "n": fw["n"],
                    "counties": county_count(wr, win)})
    return out


def dt_trend_trim(corn_rows, soy_rows, trends, pool=DT.POOL, high=DT.HIGH, low=DT.LOW):
    """The 0.3.0 triple difference (eras of 0.1.0) on pool-state counties whose
    1981-2025 temperature trend lies inside the pooled interquartile range."""
    pool = set(pool)
    vals = [v for f, v in trends.items() if f[:2] in pool]
    q1, q3 = quantile(vals, 0.25), quantile(vals, 0.75)
    keepf = {f for f, v in trends.items() if f[:2] in pool and q1 <= v <= q3}
    pc = R.era_filter([r for r in corn_rows if r["fips"] in keepf], R.ERAS)
    ps = R.era_filter([r for r in soy_rows if r["fips"] in keepf], R.ERAS)
    hs, ls = set(high), set(low)
    fit = DT.ddd_fit(pc, ps, lambda r: r["state"] in hs, lambda r: r["state"] in ls)

    def mean_trend(sts):
        v = [x for f, x in trends.items() if f[:2] in sts]
        return sum(v) / len(v) if v else None

    return {"iqr_C_per_decade": [q1, q3], "counties_kept": len(keepf),
            "mean_trend_high_all": mean_trend(hs), "mean_trend_low_all": mean_trend(ls),
            "T": fit["T"], "T_year": fit["T_year"], "T_twoway": fit["T_twoway"],
            "rows": fit["rows"]}


# ------------------------------------------------------------------ grading
PRED_KEYS = ("RC1_holds_rise_direction", "RC2_holds_no_detectable_difference",
             "RC3_holds_rise_direction_to2025", "RC4_holds_warming_counties_lost_direction",
             "RC5_holds_no_detectable_difference")


def grade_rc(res):
    """Pre-registered predictions RC1-RC5 and gates RG1-RG3 (PREREG-RC.md)."""
    r1 = res["rc1_corn_mw12"]
    r2 = res["rc2_joint_mw12"]
    r3 = res["rc3_corn_mw12_to2025"]
    m = res["rc45_mechanism"]
    g = {
        "RG1_corn_L_counties_ge_500": r1["counties"]["L"] >= 500,
        "RG2_soy_L_counties_ge_400": r2["counties"]["soy"]["L"] >= 400,
        "RG3_tercile_counties_ge_100": res["terciles"]["per_tercile"] >= 100,
        "RC1_class": r1["class"],
        "RC1_holds_rise_direction": r1["change"]["diff"] < 0,
        "RC2_class": r2["did_class"],
        "RC2_holds_no_detectable_difference": r2["did_class"] == "no detectable difference",
        "RC3_class": r3["class"],
        "RC3_holds_rise_direction_to2025": r3["change"]["diff"] < 0,
        "RC4_class": m["W4_class"],
        "RC4_holds_warming_counties_lost_direction": m["W4"]["diff"] < 0,
        "RC5_class": m["T4_class"],
        "RC5_holds_no_detectable_difference": m["T4_class"] == "no detectable difference",
    }
    g["predictions_held"] = sum(1 for k in PRED_KEYS if g[k])
    return g


# ------------------------------------------------------------------ pipeline
def stage_model_rc(ddir, sdir, out, y0, y1, keep):
    rows, census = S.load_panels(ddir, sdir, keep, y0, y1)
    log("panels:", census)
    corn_mw = in_states(rows["corn"], MW12)
    soy_mw = in_states(rows["soy"], MW12)
    res = {"census": census, "states_mw12": MW12, "thresholds": B_CROP, "season": SEASON,
           "windows": {"pair1": PAIR1, "pair2": PAIR2},
           "temperature_proxy": "March-August degree days above 0 C / 184 (deg C)"}

    res["rc1_corn_mw12"] = pair_fit(corn_mw, PAIR1, B_CROP["corn"])
    log("RC1:", json.dumps({k: res["rc1_corn_mw12"][k] for k in ("EDD_E", "EDD_L", "class")}))
    res["rc2_joint_mw12"] = pair_joint(corn_mw, soy_mw, PAIR1)
    log("RC2:", res["rc2_joint_mw12"]["did_class"], res["rc2_joint_mw12"]["did"]["diff"])
    res["rc3_corn_mw12_to2025"] = pair_fit(corn_mw, PAIR2, B_CROP["corn"])
    res["rc3_joint_mw12_to2025"] = pair_joint(corn_mw, soy_mw, PAIR2)
    log("RC3:", res["rc3_corn_mw12_to2025"]["class"])

    trends = temp_trends(corn_mw, E1[1], L1[2])
    warm, cool, tinfo = trend_terciles(trends)
    res["terciles"] = tinfo
    res["terciles"]["warm_by_state"] = {s: sum(1 for f in warm if f[:2] == s) for s in MW12}
    res["terciles"]["cool_by_state"] = {s: sum(1 for f in cool if f[:2] == s) for s in MW12}
    res["rc45_mechanism"] = mechanism(corn_mw, soy_mw, warm, cool, PAIR1)
    log("RC4/5:", res["rc45_mechanism"]["W4_class"], res["rc45_mechanism"]["T4_class"])

    rob = {}
    rob["east_corn"] = pair_fit(rows["corn"], PAIR1, B_CROP["corn"])
    rob["east_joint"] = pair_joint(rows["corn"], rows["soy"], PAIR1)
    rob["mw12_corn_no2012"] = pair_fit([r for r in corn_mw if r["year"] != 2012], PAIR1, B_CROP["corn"])
    rob["mw12_corn_AprSep"] = pair_fit(corn_mw, PAIR1, B_CROP["corn"], season="AprSep")
    rob["mw12_joint_same30"] = pair_joint(corn_mw, soy_mw, PAIR1, b_corn=30, b_soy=30)
    try:
        t81 = temp_trends(rows["corn"], 1981, 2025)
        rob["dt_trend_trim"] = dt_trend_trim(rows["corn"], rows["soy"], t81)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        rob["dt_trend_trim"] = {"error": str(e)}
    res["robustness"] = rob

    res["rolling30"] = {"corn_mw12": rolling30(corn_mw, B_CROP["corn"]),
                        "soy_mw12": rolling30(soy_mw, B_CROP["soy"])}

    res["grades"] = grade_rc(res)
    with open(os.path.join(out, "rcheck_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--y0", type=int, default=1951)
    ap.add_argument("--y1", type=int, default=2025)
    ap.add_argument("--max-wait-min", type=int, default=480)
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "cornheat")
    sdir = os.path.join(ddir, "soy")
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    DT.wait_for_inputs(ddir, sdir, a.y0, a.y1, a.max_wait_min)
    keep = R.east_sample(R.load_geo(R.stage_geo(ddir)))
    log("east sample counties:", len(keep))
    if not os.path.exists(os.path.join(sdir, "nass_cornsoy_county.tsv")):
        S.stage_nass_two(sdir, a.out_dir)
    S.ensure_weather(ddir, a.y0, a.y1, keep)
    stage_model_rc(ddir, sdir, a.out_dir, a.y0, a.y1, keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
