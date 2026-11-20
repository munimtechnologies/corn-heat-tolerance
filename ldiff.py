# ldiff.py - is US corn's heat sensitivity rising or falling? A pre-registered
# reconciliation of two published answers (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-LD.md (marker corn-heat-tolerance-0.7.0-ld-prereg).
#
# Two published studies give opposite answers on overlapping US data:
#  * Yu, Miao & Khanna (Sci. Rep. 11:12351, 2021), "flexible long differences"
#    on 5-year averages: corn's yield loss per overheating degree day (> 29 C)
#    FELL by 58% from 1958-62 to 2013-17 (soybeans 55%).
#  * Raghuram & Coffel (Environ. Res. Lett. 21:124041, 2026), year-to-year
#    variation in 30-year rolling windows: Midwest corn's loss per killing degree
#    day ROSE by nearly 20% from 1960 to 2019 (tested here in 0.6.0, rcheck.py).
#
# With two periods and county fixed effects, the flexible long difference is
#     dy_c = delta + beta . dw_c + eta . w1_c + e_c
# (dy: change in mean log yield; dw: change in mean weather; w1: mean weather in
# the later period). eta, the "change in sensitivity", is identified from whether
# counties with MORE extreme heat in the later period had FASTER yield growth.
# Hypothesis H-LD: a large part of that positive eta is between-state yield
# convergence (hot, low-yield southern and western counties catching up), not
# heat adaptation. Test: the same model with state fixed effects (delta_s), which
# compares counties only with other counties of their own state.
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

WNAMES = ("GDD", "EDD", "P", "P2")
B_CROP = S.B_CROP                      # corn 29 C, soybeans 30 C
SEASON = "MarAug"
MIN_YEARS = 3                          # of the 5 years in each period
PRIMARY = ((1958, 1962), (2013, 2017))           # Yu et al.'s 55-year model
EXTENDED = ((1958, 1962), (2021, 2025))
PAIRS20 = (((1958, 1962), (1978, 1982)), ((1968, 1972), (1988, 1992)),
           ((1978, 1982), (1998, 2002)), ((1988, 1992), (2008, 2012)))
MW12 = ("17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55")
Y0, Y1 = 1958, 2025
log = R.log


# ------------------------------------------------------------------ data
def weather_vec(r, b, season=SEASON):
    """[GDD 10..b, EDD > b, P (dm), P^2] of one county-year row (cornheat_model units)."""
    dd = r["dd"][season]
    p = float(r["P"][season]) / 100.0
    return [float(dd[10]) - float(dd[b]), float(dd[b]), p, p * p]


def period_means(rows, period, b, season=SEASON, min_years=MIN_YEARS):
    """Per county: mean log yield and mean weather over the years of `period`
    that have a yield. Counties with fewer than min_years such years are dropped."""
    y0, y1 = period
    acc = {}
    for r in rows:
        if not y0 <= r["year"] <= y1:
            continue
        a = acc.setdefault(r["fips"], {"state": r["state"], "years": set(), "y": 0.0,
                                       "w": [0.0] * len(WNAMES)})
        if r["year"] in a["years"]:
            continue
        a["years"].add(r["year"])
        a["y"] += float(r["logy"])
        for k, v in enumerate(weather_vec(r, b, season)):
            a["w"][k] += v
    out = {}
    for f, a in acc.items():
        n = len(a["years"])
        if n >= min_years:
            out[f] = {"state": a["state"], "n": n, "y": a["y"] / n, "w": [x / n for x in a["w"]]}
    return out


def ld_records(rows, pair, b, season=SEASON, min_years=MIN_YEARS):
    """One record per county present in both periods."""
    m0 = period_means(rows, pair[0], b, season, min_years)
    m1 = period_means(rows, pair[1], b, season, min_years)
    recs = []
    for f in sorted(set(m0) & set(m1)):
        a, c = m0[f], m1[f]
        recs.append({"fips": f, "state": a["state"], "dy": c["y"] - a["y"], "y0": a["y"],
                     "dw": [x1 - x0 for x0, x1 in zip(a["w"], c["w"])],
                     "w0": list(a["w"]), "w1": list(c["w"])})
    return recs


# ------------------------------------------------------------------ model
def fit_ld(recs, fe="none", flexible=True, add_y0=False):
    """OLS of dy on dw (and w1 if flexible; and initial log yield if add_y0) with a
    common intercept (fe='none', model A) or state fixed effects (fe='state',
    model B). Variance clustered by state. eta_over_beta_EDD = eta/beta, the
    proportional change in the EDD response (negative = loss per EDD fell)."""
    import numpy as np
    names = ["d" + w for w in WNAMES]
    if flexible:
        names += [w + "_1" for w in WNAMES]
    if add_y0:
        names.append("y0")
    n = len(recs)
    if n <= len(names) + 1:
        raise ValueError("too few counties (%d) for %d regressors" % (n, len(names)))
    X = np.zeros((n, len(names)))
    y = np.zeros(n)
    st = []
    for i, r in enumerate(recs):
        row = list(r["dw"])
        if flexible:
            row += list(r["w1"])
        if add_y0:
            row.append(r["y0"])
        X[i, :] = row
        y[i] = r["dy"]
        st.append(r["state"])
    groups = st if fe == "state" else ["all"] * n
    g, ng = M.group_index(groups)
    M.demean(X, g, ng)
    y = y - (np.bincount(g, weights=y, minlength=ng) / np.bincount(g, minlength=ng))[g]
    bread = np.linalg.pinv(X.T @ X)
    beta = bread @ (X.T @ y)
    e = y - X @ beta
    meat, nst = M.cluster_meat(X * e[:, None], st)
    V = bread @ meat @ bread
    tss = float(y @ y)
    out = {"n": n, "states": nst, "fe": fe, "flexible": flexible, "add_y0": add_y0,
           "names": names, "coef": {}, "r2_within": (1.0 - float(e @ e) / tss) if tss > 0 else None}
    for j, nm in enumerate(names):
        bj = float(beta[j])
        se = math.sqrt(max(0.0, float(V[j, j])))
        z = bj / se if se > 0 else float("nan")
        out["coef"][nm] = {"b": bj, "se": se, "p": M.p_two_sided(z) if z == z else float("nan")}
    if flexible:
        bE = out["coef"]["dEDD"]["b"]
        out["eta_over_beta_EDD"] = out["coef"]["EDD_1"]["b"] / bE if bE != 0 else None
    return out


def ab(recs):
    """Model A (common intercept) and model B (state fixed effects)."""
    return {"A": fit_ld(recs, "none"), "B": fit_ld(recs, "state")}


def pair_summary(rows, pair, b, season=SEASON):
    recs = ld_records(rows, pair, b, season)
    out = ab(recs)
    out["periods"] = [list(pair[0]), list(pair[1])]
    out["counties"] = len(recs)
    out["by_state"] = {}
    for r in recs:
        out["by_state"][r["state"]] = out["by_state"].get(r["state"], 0) + 1
    out["mean_dEDD"] = sum(r["dw"][1] for r in recs) / len(recs)
    return out


# ------------------------------------------------------------------ grading
def sensitivity_fell(f):
    """beta_EDD < 0 (heat hurts) and eta_EDD > 0 (the later loss per EDD is smaller)."""
    return f["coef"]["dEDD"]["b"] < 0 and f["coef"]["EDD_1"]["b"] > 0


def shrank(fa, fb, share=0.5):
    """eta_EDD of model A is positive and model B's is below share * model A's."""
    ha, hb = fa["coef"]["EDD_1"]["b"], fb["coef"]["EDD_1"]["b"]
    return ha > 0 and hb < share * ha


def fall_detectable(f):
    c = f["coef"]["EDD_1"]
    return c["b"] > 0 and c["p"] == c["p"] and c["p"] < 0.05


PRED_KEYS = ("LD1_holds_corn_fell_A", "LD2_holds_soy_fell_A", "LD3_holds_corn_shrinks_within_state",
             "LD4_holds_soy_shrinks_within_state", "LD5_holds_corn_no_detectable_fall_B")


def grade_ld(res):
    """Pre-registered predictions LD1-LD5 and gates LG1-LG3 (PREREG-LD.md)."""
    c, s = res["corn"], res["soy"]
    g = {
        "LG1_corn_counties_ge_800": c["counties"] >= 800,
        "LG2_soy_counties_ge_400": s["counties"] >= 400,
        "LG3_corn_states_ge_15": c["B"]["states"] >= 15,
        "LD1_holds_corn_fell_A": sensitivity_fell(c["A"]),
        "LD2_holds_soy_fell_A": sensitivity_fell(s["A"]),
        "LD3_holds_corn_shrinks_within_state": shrank(c["A"], c["B"]),
        "LD4_holds_soy_shrinks_within_state": shrank(s["A"], s["B"]),
        "LD5_holds_corn_no_detectable_fall_B": not fall_detectable(c["B"]),
        "corn_eta_over_beta_A": c["A"]["eta_over_beta_EDD"],
        "corn_eta_over_beta_B": c["B"]["eta_over_beta_EDD"],
        "soy_eta_over_beta_A": s["A"]["eta_over_beta_EDD"],
        "soy_eta_over_beta_B": s["B"]["eta_over_beta_EDD"],
    }
    g["predictions_held"] = sum(1 for k in PRED_KEYS if g[k])
    return g


def reconcile(rc_grades, ld_grades):
    """Joint verdict with 0.6.0 (rcheck_results.json grades), fixed in PREREG-LD.md."""
    rise = bool(rc_grades.get("RC1_holds_rise_direction"))
    fell = bool(ld_grades.get("LD1_holds_corn_fell_A"))
    shr = bool(ld_grades.get("LD3_holds_corn_shrinks_within_state"))
    if rise and fell:
        return "reconciled: the long-difference fall is between-state" if shr else "conflict persists within states"
    if rise:
        return "no conflict on this data: long differences show no fall"
    if fell:
        return "no conflict on this data: year-to-year sensitivity did not rise"
    return "neither published direction on this data"


# ------------------------------------------------------------------ pipeline
def stage_model_ld(ddir, sdir, out, y0, y1, keep):
    rows, census = S.load_panels(ddir, sdir, keep, y0, y1)
    log("panels:", census)
    res = {"census": census, "thresholds": B_CROP, "season": SEASON, "min_years": MIN_YEARS,
           "primary": PRIMARY, "units": "log yield per degree day; P in decimetres"}
    for crop in ("corn", "soy"):
        res[crop] = pair_summary(rows[crop], PRIMARY, B_CROP[crop])
        log(crop, "A eta/beta:", res[crop]["A"]["eta_over_beta_EDD"],
            "B eta/beta:", res[crop]["B"]["eta_over_beta_EDD"], "n", res[crop]["counties"])

    rob = {}
    for crop in ("corn", "soy"):
        b = B_CROP[crop]
        recs = ld_records(rows[crop], PRIMARY, b)
        rob[crop + "_extended_2021_25"] = pair_summary(rows[crop], EXTENDED, b)
        rob[crop + "_yu_match_AprSep_29"] = pair_summary(rows[crop], PRIMARY, 29, season="AprSep")
        rob[crop + "_standard_ld"] = {"A": fit_ld(recs, "none", flexible=False),
                                      "B": fit_ld(recs, "state", flexible=False)}
        rob[crop + "_A_plus_initial_yield"] = fit_ld(recs, "none", add_y0=True)
        mw = [r for r in recs if r["state"] in MW12]
        rob[crop + "_mw12"] = ab(mw) if len(mw) > 30 else {"error": "too few counties"}
        p20 = []
        for pair in PAIRS20:
            try:
                ps = pair_summary(rows[crop], pair, b)
                p20.append({"periods": ps["periods"], "counties": ps["counties"],
                            "A": ps["A"]["eta_over_beta_EDD"], "B": ps["B"]["eta_over_beta_EDD"],
                            "eta_A": ps["A"]["coef"]["EDD_1"], "eta_B": ps["B"]["coef"]["EDD_1"]})
            except (ValueError, ZeroDivisionError) as e:
                p20.append({"periods": [list(pair[0]), list(pair[1])], "error": str(e)})
        ok = [x for x in p20 if "error" not in x and x["A"] is not None and x["B"] is not None]
        rob[crop + "_pairs20"] = {"pairs": p20,
                                  "mean_A": sum(x["A"] for x in ok) / len(ok) if ok else None,
                                  "mean_B": sum(x["B"] for x in ok) / len(ok) if ok else None}
    cs = set(r["fips"] for r in ld_records(rows["corn"], PRIMARY, B_CROP["corn"]))
    ss = set(r["fips"] for r in ld_records(rows["soy"], PRIMARY, B_CROP["soy"]))
    both = cs & ss
    rob["common_counties"] = {
        "counties": len(both),
        "corn": ab([r for r in ld_records(rows["corn"], PRIMARY, B_CROP["corn"]) if r["fips"] in both]),
        "soy": ab([r for r in ld_records(rows["soy"], PRIMARY, B_CROP["soy"]) if r["fips"] in both])}
    res["robustness"] = rob
    res["grades"] = grade_ld(res)
    with open(os.path.join(out, "ldiff_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1, default=float))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-wait-min", type=int, default=480)
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "cornheat")
    sdir = os.path.join(ddir, "soy")
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    DT.wait_for_inputs(ddir, sdir, 1951, 2025, a.max_wait_min)
    keep = R.east_sample(R.load_geo(R.stage_geo(ddir)))
    log("east sample counties:", len(keep))
    if not os.path.exists(os.path.join(sdir, "nass_cornsoy_county.tsv")):
        S.stage_nass_two(sdir, a.out_dir)
    S.ensure_weather(ddir, Y0, Y1, keep)
    stage_model_ld(ddir, sdir, a.out_dir, Y0, Y1, keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
